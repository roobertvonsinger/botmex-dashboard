# tests/test_bet_anti_hammer_and_resting.py
"""Pruebas para las 4 protecciones anti-taladro y rotación /bet:
1. Persistencia de mission_id en deposit_attempts vía _record_attempt.
2. Regla de Reposo 2x2 en _get_resting_accounts con ventana de 4 misiones.
3. Priorización de cuentas sin intentos (attempts ASC) sobre jwt_order.
4. Blindaje del relevo dinámico: no reusar cuentas con declines en la misma corrida.
5. probe_amount temporal a 100.0 MXN.
"""
import json
import sqlite3
import pytest

import auto_deposit as ad
import deposits as dep
import bet_policy


def test_probe_amount_is_100():
    assert bet_policy.DEFAULT.probe_amount == 100.0
    assert ad.PROBE_AMOUNT == 100.0


def test_record_attempt_persists_mission_id(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(str(db_path))
    con.execute("""
        CREATE TABLE deposit_attempts (
            attempt_id TEXT PRIMARY KEY,
            batch_id TEXT,
            mission_id TEXT,
            account_email TEXT,
            card_id INTEGER,
            amount REAL,
            source TEXT,
            operator_id INTEGER,
            status TEXT,
            rejection_reason TEXT,
            gateway_response_raw TEXT,
            gateway_txn_id TEXT,
            balance_before REAL,
            balance_after REAL,
            duration_ms INTEGER,
            captcha_cost REAL,
            card_pipe TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

    # Mock _bot_db en deposits
    from betmexico_db import BetmexicoDB
    mock_db = BetmexicoDB(str(db_path))
    monkeypatch.setattr("betmexico_db.db", mock_db)

    dep._record_attempt(
        attempt_id="att_1",
        email="test@user.com",
        amount=100.0,
        status="rejected",
        rejection_reason="BANK_REJECTED",
        duration_ms=120,
        operator_id=1,
        card_pipe="5119163057547385|0131|495",
        mission_id="m_test_123",
    )

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM deposit_attempts WHERE attempt_id='att_1'").fetchone()
    assert row is not None
    assert row["mission_id"] == "m_test_123"
    assert row["source"] == "auto_mission"
    con.close()


def test_get_resting_accounts_2x2_window(tmp_path):
    db_path = tmp_path / "test_resting.db"
    con = sqlite3.connect(str(db_path))
    con.execute("""
        CREATE TABLE auto_missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT,
            accounts_selected TEXT,
            matches TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE deposit_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT,
            account_email TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Sembrar m1 y m2 donde acc_bad@x.com intentó y no fondeó en ambas
    con.execute("INSERT INTO auto_missions (mission_id, status) VALUES ('m2', 'failed')")
    con.execute("INSERT INTO auto_missions (mission_id, status) VALUES ('m1', 'failed')")

    con.execute("INSERT INTO deposit_attempts (mission_id, account_email, status) VALUES ('m2', 'acc_bad@x.com', 'rejected')")
    con.execute("INSERT INTO deposit_attempts (mission_id, account_email, status) VALUES ('m1', 'acc_bad@x.com', 'rejected')")
    con.execute("INSERT INTO deposit_attempts (mission_id, account_email, status) VALUES ('m1', 'acc_good@x.com', 'approved')")
    con.commit()
    con.close()

    resting = ad._get_resting_accounts(str(db_path))
    assert "acc_bad@x.com" in resting
    assert "acc_good@x.com" not in resting


def test_selection_prioritizes_zero_attempts(seed_db):
    db_path = str(seed_db)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Limpiar cuentas pre-existentes
    con.execute("DELETE FROM accounts")
    con.execute("DELETE FROM deposit_attempts")

    # acc_tired tiene sesión activa pero 8 reintentos
    con.execute("""
        INSERT INTO accounts (id, email, password, first_checked_at, last_checked_at, grade, status, published_to_pool, kyc_verified, jwt_token, jwt_expires_at, balance_real)
        VALUES (1, 'tired@x.com', 'pass', '2026-09-01', '2026-09-01', 'D', 'LIVE', 1, 1, 'live_jwt_token_12345678901234567890', strftime('%s','now') + 3600, 0.0)
    """)
    for _ in range(8):
        con.execute("INSERT INTO deposit_attempts (account_email, amount, status, rejection_reason) VALUES ('tired@x.com', 100.0, 'rejected', 'BANK_REJECTED')")

    # acc_fresh no tiene sesión activa (jwt_token null) pero tiene 0 intentos
    con.execute("""
        INSERT INTO accounts (id, email, password, first_checked_at, last_checked_at, grade, status, published_to_pool, kyc_verified, jwt_token, jwt_expires_at, balance_real)
        VALUES (2, 'fresh@x.com', 'pass', '2026-09-01', '2026-09-01', 'D', 'LIVE', 1, 1, NULL, NULL, 0.0)
    """)
    con.commit()
    con.close()

    # Ejecutar plan_auto_mission
    plan = ad.plan_auto_mission(db_path, ["5263540159335880|0529|882"], amount=100.0, target_count=1)
    assert plan["feasible"] is True
    assert len(plan["accounts"]) >= 1
    # La cuenta fresca debe ganar la selección sobre la cuenta taladrada
    assert plan["accounts"][0]["email"] == "fresh@x.com"
