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


