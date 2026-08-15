"""test_auto_batch_withdrawals.py — Tests para retiros automáticos en batches de $200 y guardarraíl anti-tarjeta."""

import pytest
import sqlite3
import httpx
from unittest.mock import AsyncMock, patch

from withdrawals import (
    execute_auto_batch_withdrawal,
    DEFAULT_BATCH_AMOUNT,
    BATCH_WITHDRAWAL_COOLDOWN_SEC,
)


@pytest.mark.asyncio
async def test_auto_batch_withdrawal_success(tmp_path, monkeypatch):
    """Verifica que execute_auto_batch_withdrawal divide un saldo de $450 en batches de $200, $200 y $50."""
    db_file = tmp_path / "test.db"
    con = sqlite3.connect(str(db_file))
    con.execute("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            email TEXT,
            jwt_token TEXT,
            jwt_expires_at INTEGER,
            status TEXT DEFAULT 'LIVE',
            withdrawal_ready INTEGER DEFAULT 1,
            balance_real REAL DEFAULT 450.0
        )
    """)
    con.execute("INSERT INTO accounts (id, email, jwt_token, jwt_expires_at, status, withdrawal_ready, balance_real) VALUES (1, 'user@bmx.mx', 'valid_jwt', 9999999999, 'LIVE', 1, 450.0)")
    con.commit()
    con.close()

    # Mock get_real_balance
    bal_values = [
        {"Real": 450.0},
        {"Real": 250.0},
        {"Real": 50.0},
        {"Real": 0.0},
    ]

    async def mock_balance(jwt, proxy_url):
        if bal_values:
            return bal_values.pop(0)
        return {"Real": 0.0}

    # Mock execute_withdrawal
    tx_counter = [0]
    async def mock_exec_wd(db_path, account_id, amount):
        tx_counter[0] += 1
        return {
            "transactionId": f"tx_00{tx_counter[0]}",
            "amount": amount,
            "account_email": "user@bmx.mx",
            "_jwt": "valid_jwt",
            "_proxy_url": None,
        }

    # Mock bank transaction audit (gateway=2 SPEI)
    async def mock_bank_tx(jwt, proxy_url, tx_id):
        return {
            "gateway": 2,
            "gateway_spei": True,
            "gateway_mismatch": False,
        }

    # Mock refresh post-retiro y cooldown sleep
    monkeypatch.setattr("withdrawals.get_real_balance", mock_balance)
    monkeypatch.setattr("withdrawals.execute_withdrawal", mock_exec_wd)
    monkeypatch.setattr("withdrawals.get_bank_transaction", mock_bank_tx)
    monkeypatch.setattr("withdrawals._refresh_account_after_withdrawal", AsyncMock())
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    result = await execute_auto_batch_withdrawal(str(db_file), 1, 12345)

    assert result["ok"] is True
    assert result["batches_count"] == 3
    assert result["total_withdrawn"] == 450.0
    assert len(result["batches"]) == 3
    assert result["batches"][0]["amount"] == 200.0
    assert result["batches"][1]["amount"] == 200.0
    assert result["batches"][2]["amount"] == 50.0


@pytest.mark.asyncio
async def test_auto_batch_withdrawal_card_refund_guard(tmp_path, monkeypatch):
    """Verifica que si un retiro se desvía a tarjeta (gateway=1), el proceso se DETIENE de inmediato."""
    db_file = tmp_path / "test.db"
    con = sqlite3.connect(str(db_file))
    con.execute("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            email TEXT,
            jwt_token TEXT,
            jwt_expires_at INTEGER,
            status TEXT DEFAULT 'LIVE',
            withdrawal_ready INTEGER DEFAULT 1,
            balance_real REAL DEFAULT 600.0
        )
    """)
    con.execute("INSERT INTO accounts (id, email, jwt_token, jwt_expires_at, status, withdrawal_ready, balance_real) VALUES (2, 'carduser@bmx.mx', 'valid_jwt', 9999999999, 'LIVE', 1, 600.0)")
    con.commit()
    con.close()

    async def mock_balance(jwt, proxy_url):
        return {"Real": 600.0}

    async def mock_exec_wd(db_path, account_id, amount):
        return {
            "transactionId": "tx_card_refund",
            "amount": amount,
            "account_email": "carduser@bmx.mx",
            "_jwt": "valid_jwt",
            "_proxy_url": None,
        }

    # Gateway 1 = tarjeta (reembolso detectado)
    async def mock_bank_tx(jwt, proxy_url, tx_id):
        return {
            "gateway": 1,
            "gateway_spei": False,
            "gateway_mismatch": True,
        }

    monkeypatch.setattr("withdrawals.get_real_balance", mock_balance)
    monkeypatch.setattr("withdrawals.execute_withdrawal", mock_exec_wd)
    monkeypatch.setattr("withdrawals.get_bank_transaction", mock_bank_tx)
    monkeypatch.setattr("withdrawals._refresh_account_after_withdrawal", AsyncMock())
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    result = await execute_auto_batch_withdrawal(str(db_file), 2, 12345)

    assert result["ok"] is False
    assert result["stopped_reason"] == "card_refund_detected"
    assert "reembolso de tarjeta" in result["error"]
    assert result["batches_count"] == 1

    # Verificar que withdrawal_ready se puso en 0 en la BD
    con2 = sqlite3.connect(str(db_file))
    row = con2.execute("SELECT withdrawal_ready FROM accounts WHERE id=2").fetchone()
    con2.close()
    assert row[0] == 0
