# tests/test_bet_retry_characterization.py
"""Red de caracterización (golden-master) del orquestador `run_auto_mission`.

FASE 0 del refactor a nodos (`docs/BET_POLICY.md`). Estos tests fijan la
**secuencia exacta** de efectos observables del `run_auto_mission` ACTUAL por
cada rama de `result_code`: orden de intentos, orden de sleeps, transiciones de
`status`, orden de unlock, cuentas marcadas dead.

`tests/test_auto_mission.py` ya cubre las ramas, pero con asserts de *pertenencia*
(`X in sleeps`). El refactor de FASE 1 podría reordenar efectos y seguir pasando.
Estos tests exigen la secuencia — deben pasar SIN EDITARSE tras el refactor.
Si un test de aquí se rompe con el refactor, la conducta cambió: hay que
entender por qué antes de tocar el assert.
"""
import asyncio
import json

import pytest

import auto_deposit as ad
import deposits as dep

P1 = "4111111111111111|1230|123"
P2 = "4222222222222222|1129|456"
P3 = "4333333333333333|1029|789"


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
    """Mismo patrón que tests/test_auto_mission.py::H — seams mockeados, sleeps
    instantáneos, todo capturado en orden."""
    h = type("H", (), {})()
    h.updates, h.unlocked, h.locked, h.attempts = [], [], [], []
    h.cooldowns, h.sleeps, h.pools, h.dead = [], [], [], []
    h.run_calls = []
    h.status = "matching"
    h.target_count = 1
    h.card_pipes = [P1]
    h.script = lambda email, amount, kw: {
        "success": True, "result_code": "BANK_APPROVED",
        "jwt": "J", "used_proxy": "P", "duration_ms": 5,
    }

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
    monkeypatch.setattr(ad, "_pull_fresh_live_account", lambda *a, **k: None)
    monkeypatch.setattr(ad, "_has_card_deposit_24h", lambda email: False)

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

    # FASE 2 usa random.uniform(45,60) como piso anti-fuga antes de la 1a rep.
    # Lo fijamos para que la secuencia de sleeps sea determinista.
    monkeypatch.setattr(ad.random, "uniform", lambda a, b: 50.0)
    return h


def plan(*ids):
    return {"accounts": [{"id": i, "email": f"acc{i}@x.com", "grade": "A",
                          "card_pipe": P1} for i in ids]}


def run(H, pl, mid="m1", **kw):
    asyncio.run(ad.run_auto_mission(mid, pl, {"role": "superadmin", "telegram_id": 555}, **kw))


def statuses(H):
    return [u["status"] for u in H.updates if "status" in u]


def probe_emails(H):
    return [c["email"] for c in H.run_calls if c["amount"] == ad.PROBE_AMOUNT]


def sched_calls(H):
    return [c for c in H.run_calls if c["amount"] == 150]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Happy path — 1 cuenta, 1 tarjeta, probe aprueba
# ─────────────────────────────────────────────────────────────────────────────
def test_char_happy_path_single_account(H):
    H.target_count = 1
    run(H, plan(1))

    assert probe_emails(H) == ["acc1@x.com"]
    assert sched_calls(H) == [{"email": "acc1@x.com", "amount": 150,
                               "session_jwt": "J", "session_proxy": "P",
                               "persist_login_data": False}]
    assert statuses(H) == ["matching", "scheduling", "completed"]
    # único sleep: el piso anti-fuga de FASE 2 (random.uniform(45,60), fijado a 50)
    assert H.sleeps == pytest.approx([50.0], abs=1.0)
    assert H.locked == [1]
    assert H.unlocked == [1]       # cierre libera todos los locks (finally)
    final = H.updates[-1]
    assert final["total_approved"] == 2 and final["total_deposited"] == 10 + 150


# ─────────────────────────────────────────────────────────────────────────────
# 2. 3-strikes de tarjeta por BANK_REJECTED en 3 cuentas distintas
# ─────────────────────────────────────────────────────────────────────────────
def test_char_three_strikes_bank_rejected_exact_sequence(H):
    H.card_pipes = [P1]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "BANK_REJECTED", "error": "Fondos insuficientes"}
    run(H, plan(1, 2, 3, 4))

    assert probe_emails(H) == ["acc1@x.com", "acc2@x.com", "acc3@x.com"]
    assert "acc4@x.com" not in probe_emails(H)
    # doble unlock por cuenta: la rama de decline desbloquea pero NUNCA limpia
    # target["locked"], así que el purge de _retire_card (al 3er strike) vuelve a
    # desbloquear las 3. Idempotente en prod (UPDATE ... WHERE id=?). Si el
    # refactor lo deja en [1,2,3] limpio, este assert debe revisarse a conciencia.
    assert H.unlocked == [1, 2, 1, 2, 3, 3]
    assert sorted(set(H.unlocked)) == [1, 2, 3]
    # 5s de gap entre cuentas distintas tras cada decline; jamás el cooldown de misma cuenta
    assert H.sleeps == [ad.MM_CROSS_ACCOUNT_GAP, ad.MM_CROSS_ACCOUNT_GAP]
    assert dep.MM_COOLDOWN not in H.sleeps
    assert statuses(H)[-1] == "failed"
    assert H.updates[-1]["phase_detail"] == "sin matches"


# ─────────────────────────────────────────────────────────────────────────────
# 3. 3DS certifica hasta 3 cuentas A+ y preserva la tarjeta hasta el 3er intento
# ─────────────────────────────────────────────────────────────────────────────
def test_char_threeds_certifies_three_accounts_exact_sequence(H):
    H.card_pipes = [P1]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "3DS_REQUIRED", "error": "3ds challenge"}
    run(H, plan(1, 2, 3, 4))

    assert probe_emails(H) == ["acc1@x.com", "acc2@x.com", "acc3@x.com"]
    assert H.unlocked == [1, 2, 1, 2, 3, 3]     # mismo doble-unlock que el 3-strikes de decline
    assert sorted(set(H.unlocked)) == [1, 2, 3]
    assert statuses(H)[-1] == "failed"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Anti-taladro: 2 declines en la misma cuenta con 3 tarjetas → reposo
# ─────────────────────────────────────────────────────────────────────────────
def test_char_account_anti_drill_caps_at_two_declines(H):
    H.card_pipes = [P1, P2, P3]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "BANK_REJECTED", "error": "x"}
    run(H, plan(1))

    probes_acc1 = [c for c in H.run_calls
                   if c["amount"] == ad.PROBE_AMOUNT and c["email"] == "acc1@x.com"]
    assert len(probes_acc1) == ad.MM_MAX_ACCOUNT_DECLINES_PER_RUN
    # entre las 2 tarjetas de la MISMA cuenta: cooldown de misma cuenta, no gap de 5s
    assert dep.MM_COOLDOWN in H.sleeps
    assert 1 in H.unlocked


# ─────────────────────────────────────────────────────────────────────────────
# 5. RATE_LIMITED → circuit breaker ABORTA la misión
#
# Conducta correcta (fix 2026-09-09): al 2º 429 consecutivo el breaker dispara
# (`circuit_breaker_consecutive_429 = 2`). `_apply_action` setea `cancelled = True`
# y hace broadcast "aborted"; el outer loop de FASE 1 (`while not _cancelled()
# and not cancelled`) sale de inmediato. acc3 y acc4 NUNCA se tocan — ése es el
# punto del breaker: no quemar más captchas bajo rate-limit.
# ─────────────────────────────────────────────────────────────────────────────
def test_char_rate_limit_circuit_breaker_aborts_mission(H):
    H.card_pipes = [P1]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "RATE_LIMITED", "error": "429 rate limit"}
    run(H, plan(1, 2, 3, 4))

    # el breaker dispara al 2º 429 → la misión aborta sin tocar acc3/acc4
    assert H.dead == ["acc1@x.com", "acc2@x.com"]
    assert probe_emails(H) == ["acc1@x.com", "acc2@x.com"]
    assert 25 not in H.sleeps
    assert statuses(H)[-1] == "cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# 6. DEAD (login 429 permanente) → 1 intento, sin backoff, siguiente cuenta
# ─────────────────────────────────────────────────────────────────────────────
def test_char_dead_account_single_attempt_no_backoff(H):
    H.card_pipes = [P1, P2, P3]

    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "DEAD",
                    "error": "RATE_LIMITED_PERMANENT (BAN)", "account_dead": True}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1, 2))

    acc1_calls = [c for c in H.run_calls if c["email"] == "acc1@x.com"]
    assert len(acc1_calls) == 1
    assert 25 not in H.sleeps
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert [m["account_id"] for m in matches] == [2]
    assert 1 in H.unlocked


# ─────────────────────────────────────────────────────────────────────────────
# 7. Transitorio → 4 reintentos con backoff de 25s, luego abandona el par
# ─────────────────────────────────────────────────────────────────────────────
def test_char_transient_four_retries_then_gives_up(H):
    H.card_pipes = [P1]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "BEGIN_ERROR", "error": "gateway 502"}
    run(H, plan(1))

    acc1_probes = [c for c in H.run_calls
                   if c["email"] == "acc1@x.com" and c["amount"] == ad.PROBE_AMOUNT]
    assert len(acc1_probes) == ad.MATCH_TRANSIENT_RETRIES + 1  # 1 inicial + 4 retries
    assert H.sleeps.count(25) == ad.MATCH_TRANSIENT_RETRIES
    assert statuses(H)[-1] == "failed"


# ─────────────────────────────────────────────────────────────────────────────
# 8. CARD_LOCKED_OTHER_ACCOUNT → jubila en el 1er intento, gap 5s (no 25s)
# ─────────────────────────────────────────────────────────────────────────────
def test_char_card_locked_other_account_retires_immediately(H):
    H.card_pipes = [P1]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "CARD_LOCKED_OTHER_ACCOUNT",
        "error": "Tarjeta ya aprobada en otro@x.com"}
    run(H, plan(1))

    assert len(probe_emails(H)) == 1
    assert 25 not in H.sleeps
    assert statuses(H)[-1] == "failed"


# ─────────────────────────────────────────────────────────────────────────────
# 9. BALANCE_LIMIT_EXCEEDED → salta cuenta, preserva tarjeta a la siguiente
# ─────────────────────────────────────────────────────────────────────────────
def test_char_balance_limit_exceeded_preserves_card(H):
    def script(email, amount, kw):
        if email == "acc1@x.com":
            return {"success": False, "result_code": "BALANCE_LIMIT_EXCEEDED", "error": "saldo"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    H.card_pipes = [P1]
    run(H, {"accounts": [
        {"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1},
        {"id": 2, "email": "acc2@x.com", "grade": "A", "card_pipe": P1},
    ]})

    assert 1 in H.unlocked
    matches = json.loads(next(u["matches"] for u in H.updates if "matches" in u))
    assert [m["email"] for m in matches] == ["acc2@x.com"]


# ─────────────────────────────────────────────────────────────────────────────
# 10. FASE 2 scheduled — 9 reps, sleep(60) entre cada una, serie de totales
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_nine_reps_exact_sleep_and_totals(H):
    H.target_count = 9
    run(H, plan(1))

    assert len(sched_calls(H)) == 9
    # piso anti-fuga (~50) + 8 gaps de 60 entre las 9 reps
    assert H.sleeps[0] == pytest.approx(50.0, abs=1.0)
    assert H.sleeps[1:] == [60] * 8
    approved_series = [u["total_approved"] for u in H.updates if "total_approved" in u]
    assert approved_series == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10]
    final = H.updates[-1]
    assert final["status"] == "completed"
    assert final["total_deposited"] == 10 + 9 * 150


# ─────────────────────────────────────────────────────────────────────────────
# 11. FASE 2 — decline aborta esa cuenta sin reintentar
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_decline_aborts_account(H):
    H.target_count = 9
    n = {"i": 0}

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
        n["i"] += 1
        if n["i"] == 2:
            return {"success": False, "result_code": "BANK_REJECTED", "error": "rechazada"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))

    assert len(sched_calls(H)) == 2
    assert H.sleeps[0] == pytest.approx(50.0, abs=1.0)  # piso anti-fuga
    assert H.sleeps[1:] == [60]              # 1 gap tras la 1a rep exitosa, break en la 2a
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 12. Cancel cooperativo tras el match → no arranca FASE 2, cierra cancelled
# ─────────────────────────────────────────────────────────────────────────────
def test_char_cancel_after_match_skips_phase_two(H):
    H.target_count = 9

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            H.status = "cancelled"
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
    H.script = script
    run(H, plan(1))

    assert sched_calls(H) == []
    assert H.updates[-1]["status"] == "cancelled"
    assert 1 in H.unlocked


# ═════════════════════════════════════════════════════════════════════════════
# FASE 2 (scheduled) — caracterización extendida (Fase 1b del refactor).
# Ramas de `auto_deposit.py` L2322-2448: ok→progress / terminal-para-esta-cuenta
# (rate/dead/3DS/decline/ambiguo/CARD_LOCKED/PENDING_NOT_APPLIED) / transitorio
# (retries x4, backoff 25s, reset de session_jwt en "sesión rechazada"/"401"/
# "redirectlogin"). Estos tests deben pasar SIN EDITARSE tras cablear
# `decide_next_action(phase="SCHEDULED")` + `_apply_sched_action`.
# ═════════════════════════════════════════════════════════════════════════════
def _sched_script(fail_on_rep, result):
    """probe siempre aprueba; la rep número `fail_on_rep` devuelve `result`."""
    n = {"i": 0}

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
        n["i"] += 1
        if n["i"] == fail_on_rep:
            return dict(result)
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}

    return script


# ─────────────────────────────────────────────────────────────────────────────
# 13. FASE 2 — RATE_LIMITED en una rep: _mark_rate_limited_dead + failed++, break
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_rate_limited_marks_dead_and_breaks(H):
    H.target_count = 9
    H.script = _sched_script(2, {"success": False, "result_code": "RATE_LIMITED",
                                 "error": "429 rate limit"})
    run(H, plan(1))

    assert len(sched_calls(H)) == 2                  # paró en la rep declinada
    assert H.dead == ["acc1@x.com"]                  # _mark_rate_limited_dead
    assert 25 not in H.sleeps                        # terminal, no backoff transitorio
    assert H.sleeps[1:] == [60]                      # 1 gap tras la 1a rep OK
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 14. FASE 2 — DEAD / account_dead: cuenta terminal, sin _mark_rate_limited_dead
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_dead_code_breaks_without_rate_mark(H):
    H.target_count = 9
    H.script = _sched_script(2, {"success": False, "result_code": "DEAD",
                                 "error": "cuenta baneada", "account_dead": True})
    run(H, plan(1))

    assert len(sched_calls(H)) == 2
    assert H.dead == []                              # NO pasa por _mark_rate_limited_dead
    assert 25 not in H.sleeps
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 15. FASE 2 — 3DS_REQUIRED aborta la cuenta (sin certificar A+ ni rotar tarjeta)
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_threeds_aborts_account(H):
    H.target_count = 9
    H.script = _sched_script(2, {"success": False, "result_code": "3DS_REQUIRED",
                                 "error": "3ds challenge"})
    run(H, plan(1))

    assert len(sched_calls(H)) == 2
    assert H.dead == []
    assert 25 not in H.sleeps
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 16. FASE 2 — PENDING_NOT_APPLIED y cargo ambiguo son terminales
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("code,err", [
    ("PENDING_NOT_APPLIED", "no aplicado"),
    ("SUBMIT_ERROR", "submit lanzó excepción tras enviar"),
    ("CARD_LOCKED_OTHER_ACCOUNT", "Tarjeta ya aprobada en otro@x.com"),
])
def test_char_scheduled_ambiguous_and_pending_are_terminal(H, code, err):
    H.target_count = 9
    H.script = _sched_script(2, {"success": False, "result_code": code, "error": err})
    run(H, plan(1))

    assert len(sched_calls(H)) == 2
    assert 25 not in H.sleeps
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 17. FASE 2 — transitorio: 4 reintentos con backoff de 25s, luego abandona cuenta
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_transient_four_retries_then_break(H):
    H.target_count = 9
    seen = {"probe": False}

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
        return {"success": False, "result_code": "BEGIN_ERROR", "error": "gateway 502"}
    H.script = script
    run(H, plan(1))

    assert len(sched_calls(H)) == dep.SCHED_MAX_TRANSIENT_RETRIES + 1  # 1 inicial + 4 retries
    assert H.sleeps.count(dep.SCHED_RETRY_BACKOFF_SEC) == dep.SCHED_MAX_TRANSIENT_RETRIES
    assert H.updates[-1]["status"] == "completed"
    assert H.updates[-1]["total_failed"] == 1
    aborts = [u["phase_detail"] for u in H.updates if "sin éxito tras" in u.get("phase_detail", "")]
    assert aborts == ["acc1@x.com sin éxito tras 4 reintentos"]


# ─────────────────────────────────────────────────────────────────────────────
# 18. FASE 2 — sesión stale ("401"/"redirectlogin"/"sesión rechazada") con jwt
#     vivo → el siguiente intento arranca con session_jwt=None
# ─────────────────────────────────────────────────────────────────────────────
def test_char_scheduled_session_reset_on_stale_marker(H):
    H.target_count = 9
    reps = {"i": 0}

    def script(email, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}
        reps["i"] += 1
        if reps["i"] == 1:
            return {"success": False, "result_code": "PAYMENT_ERROR",
                    "error": "redirectLogin — sesión rechazada (401)"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J2", "used_proxy": "P2"}
    H.script = script
    run(H, plan(1))

    jwts = [c["session_jwt"] for c in sched_calls(H)]
    assert jwts[0] == "J"        # 1a rep reusa la sesión del match
    assert jwts[1] is None       # tras el marcador stale, se fuerza re-login
    assert H.sleeps.count(dep.SCHED_RETRY_BACKOFF_SEC) == 1  # 1 backoff transitorio
