# tests/test_bet_policy.py
"""`bet_policy.BetPolicyConfig` — FASE 1: solo el dataclass congelado + `DEFAULT`.

El único contrato de esta fase: los defaults son EXACTAMENTE los valores que hoy
viven dispersos como constantes de módulo en `auto_deposit.py` / `deposits.py`.
Cero cambio de conducta. `load_policy()` + override de disco + bounds llegan en
FASE 2 (ver `docs/BET_POLICY.md`).
"""
import dataclasses

import pytest

import auto_deposit as ad
import deposits as dep
import bet_policy


def test_default_is_a_frozen_betpolicyconfig():
    assert isinstance(bet_policy.DEFAULT, bet_policy.BetPolicyConfig)
    with pytest.raises(Exception):
        bet_policy.DEFAULT.mm_cooldown_s = 999


def test_defaults_match_live_module_constants():
    d = bet_policy.DEFAULT
    assert d.probe_amount == ad.PROBE_AMOUNT
    assert d.match_transient_retries == ad.MATCH_TRANSIENT_RETRIES
    assert d.cross_account_gap_s == ad.MM_CROSS_ACCOUNT_GAP
    assert d.account_max_declines_per_run == ad.MM_MAX_ACCOUNT_DECLINES_PER_RUN
    assert d.card_max_declines == ad.MM_CARD_MAX_DECLINES
    assert d.card_max_attempts == ad.MM_CARD_MAX_DECLINES
    assert d.max_accounts_hard_cap == ad.MAX_ACCOUNTS_HARD_CAP
    assert d.mm_cooldown_s == dep.MM_COOLDOWN
    assert d.transient_backoff_s == 25  # `_sleep_step(25)` hardcodeado en el inner loop


def test_locked_fields_cover_the_canonical_invariants():
    # invariantes 4 (tarjeta 3-strikes), 5 (cuenta anti-taladro), 7 (3DS→A+),
    # 10 (circuit breaker 429) — el tuner de FASE 4 jamás toca estos campos.
    assert bet_policy._LOCKED_FIELDS == frozenset({
        "account_max_declines_per_run",
        "card_max_declines",
        "card_max_attempts",
        "circuit_breaker_consecutive_429",
    })


def test_all_locked_fields_exist_on_the_dataclass():
    field_names = {f.name for f in dataclasses.fields(bet_policy.BetPolicyConfig)}
    assert bet_policy._LOCKED_FIELDS <= field_names
