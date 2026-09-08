# tests/test_bet_retry_policy.py
"""Unit puro de `bet_retry_policy.decide_next_action` — FASE 1 del refactor de `/bet`.

`decide_next_action` es la función determinista que, dado el outcome de un intento
de matchmaking (probe $10) + los contadores de cuenta/tarjeta/misión, decide la
próxima acción SIN efectos secundarios. El shell (`run_auto_mission`) aplica el
`Action` resultante vía `_apply_action`.

Estos tests fijan la semántica de cada rama. El contrato de no-regresión de que
el shell aplica el `Action` igual que el código monolítico de hoy lo dan
`tests/test_bet_retry_characterization.py` + `tests/test_auto_mission.py`.

Orden de ramas que replica (igual que `auto_deposit.py` L1838-2141):
  ok → BALANCE_LIMIT_EXCEEDED → 3DS → familia dead/429 (+ circuit breaker)
  → decline real / cargo ambiguo → CARD_LOCKED_OTHER_ACCOUNT → transitorio
"""
import pytest

import bet_policy
import bet_retry_policy as rp
from bet_retry_policy import ActionKind

CFG = bet_policy.DEFAULT


# ── builders ─────────────────────────────────────────────────────────────────
def _outcome(ok=False, code="", error="", account_dead=False):
    return rp.OutcomeView(ok=ok, code=code, error=error, account_dead=account_dead)


def _account(declines_this_run=0, remaining_candidates=1, is_locked=True, matched=False):
    return rp.AccountRetryState(
        declines_this_run=declines_this_run,
        remaining_candidates=remaining_candidates,
        is_locked=is_locked,
        matched=matched,
    )


def _card(attempts=0, declines=0):
    return rp.CardRetryState(attempts=attempts, declines=declines)


def _mission(consecutive_rate_limits=0, transient_count=0, phase="MATCHMAKING"):
    return rp.MissionRetryState(
        consecutive_rate_limits=consecutive_rate_limits,
        transient_count=transient_count,
        phase=phase,
    )


def decide(outcome, account=None, card=None, mission=None):
    return rp.decide_next_action(
        outcome, account or _account(), card or _card(), mission or _mission(), CFG
    )


# ── 1. ok → ACCEPT ───────────────────────────────────────────────────────────
def test_ok_returns_accept():
    a = decide(_outcome(ok=True, code="BANK_APPROVED"))
    assert a.kind is ActionKind.ACCEPT


def test_ok_retires_card_and_removes_from_others():
    a = decide(_outcome(ok=True, code="BANK_APPROVED"))
    assert a.retire_card is True
    assert a.remove_card_from_others is True


def test_ok_marks_account_rest_and_counts_approved_deposit():
    a = decide(_outcome(ok=True, code="BANK_APPROVED"))
    assert a.rest_account is True
    assert a.d_approved == 1
    assert a.d_failed == 0
    assert a.d_deposited == CFG.probe_amount


def test_ok_resets_consecutive_rate_limits():
    a = decide(
        _outcome(ok=True, code="BANK_APPROVED"),
        mission=_mission(consecutive_rate_limits=1),
    )
    assert a.reset_consecutive_rate_limits is True
    assert a.d_consecutive_rate_limits == 0


# ── 2. BALANCE_LIMIT_EXCEEDED → SKIP_ACCOUNT (tarjeta preservada) ─────────────
def test_balance_limit_skips_account():
    a = decide(_outcome(code="BALANCE_LIMIT_EXCEEDED"))
    assert a.kind is ActionKind.SKIP_ACCOUNT
    assert a.rest_account is True
    assert a.clear_account_candidates is True


def test_balance_limit_preserves_card_no_strikes():
    a = decide(_outcome(code="BALANCE_LIMIT_EXCEEDED"), card=_card(attempts=1, declines=1))
    assert a.retire_card is False
    assert a.requeue_card is True
    assert a.d_card_declines == 0
    assert a.d_card_attempts == 0
    assert a.d_account_declines == 0
    assert a.d_failed == 0


def test_balance_limit_does_not_touch_rate_limit_counter():
    a = decide(
        _outcome(code="BALANCE_LIMIT_EXCEEDED"),
        mission=_mission(consecutive_rate_limits=1),
    )
    assert a.reset_consecutive_rate_limits is False
    assert a.d_consecutive_rate_limits == 0


# ── 3. 3DS_REQUIRED → THREEDS_CERT ───────────────────────────────────────────
def test_threeds_first_attempt_bumps_grade_and_requeues():
    a = decide(_outcome(code="3DS_REQUIRED"), card=_card(attempts=0))
    assert a.kind is ActionKind.THREEDS_CERT
    assert a.bump_grade_aplus is True
    assert a.mark_account_tried_for_card is True
    assert a.retire_card is False
    assert a.requeue_card is True
    assert a.d_card_attempts == 1


def test_threeds_never_strikes_account_declines():
    a = decide(_outcome(code="3DS_REQUIRED"), account=_account(declines_this_run=1))
    assert a.d_account_declines == 0
    assert a.d_card_declines == 0
    assert a.d_failed == 0


def test_threeds_retires_card_on_third_attempt():
    a = decide(_outcome(code="3DS_REQUIRED"), card=_card(attempts=2))
    assert a.retire_card is True
    assert a.requeue_card is False
    assert a.bump_grade_aplus is True
    assert a.d_card_attempts == 1


def test_threeds_rests_account_when_no_candidates_left():
    a = decide(_outcome(code="3DS_REQUIRED"), account=_account(remaining_candidates=0))
    assert a.rest_account is True


def test_threeds_keeps_account_when_candidates_remain():
    a = decide(_outcome(code="3DS_REQUIRED"), account=_account(remaining_candidates=2))
    assert a.rest_account is False
    assert a.wait_s == CFG.mm_cooldown_s


def test_threeds_does_not_touch_rate_limit_counter():
    a = decide(
        _outcome(code="3DS_REQUIRED"), mission=_mission(consecutive_rate_limits=1)
    )
    assert a.reset_consecutive_rate_limits is False
    assert a.d_consecutive_rate_limits == 0


# ── 4. familia dead / 429 → ACCOUNT_DEAD ─────────────────────────────────────
def test_rate_limited_isolates_account_first_hit():
    a = decide(_outcome(code="RATE_LIMITED", error="429 rate limit"))
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.dead_kind == "rate_limited"
    assert a.mark_rate_limited_dead is True
    assert a.d_consecutive_rate_limits == 1
    assert a.circuit_breaker_hit is False
    assert a.abort_mission is False
    assert a.rest_account is True
    assert a.clear_account_candidates is True
    assert a.d_failed == 1
    assert a.d_account_declines == 1


def test_rate_limited_second_consecutive_trips_circuit_breaker():
    a = decide(
        _outcome(code="RATE_LIMITED", error="429"),
        mission=_mission(consecutive_rate_limits=1),
    )
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.circuit_breaker_hit is True
    assert a.abort_mission is True
    assert a.mark_rate_limited_dead is True
    assert a.d_consecutive_rate_limits == 1


def test_circuit_breaker_does_not_strike_or_rest_account():
    # el código actual hace `break` ANTES de failed++/declines++/done/unlock
    a = decide(
        _outcome(code="RATE_LIMITED", error="429"),
        mission=_mission(consecutive_rate_limits=1),
    )
    assert a.d_failed == 0
    assert a.d_account_declines == 0
    assert a.rest_account is False
    assert a.clear_account_candidates is False


def test_error_string_429_without_code_is_rate_limited():
    a = decide(_outcome(code="BEGIN_ERROR", error="gateway said 429 too many requests"))
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.dead_kind == "rate_limited"
    assert a.mark_rate_limited_dead is True


def test_kyc_pending_marks_account_dead_and_resets_rate_limits():
    a = decide(
        _outcome(code="KYC_PENDING"), mission=_mission(consecutive_rate_limits=1)
    )
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.dead_kind == "kyc"
    assert a.reset_consecutive_rate_limits is True
    assert a.rest_account is True
    assert a.clear_account_candidates is True
    assert a.d_failed == 1
    assert a.d_account_declines == 1


def test_dead_code_marks_account_dead_with_reason():
    a = decide(_outcome(code="DEAD", error="cuenta baneada permanentemente"))
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.dead_kind == "dead"
    assert a.dead_reason == "cuenta baneada permanentemente"
    assert a.reset_consecutive_rate_limits is True


def test_dead_code_with_rate_limit_in_error_string_routes_to_rate_limited():
    # comportamiento actual: cualquier "RATE_LIMITED"/"429" en el error gana la rama 429,
    # sin importar el result_code (auto_deposit.py L2015).
    a = decide(_outcome(code="DEAD", error="RATE_LIMITED_PERMANENT (BAN)", account_dead=True))
    assert a.dead_kind == "rate_limited"
    assert a.mark_rate_limited_dead is True


def test_dead_reason_falls_back_to_code_when_no_error():
    a = decide(_outcome(code="AUTOEXCLUSION"))
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.dead_kind == "dead"
    assert a.dead_reason == "AUTOEXCLUSION"


def test_account_dead_flag_routes_to_account_dead():
    a = decide(_outcome(code="SOMETHING_ODD", account_dead=True))
    assert a.kind is ActionKind.ACCOUNT_DEAD
    assert a.dead_kind == "dead"


def test_dead_family_never_retires_card():
    a = decide(_outcome(code="DEAD", error="ban"), card=_card(declines=2, attempts=2))
    assert a.retire_card is False


# ── 5. decline real / cargo ambiguo → CARD_DECLINE ───────────────────────────
def test_bank_rejected_first_strike_requeues_card_and_cools_account():
    a = decide(_outcome(code="BANK_REJECTED", error="Fondos insuficientes"))
    assert a.kind is ActionKind.CARD_DECLINE
    assert a.retire_card is False
    assert a.requeue_card is True
    assert a.mark_account_tried_for_card is True
    assert a.rest_account is False
    assert a.wait_s == CFG.mm_cooldown_s
    assert a.d_card_declines == 1
    assert a.d_card_attempts == 1
    assert a.d_account_declines == 1
    assert a.d_failed == 1


def test_bank_rejected_third_decline_retires_card():
    a = decide(_outcome(code="BANK_REJECTED"), card=_card(declines=2, attempts=2))
    assert a.retire_card is True
    assert a.requeue_card is False


def test_card_retired_when_attempts_hit_cap_via_mixed_3ds_and_decline():
    # 2 intentos previos (1 decline + 1 3DS) → attempts=2, declines=1; este decline lleva a 3
    a = decide(_outcome(code="BANK_REJECTED"), card=_card(declines=1, attempts=2))
    assert a.retire_card is True


def test_account_rests_on_second_decline_this_run():
    a = decide(_outcome(code="BANK_REJECTED"), account=_account(declines_this_run=1))
    assert a.rest_account is True
    assert a.wait_s == 0.0


def test_account_rests_when_no_candidates_left_even_on_first_decline():
    a = decide(
        _outcome(code="BANK_REJECTED"), account=_account(remaining_candidates=0)
    )
    assert a.rest_account is True


def test_ambiguous_submit_error_takes_decline_path_no_bank_strike_semantics():
    a = decide(_outcome(code="SUBMIT_ERROR", error="submit lanzó excepción"))
    assert a.kind is ActionKind.CARD_DECLINE
    assert a.d_card_declines == 1
    assert a.d_card_attempts == 1
    assert a.d_account_declines == 1


def test_ambiguous_unknown_txn_status_takes_decline_path():
    a = decide(_outcome(code="UNKNOWN_TXN_STATUS_7"))
    assert a.kind is ActionKind.CARD_DECLINE


def test_decline_does_not_reset_rate_limit_counter():
    a = decide(
        _outcome(code="BANK_REJECTED"), mission=_mission(consecutive_rate_limits=1)
    )
    assert a.reset_consecutive_rate_limits is False
    assert a.d_consecutive_rate_limits == 0


# ── 6. CARD_LOCKED_OTHER_ACCOUNT → RETIRE_CARD_LOCKED ────────────────────────
def test_card_locked_retires_immediately_short_gap_no_account_strike():
    a = decide(_outcome(code="CARD_LOCKED_OTHER_ACCOUNT", error="ya aprobada en otro@x.com"))
    assert a.kind is ActionKind.RETIRE_CARD_LOCKED
    assert a.retire_card is True
    assert a.remove_card_from_others is True
    assert a.rest_account is False
    assert a.d_account_declines == 0
    assert a.d_card_declines == 0
    assert a.wait_s == CFG.cross_account_gap_s
    assert a.d_failed == 1


def test_card_locked_detected_via_error_string():
    a = decide(_outcome(code="PAYMENT_ERROR", error="La tarjeta pertenece a otra cuenta"))
    assert a.kind is ActionKind.RETIRE_CARD_LOCKED


def test_card_locked_detected_via_cardalreadyassociated():
    a = decide(_outcome(code="PAYMENT_ERROR", error="CardAlreadyAssociated"))
    assert a.kind is ActionKind.RETIRE_CARD_LOCKED


# ── 7. transitorio → RETRY_SAME / GIVE_UP_PAIR ───────────────────────────────
def test_transient_first_hit_retries_same_pair_with_backoff():
    a = decide(_outcome(code="BEGIN_ERROR", error="gateway 502"), mission=_mission(transient_count=0))
    assert a.kind is ActionKind.RETRY_SAME
    assert a.wait_s == CFG.transient_backoff_s
    assert a.d_transient == 1
    assert a.d_failed == 0


def test_transient_retries_up_to_the_cap():
    a = decide(
        _outcome(code="BEGIN_ERROR"),
        mission=_mission(transient_count=CFG.match_transient_retries - 1),
    )
    assert a.kind is ActionKind.RETRY_SAME


def test_transient_gives_up_after_cap_exhausted():
    a = decide(
        _outcome(code="BEGIN_ERROR"),
        mission=_mission(transient_count=CFG.match_transient_retries),
    )
    assert a.kind is ActionKind.GIVE_UP_PAIR
    assert a.d_failed == 1
    assert a.wait_s == CFG.mm_cooldown_s
    assert a.rest_account is False
    assert a.retire_card is False
    assert a.d_account_declines == 0
    assert a.d_card_declines == 0


def test_timeout_is_transient():
    a = decide(_outcome(code="TIMEOUT"))
    assert a.kind is ActionKind.RETRY_SAME


def test_login_failed_is_transient_not_dead():
    a = decide(_outcome(code="LOGIN_FAILED", error="captcha pool empty"))
    assert a.kind is ActionKind.RETRY_SAME


def test_unknown_code_is_transient():
    a = decide(_outcome(code="SOME_NEW_CODE"))
    assert a.kind is ActionKind.RETRY_SAME


# ── inmutabilidad: la policy nunca muta sus inputs ──────────────────────────
def test_decide_does_not_mutate_inputs():
    o, acc, card, mis = (
        _outcome(code="BANK_REJECTED"),
        _account(declines_this_run=1),
        _card(attempts=1, declines=1),
        _mission(consecutive_rate_limits=1, transient_count=2),
    )
    decide(o, acc, card, mis)
    assert acc.declines_this_run == 1
    assert card.attempts == 1 and card.declines == 1
    assert mis.consecutive_rate_limits == 1 and mis.transient_count == 2


def test_action_is_frozen():
    a = decide(_outcome(ok=True, code="BANK_APPROVED"))
    with pytest.raises(Exception):
        a.kind = ActionKind.CARD_DECLINE


# ═════════════════════════════════════════════════════════════════════════════
# FASE 2 (scheduled) — `decide_next_action` con `mission.phase == "SCHEDULED"`.
# Sin rotación de tarjeta/cuenta: PROGRESS / ABORT_ACCOUNT / RETRY_SAME.
# Espejo de `auto_deposit.py` L2322-2448.
# ═════════════════════════════════════════════════════════════════════════════
def _sched(reps_completed=0, reps_target=9, transient_count=0, session_jwt_present=True):
    return rp.MissionRetryState(
        phase="SCHEDULED",
        reps_completed=reps_completed,
        reps_target=reps_target,
        transient_count=transient_count,
        session_jwt_present=session_jwt_present,
    )


def sdecide(outcome, mission=None):
    return rp.decide_next_action(
        outcome, _account(), _card(), mission or _sched(), CFG
    )


# ── ok → PROGRESS ───────────────────────────────────────────────────────────
def test_sched_ok_progresses_and_gaps_60s_when_reps_remain():
    a = sdecide(_outcome(ok=True, code="BANK_APPROVED"), _sched(reps_completed=0, reps_target=9))
    assert a.kind is ActionKind.PROGRESS
    assert a.d_approved == 1
    assert a.d_failed == 0
    assert a.wait_s == CFG.sched_rep_gap_s == 60


def test_sched_ok_last_rep_has_no_gap():
    a = sdecide(_outcome(ok=True, code="BANK_APPROVED"), _sched(reps_completed=8, reps_target=9))
    assert a.kind is ActionKind.PROGRESS
    assert a.wait_s == 0.0


# ── terminal para la cuenta → ABORT_ACCOUNT (broadcast) ─────────────────────
def test_sched_rate_limited_aborts_account_and_marks_dead():
    a = sdecide(_outcome(code="RATE_LIMITED", error="429 rate limit"))
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.sched_abort_terminal is True
    assert a.dead_kind == "rate_limited"
    assert a.mark_rate_limited_dead is True
    assert a.d_failed == 1


def test_sched_error_string_429_aborts_account_and_marks_dead():
    a = sdecide(_outcome(code="PAYMENT_ERROR", error="gateway said 429"))
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.dead_kind == "rate_limited"
    assert a.mark_rate_limited_dead is True


def test_sched_dead_family_aborts_account_without_rate_mark():
    a = sdecide(_outcome(code="DEAD", error="cuenta baneada", account_dead=True))
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.sched_abort_terminal is True
    assert a.dead_kind == "dead"
    assert a.mark_rate_limited_dead is False
    assert a.dead_reason == "cuenta baneada"
    assert a.d_failed == 1


def test_sched_kyc_pending_aborts_as_dead_family():
    a = sdecide(_outcome(code="KYC_PENDING"))
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.dead_kind == "dead"          # KYC_PENDING ∈ MM_DEAD_RC → rama UPDATE DEAD


@pytest.mark.parametrize("code,err", [
    ("3DS_REQUIRED", "3ds challenge"),
    ("BANK_REJECTED", "Fondos insuficientes"),
    ("PENDING_NOT_APPLIED", "no aplicado"),
    ("SUBMIT_ERROR", "excepción tras enviar"),
    ("UNKNOWN_TXN_STATUS_7", ""),
    ("CARD_LOCKED_OTHER_ACCOUNT", "ya aprobada en otra cuenta"),
])
def test_sched_terminal_codes_abort_without_db_side_writes(code, err):
    a = sdecide(_outcome(code=code, error=err))
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.sched_abort_terminal is True
    assert a.dead_kind == ""             # ni rate-limit ni dead-family → solo failed++
    assert a.mark_rate_limited_dead is False
    assert a.d_failed == 1


# ── transitorio → RETRY_SAME / ABORT_ACCOUNT (sin broadcast) ────────────────
def test_sched_transient_first_hit_retries_with_backoff():
    a = sdecide(_outcome(code="BEGIN_ERROR", error="gateway 502"), _sched(transient_count=0))
    assert a.kind is ActionKind.RETRY_SAME
    assert a.wait_s == CFG.sched_retry_backoff_s == 25
    assert a.d_transient == 1
    assert a.d_failed == 0


def test_sched_transient_retries_up_to_the_cap():
    a = sdecide(
        _outcome(code="TIMEOUT"),
        _sched(transient_count=CFG.sched_max_transient_retries - 1),
    )
    assert a.kind is ActionKind.RETRY_SAME


def test_sched_transient_gives_up_after_cap_aborts_account_no_broadcast():
    a = sdecide(
        _outcome(code="BEGIN_ERROR"),
        _sched(transient_count=CFG.sched_max_transient_retries),
    )
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.sched_abort_terminal is False   # transitorio agotado ≠ clasificación terminal
    assert a.d_failed == 1


def test_sched_login_failed_is_transient_not_terminal():
    a = sdecide(_outcome(code="LOGIN_FAILED", error="captcha pool empty"))
    assert a.kind is ActionKind.RETRY_SAME


# ── reset de sesión stale ──────────────────────────────────────────────────
@pytest.mark.parametrize("err", [
    "redirectLogin", "HTTP 401 Unauthorized", "sesión rechazada por el servidor",
])
def test_sched_session_stale_marker_sets_reset_when_jwt_present(err):
    a = sdecide(_outcome(code="PAYMENT_ERROR", error=err), _sched(session_jwt_present=True))
    assert a.kind is ActionKind.RETRY_SAME
    assert a.reset_session is True


def test_sched_session_stale_marker_ignored_when_no_jwt():
    a = sdecide(_outcome(code="PAYMENT_ERROR", error="401"), _sched(session_jwt_present=False))
    assert a.reset_session is False


def test_sched_session_reset_applies_even_when_giving_up():
    a = sdecide(
        _outcome(code="PAYMENT_ERROR", error="redirectLogin"),
        _sched(transient_count=CFG.sched_max_transient_retries, session_jwt_present=True),
    )
    assert a.kind is ActionKind.ABORT_ACCOUNT
    assert a.reset_session is True


def test_sched_non_stale_transient_has_no_reset():
    a = sdecide(_outcome(code="BEGIN_ERROR", error="gateway 502"))
    assert a.reset_session is False


# ── FASE 1 intacta: sin phase="SCHEDULED" nada cambia ──────────────────────
def test_matchmaking_phase_still_routes_through_fase1_branches():
    a = decide(_outcome(code="BANK_REJECTED", error="Fondos insuficientes"))
    assert a.kind is ActionKind.CARD_DECLINE   # no PROGRESS/ABORT_ACCOUNT


def test_sched_decide_does_not_mutate_inputs():
    o, mis = _outcome(code="BEGIN_ERROR", error="401"), _sched(transient_count=2)
    rp.decide_next_action(o, _account(), _card(), mis, CFG)
    assert mis.transient_count == 2 and mis.reps_completed == 0
