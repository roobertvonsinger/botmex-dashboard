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
        balance_real REAL,
        withdrawal_ready INTEGER DEFAULT 0,
        dead_reason TEXT,
        dead_at TEXT,
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


def test_accounts_withdrawal_ready_with_balance_excluded_grade_d_is_not(tmp_path):
    """withdrawal_ready=1 con saldo activo (>= $100) queda EXCLUIDA. Grade D por sí
    solo ya NO excluye (Robert 2026-09-10: el grading está deficiente)."""
    rows = [
        {"id": 1, "email": "with_acc@test.com", "status": "LIVE", "published_to_pool": 1, "withdrawal_ready": 1, "balance_real": 250.0, "grade": "A", "kyc_verified": 1},
        {"id": 2, "email": "grade_d@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "D", "kyc_verified": 1},
        {"id": 3, "email": "ok_acc@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "A", "kyc_verified": 1},
    ]
    win = {r["email"]: {"available": 2000.0} for r in rows}
    sel = ad.select_accounts_for_auto(rows, 150, 5, win)
    sel_emails = [r["email"] for r in sel]
    assert "with_acc@test.com" not in sel_emails
    assert "grade_d@test.com" in sel_emails
    assert "ok_acc@test.com" in sel_emails


def test_accounts_withdrawal_ready_zero_balance_is_eligible(tmp_path):
    """Cuentas con withdrawal_ready=1 pero saldo $0.0 son elegibles para depósito (canal de retiro ya listo)."""
    rows = [
        {"id": 1, "email": "clabe_ready@test.com", "status": "LIVE", "published_to_pool": 1, "withdrawal_ready": 1, "balance_real": 0.0, "grade": "A", "kyc_verified": 1},
    ]
    win = {r["email"]: {"available": 2000.0} for r in rows}
    sel = ad.select_accounts_for_auto(rows, 150, 1, win)
    sel_emails = [r["email"] for r in sel]
    assert "clabe_ready@test.com" in sel_emails


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
    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123", "4222222222222222|12|28|123"], amount=150, target_count=2)
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
    res = ad.plan_auto_mission(db, card_pipes=["4111111111111111|12|28|123", "4222222222222222|12|28|123"], amount=150, target_count=2)
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
    pipes = [f"411111111111111{i}|12|28|123" for i in range(5)]
    res = ad.plan_auto_mission(db, card_pipes=pipes, amount=150, target_count=5, max_accounts=5)
    emails = [a["email"] for a in res["accounts"]]
    assert sum(1 for e in emails if e.startswith("top")) == 2
    assert sum(1 for e in emails if e.startswith("mid")) == 2
    assert sum(1 for e in emails if e == "low@test.com") == 1


# ── Recalibración D (Robert 2026-09-10): sort_key graduado + orden B `5 3 1 2 4` ──
#   Prioridad dentro de tier: 3DS <24h → JWT vivo → fails ASC (graduado) →
#   cards ASC (graduado, 0<1<2) → grade (peso real) → actividad más antigua primero.
def _dk(email, **over):
    base = {
        "id": None, "email": email, "status": "LIVE", "grade": "B",
        "grade_score": 70, "balance_real": 0.0, "published_to_pool": 1,
        "kyc_verified": 1, "locked_by": None, "cooldown_until": None,
        "jwt_expires_at": 0,  # sin JWT vivo -> todas caen a tier_low (grade B)
    }
    base.update(over)
    return base


def _dwin(*emails):
    return {e: {"available": 5000.0} for e in emails}


def test_fails_graduated_not_binary():
    """Criterio 3: menos fallas primero, GRADUADO (1 fail < 5 fails), no binario."""
    rows = [_dk("f5@t.com"), _dk("f1@t.com")]  # f5 primero en el input
    meta = {"f5@t.com": {"total_fails": 5}, "f1@t.com": {"total_fails": 1}}
    sel = ad.select_accounts_for_auto(rows, 150, 2, _dwin("f5@t.com", "f1@t.com"), meta_map=meta)
    order = [r["email"] for r in sel]
    assert order.index("f1@t.com") < order.index("f5@t.com")


def test_cards_graduated_zero_beats_one():
    """Criterio 1: 0 tarjetas guardadas antes que 1 (graduado, no binario a >=2)."""
    rows = [_dk("c1@t.com"), _dk("c0@t.com")]  # c1 primero en el input
    meta = {"c1@t.com": {"cards_count": 1}, "c0@t.com": {"cards_count": 0}}
    sel = ad.select_accounts_for_auto(rows, 150, 2, _dwin("c1@t.com", "c0@t.com"), meta_map=meta)
    order = [r["email"] for r in sel]
    assert order.index("c0@t.com") < order.index("c1@t.com")


def test_oldest_activity_ranked_first():
    """Criterio 5b: la cuenta cuya actividad más reciente es la más ANTIGUA va primero."""
    import time as _t
    now = int(_t.time())
    rows = [_dk("recent@t.com"), _dk("rested@t.com")]  # recent primero en el input
    meta = {
        "recent@t.com": {"last_activity_epoch": now - 2 * 86400},
        "rested@t.com": {"last_activity_epoch": now - 40 * 86400},
    }
    sel = ad.select_accounts_for_auto(rows, 150, 2, _dwin("recent@t.com", "rested@t.com"), meta_map=meta)
    order = [r["email"] for r in sel]
    assert order.index("rested@t.com") < order.index("recent@t.com")


def test_grade_beats_bin_affinity():
    """Criterio 2: grade es peso real — B sin afinidad BIN gana a C con afinidad BIN."""
    rows = [_dk("c_bin@t.com", grade="C"), _dk("b_nobin@t.com", grade="B")]
    meta = {
        "c_bin@t.com": {"approved_bin_pipes": {"411111": {"411111xxxxxx1111|12|30|123"}}},
        "b_nobin@t.com": {},
    }
    sel = ad.select_accounts_for_auto(rows, 150, 2, _dwin("c_bin@t.com", "b_nobin@t.com"), meta_map=meta)
    order = [r["email"] for r in sel]
    assert order.index("b_nobin@t.com") < order.index("c_bin@t.com")


def test_threeds_beats_grade_within_selection():
    """E-q1: el 3DS <24h gana a grade — ya comprobó lo que el grading intenta predecir."""
    rows = [_dk("aplus_no3ds@t.com", grade="A+"), _dk("c_3ds@t.com", grade="C")]
    meta = {"aplus_no3ds@t.com": {}, "c_3ds@t.com": {"has_3ds_24h": True}}
    sel = ad.select_accounts_for_auto(rows, 150, 2, _dwin("aplus_no3ds@t.com", "c_3ds@t.com"), meta_map=meta)
    order = [r["email"] for r in sel]
    assert order[0] == "c_3ds@t.com"


# ── Fase 3: advisor_boost — puro desempate dentro del tier ───────────────────
def _adv_rows(*emails):
    import time as _t
    return [
        {
            "id": None, "email": e, "status": "LIVE", "grade": "A",
            "grade_score": 50, "balance_real": 0.0, "published_to_pool": 1,
            "kyc_verified": 1, "locked_by": None, "cooldown_until": None,
            "jwt_expires_at": int(_t.time()) + 3600,
        }
        for e in emails
    ]


def _adv_win(*emails):
    return {e: {"available": 5000.0} for e in emails}


def test_advisor_boost_none_is_identity():
    rows = _adv_rows("a@t.com", "b@t.com", "c@t.com")
    base = ad.select_accounts_for_auto(rows, 150, 3, _adv_win("a@t.com", "b@t.com", "c@t.com"))
    with_none = ad.select_accounts_for_auto(
        rows, 150, 3, _adv_win("a@t.com", "b@t.com", "c@t.com"), advisor_boost=None
    )
    assert [r["email"] for r in base] == [r["email"] for r in with_none]


def test_advisor_boost_reorders_within_tier():
    emails = ["a@t.com", "b@t.com", "c@t.com"]
    rows = _adv_rows(*emails)
    base = [r["email"] for r in ad.select_accounts_for_auto(rows, 150, 3, _adv_win(*emails))]
    # empujar la última de `base` al frente con un boost fuerte
    boosted = ad.select_accounts_for_auto(
        rows, 150, 3, _adv_win(*emails), advisor_boost={base[-1]: 3}
    )
    assert [r["email"] for r in boosted][0] == base[-1]


def test_advisor_boost_cannot_pull_excluded_account():
    rows = _adv_rows("live@t.com") + [
        {"id": None, "email": "dead@t.com", "status": "DEAD", "grade": "A",
         "published_to_pool": 1, "kyc_verified": 1, "jwt_expires_at": 9999999999}
    ]
    sel = ad.select_accounts_for_auto(
        rows, 150, 9, _adv_win("live@t.com", "dead@t.com"),
        advisor_boost={"dead@t.com": 3},
    )
    assert [r["email"] for r in sel] == ["live@t.com"]


# ── Recalibración grade-D (Robert 2026-09-10) ────────────────────────────────
# "El grading está deficiente; las D no son realmente D. TODAS las cuentas LIVE
#  entran al /bet. Solo quedan fuera las sacadas del pool (published_to_pool=0
#  por depósito o manual), las de saldo >= $100, o las con dead_reason. Si sale
#  un A+/A solito se prioriza, pero grade D NO es un descarte."

def test_grade_d_live_pooled_account_is_selected(tmp_path):
    rows = [
        {"id": 1, "email": "d_ok@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "D", "kyc_verified": 1},
        {"id": 2, "email": "aplus@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "A+", "kyc_verified": 1},
    ]
    win = {r["email"]: {"available": 5000.0} for r in rows}
    sel_emails = [r["email"] for r in ad.select_accounts_for_auto(rows, 150, 5, win)]
    assert "d_ok@test.com" in sel_emails
    # prioridad preservada: A+ va antes que D dentro del mismo tier
    assert sel_emails.index("aplus@test.com") < sel_emails.index("d_ok@test.com")


def test_grade_d_excluded_only_by_pool_or_funds(tmp_path):
    rows = [
        {"id": 1, "email": "d_nopool@test.com", "status": "LIVE", "published_to_pool": 0, "grade": "D", "kyc_verified": 1},
        {"id": 2, "email": "d_funded@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "D", "kyc_verified": 1, "balance_real": 250.0},
        {"id": 3, "email": "d_ok@test.com", "status": "LIVE", "published_to_pool": 1, "grade": "D", "kyc_verified": 1, "balance_real": 0.0},
    ]
    win = {r["email"]: {"available": 5000.0} for r in rows}
    sel_emails = [r["email"] for r in ad.select_accounts_for_auto(rows, 150, 5, win)]
    assert sel_emails == ["d_ok@test.com"]


def test_plan_auto_mission_includes_grade_d(tmp_path):
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified) VALUES ('d1@t.com','LIVE','D',1,1)")
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified) VALUES ('a1@t.com','LIVE','A',1,1)")
    con.commit(); con.close()
    res = ad.plan_auto_mission(
        db, card_pipes=["4111111111111111|12|28|123", "4222222222222222|12|28|123"],
        amount=150, target_count=9,
    )
    emails = [a["email"] for a in res["accounts"]]
    assert "d1@t.com" in emails


def test_pull_fresh_live_account_allows_grade_d(tmp_path):
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified, jwt_expires_at) "
        "VALUES ('donly@t.com','LIVE','D',1,1,9999999999)"
    )
    con.commit(); con.close()
    got = ad._pull_fresh_live_account(db, already_checked=set(), married_owners={})
    assert got is not None and got["email"] == "donly@t.com"


def test_married_grade_d_owner_live_is_fast_tracked(tmp_path):
    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified) VALUES ('mard@t.com','LIVE','D',1,1)")
    con.commit(); con.close()
    pipe = "4111111111111111|12|28|123"
    res = ad.plan_auto_mission(
        db, card_pipes=[pipe], amount=150, target_count=9,
        married_pairs=[{"email": "mard@t.com", "card_pipe": pipe}],
    )
    emails = [a["email"] for a in res["accounts"]]
    assert "mard@t.com" in emails

