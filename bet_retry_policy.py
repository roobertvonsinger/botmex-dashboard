"""bet_retry_policy — decisión determinista de retry/rotación para `/bet` FASE 1.

FASE 1 del refactor a nodos (`docs/BET_POLICY.md`). `decide_next_action` es una
función **pura**: dado el outcome de un intento de matchmaking (probe $10) + los
contadores de cuenta/tarjeta/misión + la política, devuelve un `Action` que
describe la próxima acción. **No** toca BD, no duerme, no lockea, no logea. El
shell (`run_auto_mission._apply_action`) aplica el `Action` — efectos y su orden
idénticos al código monolítico de hoy (`auto_deposit.py` L1838-2141).

Orden de ramas (réplica exacta del inner loop actual):
  ok → BALANCE_LIMIT_EXCEEDED → 3DS → familia dead/429 (+ circuit breaker)
  → decline real / cargo ambiguo → CARD_LOCKED_OTHER_ACCOUNT → transitorio

Clasificación de `result_code`: se reusa la taxonomía única de `deposits`
(`MM_DEAD_RC`, `MM_THREEDS_RC`, `_mm_is_real_decline`, `_mm_is_ambiguous_charge`)
para que policy y persistencia jamás diverjan.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import deposits as _dep
from bet_policy import BetPolicyConfig


class ActionKind(str, Enum):
    ACCEPT = "ACCEPT"                          # ok — match encontrado
    SKIP_ACCOUNT = "SKIP_ACCOUNT"              # BALANCE_LIMIT_EXCEEDED — cuenta fuera, tarjeta preservada
    THREEDS_CERT = "THREEDS_CERT"              # 3DS — cuenta certificada A+, tarjeta puede seguir
    ACCOUNT_DEAD = "ACCOUNT_DEAD"              # dead / 429 / KYC — cuenta terminal
    CARD_DECLINE = "CARD_DECLINE"              # rechazo real o cargo ambiguo — strike a tarjeta + cuenta
    RETIRE_CARD_LOCKED = "RETIRE_CARD_LOCKED"  # CARD_LOCKED_OTHER_ACCOUNT — jubila tarjeta, gap corto
    RETRY_SAME = "RETRY_SAME"                  # transitorio — reintentar el mismo par tras backoff
    GIVE_UP_PAIR = "GIVE_UP_PAIR"              # transitorio agotado — abandonar el par, cooldown de cuenta


# ── vistas inmutables que el shell construye ANTES de cualquier mutación ──────
@dataclass(frozen=True)
class OutcomeView:
    ok: bool
    code: str
    error: str = ""
    account_dead: bool = False


@dataclass(frozen=True)
class AccountRetryState:
    declines_this_run: int = 0        # target["declines"] ANTES de este outcome
    remaining_candidates: int = 0     # len(target["candidates"]) tras hacer pop del pipe en curso
    is_locked: bool = False
    matched: bool = False


@dataclass(frozen=True)
class CardRetryState:
    attempts: int = 0                 # card_attempts_map[k] ANTES de este outcome
    declines: int = 0                 # card_declines_map[k] ANTES de este outcome


@dataclass(frozen=True)
class MissionRetryState:
    phase: str = "MATCHMAKING"
    consecutive_rate_limits: int = 0  # ANTES de este outcome
    transient_count: int = 0          # el contador `transient` del par ANTES de incrementar


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    reason: str = ""
    wait_s: float = 0.0               # cooldown de cuenta o backoff de reintento (según kind)

    # efectos sobre la tarjeta
    retire_card: bool = False
    requeue_card: bool = False            # best-effort: encolar en otra cuenta / jalar fresca
    remove_card_from_others: bool = False # hard: quitar el pipe de todas las demás candidatas
    mark_account_tried_for_card: bool = False

    # efectos sobre la cuenta
    rest_account: bool = False            # marcar cuenta done (+ unlock según reglas del kind)
    clear_account_candidates: bool = False
    bump_grade_aplus: bool = False

    # familia dead
    dead_kind: str = ""                   # "" | "rate_limited" | "kyc" | "dead"
    dead_reason: str = ""
    mark_rate_limited_dead: bool = False

    # misión
    circuit_breaker_hit: bool = False
    abort_mission: bool = False

    # deltas de contadores que aplica el shell (la policy nunca muta sus inputs)
    d_account_declines: int = 0
    d_card_declines: int = 0
    d_card_attempts: int = 0
    d_consecutive_rate_limits: int = 0
    d_transient: int = 0
    reset_consecutive_rate_limits: bool = False

    # contabilidad de la misión
    d_approved: int = 0
    d_failed: int = 0
    d_deposited: float = 0.0


# ── helpers de clasificación (espejo del inner loop actual) ──────────────────
_DEAD_CODES = frozenset({
    "RATE_LIMITED", "DEAD", "BAN", "RATE_LIMITED_PERMANENT", "KYC_PENDING",
})


def _is_rate_limited(o: OutcomeView) -> bool:
    err = o.error or ""
    return o.code == "RATE_LIMITED" or "RATE_LIMITED" in err or "429" in err


def _is_dead_family(o: OutcomeView) -> bool:
    err = o.error or ""
    return (
        o.code in _DEAD_CODES
        or o.code in _dep.MM_DEAD_RC
        or bool(o.account_dead)
        or "RATE_LIMITED" in err
        or "429" in err
    )


def _is_card_locked(o: OutcomeView) -> bool:
    e = (o.error or "").lower()
    return (
        o.code == "CARD_LOCKED_OTHER_ACCOUNT"
        or "otra cuenta" in e
        or "cardalreadyassociated" in e
    )


def decide_next_action(
    outcome: OutcomeView,
    account: AccountRetryState,
    card: CardRetryState,
    mission: MissionRetryState,
    config: BetPolicyConfig,
) -> Action:
    """Función pura. Réplica del orden de ramas del inner `while True` de FASE 1."""
    o, a, c, m, cfg = outcome, account, card, mission, config

    # ── 1. ok → ACCEPT ──────────────────────────────────────────────────────
    if o.ok:
        return Action(
            kind=ActionKind.ACCEPT,
            reason="match aprobado",
            retire_card=True,
            remove_card_from_others=True,
            rest_account=True,
            reset_consecutive_rate_limits=True,
            d_approved=1,
            d_deposited=cfg.probe_amount,
        )

    # ── 2. BALANCE_LIMIT_EXCEEDED → SKIP_ACCOUNT (tarjeta intacta) ───────────
    if o.code == "BALANCE_LIMIT_EXCEEDED":
        return Action(
            kind=ActionKind.SKIP_ACCOUNT,
            reason="cuenta con saldo activo — saltada sin quemar tarjeta",
            rest_account=True,
            clear_account_candidates=True,
            requeue_card=True,
        )

    # ── 3. 3DS_REQUIRED → THREEDS_CERT ─────────────────────────────────────
    if o.code in _dep.MM_THREEDS_RC:
        retire = (c.attempts + 1) >= cfg.card_max_attempts
        return Action(
            kind=ActionKind.THREEDS_CERT,
            reason=(
                f"3DS — {cfg.card_max_attempts} intentos alcanzados, tarjeta jubilada"
                if retire
                else "3DS — cuenta A+ detectada, tarjeta disponible para otra cuenta"
            ),
            bump_grade_aplus=True,
            mark_account_tried_for_card=True,
            retire_card=retire,
            requeue_card=not retire,
            rest_account=(a.remaining_candidates == 0),
            wait_s=cfg.mm_cooldown_s,  # el código actual setea cooldown SIEMPRE, luego evalúa done
            d_card_attempts=1,
        )

    # ── 4. familia dead / 429 → ACCOUNT_DEAD ───────────────────────────────
    if _is_dead_family(o):
        if _is_rate_limited(o):
            trips = (m.consecutive_rate_limits + 1) >= cfg.circuit_breaker_consecutive_429
            if trips:
                # el código actual hace `break` ANTES de failed++/declines++/done/unlock
                return Action(
                    kind=ActionKind.ACCOUNT_DEAD,
                    reason="circuit breaker — 429 rate limits consecutivos, abortando misión",
                    dead_kind="rate_limited",
                    mark_rate_limited_dead=True,
                    circuit_breaker_hit=True,
                    abort_mission=True,
                    d_consecutive_rate_limits=1,
                )
            return Action(
                kind=ActionKind.ACCOUNT_DEAD,
                reason="rate limit — cuenta aislada",
                dead_kind="rate_limited",
                mark_rate_limited_dead=True,
                d_consecutive_rate_limits=1,
                rest_account=True,
                clear_account_candidates=True,
                d_failed=1,
                d_account_declines=1,
            )
        if o.code == "KYC_PENDING":
            return Action(
                kind=ActionKind.ACCOUNT_DEAD,
                reason="KYC en proceso de validación — cuenta marcada dead",
                dead_kind="kyc",
                reset_consecutive_rate_limits=True,
                rest_account=True,
                clear_account_candidates=True,
                d_failed=1,
                d_account_declines=1,
            )
        return Action(
            kind=ActionKind.ACCOUNT_DEAD,
            reason="cuenta muerta (login denied / ban permanente / autoexclusión)",
            dead_kind="dead",
            dead_reason=(o.error or o.code),
            reset_consecutive_rate_limits=True,
            rest_account=True,
            clear_account_candidates=True,
            d_failed=1,
            d_account_declines=1,
        )

    # ── 5. decline real / cargo ambiguo → CARD_DECLINE ─────────────────────
    if _dep._mm_is_real_decline(o.code) or _dep._mm_is_ambiguous_charge(o.code):
        retire = (
            (c.declines + 1) >= cfg.card_max_declines
            or (c.attempts + 1) >= cfg.card_max_attempts
        )
        rest = (
            (a.declines_this_run + 1) >= cfg.account_max_declines_per_run
            or a.remaining_candidates == 0
        )
        return Action(
            kind=ActionKind.CARD_DECLINE,
            reason=(
                "tarjeta jubilada — 3 intentos en cuentas distintas"
                if retire
                else "rechazo bancario — encolando para intento en cuenta distinta"
            ),
            mark_account_tried_for_card=True,
            retire_card=retire,
            requeue_card=not retire,
            rest_account=rest,
            wait_s=(0.0 if rest else cfg.mm_cooldown_s),
            d_card_declines=1,
            d_card_attempts=1,
            d_account_declines=1,
            d_failed=1,
        )

    # ── 6. CARD_LOCKED_OTHER_ACCOUNT → RETIRE_CARD_LOCKED ──────────────────
    if _is_card_locked(o):
        return Action(
            kind=ActionKind.RETIRE_CARD_LOCKED,
            reason="tarjeta detectada en otra cuenta — jubilada",
            retire_card=True,
            remove_card_from_others=True,
            wait_s=cfg.cross_account_gap_s,
            d_failed=1,
        )

    # ── 7. transitorio (nuestro lado) → RETRY_SAME / GIVE_UP_PAIR ──────────
    if (m.transient_count + 1) > cfg.match_transient_retries:
        return Action(
            kind=ActionKind.GIVE_UP_PAIR,
            reason=f"transitorio — abandonado tras {cfg.match_transient_retries} reintentos",
            wait_s=cfg.mm_cooldown_s,
            d_failed=1,
        )
    return Action(
        kind=ActionKind.RETRY_SAME,
        reason="transitorio (gateway/login/timeout) — reintentar el par",
        wait_s=cfg.transient_backoff_s,
        d_transient=1,
    )
