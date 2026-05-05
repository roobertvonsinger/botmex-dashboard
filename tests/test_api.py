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


def test_superadmin_conectados(client):
    r = client.get("/api/superadmin/conectados")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert data == []


def test_superadmin_actividad(client):
    r = client.get("/api/superadmin/actividad")
    assert r.status_code == 200
    data = r.json()
    assert "recentChecks" in data
    assert "byHour" in data
    assert isinstance(data["recentChecks"], list)
    assert isinstance(data["byHour"], list)
    # Seed has 3 accounts all with last_checked_at set
    assert len(data["recentChecks"]) == 3
    # All seeded checks share the same timestamp ("2026-05-05 11:00:00")
    assert len(data["byHour"]) == 1


def test_superadmin_alertas(client):
    r = client.get("/api/superadmin/alertas")
    assert r.status_code == 200
    data = r.json()
    assert "recentDead" in data
    assert "noRecentCheck" in data
    assert isinstance(data["recentDead"], list)
    # Seed has exactly 1 DEAD account
    assert len(data["recentDead"]) == 1
    # Both LIVE accounts have fresh last_checked_at (within 48h of seed time)
    assert data["noRecentCheck"] == 0


def test_superadmin_pool_no_key(client, monkeypatch):
    monkeypatch.delenv("CAPMONSTER_KEY", raising=False)
    r = client.get("/api/superadmin/pool")
    assert r.status_code == 200
    data = r.json()
    assert "capmonster" in data
    assert "balance" in data["capmonster"]
    assert "error" in data["capmonster"]
    assert data["capmonster"]["balance"] is None
    assert data["capmonster"]["error"] == "CAPMONSTER_KEY not set"


def test_lock_account(client):
    accounts = client.get("/api/accounts?status=LIVE").json()
    acc_id = accounts[0]["id"]

    r = client.post(
        f"/api/accounts/{acc_id}/lock",
        json={"operator": "RobertVS", "hours": 2},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["locked_by"] == "RobertVS"
    assert data["locked_until"] is not None


def test_unlock_account(client):
    accounts = client.get("/api/accounts?status=LIVE").json()
    acc_id = accounts[0]["id"]

    client.post(f"/api/accounts/{acc_id}/lock", json={"operator": "RobertVS", "hours": 2})
    r = client.post(f"/api/accounts/{acc_id}/unlock")
    assert r.status_code == 200
    assert r.json()["locked_by"] is None

    # Verify DB state via re-query
    rows = client.get("/api/accounts?status=all").json()
    target = next(row for row in rows if row["id"] == acc_id)
    assert target["locked_by"] is None
    assert target["locked_at"] is None


def test_lock_conflict(client):
    accounts = client.get("/api/accounts?status=LIVE").json()
    acc_id = accounts[0]["id"]

    client.post(f"/api/accounts/{acc_id}/lock", json={"operator": "RobertVS", "hours": 2})
    r = client.post(f"/api/accounts/{acc_id}/lock", json={"operator": "Lau", "hours": 2})
    assert r.status_code == 409
    assert "RobertVS" in r.json()["detail"]


def test_lock_not_found(client):
    r = client.post("/api/accounts/99999/lock", json={"operator": "RobertVS", "hours": 2})
    assert r.status_code == 404


import asyncio
import pytest


@pytest.mark.asyncio
async def test_sse_immediate_heartbeat():
    """El generator emite heartbeat inmediato al conectar."""
    from app import _sse_generator
    gen = _sse_generator()
    try:
        first = await gen.__anext__()
        assert first == ": heartbeat\n\n"
    finally:
        await gen.aclose()


@pytest.mark.asyncio
async def test_sse_broadcast_delivery():
    """Un evento _broadcast llega al cliente conectado."""
    from app import _sse_generator, _broadcast, _sse_queues
    gen = _sse_generator()
    try:
        await gen.__anext__()  # heartbeat inicial — registra el queue
        assert len(_sse_queues) == 1
        _broadcast({"type": "locked", "id": 42, "operator": "RobertVS"})
        msg = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
        assert msg.startswith("data: ")
        assert '"type": "locked"' in msg
        assert '"id": 42' in msg
    finally:
        await gen.aclose()
    # After aclose, queue should be removed
    assert len(_sse_queues) == 0
