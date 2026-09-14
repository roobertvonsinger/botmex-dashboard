import json
import sqlite3
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

import playdoit_db
import playdoit_api
from db_registry import db


def test_playdoit_db_crud(seed_db):
    # 1. Init table
    playdoit_db.init_playdoit_table()

    # Verify table exists in DB
    with db() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "playdoit_accounts" in tables

    # 2. Insert account
    acc1_data = {
        "email": "test1@playdoit.mx",
        "password": "pass123",
        "fullname": "Juan Perez",
        "birthdate": "1990-01-01",
        "national_id": "PEJU900101",
        "balance_cash": 250.0,
        "balance_promo": 50.0,
        "balance_total": 300.0,
        "total_deposits": 500.0,
        "net_deposits": 400.0,
        "deposit_count": 2,
        "bank_details": '[{"BankName": "BBVA", "Number": "1234"}]',
        "document_status": "APPROVED",
        "status": "LIVE",
    }
    acc_id = playdoit_db.upsert_playdoit_account(acc1_data, checked_by=1341812706)
    assert acc_id > 0

    # 3. List accounts
    accounts = playdoit_db.list_playdoit_accounts(status="LIVE")
    assert len(accounts) == 1
    assert accounts[0]["email"] == "test1@playdoit.mx"
    assert accounts[0]["fullname"] == "Juan Perez"
    assert accounts[0]["balance_total"] == 300.0
    assert accounts[0]["platform"] == "playdoit"
    assert accounts[0]["check_count"] == 1

    # 4. Upsert same account (update on conflict)
    acc1_update = dict(acc1_data)
    acc1_update["balance_cash"] = 350.0
    acc1_update["balance_total"] = 400.0
    playdoit_db.upsert_playdoit_account(acc1_update, checked_by=1341812706)

    accounts_after = playdoit_db.list_playdoit_accounts(status="LIVE")
    assert len(accounts_after) == 1  # No duplicate
    assert accounts_after[0]["balance_total"] == 400.0
    assert accounts_after[0]["check_count"] == 2

    # 5. Mark dead
    playdoit_db.mark_playdoit_dead("test1@playdoit.mx", "Credenciales invalidas")
    dead_accounts = playdoit_db.list_playdoit_accounts(status="DEAD")
    assert len(dead_accounts) == 1
    assert dead_accounts[0]["dead_reason"] == "Credenciales invalidas"

    # 6. Stats
    stats = playdoit_db.get_playdoit_stats()
    assert stats["total_accounts"] == 1
    assert stats["dead_accounts"] == 1
    assert stats["live_accounts"] == 0


def test_playdoit_accounts_isolation(seed_db):
    """Verifica que las cuentas PlayDoit no se mezclen con la tabla accounts de BetMexico."""
    playdoit_db.init_playdoit_table()

    # Contar cuentas BetMexico antes
    with db() as conn:
        bmx_before = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]

    # Insertar en playdoit_accounts
    playdoit_db.upsert_playdoit_account({
        "email": "isolate@playdoit.mx",
        "password": "secret",
        "balance_total": 500.0,
    })

    # Contar cuentas BetMexico despues
    with db() as conn:
        bmx_after = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        # Debe ser exactamente el mismo
        assert bmx_before == bmx_after
        # Y la cuenta PlayDoit no debe existir en accounts
        found = conn.execute("SELECT 1 FROM accounts WHERE email='isolate@playdoit.mx'").fetchone()
        assert found is None


def test_playdoit_api_result_dataclass():
    res = playdoit_api.PlaydoitCheckResult(
        ok=True,
        email="player@playdoit.mx",
        password="pass",
        balance_cash=120.5,
        balance_promo=10.0,
        balance_total=130.5,
        fullname="Roberto Gomez",
    )
    d = res.to_dict()
    assert d["email"] == "player@playdoit.mx"
    assert d["balance_cash"] == 120.5
    assert d["status"] == "LIVE"
    assert d["dead_reason"] is None

    res_fail = playdoit_api.PlaydoitCheckResult(
        ok=False,
        email="fail@playdoit.mx",
        password="wrong",
        error="Login fallido: Password incorrecto",
    )
    df = res_fail.to_dict()
    assert df["status"] == "DEAD"
    assert df["dead_reason"] == "Login fallido: Password incorrecto"


@pytest.mark.asyncio
async def test_playdoit_client_mock():
    client = playdoit_api.PlaydoitClient()

    mock_login_resp = MagicMock(spec=httpx.Response)
    mock_login_resp.status_code = 200
    mock_login_resp.json.return_value = {"success": True, "message": "OK"}

    mock_bal_resp = MagicMock(spec=httpx.Response)
    mock_bal_resp.status_code = 200
    mock_bal_resp.json.return_value = {"cash": 150.0, "promo": 20.0, "balance": 170.0}

    mock_player_resp = MagicMock(spec=httpx.Response)
    mock_player_resp.status_code = 200
    mock_player_resp.json.return_value = {
        "firstName": "Ana",
        "lastName": "Lopez",
        "birthDate": "1995-05-15",
        "nationalIdNumber": "LOAN950515",
    }

    mock_methods_resp = MagicMock(spec=httpx.Response)
    mock_methods_resp.status_code = 200
    mock_methods_resp.json.return_value = {
        "totalDeposits": 1000.0,
        "netDeposits": 800.0,
        "totalDepositCount": 5,
    }

    mock_details_resp = MagicMock(spec=httpx.Response)
    mock_details_resp.status_code = 200
    mock_details_resp.json.return_value = []

    mock_docs_resp = MagicMock(spec=httpx.Response)
    mock_docs_resp.status_code = 200
    mock_docs_resp.json.return_value = {"documentStatus": "VERIFIED"}

    # Mock del httpx.AsyncClient interno
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=[
        MagicMock(status_code=200), # Warmup
        mock_bal_resp,              # Balance
        mock_player_resp,           # Player
        mock_methods_resp,          # Methods
        mock_details_resp,          # Details
        mock_docs_resp,             # Docs
    ])
    mock_http_client.post = AsyncMock(return_value=mock_login_resp)
    mock_http_client.__aenter__.return_value = mock_http_client
    mock_http_client.__aexit__.return_value = None

    with patch.object(client, "_create_client", return_value=mock_http_client):
        res = await client.check_credentials_and_fetch("ana@playdoit.mx", "pass123")
        assert res.ok is True
        assert res.balance_cash == 150.0
        assert res.balance_promo == 20.0
        assert res.balance_total == 170.0
        assert res.fullname == "Ana Lopez"
        assert res.birthdate == "1995-05-15"
        assert res.total_deposits == 1000.0
        assert res.deposit_count == 5
        assert res.document_status == "VERIFIED"


def test_app_playdoit_endpoints(client, seed_db):
    playdoit_db.init_playdoit_table()
    playdoit_db.upsert_playdoit_account({
        "email": "api_test@playdoit.mx",
        "password": "pass",
        "balance_total": 99.0,
        "status": "LIVE"
    })

    # GET /api/playdoit/accounts
    r = client.get("/api/playdoit/accounts")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(a["email"] == "api_test@playdoit.mx" for a in data)

    # GET /api/playdoit/stats
    r_stats = client.get("/api/playdoit/stats")
    assert r_stats.status_code == 200
    stats = r_stats.json()
    assert "total_accounts" in stats
    assert "live_accounts" in stats
    assert "dead_accounts" in stats
