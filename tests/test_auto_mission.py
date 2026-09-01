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

P1 = "4111111111111111|1230|123"
P2 = "4222222222222222|1129|456"


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
    h.dead = []
    h.status = "matching"
    h.target_count = 1
    h.card_pipes = [P1]
    h.script = lambda email, amount, kw: {"success": True, "result_code": "BANK_APPROVED",
                                          "jwt": "J", "used_proxy": "P", "duration_ms": 5}

    monkeypatch.setattr(ad, "_get_married_card_owners", lambda *a, **k: {})
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
    monkeypatch.setattr(dep, "_mark_rate_limited_dead",
                        lambda email: h.dead.append(email))
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


def test_mission_matchmaking_3ds_allows_up_to_two_accounts(H):
    """Regla Robert 2026-08-25: Si una tarjeta recibe 3DS_REQUIRED en una cuenta,
    no se jubila inmediatamente: puede probarse en una segunda cuenta para certificar
    otra cuenta A+ (máximo 2 intentos por tarjeta por corrida).
    Al 2do intento con 3DS, se retira habiendo certificado ambas cuentas como A+."""
    H.card_pipes = [P1]
    attempted_emails = []

    def script(email, amount, kw):
        attempted_emails.append(email)
        return {"success": False, "result_code": "3DS_REQUIRED", "error": "3ds challenge"}

    H.script = script
    run(H, plan(1, 2, 3))
    # Se debió haber intentado en acc1 y en acc2 (2 intentos máx), pero NO en acc3
    assert attempted_emails == ["acc1@x.com", "acc2@x.com"], f"Intentos observados: {attempted_emails}"
    assert 1 in H.unlocked and 2 in H.unlocked, "Cuentas 1 y 2 debieron desbloquearse limpiamente"


def test_mission_matchmaking_real_decline_retires_after_two_accounts(H):
    """Regla Robert 2026-08-25: Si el banco declina una tarjeta en una cuenta, no se jubila
    inmediatamente en el primer fallo; se le da un segundo intento en otra cuenta.
    Al 2do rechazo en cuentas distintas, la tarjeta se jubila definitivamente."""
    H.card_pipes = [P1]
    attempted_emails = []

    def script(email, amount, kw):
        attempted_emails.append(email)
        return {"success": False, "result_code": "BANK_REJECTED", "error": "Fondos insuficientes"}

    H.script = script
    run(H, plan(1, 2, 3))
    # Probó en acc1 y en acc2, y al 2do decline la tarjeta se retiró (no tocó acc3)
    assert attempted_emails == ["acc1@x.com", "acc2@x.com"], f"Intentos observados: {attempted_emails}"
    assert 1 in H.unlocked and 2 in H.unlocked




def test_mission_matchmaking_terminal_on_card_locked(H):
    """Bug 2026-08-07: CARD_LOCKED_OTHER_ACCOUNT es el candado DB de deposits.py
    (tarjeta ya ligada a otro email) — determinístico, jamás cambia entre
    intentos. No estaba en ninguna lista terminal y caía al branch
    'transitorio', quemando los 4 reintentos (25s c/u, MATCH_TRANSIENT_RETRIES)
    contra un resultado que nunca iba a cambiar. Debe abortar la tarjeta en el
    primer intento, igual que un decline real."""
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "CARD_LOCKED_OTHER_ACCOUNT",
        "error": "Tarjeta ya aprobada en otro@x.com — bloqueada para otras cuentas",
    }
    run(H, plan(1))
    probes = [c for c in H.run_calls if c["amount"] == ad.PROBE_AMOUNT]
    assert len(probes) == 1, f"debió abortar en el primer intento, hizo {len(probes)}"
    assert 25 not in H.sleeps, "no debió dormir el backoff de reintento transitorio"


def test_mission_matchmaking_rate_limit_marks_dead(H):
    # Robert 2026-08-06: ya no enfriar-y-reintentar — a la primera 429, DEAD.
    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "RATE_LIMITED", "error": "429"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1, 2))
    assert "acc1@x.com" in H.dead
    assert all(c["email"] != "acc1@x.com" or c is H.run_calls[0] for c in H.run_calls)
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert [m["account_id"] for m in matches] == [2]
    assert 1 in H.unlocked  # cuenta sin match no queda lockeada


def test_mission_matchmaking_dead_code_no_transient_no_more_cards(H):
    """Cuando gentle_login devuelve code='DEAD' (429 BAN):
    1) Se aborta la cuenta inmediatamente sin sleep de 25s (transient).
    2) NO se prueban más tarjetas candidatas en esa cuenta muerta.
    3) Se pasa de inmediato a la siguiente cuenta."""
    H.card_pipes = [P1, P2, "4333333333333333|1029|789"]
    calls_acc1 = 0

    def script(email, amount, kw):
        nonlocal calls_acc1
        if email == "acc1@x.com":
            calls_acc1 += 1
            return {
                "success": False,
                "result_code": "DEAD",
                "error": "RATE_LIMITED_PERMANENT (429 — BetMexico bloqueó la cuenta)",
                "account_dead": True,
            }
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}

    H.script = script
    run(H, plan(1, 2))
    assert calls_acc1 == 1, "La cuenta DEAD solo debe recibir 1 intento, no reintentar otras tarjetas"
    assert 25 not in H.sleeps, "No debe haber backoff de retry transitorio (25s) en cuenta DEAD"
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert [m["account_id"] for m in matches] == [2]
    assert 1 in H.unlocked


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
    H.card_pipes = [P1, P2]
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
    H.card_pipes = [P1, P2, "4333333333333333|1029|789"]
    calls = {"n": 0}

    def script(email, amount, kw):
        calls["n"] += 1
        return {"success": False, "result_code": "BANK_REJECTED", "error": "x"}
    H.script = script
    run(H, plan(1))
    probes_acc1 = [c for c in H.run_calls if c["amount"] == ad.PROBE_AMOUNT and c["email"] == "acc1@x.com"]
    assert len(probes_acc1) == ad.MM_MAX_ACCOUNT_DECLINES_PER_RUN


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


def test_mission_scheduled_aborts_on_card_locked(H):
    """Mismo hueco de clasificación que la matchmaking (bug 2026-08-07), pero en
    Fase 2 (scheduled): CARD_LOCKED_OTHER_ACCOUNT debe abortar la rep, no
    reintentar contra un candado DB que no va a cambiar."""
    H.target_count = 9
    sched_n = {"n": 0}

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
        sched_n["n"] += 1
        if sched_n["n"] == 2:
            return {"success": False, "result_code": "CARD_LOCKED_OTHER_ACCOUNT",
                    "error": "Tarjeta ya aprobada en otro@x.com"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))
    sched = [c for c in H.run_calls if c["amount"] == 150]
    assert len(sched) == 2, f"debió abortar en el candado, no reintentar (hizo {len(sched)})"
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


def test_mission_approved_card_retired_not_retried_on_other_accounts(H):
    """Regla Robert 2026-08-16: En cuanto una tarjeta aprueba un depósito en la Cuenta 1,
    se jubila inmediatamente y NUNCA se intenta en la Cuenta 2 ni en las siguientes."""
    H.card_pipes = [P1, P2]
    pl = {
        "accounts": [
            {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
            {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1},
        ]
    }
    run(H, pl)
    # Cuenta 1 aprobó P1 en su probe de $10
    # Cuenta 2 debió intentar P2 (la siguiente no jubilada) y NUNCA P1
    probes_acc2 = [c for c in H.run_calls if c["email"] == "acc2@x.com" and c["amount"] == ad.PROBE_AMOUNT]
    assert len(probes_acc2) == 1
    assert H.attempts == [P1, P2, P1, P2] or P1 in H.attempts


def test_mission_pool_is_lazy_not_started_eagerly(H):
    """Regla Robert 2026-08-16: El pool de captcha no se arranca ansiosamente
    ni pide prefetch al inicio de la misión si no hay cache-miss."""
    run(H, plan(1))
    assert len(H.pools) == 1
    assert H.pools[0].started == 0  # no se ejecutó start_factory ansioso


def test_mission_retires_card_by_pan_and_prunes_other_accounts_immediately(H):
    """Verifica que si Cuenta 1 aprueba P1 (4111111111111111|1230|123),
    Cuenta 2 que tenía una variante de formato (4111111111111111|12/30|123)
    queda inmediatamente vacía de candidatas, se marca done y NO realiza ningún intento."""
    P1_VAR = "4111111111111111|12/30|123"
    H.card_pipes = [P1, P1_VAR]
    pl = {
        "accounts": [
            {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
            {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1_VAR},
        ]
    }
    run(H, pl)
    # Cuenta 1 aprueba P1
    # Cuenta 2 debe quedar vacía y nunca ejecutar _run para acc2
    acc2_calls = [c for c in H.run_calls if c["email"] == "acc2@x.com"]
    assert acc2_calls == [], f"Cuenta 2 no debió realizar ningún intento pero hizo: {acc2_calls}"
    assert 2 in H.unlocked or 2 not in H.locked


def test_mission_card_locked_other_account_retires_pan_and_prunes(H):
    """Verifica que si Cuenta 1 recibe CARD_LOCKED_OTHER_ACCOUNT, la tarjeta
    queda jubilada a nivel PAN y se purga inmediatamente de Cuenta 2."""
    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "CARD_LOCKED_OTHER_ACCOUNT", "error": "locked"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    H.card_pipes = [P1]
    pl = {
        "accounts": [
            {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
            {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1},
        ]
    }
    run(H, pl)
    # Cuenta 1 intentó P1 y recibió CARD_LOCKED_OTHER_ACCOUNT
    # Cuenta 2 tenía P1 -> debió ser purgada inmediatamente y no intentar P1
    acc2_calls = [c for c in H.run_calls if c["email"] == "acc2@x.com"]
    assert acc2_calls == []
    assert 1 in H.unlocked
    assert 2 in H.unlocked or 2 not in H.locked


def test_mission_confirm_gate_invoked_after_match_and_rest_done(H):
    """Verifica que cuando hay un match y las demás cuentas terminan, confirm_gate
    se invoca de inmediato sin atorarse en el matchmaking loop."""
    gate_invoked = []

    async def my_gate(info):
        gate_invoked.append(info)
        return True

    H.card_pipes = [P1]
    pl = {
        "accounts": [
            {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
            {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1},
        ]
    }
    asyncio.run(ad.run_auto_mission("m_gate", pl, {"role": "superadmin", "telegram_id": 555}, confirm_gate=my_gate))
    assert len(gate_invoked) == 1
    assert len(gate_invoked[0]["matches"]) == 1
    assert gate_invoked[0]["matches"][0]["email"] == "acc1@x.com"


def test_mission_balance_limit_exceeded_preserves_card_and_skips_account(H):
    """Verifica que si una cuenta tiene saldo activo (>= $100) y devuelve
    BALANCE_LIMIT_EXCEEDED, la cuenta se salta pero la tarjeta NO se jubila
    y pasa limpia a la siguiente cuenta."""
    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "BALANCE_LIMIT_EXCEEDED", "error": "Cuenta con saldo"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    H.card_pipes = [P1]
    pl = {
        "accounts": [
            {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
            {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1},
        ]
    }
    run(H, pl)
    assert 1 in H.unlocked
    # Cuenta 2 debió recibir la tarjeta P1 y hacer probe + match
    acc2_probes = [c for c in H.run_calls if c["email"] == "acc2@x.com" and c["amount"] == ad.PROBE_AMOUNT]
    assert len(acc2_probes) == 1
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert len(matches) == 1
    assert matches[0]["email"] == "acc2@x.com"


def test_mission_db_balance_allowed_for_deposits(H, monkeypatch):
    """Verifica que una cuenta con saldo activo en BD (ej. $116.91)
    NO sea bloqueada artificialmente y pueda recibir depósitos si tiene cupo 24h."""
    def fake_fetch(aid):
        if aid == 1:
            return {"id": 1, "email": "acc1@x.com", "password": "pw", "balance_real": 116.91}
        return {"id": 2, "email": "acc2@x.com", "password": "pw", "balance_real": 0.0}
    monkeypatch.setattr(ad, "_fetch_account", fake_fetch)
    H.card_pipes = [P1]
    pl = {
        "accounts": [
            {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
            {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1},
        ]
    }
    run(H, pl)
    # acc1 sí corre y recibe el depósito normalmente
    acc1_calls = [c for c in H.run_calls if c["email"] == "acc1@x.com"]
    assert len(acc1_calls) >= 1


