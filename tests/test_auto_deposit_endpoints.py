# tests/test_auto_deposit_endpoints.py
"""Tests de los endpoints del modo auto-depósito V2 (Task C del plan
docs/superpowers/plans/2026-07-28-modo-auto-deposito-v2.md):

  POST /api/deposits/auto                      (C1 — 10 tests)
  POST /api/deposits/auto/{mission_id}/cancel  (C2)
  GET  /api/deposits/auto/{mission_id}/status  (C2)

`plan_auto_mission`/`run_auto_mission` se mockean por monkeypatch sobre el
módulo auto_deposit (run_auto_mission la implementa Task D en paralelo — los
tests NO dependen de su existencia real). Los tests de validación/cap no
mockean nada.
"""
import json
import sqlite3
from datetime import datetime, timezone


# ── helpers ──────────────────────────────────────────────────────────────────
VALID_BODY = {
    "card_pipes": ["4111111111111111|1230|123"],
    "amount": 150,
    "target_count": 9,
}

FEASIBLE_PLAN = {
    "accounts": [
        {"id": 1, "email": "a@test.com", "grade": "A",
         "card_pipe": "4111111111111111|1230|123"},
    ],
    "total_estimated": 1350.0,
    "feasible": True,
    "reason": "",
}


def _mock_plan_and_run(monkeypatch, plan=None):
    """Mockea plan_auto_mission/run_auto_mission en el módulo auto_deposit.
    Retorna dict `calls` con las invocaciones de run_auto_mission."""
    calls = {"run": []}
    plan = FEASIBLE_PLAN if plan is None else plan
    monkeypatch.setattr(
        "auto_deposit.plan_auto_mission", lambda *a, **k: plan, raising=False
    )

    def fake_run(mission_id, plan_arg, user):
        calls["run"].append(
            {"mission_id": mission_id, "plan": plan_arg, "user": user}
        )

        async def _noop():
            return None

        return _noop()

    monkeypatch.setattr("auto_deposit.run_auto_mission", fake_run, raising=False)
    return calls


def _insert_mission(db_path, mission_id="m1234567", status="matching",
                    phase_detail=None, matches=None, accounts=None):
    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO auto_missions (mission_id, operator_id, card_pipes, "
            "amount, target_count, accounts_selected, matches, status, "
            "phase_detail, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                mission_id, 555,
                json.dumps(["4111111111111111|1230|123"]),
                150.0, 9,
                json.dumps(accounts if accounts is not None else [1]),
                json.dumps(matches if matches is not None else []),
                status, phase_detail, now, now,
            ),
        )
        con.commit()
    finally:
        con.close()


def _get_mission(db_path, mission_id):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM auto_missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


# ── C1 — POST /api/deposits/auto ─────────────────────────────────────────────
def test_auto_403_non_sa(make_client):
    c = make_client(role="admin")
    r = c.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 403


def test_auto_400_no_cards(client):
    r = client.post("/api/deposits/auto", json={})
    assert r.status_code == 400


def test_auto_400_exceeds_cap(client):
    # 150 × 20 = 3000 > DEP_MAX_24H (1499) — validación pura, sin mocks
    r = client.post("/api/deposits/auto", json={
        "card_pipes": ["4111111111111111|1230|123"],
        "amount": 150, "target_count": 20,
    })
    assert r.status_code == 400


def test_auto_400_amount_over_per_txn(client):
    # 500 > DEP_MAX_PER_TXN (499) — validación pura, sin mocks
    r = client.post("/api/deposits/auto", json={
        "card_pipes": ["4111111111111111|1230|123"],
        "amount": 500, "target_count": 1,
    })
    assert r.status_code == 400


def test_auto_409_not_feasible(client, monkeypatch):
    _mock_plan_and_run(monkeypatch, plan={
        "accounts": [], "total_estimated": 0,
        "feasible": False, "reason": "sin cuentas elegibles",
    })
    r = client.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 409
    assert "sin cuentas elegibles" in r.json()["detail"]


def test_auto_happy_returns_mission_id(client, monkeypatch):
    _mock_plan_and_run(monkeypatch)
    r = client.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["mission_id"]
    assert body["accounts_selected"] == 1
    assert body["total_estimated"] == 1350.0
    assert body["status"] == "matching"


def test_auto_persists_mission(client, seed_db, monkeypatch):
    _mock_plan_and_run(monkeypatch)
    r = client.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 200
    row = _get_mission(seed_db, r.json()["mission_id"])
    assert row is not None
    assert row["status"] == "pending"
    assert row["amount"] == 150.0
    assert row["target_count"] == 9
    assert json.loads(row["card_pipes"]) == ["4111111111111111|1230|123"]
    assert json.loads(row["accounts_selected"]) == [1]
    matches = json.loads(row["matches"])
    assert matches[0]["account_id"] == 1
    assert matches[0]["card_pipe"] == "4111111111111111|1230|123"
    assert row["created_at"] and row["updated_at"]


def test_auto_broadcasts_start(client, monkeypatch):
    _mock_plan_and_run(monkeypatch)
    import app as app_mod
    events = []
    monkeypatch.setattr(app_mod, "_broadcast", events.append)
    r = client.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 200
    auto_events = [e for e in events if e.get("kind") == "auto_mission"]
    assert len(auto_events) == 1
    assert auto_events[0]["status"] == "started"
    assert auto_events[0]["mission_id"] == r.json()["mission_id"]
    assert auto_events[0]["accounts"] == 1


def test_auto_launches_background_task(client, monkeypatch):
    calls = _mock_plan_and_run(monkeypatch)
    r = client.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 200
    assert len(calls["run"]) == 1
    assert calls["run"][0]["mission_id"] == r.json()["mission_id"]
    assert calls["run"][0]["plan"]["feasible"] is True
    assert isinstance(calls["run"][0]["user"], dict)


def test_auto_respects_mission_sem(client, monkeypatch):
    class _LockedSem:
        def locked(self):
            return True

    monkeypatch.setattr("deposits._mission_sem", _LockedSem())
    r = client.post("/api/deposits/auto", json=VALID_BODY)
    assert r.status_code == 429


# ── C2 — cancel + status ─────────────────────────────────────────────────────
def test_cancel_403_non_sa(make_client, seed_db):
    _insert_mission(seed_db)
    c = make_client(role="admin")
    r = c.post("/api/deposits/auto/m1234567/cancel")
    assert r.status_code == 403


def test_cancel_404_unknown(client):
    r = client.post("/api/deposits/auto/nope0000/cancel")
    assert r.status_code == 404


def test_cancel_sets_status(client, seed_db):
    _insert_mission(seed_db, mission_id="m1234567", status="matching")
    r = client.post("/api/deposits/auto/m1234567/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    row = _get_mission(seed_db, "m1234567")
    assert row["status"] == "cancelled"


def test_status_404_unknown(client):
    r = client.get("/api/deposits/auto/nope0000/status")
    assert r.status_code == 404


def test_status_returns_mission(client, seed_db):
    matches = [{"account_id": 1, "card_pipe": "4111111111111111|1230|123",
                "email": "a@test.com"}]
    _insert_mission(seed_db, mission_id="m1234567", status="scheduling",
                    matches=matches, accounts=[1])
    r = client.get("/api/deposits/auto/m1234567/status")
    assert r.status_code == 200
    body = r.json()
    assert body["mission_id"] == "m1234567"
    assert body["status"] == "scheduling"
    assert body["amount"] == 150.0
    assert body["target_count"] == 9
    assert body["matches"] == matches          # parseados de JSON, no string
    assert body["accounts_selected"] == [1]
    assert body["card_pipes"] == ["4111111111111111|1230|123"]


def test_status_includes_phase_detail(client, seed_db):
    _insert_mission(seed_db, mission_id="m1234567", status="scheduling",
                    phase_detail="cuenta 2/3: rep 5/9")
    r = client.get("/api/deposits/auto/m1234567/status")
    assert r.status_code == 200
    assert r.json()["phase_detail"] == "cuenta 2/3: rep 5/9"
