def test_health_returns_db_path_and_count(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["accounts"] == 3
    assert body["db"].endswith("test.db")


def test_accounts_default_returns_only_live(client):
    r = client.get("/api/accounts")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2  # las 2 LIVE del seed
    assert all(row["status"] == "LIVE" for row in rows)


def test_accounts_filter_by_grade(client):
    r = client.get("/api/accounts?grade=A")
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["email"] == "a@test.com"
    assert rows[0]["grade"] == "A"


def test_accounts_status_all_returns_dead_too(client):
    r = client.get("/api/accounts?status=all")
    rows = r.json()
    assert len(rows) == 3
    statuses = {row["status"] for row in rows}
    assert statuses == {"LIVE", "DEAD"}


def test_accounts_response_shape(client):
    r = client.get("/api/accounts")
    row = r.json()[0]
    expected_keys = {
        "id", "email", "balance_total", "balance_real",
        "last_deposit_amount", "last_deposit_date", "status", "grade",
        "locked_by", "locked_at", "last_checked_at", "check_count"
    }
    assert set(row.keys()) == expected_keys


def test_accounts_ordering_by_balance_desc(client):
    r = client.get("/api/accounts")
    rows = r.json()
    balances = [row["balance_total"] for row in rows]
    assert balances == sorted(balances, reverse=True)


def test_stats_returns_expected_aggregates(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "live": 2,
        "total": 3,
        "totalBalance": 150.5,  # 100 + 50.5
        "withBalance": 2,        # ambas LIVE tienen saldo > 0
        "inUse": 0,              # ninguna locked
    }
