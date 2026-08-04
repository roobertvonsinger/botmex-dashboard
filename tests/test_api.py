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
        "id", "email", "password", "balance_total", "balance_real",
        "last_deposit_amount", "last_deposit_date", "status", "grade",
        "locked_by", "locked_at", "last_checked_at", "check_count",
        "cards_count",
    }
    assert expected_keys <= set(row.keys())


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
        "inUse": 2,              # a@ y c@ lockeadas por 555 en seed A2.1
    }


def test_superadmin_conectados(client):
    r = client.get("/api/superadmin/kpis")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["online"]["operators"], list)
    # Seed no tiene actividad < 5min ni locks de operador real → 0 activos
    assert data["online"]["active"] == 0


def test_superadmin_actividad(client):
    r = client.get("/api/superadmin/kpis")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["feed"], list)
    # Seed tiene 2 deposit_attempts + 2 cuentas lockeadas → feed no vacío
    assert len(data["feed"]) >= 1


def test_superadmin_alertas(client):
    r = client.get("/api/superadmin/kpis")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["alerts"], list)


def test_superadmin_pool_no_key(client, monkeypatch):
    monkeypatch.delenv("CAPMONSTER_KEY", raising=False)
    monkeypatch.delenv("BMX_CAPMONSTER_KEY", raising=False)
    # _capmonster_balance tiene fallback hardcoded; simulamos el path "sin key"
    import app as app_mod
    monkeypatch.setattr(app_mod, "_capmonster_balance",
                        lambda: {"balance": None, "error": "CAPMONSTER_KEY not set"})
    r = client.get("/api/superadmin/kpis")
    assert r.status_code == 200
    data = r.json()
    assert data["capmonster_balance"] is None
    assert data["capmonster_error"] == "CAPMONSTER_KEY not set"


def test_lock_account(make_client):
    sa = make_client(role="superadmin")
    accounts = sa.get("/api/accounts?status=LIVE").json()
    acc_id = next(a["id"] for a in accounts if not a.get("locked_by"))

    op = make_client(role="operator")
    r = op.post(
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


def test_lock_conflict(make_client):
    sa = make_client(role="superadmin")
    accounts = sa.get("/api/accounts?status=LIVE").json()
    acc_id = next(a["id"] for a in accounts if not a.get("locked_by"))

    op = make_client(role="operator")
    op.post(f"/api/accounts/{acc_id}/lock", json={"operator": "RobertVS", "hours": 2})
    r = op.post(f"/api/accounts/{acc_id}/lock", json={"operator": "Lau", "hours": 2})
    assert r.status_code == 409
    assert "RobertVS" in r.json()["detail"]


def test_lock_not_found(client):
    r = client.post("/api/accounts/99999/lock", json={"operator": "RobertVS", "hours": 2})
    assert r.status_code == 404


def test_deposits_empty_returns_list(client):
    r = client.get("/api/deposits")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2  # seed A2.1 inserta 2 deposit_attempts


def test_deposits_stats_empty(client):
    r = client.get("/api/deposits/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2          # seed A2.1: 2 deposit_attempts
    assert data["approved"] == 0       # status "APPROVED" (mayús) != 'approved' en SQLite BINARY
    assert data["rejected"] == 0
    assert data["pending"] == 2
    assert data["success_rate"] == 0.0
    assert data["total_amount_approved"] == 0.0


import asyncio
import pytest


_SA_CTX = {"role": "superadmin", "telegram_id": 1341812706, "display": "RobertVS"}


@pytest.mark.asyncio
async def test_sse_immediate_heartbeat():
    """El generator emite heartbeat inmediato al conectar."""
    from app import _sse_generator
    gen = _sse_generator(_SA_CTX)
    try:
        first = await gen.__anext__()
        assert first == ": heartbeat\n\n"
    finally:
        await gen.aclose()


@pytest.mark.asyncio
async def test_sse_broadcast_delivery():
    """Un evento _broadcast llega al cliente SA conectado."""
    from app import _sse_generator, _broadcast, _sse_queues
    gen = _sse_generator(_SA_CTX)
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
