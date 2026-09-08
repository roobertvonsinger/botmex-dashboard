"""bet_policy — política centralizada del flujo `/bet` (auto-depósito + matchmaking).

FASE 1 del refactor a nodos (`docs/BET_POLICY.md`): las constantes/umbrales que
hoy viven dispersos como módulo-nivel en `auto_deposit.py` / `deposits.py` se
centralizan en un objeto **congelado** y versionado. Esta fase entrega SOLO el
dataclass + `DEFAULT` (defaults = valores exactos actuales → cero cambio de
conducta). `load_policy()` con override en disco (`/data/bet_policy.json`),
`_SANE_BOUNDS` y el CLI `apply()` llegan en FASE 2.

Campos `_LOCKED`: protegen las invariantes canónicas 4/5/7/10. El `bet_tuner`
(FASE 4) jamás los modifica.
"""
from __future__ import annotations

from dataclasses import dataclass

# Versión del esquema de política. Un override de disco con otra versión se ignora
# entero (FASE 2). Subir esto en cada cambio de forma del dataclass.
POLICY_VERSION = 1


@dataclass(frozen=True)
class BetPolicyConfig:
    """Snapshot inmutable de la política. Se congela una vez al arranque de la
    misión — un cambio del tuner a mitad de vuelo nunca afecta una misión viva."""

    # ── montos / reintentos ──────────────────────────────────────────────────
    probe_amount: float = 10.0            # D1: probe de matchmaking (dinero real)
    match_transient_retries: int = 4      # reintentos por PAR ante fallo transitorio (nuestro lado)
    transient_backoff_s: int = 25         # espera entre reintentos transitorios (enfría IP en 406)

    # ── ritmo anti-rafagueo ──────────────────────────────────────────────────
    mm_cooldown_s: int = 45               # piso entre reusos de la MISMA cuenta
    cross_account_gap_s: int = 5          # respiro entre cuentas DISTINTAS

    # ── topes que protegen invariantes canónicas (_LOCKED) ───────────────────
    account_max_declines_per_run: int = 2      # invariante 5 — anti-taladro de cuenta
    card_max_declines: int = 3                 # invariante 4 — 3 rechazos en 3 cuentas → jubilar tarjeta
    card_max_attempts: int = 3                 # invariante 7 — hasta 3 cuentas A+ por tarjeta vía 3DS
    circuit_breaker_consecutive_429: int = 2   # invariante 10 — 2 cuentas 429 seguidas → abortar

    # ── tope duro de corrida ─────────────────────────────────────────────────
    max_accounts_hard_cap: int = 10      # Robert 2026-08-05: tope duro por corrida


# Campos que el tuner NUNCA toca y que `load_policy()` (FASE 2) rechaza de un
# override de disco. Cambiarlos = code review, no un knob.
_LOCKED_FIELDS = frozenset({
    "account_max_declines_per_run",
    "card_max_declines",
    "card_max_attempts",
    "circuit_breaker_consecutive_429",
})


# Política horneada en código. FASE 1: el shell usa esto directamente.
DEFAULT = BetPolicyConfig()
