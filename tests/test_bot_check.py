import os, pytest

def test_filter_and_sanitize_check_combos(seed_db):
    from app import filter_and_sanitize_check_combos, db
    with db(write=True) as c:
        c.execute("INSERT OR IGNORE INTO accounts (email, password, status, first_checked_at, last_checked_at) VALUES ('existente@gmail.com', 'pass123', 'LIVE', '2026-01-01', '2026-01-01')")
        c.execute("INSERT OR IGNORE INTO account_cards (account_email, card_number) VALUES ('existente@gmail.com', '4111111111111111')")

    combos = [
        "existente@gmail.com:pass123", # Debe ser descartado por BD (email)
        "nuevo1@gmail.com:pass123:4111111111111111|12|30|123", # Debe ser descartado por BD (tarjeta)
        "nuevo2@gmail.com:pass123:5579070133314628|12|30|123", # Válido (Luhn + Stripe token OK)
        "nuevo2@gmail.com:pass123:5579070133314628|12|30|123", # Duplicado interno
    ]

    res = filter_and_sanitize_check_combos(combos)
    assert res["total_received"] == 4
    assert res["dupes_count"] == 1
    assert "existente@gmail.com" in res["in_db_emails"]
    assert "4111111111111111" in res["in_db_cards"]
    assert len(res["valid_combos"]) == 1
    assert res["valid_combos"][0]["email"] == "nuevo2@gmail.com"


def test_api_bot_check_limits(client):
    # Texto > 100 combos debe fallar con 400
    text_combos = [f"user{i}@test.com:pass" for i in range(101)]
    res = client.post("/api/bot/check", json={"operator_id": 1341812706, "combos": text_combos, "source_type": "text"})
    assert res.status_code == 400
    assert "límite de 100" in res.json()["detail"]

    # File > 5000 debe fallar con 400
    file_combos = [f"user{i}@test.com:pass" for i in range(5001)]
    res = client.post("/api/bot/check", json={"operator_id": 1341812706, "combos": file_combos, "source_type": "file"})
    assert res.status_code == 400
    assert "límite máximo de 5,000" in res.json()["detail"]


def test_api_bot_check_confirmation_flow(client):
    combos = ["nuevo_bot_user@gmail.com:pass123"]
    # confirmed = false
    res = client.post("/api/bot/check", json={"operator_id": 1341812706, "combos": combos, "source_type": "text", "confirmed": False})
    assert res.status_code == 200
    data = res.json()
    assert data["require_confirmation"] is True
    assert "botmexico.net" in data["message"]



