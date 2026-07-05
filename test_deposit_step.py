"""Tests del evento SSE `deposit_step` (Fase 2, spec 2026-07-05).

Cubre SOLO el wrapper `_wrap_deposit_step` + su mapeo de payload
(`_deposit_step_payload`). NO toca la lógica de depósito real (login/begin/
submit/check), NO toca `_record_attempt`, NO toca el evento `deposit` de
cierre — esos siguen intactos.

Usa el fixture `seed_db` (conftest.py) para que `from app import _broadcast,
_resolve_who` (import diferido dentro de deposits.py) no explote por falta de
BETMEX_DB — mismo patrón que test_sse_visibility.py.
"""
import asyncio

import deposits


def _run(coro):
    return asyncio.run(coro)


# ── Test 1: wrapper emite en los 4 cierres, sin romper el stream local ──────

def test_wrapper_emits_on_all_four_phase_closures(seed_db, monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(app, "_broadcast", lambda ev: calls.append(ev))

    inner_calls = []

    async def inner_cb(name, payload):
        inner_calls.append((name, payload))

    wrapped = deposits._wrap_deposit_step(
        inner_cb, email="x@y.z", actor=123, attempt_id="abc"
    )

    _run(wrapped("login_done", {"ok": True, "duration_ms": 50, "from_cache": False}))
    _run(wrapped("gateway_begin_done", {"order_id": "OID1", "ok": True, "duration_ms": 40}))
    _run(wrapped("gateway_submit_done", {"result_code": "BANK_APPROVED", "is_3ds": False, "duration_ms": 80}))
    _run(wrapped("gateway_check_done", {"txn_status": 6, "duration_ms": 30}))

    # (a) el stream local (inner_cb) recibió las 4 llamadas intactas
    assert len(inner_calls) == 4
    assert inner_calls[0][0] == "login_done"
    assert inner_calls[0][1] == {"ok": True, "duration_ms": 50, "from_cache": False}

    # (b) _broadcast se llamó 4 veces con kind == deposit_step, steps correctos
    assert len(calls) == 4
    steps = [ev["step"] for ev in calls]
    assert steps == ["login", "begin", "submit", "check"]
    for ev in calls:
        assert ev["kind"] == "deposit_step"
        assert ev["type"] == "activity"
        assert ev["email"] == "x@y.z"
        assert ev["attempt_id"] == "abc"
        assert "who_id" in ev

    login_ev, begin_ev, submit_ev, check_ev = calls
    assert login_ev["ok"] is True
    assert login_ev["duration_ms"] == 50
    assert begin_ev["ok"] is True
    assert begin_ev["duration_ms"] == 40
    assert submit_ev["duration_ms"] == 80
    assert check_ev["duration_ms"] == 30


# ── Test 2: submit/check mapean `code` desde result_code / txn_status ───────

def test_submit_and_check_map_code(seed_db, monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(app, "_broadcast", lambda ev: calls.append(ev))

    async def inner_cb(name, payload):
        pass

    wrapped = deposits._wrap_deposit_step(inner_cb, email="x@y.z", actor=123)

    _run(wrapped("gateway_submit_done", {"result_code": "BANK_REJECTED", "is_3ds": False, "duration_ms": 80}))
    _run(wrapped("gateway_check_done", {"txn_status": 6, "duration_ms": 30}))

    assert len(calls) == 2
    submit_ev, check_ev = calls
    assert submit_ev["code"] == "BANK_REJECTED"
    assert submit_ev["step"] == "submit"
    assert check_ev["code"] == "txn:6"
    assert check_ev["step"] == "check"


# ── Test 3: NO duplica el cierre — solo los 4 *_done broadcastean ──────────

def test_wrapper_does_not_broadcast_on_other_phases(seed_db, monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(app, "_broadcast", lambda ev: calls.append(ev))

    inner_calls = []

    async def inner_cb(name, payload):
        inner_calls.append((name, payload))

    wrapped = deposits._wrap_deposit_step(inner_cb, email="x@y.z", actor=123)

    _run(wrapped("done", {"success": True, "result_code": "BANK_APPROVED"}))
    _run(wrapped("login_start", {"email": "x@y.z"}))

    # inner sigue recibiendo TODO (stream local intacto)
    assert len(inner_calls) == 2
    # pero _broadcast NO se llamó — el evento `deposit` de cierre (_record_attempt)
    # sigue siendo el único broadcast de cierre.
    assert len(calls) == 0


# ── Test 4: filtro de rol reusa _event_visible_to (SIN cambios) ────────────

def test_role_filter_reuses_event_visible_to(seed_db):
    import app

    A = 123
    B = 456
    SA_CTX = {"role": "superadmin", "telegram_id": 999}
    OP_SELF_CTX = {"telegram_id": A}
    OP_OTHER_CTX = {"telegram_id": B}

    ev = {"kind": "deposit_step", "who_id": A}

    assert app._event_visible_to(ev, SA_CTX) is True
    assert app._event_visible_to(ev, OP_SELF_CTX) is True
    assert app._event_visible_to(ev, OP_OTHER_CTX) is False
