"""Tests para la lógica multivariable de selección de cuentas y asignación de tarjetas en auto_deposit.py.
Verifica:
1. Gate duro: published_to_pool == 1 (o RESERVADA_SA).
2. Enfriamiento 48h para cuentas con depósito APROBADO en dashboard.
3. Degradación a Tier LOW para cuentas con depósitos por SPEI / externos recientes (<24h).
4. Boost a Tier TOP para cuentas con evento 3DS_REQUIRED reciente (<24h).
5. Estratificación intercalada interna (1 TOP, 2 MID, resto LOW) sin etiquetas visuales de Grade.
6. Cooldown de BIN de 30 días únicamente tras aprobación exitosa (misma tarjeta permitida, otro pipe del mismo BIN bloqueado 30d).
7. Vinculación estricta 1:1 de tarjetas casadas a su cuenta.
"""
import pytest
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

import auto_deposit as ad


def _make_db(tmp_path):
    db_file = tmp_path / "test_betmexico.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        fullname TEXT,
        status TEXT DEFAULT 'LIVE',
        grade TEXT DEFAULT 'B',
        grade_score INTEGER DEFAULT 70,
        kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 0,
        locked_by INTEGER,
        cooldown_until INTEGER,
        jwt_expires_at INTEGER DEFAULT 2147483647
    );

    CREATE TABLE deposit_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_email TEXT,
        amount REAL,
        status TEXT,
        rejection_reason TEXT,
        card_pipe TEXT,
        created_at TEXT
    );

    CREATE TABLE account_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_email TEXT,
        txn_date TEXT,
        amount REAL,
        status INTEGER,
        txn_type INTEGER,
        gateway INTEGER
    );

    CREATE TABLE account_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_email TEXT,
        number TEXT,
        exp_month TEXT,
        exp_year TEXT,
        cvv TEXT,
        status TEXT DEFAULT 'ACTIVE'
    );

    CREATE TABLE bin_stats (
        bin TEXT PRIMARY KEY,
        total_attempts INTEGER,
        approved_count INTEGER,
        approval_rate REAL
    );
    """)
    con.close()
    return db_file


def test_gate_duro_published_to_pool(tmp_path):
    """Solo cuentas con published_to_pool == 1 o RESERVADA_SA entran a la selección."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    # 2 cuentas LIVE: email1 con pool=0, email2 con pool=1
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('off@test.com', 'LIVE', 0)")
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('on@test.com', 'LIVE', 1)")
    con.commit()
    con.close()

    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=5)
    emails = [a["email"] for a in res["accounts"]]
    assert "off@test.com" not in emails
    assert "on@test.com" in emails


test_gate_duro_published_to_pool.__doc__ = "Verifica gate duro de pool"


def test_cooldown_48h_dashboard_approved(tmp_path):
    """Una cuenta con depósito aprobado en el dashboard en las últimas 48h queda excluida del automatch."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('recent_dep@test.com', 'LIVE', 1)")
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('old_dep@test.com', 'LIVE', 1)")

    now_iso = datetime.now(timezone.utc).isoformat()
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()

    # recent_dep tuvo approved hace 10h
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, created_at) VALUES ('recent_dep@test.com', 150, 'approved', ?)", (now_iso,))
    # old_dep tuvo approved hace 50h
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, created_at) VALUES ('old_dep@test.com', 150, 'approved', ?)", (old_iso,))
    con.commit()
    con.close()

    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=5)
    emails = [a["email"] for a in res["accounts"]]
    assert "recent_dep@test.com" not in emails
    assert "old_dep@test.com" in emails


def test_spei_or_funds_excluded_from_auto_mission(tmp_path):
    """Cuentas con depósitos por SPEI recientes (<48h) o retiros quedan TOTALMENTE EXCLUIDAS del auto-match."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('spei_acc@test.com', 'LIVE', 1)")
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('clean_acc@test.com', 'LIVE', 1)")

    now_iso = datetime.now(timezone.utc).isoformat()
    # spei_acc tuvo depósito SPEI (gateway=2, status=6) hace 2h
    con.execute("INSERT INTO account_transactions (account_email, txn_date, amount, status, txn_type, gateway) VALUES ('spei_acc@test.com', ?, 200, 6, 1, 2)", (now_iso,))
    con.commit()
    con.close()

    # Al pedir hasta 5 cuentas, spei_acc no debe entrar NUNCA
    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=5)
    emails = [a["email"] for a in res["accounts"]]
    assert "spei_acc@test.com" not in emails
    assert "clean_acc@test.com" in emails


def test_gate_duro_kyc_verified(tmp_path):
    """Cuentas con kyc_verified != 1 quedan totalmente excluidas."""
    rows = [
        {"id": 1, "email": "nokyc@test.com", "status": "LIVE", "published_to_pool": 1, "kyc_verified": 0, "grade": "A"},
        {"id": 2, "email": "unverified@test.com", "status": "LIVE", "published_to_pool": 1, "kyc_verified": None, "grade": "A"},
        {"id": 3, "email": "okkyc@test.com", "status": "LIVE", "published_to_pool": 1, "kyc_verified": 1, "grade": "A"},
    ]
    win = {r["email"]: {"available": 2000.0} for r in rows}
    sel = ad.select_accounts_for_auto(rows, 150, 5, win)
    sel_emails = [r["email"] for r in sel]
    assert "nokyc@test.com" not in sel_emails
    assert "unverified@test.com" not in sel_emails
    assert "okkyc@test.com" in sel_emails


def test_gate_duro_dead_reason(tmp_path):
    """Cuentas con dead_reason o dead_at quedan totalmente excluidas."""
    rows = [
        {"id": 1, "email": "dead_reason@test.com", "status": "LIVE", "published_to_pool": 1, "kyc_verified": 1, "dead_reason": "IsUserInValidationProcess", "grade": "A"},
        {"id": 2, "email": "dead_at@test.com", "status": "LIVE", "published_to_pool": 1, "kyc_verified": 1, "dead_at": "2026-08-18 01:00:00", "grade": "A"},
        {"id": 3, "email": "alive@test.com", "status": "LIVE", "published_to_pool": 1, "kyc_verified": 1, "grade": "A"},
    ]
    win = {r["email"]: {"available": 2000.0} for r in rows}
    sel = ad.select_accounts_for_auto(rows, 150, 5, win)
    sel_emails = [r["email"] for r in sel]
    assert "dead_reason@test.com" not in sel_emails
    assert "dead_at@test.com" not in sel_emails
    assert "alive@test.com" in sel_emails


def test_accounts_with_real_funds_excluded(tmp_path):
    """Cuentas con saldo real o total >= $10.0 quedan TOTALMENTE EXCLUIDAS del auto-match."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    # Cuenta con $598.49 de saldo real (caso de Linda Carolina)
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('rich_acc@test.com', 'LIVE', 1)")
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('empty_acc@test.com', 'LIVE', 1)")
    con.commit()
    con.close()

    # Simulamos rows con balance_real
    rows = [
        {"id": 1, "email": "rich_acc@test.com", "status": "LIVE", "published_to_pool": 1, "balance_real": 598.49, "grade": "A", "kyc_verified": 1},
        {"id": 2, "email": "empty_acc@test.com", "status": "LIVE", "published_to_pool": 1, "balance_real": 0.0, "grade": "A", "kyc_verified": 1},
    ]
    win = {"rich_acc@test.com": {"available": 2000.0}, "empty_acc@test.com": {"available": 2000.0}}
    sel = ad.select_accounts_for_auto(rows, 150, 5, win)
    sel_emails = [r["email"] for r in sel]
    assert "rich_acc@test.com" not in sel_emails
    assert "empty_acc@test.com" in sel_emails


def test_accounts_withdrawal_ready_or_grade_d_excluded(tmp_path):
    """Cuentas con withdrawal_ready=1 o grado D quedan TOTALMENTE EXCLUIDAS."""
    rows = [
        {"id": 1, "email": "with_acc@test.com", "status": "LIVE", "published_to_pool": 1, "withdrawal_ready": 1, "grade": "A", "kyc_verified": 1},
        {"id": 2, "email": "grade_d@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "D", "kyc_verified": 1},
        {"id": 3, "email": "ok_acc@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "A", "kyc_verified": 1},
    ]
    win = {r["email"]: {"available": 2000.0} for r in rows}
    sel = ad.select_accounts_for_auto(rows, 150, 5, win)
    sel_emails = [r["email"] for r in sel]
    assert "with_acc@test.com" not in sel_emails
    assert "grade_d@test.com" not in sel_emails
    assert "ok_acc@test.com" in sel_emails


def test_boost_3ds_recent_to_top(tmp_path):
    """Evento 3DS_REQUIRED en las últimas 24h eleva la cuenta a Tier TOP."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('threeds_acc@test.com', 'LIVE', 1)")
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('normal_acc@test.com', 'LIVE', 1)")

    now_iso = datetime.now(timezone.utc).isoformat()
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, created_at) VALUES ('threeds_acc@test.com', 150, '3DS_REQUIRED', ?)", (now_iso,))
    con.commit()
    con.close()

    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=1)
    emails = [a["email"] for a in res["accounts"]]
    assert emails[0] == "threeds_acc@test.com"


def test_bin_cooldown_30d_on_approval(tmp_path):
    """Si un pipe del BIN X aprobó en Cuenta A hace <30 días, se prohíbe OTRA tarjeta del mismo BIN X en Cuenta A.
    La MISMA tarjeta previa SÍ está permitida. Si solo hubo rechazos, NO aplica el cooldown.
    """
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('acc_bin@test.com', 'LIVE', 1)")

    pipe_viego = "4915661111111111|12|30|123"
    pipe_nuevo_mismo_bin = "4915669999999999|12|30|999"
    pipe_distinto_bin = "5264241111111111|12|30|456"

    pipe_viego_norm = ad._normalize_pipe_to_3part(pipe_viego)
    pipe_distinto_norm = ad._normalize_pipe_to_3part(pipe_distinto_bin)

    recent_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    # Registramos aprobación previa con pipe_viego (BIN 491566)
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, card_pipe, created_at) VALUES ('acc_bin@test.com', 150, 'approved', ?, ?)", (pipe_viego_norm, recent_iso))
    con.commit()
    con.close()

    # 1. Probar asignación enviando solo pipe_nuevo_mismo_bin (debe fallar la asignación porque el BIN está enfriando para tarjetas nuevas)
    res1 = ad.plan_auto_mission(db, card_pipes=[pipe_nuevo_mismo_bin], amount=150, target_count=1)
    assert not res1["accounts"] or res1["feasible"] is False

    # 2. Probar asignación enviando pipe_distinto_bin (debe pasar)
    res2 = ad.plan_auto_mission(db, card_pipes=[pipe_distinto_bin], amount=150, target_count=1)
    assert res2["accounts"][0]["card_pipe"] == pipe_distinto_norm

    # 3. Probar asignación enviando pipe_viego (misma tarjeta exacta aprobada -> debe pasar)
    res3 = ad.plan_auto_mission(db, card_pipes=[pipe_viego], amount=150, target_count=1)
    assert res3["accounts"][0]["card_pipe"] == pipe_viego_norm


def test_tol_pipe_only_one_account(tmp_path):
    """RF4: un pipe tolerado solo se asigna a 1 cuenta, aunque haya 3 cuentas."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    for i in range(3):
        con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES (?, 'LIVE', 1)",
                    (f"acc{i}@test.com",))
    con.commit()
    con.close()
    pipe = "4169160000000000|12|28|123"
    res = ad.plan_auto_mission(db, card_pipes=[pipe], amount=150, target_count=3, tol_pipes={pipe})
    with_pipe = [a for a in res["accounts"] if a["card_pipe"] == ad._normalize_pipe_to_3part(pipe)]
    assert len(with_pipe) <= 1


def test_dynamic_order_recently_tried_last(tmp_path):
    """RF5: una cuenta intentada <60min queda al final de su tier (mismo grade)."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool) VALUES ('fresh@test.com', 'LIVE', 'A', 1)")
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool) VALUES ('tried@test.com', 'LIVE', 'A', 1)")
    now_iso = datetime.now(timezone.utc).isoformat()
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, created_at) VALUES ('tried@test.com', 150, 'rejected', ?)", (now_iso,))
    con.commit()
    con.close()
    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=2)
    order = [a["email"] for a in res["accounts"]]
    assert order.index("tried@test.com") > order.index("fresh@test.com")


def test_cards_heavy_deprioritized(tmp_path):
    """RF5: cuenta con 2+ tarjetas asociadas se deprioriza sobre una con 0."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool) VALUES ('light@test.com', 'LIVE', 'A', 1)")
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool) VALUES ('heavy@test.com', 'LIVE', 'A', 1)")
    for i in range(2):
        con.execute("INSERT INTO account_cards (number, account_email) VALUES (?, 'heavy@test.com')", (f"4{i}999999999999",))
    con.commit()
    con.close()
    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=2)
    order = [a["email"] for a in res["accounts"]]
    assert order.index("heavy@test.com") > order.index("light@test.com")


def test_tier_proportion_2_2_1(tmp_path):
    """RF5: con 5 cuentas (2 top/2 mid/1 low disponibles) la cuota es 2-2-1."""
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    for i in range(2):
        con.execute("INSERT INTO accounts (email, status, grade, published_to_pool) VALUES (?, 'LIVE', 'A+', 1)", (f"top{i}@test.com",))
    for i in range(3):
        con.execute("INSERT INTO accounts (email, status, grade, published_to_pool) VALUES (?, 'LIVE', 'A', 1)", (f"mid{i}@test.com",))
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool, jwt_expires_at) VALUES ('low@test.com', 'LIVE', 'C', 1, 0)")
    con.commit()
    con.close()
    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123"], amount=150, target_count=5, max_accounts=5)
    emails = [a["email"] for a in res["accounts"]]
    assert sum(1 for e in emails if e.startswith("top")) == 2
    assert sum(1 for e in emails if e.startswith("mid")) == 2
    assert sum(1 for e in emails if e == "low@test.com") == 1
