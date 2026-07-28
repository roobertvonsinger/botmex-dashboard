# tests/test_auto_mission.py
"""Tests del orquestador run_auto_mission (Task D — plan v2, reglas 1-11).

Patrón del repo: tests sync + asyncio.run(scenario) (ver test_mission_sem_leak.py).
Todo lo externo está mockeado: _run_deposit_with_phases, locks, BD (seams _m_*),
pool de captcha y asyncio.sleep. Nada de red ni BD real.
"""
import asyncio
import json

import pytest

import auto_deposit as ad
import deposits as dep

P1 = "4111111111111111|12|30|123"
P2 = "4222222222222222|11|29|456"


class FakePool:
    def __init__(self):
        self.stopped = 0
        self.started = 0

    async def start_factory(self):
        self.started += 1

    async def prefetch(self, n):
        return None

    async def stop(self):
        self.stopped += 1


@pytest.fixture
def H(monkeypatch):
    """Harness: seams de auto_deposit + deposits mockeados, sleeps instantáneos."""
    h = type("H", (), {})()
    h.updates, h.unlocked, h.locked, h.attempts = [], [], [], []
    h.cooldowns, h.run_calls, h.sleeps, h.pools = [], [], [], []
    h.status = "matching"
    h.target_count = 1
    h.card_pipes = [P1]
    h.script = lambda email, amount, kw: {"success": True, "result_code": "BANK_APPROVED",
                                          "jwt": "J", "used_proxy": "P", "duration_ms": 5}

    monkeypatch.setattr(ad, "_m_update", lambda mid, **f: h.updates.append(f))
    monkeypatch.setattr(ad, "_m_status", lambda mid: h.status)
    monkeypatch.setattr(ad, "_m_load", lambda mid: {
        "amount": 150, "target_count": h.target_count,
        "card_pipes": json.dumps(h.card_pipes), "status": h.status})
    monkeypatch.setattr(ad, "_fetch_account",
                        lambda aid: {"id": aid, "email": f"acc{aid}@x.com", "password": "pw"})
    monkeypatch.setattr(ad, "_unlock", lambda aid: h.unlocked.append(aid))
    monkeypatch.setattr(ad, "_broadcast_mission", lambda *a, **k: None)

    def _make_pool(cap_key, size=1, workers=1):
        p = FakePool()
        h.pools.append(p)
        return p
    monkeypatch.setattr(dep, "_load_deps", lambda: _make_pool)
    monkeypatch.setattr(dep, "_auto_lock_for_deposit",
                        lambda aid, oid, user, hours=2: h.locked.append(aid))
    monkeypatch.setattr(dep, "_record_attempt",
                        lambda *a, **k: h.attempts.append(k.get("card_pipe")))
    monkeypatch.setattr(dep, "_set_account_cooldown",
                        lambda email, minutes=45: h.cooldowns.append(email))
    monkeypatch.setattr(dep, "_mission_sem", asyncio.Semaphore(2))

    async def _run(email, password, cc_num, cc_exp, cc_cvv, amount, user, pool,
                   phase_cb, **kw):
        h.run_calls.append({"email": email, "amount": amount, **kw})
        return h.script(email, amount, kw)
    monkeypatch.setattr(dep, "_run_deposit_with_phases", _run)

    async def _sleep(s):
        h.sleeps.append(s)
    monkeypatch.setattr(asyncio, "sleep", _sleep)
    return h


def plan(*ids):
    return {"accounts": [{"id": i, "email": f"acc{i}@x.com", "grade": "A",
                          "card_pipe": P1} for i in ids]}


def run(H, pl, mid="m1"):
    asyncio.run(ad.run_auto_mission(mid, pl, {"role": "superadmin", "telegram_id": 555}))


# ── Fase 1: matchmaking ──────────────────────────────────────────────────────
def test_mission_matchmaking_finds_match(H):
    run(H, plan(1))
    assert H.run_calls[0]["amount"] == ad.PROBE_AMOUNT
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert matches[0]["account_id"] == 1 and matches[0]["jwt"] == "J" \
        and matches[0]["proxy"] == "P"


def test_mission_matchmaking_tries_next_card(H):
    H.card_pipes = [P1, P2]
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"success": False, "result_code": "BANK_REJECTED", "error": "x"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))
    probes = [c for c in H.run_calls if c["amount"] == ad.PROBE_AMOUNT]
    assert len(probes) == 2
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert matches[0]["card_pipe"] == P2


def test_mission_matchmaking_skips_on_3ds(H):
    H.card_pipes = [P1, P2]
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"success": False, "result_code": "3DS_REQUIRED", "error": "3ds"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert matches[0]["card_pipe"] == P2  # 3DS no es decline: probó la siguiente


def test_mission_matchmaking_rate_limit_cooldown(H):
    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "RATE_LIMITED", "error": "429"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1, 2))
    assert "acc1@x.com" in H.cooldowns
    assert all(c["email"] != "acc1@x.com" or c is H.run_calls[0] for c in H.run_calls)
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert [m["account_id"] for m in matches] == [2]
    assert 1 in H.unlocked  # cuenta sin match no queda lockeada


def test_mission_matchmaking_reuses_session_between_cards(H):
    """Regla 11: tras un intento con jwt (aunque transitorio), el siguiente
    intento de la MISMA cuenta reusa session_jwt/session_proxy."""
    H.card_pipes = [P1, P2]
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        if calls["n"] == 1:  # transitorio PERO con sesión capturable
            return {"success": False, "result_code": "BEGIN_ERROR", "error": "gateway 502",
                    "jwt": "J0", "used_proxy": "P0"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J0", "used_proxy": "P0"}
    H.script = script
    run(H, plan(1))
    assert len(H.run_calls) >= 2
    assert H.run_calls[1]["session_jwt"] == "J0"
    assert H.run_calls[1]["session_proxy"] == "P0"


def test_mission_unlocks_account_when_no_card_works(H):
    H.script = lambda email, amount, kw: {"success": False, "result_code": "BANK_REJECTED",
                                          "error": "rechazada"}
    run(H, plan(1))
    assert 1 in H.locked and 1 in H.unlocked
    assert H.updates[-1]["status"] == "failed"
    assert H.updates[-1]["phase_detail"] == "sin matches"


def test_mission_same_account_waits_mm_cooldown_between_cards(H):
    """Regla Robert 2026-07-28: no reintentar en la MISMA cuenta antes de 60s
    (MM_COOLDOWN) aunque sea con otra tarjeta."""
    H.card_pipes = [P1, P2]
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"success": False, "result_code": "BANK_REJECTED", "error": "x"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))
    assert dep.MM_COOLDOWN in H.sleeps


def test_mission_cross_account_gap_is_5s_not_60s(H):
    """Regla Robert 2026-07-28: entre cuentas DISTINTAS basta un respiro de 5s,
    no el cooldown de 60s de reintento en la misma cuenta."""
    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "BANK_REJECTED", "error": "x"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1, 2))
    assert ad.MM_CROSS_ACCOUNT_GAP in H.sleeps
    assert dep.MM_COOLDOWN not in H.sleeps  # única tarjeta por cuenta: sin reintento misma cuenta


def test_mission_caps_declines_per_account_per_run(H):
    """Regla Robert 2026-07-28: tope de 2 declines por cuenta en la MISMA
    corrida — con 3+ tarjetas candidatas, no se taladra una 3a vez."""
    H.card_pipes = [P1, P2, "4333333333333333|10|29|789"]
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        return {"success": False, "result_code": "BANK_REJECTED", "error": "x"}
    H.script = script
    run(H, plan(1))
    probes = [c for c in H.run_calls if c["amount"] == ad.PROBE_AMOUNT]
    assert len(probes) == ad.MM_MAX_ACCOUNT_DECLINES_PER_RUN


def test_mission_no_lock_before_card_candidates(H):
    """Regla 7: sin tarjetas candidatas la cuenta ni se lockea ni se intenta."""
    H.card_pipes = []
    pl = {"accounts": [{"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": None}]}
    run(H, pl)
    assert H.locked == [] and H.run_calls == []
    assert H.updates[-1]["status"] == "failed"


# ── Fase 2: scheduled ────────────────────────────────────────────────────────
def test_mission_scheduled_reuses_session(H):
    H.target_count = 2
    run(H, plan(1))
    sched = [c for c in H.run_calls if c["amount"] == 150]
    assert len(sched) == 2
    assert all(c["session_jwt"] == "J" for c in sched)


def test_mission_scheduled_survives_missing_jwt(H):
    """Regla 2: match sin jwt → Fase 2 arranca con session_jwt=None y captura
    la sesión en su primer éxito (patrón SP-2)."""
    H.target_count = 2
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        if calls["n"] == 1:  # probe: éxito pero SIN jwt
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": None,
                    "used_proxy": None}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J2", "used_proxy": "P2"}
    H.script = script
    run(H, plan(1))
    sched = [c for c in H.run_calls if c["amount"] == 150]
    assert sched[0]["session_jwt"] is None
    assert sched[1]["session_jwt"] == "J2"


def test_mission_scheduled_9_reps_then_stops(H):
    H.target_count = 9
    run(H, plan(1))
    sched = [c for c in H.run_calls if c["amount"] == 150]
    assert len(sched) == 9
    final = H.updates[-1]
    assert final["status"] == "completed"
    assert final["total_approved"] == 10           # probe $10 + 9×$150
    assert final["total_deposited"] == 10 + 9 * 150  # $1360 ≤ cap $1499


def test_mission_scheduled_aborts_on_decline(H):
    H.target_count = 9
    sched_n = {"n": 0}

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
        sched_n["n"] += 1
        if sched_n["n"] == 2:
            return {"success": False, "result_code": "BANK_REJECTED", "error": "rechazada"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))
    sched = [c for c in H.run_calls if c["amount"] == 150]
    assert len(sched) == 2  # paró en el decline, no siguió a 9
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1


# ── Semáforo / cancel / persistencia ─────────────────────────────────────────
def test_mission_respects_sem(H, monkeypatch):
    """(a) misión normal corre bajo sem; (b) sem lleno → fail-fast sin intentar."""
    run(H, plan(1))  # (a) corre con el sem de 2 slots del harness
    assert H.run_calls, "con sem libre la misión debe ejecutar"
    assert dep._mission_sem._value == 2, "el semáforo quedó liberado al terminar"

    H2calls = len(H.run_calls)
    monkeypatch.setattr(dep, "_mission_sem", asyncio.Semaphore(0))  # locked
    run(H, plan(1), mid="m2")
    assert len(H.run_calls) == H2calls, "con sem lleno NO debe intentar depósitos"
    assert H.updates[-1]["status"] == "failed"
    assert "semáforo" in H.updates[-1]["phase_detail"]


def test_mission_cancel_stops(H):
    """Cancel cooperativo: status='cancelled' en BD → para antes de Fase 2,
    desbloquea la cuenta (regla 4) y cierra como cancelled."""

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            H.status = "cancelled"  # el operador cancela tras el match
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J",
                    "used_proxy": "P"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    H.target_count = 9
    run(H, plan(1))
    sched = [c for c in H.run_calls if c["amount"] == 150]
    assert sched == [], "no debió arrancar Fase 2 tras cancel"
    assert H.updates[-1]["status"] == "cancelled"
    assert 1 in H.unlocked


def test_mission_persists_incremental_totals(H):
    """Regla 3: los totales se actualizan tras CADA éxito, no solo al final."""
    H.target_count = 3
    run(H, plan(1))
    approved_series = [u["total_approved"] for u in H.updates if "total_approved" in u]
    assert approved_series == [1, 2, 3, 4, 4], approved_series
    deposited_series = [u["total_deposited"] for u in H.updates if "total_deposited" in u]
    assert deposited_series[0] == ad.PROBE_AMOUNT
    assert deposited_series[-1] == ad.PROBE_AMOUNT + 3 * 150
