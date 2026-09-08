# tests/test_bet_policy.py
"""`bet_policy` — dataclass congelado + `DEFAULT` (FASE 1) y `load_policy()` /
`_SANE_BOUNDS` / `digest()` / CLI `apply()` (FASE 2).

Contrato FASE 1: los defaults son EXACTAMENTE los valores que hoy viven dispersos
como constantes de módulo en `auto_deposit.py` / `deposits.py`. Cero cambio de
conducta.

Contrato FASE 2 (`docs/BET_POLICY.md`): `load_policy()` lee un override en disco
(`$BET_POLICY_FILE` o `/data/bet_policy.json`) y NUNCA lanza — sin archivo /
versión mala / valor fuera de `_SANE_BOUNDS` / campo `_LOCKED` → ese aporte se
descarta y el campo cae al default horneado.
"""
import dataclasses
import json

import pytest

import auto_deposit as ad
import deposits as dep
import bet_policy


@pytest.fixture
def policy_file(tmp_path, monkeypatch):
    """Redirige `load_policy()`/`apply()` a un archivo temporal aislado."""
    p = tmp_path / "bet_policy.json"
    monkeypatch.setenv("BET_POLICY_FILE", str(p))
    return p


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
    # FASE 2 (scheduled)
    assert d.sched_max_transient_retries == dep.SCHED_MAX_TRANSIENT_RETRIES
    assert d.sched_retry_backoff_s == dep.SCHED_RETRY_BACKOFF_SEC
    assert d.sched_rep_gap_s == 60  # `asyncio.sleep(60)` hardcodeado entre reps


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


# ── FASE 2 — load_policy() + override de disco + bounds ──────────────────────
def test_load_policy_without_file_returns_default(policy_file):
    assert not policy_file.exists()
    assert bet_policy.load_policy() == bet_policy.DEFAULT


def test_load_policy_valid_partial_merge(policy_file):
    policy_file.write_text(json.dumps({
        "version": bet_policy.POLICY_VERSION,
        "policy": {"mm_cooldown_s": 90, "cross_account_gap_s": 8},
    }), encoding="utf-8")
    pol = bet_policy.load_policy()
    assert pol.mm_cooldown_s == 90
    assert pol.cross_account_gap_s == 8
    # los demás campos intactos
    assert pol.probe_amount == bet_policy.DEFAULT.probe_amount
    assert pol.sched_rep_gap_s == bet_policy.DEFAULT.sched_rep_gap_s


def test_load_policy_bad_version_falls_back_to_default(policy_file):
    policy_file.write_text(json.dumps({
        "version": bet_policy.POLICY_VERSION + 99,
        "policy": {"mm_cooldown_s": 90},
    }), encoding="utf-8")
    assert bet_policy.load_policy() == bet_policy.DEFAULT


def test_load_policy_out_of_bounds_field_falls_to_default(policy_file):
    # mm_cooldown_s fuera de _SANE_BOUNDS → ese campo cae a default; el resto se aplica
    lo, hi = bet_policy._SANE_BOUNDS["mm_cooldown_s"]
    policy_file.write_text(json.dumps({
        "version": bet_policy.POLICY_VERSION,
        "policy": {"mm_cooldown_s": hi + 1000, "cross_account_gap_s": 9},
    }), encoding="utf-8")
    pol = bet_policy.load_policy()
    assert pol.mm_cooldown_s == bet_policy.DEFAULT.mm_cooldown_s
    assert pol.cross_account_gap_s == 9


def test_load_policy_ignores_locked_fields(policy_file):
    policy_file.write_text(json.dumps({
        "version": bet_policy.POLICY_VERSION,
        "policy": {"card_max_declines": 2, "circuit_breaker_consecutive_429": 5},
    }), encoding="utf-8")
    pol = bet_policy.load_policy()
    assert pol.card_max_declines == bet_policy.DEFAULT.card_max_declines == 3
    assert pol.circuit_breaker_consecutive_429 == bet_policy.DEFAULT.circuit_breaker_consecutive_429 == 2


def test_load_policy_malformed_json_returns_default(policy_file):
    policy_file.write_text("{ not json ", encoding="utf-8")
    assert bet_policy.load_policy() == bet_policy.DEFAULT


def test_digest_is_stable_sha1_prefix():
    d1 = bet_policy.digest(bet_policy.DEFAULT)
    d2 = bet_policy.digest(bet_policy.DEFAULT)
    assert d1 == d2
    assert len(d1) == 12
    assert all(ch in "0123456789abcdef" for ch in d1)


def test_digest_changes_when_a_field_changes():
    tuned = dataclasses.replace(bet_policy.DEFAULT, mm_cooldown_s=99)
    assert bet_policy.digest(tuned) != bet_policy.digest(bet_policy.DEFAULT)


def test_every_tunable_field_has_sane_bounds():
    tunable = {
        f.name for f in dataclasses.fields(bet_policy.BetPolicyConfig)
    } - bet_policy._LOCKED_FIELDS
    assert tunable <= set(bet_policy._SANE_BOUNDS), (
        "campos tuneables sin bound: %s" % (tunable - set(bet_policy._SANE_BOUNDS))
    )


def test_apply_cli_rejects_locked_and_writes_accepted(policy_file, capsys):
    proposal = policy_file.parent / "proposal.json"
    proposal.write_text(json.dumps({
        "policy": {"mm_cooldown_s": 75, "card_max_declines": 2},
    }), encoding="utf-8")
    rc = bet_policy.apply(str(proposal))
    assert rc == 0
    written = json.loads(policy_file.read_text(encoding="utf-8"))
    assert written["policy"]["mm_cooldown_s"] == 75
    assert "card_max_declines" not in written["policy"]
    # y load_policy() ahora lo refleja
    assert bet_policy.load_policy().mm_cooldown_s == 75
