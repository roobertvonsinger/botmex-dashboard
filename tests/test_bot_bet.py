# tests/test_bot_bet.py
"""Tests de integración unitaria para el endpoint /api/bot/bet y guardarraíles."""
import pytest
from fastapi.testclient import TestClient
import app as app_mod
import card_checker


@pytest.fixture
def sa_client(seed_db, monkeypatch):
    monkeypatch.setattr(app_mod, "DB_PATH", seed_db)
    import sqlite3
    con = sqlite3.connect(seed_db)
    con.execute("""
        CREATE TABLE IF NOT EXISTS operator_penalties (
            telegram_id INTEGER PRIMARY KEY,
            strikes_count INTEGER DEFAULT 0,
            penalty_until TEXT,
            last_attempts INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS auto_missions (
            mission_id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            completed_at TEXT,
            operator_id INTEGER,
            amount REAL,
            target_count INTEGER,
            card_pipes TEXT,
            accounts_selected TEXT,
            status TEXT,
            phase_detail TEXT,
            matches TEXT,
            total_deposited REAL DEFAULT 0,
            total_approved INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0
        )
    """)
    con.execute("DELETE FROM account_cards")
    con.commit()
    con.close()
    app_mod.app.dependency_overrides[app_mod.require_session] = lambda: {
        "role": "superadmin", "telegram_id": 1341812706,
        "username": "robertvs", "display": "Robert",
    }
    yield TestClient(app_mod.app)
    app_mod.app.dependency_overrides.clear()


def test_bot_bet_max_4_cards(sa_client):
    # Más de 4 tarjetas debe fallar con HTTP 400
    res = sa_client.post("/api/bot/bet", json={
        "card_pipes": [
            "4111111111111111|1230|123",
            "4111111111111111|1230|124",
            "4111111111111111|1230|125",
            "4111111111111111|1230|126",
            "4111111111111111|1230|127"
        ]
    })
    assert res.status_code == 400
    assert "1 a 4 tarjetas" in res.json()["detail"]


def test_bot_bet_luhn_failure(sa_client):
    # Tarjeta inválida por Luhn
    res = sa_client.post("/api/bot/bet", json={
        "card_pipes": ["4111111111111112|1230|123"]
    })
    assert res.status_code == 400
    assert "liveness" in res.json()["detail"].lower()


def test_bot_bet_require_confirmation(sa_client, monkeypatch):
    # Mockear perform_wabox_liveness_check
    monkeypatch.setattr(card_checker, "perform_wabox_liveness_check", lambda c: (True, "🟢 LIVE (Tokenized)", {}))

    res = sa_client.post("/api/bot/bet", json={
        "card_pipes": ["4111111111111111|1230|123"],
        "confirmed": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["require_confirmation"] is True
    assert "strikes_left" in data
    assert "ÚLTIMA CONFIRMACIÓN" in data["message"]


def test_bot_bet_no_passwords_in_response(sa_client, monkeypatch):
    monkeypatch.setattr(card_checker, "perform_wabox_liveness_check", lambda c: (True, "🟢 LIVE (Tokenized)", {}))

    import auto_deposit
    def mock_plan(db_path, card_pipes, amount, target_count):
        return {
            "feasible": True,
            "reason": "OK",
            "accounts": [{"id": 1, "email": "test@user.com", "card_pipe": card_pipes[0]}],
            "total_estimated": 1350.0
        }
    async def mock_run(mission_id, plan, user):
        pass

    monkeypatch.setattr(auto_deposit, "plan_auto_mission", mock_plan)
    monkeypatch.setattr(auto_deposit, "run_auto_mission", mock_run)

    res = sa_client.post("/api/bot/bet", json={
        "card_pipes": ["4111111111111111|1230|123"],
        "confirmed": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "password" not in data
    assert "combo" not in data
    assert data["matched_emails"] == ["test@user.com"]
    assert "https://botmexico.net/?match=" in data["dashboard_link"]
