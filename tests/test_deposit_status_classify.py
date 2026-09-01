"""TDD — classify_deposit_status(): fuente de verdad única result_code → status.

Bug raíz (2026-07-06): el catch-all `else -> "rejected"` (deposits.py single) y el
binario `"approved" if ok else "rejected"` (matchmaker/scheduled) metían CUALQUIER
fallo no-banco (RATE_LIMITED, AUTOEXCLUSION, ERROR, ...) como "rejected" = "Rechazado
(banco)" en la UI, y envenenaban bin_stats. Un rate-limit (429) del LOGIN se pintaba
como rechazo del BANCO, aunque el banco ni tocó la tarjeta.

Regla (criterio Robert, ya codificado en MM_REAL_DECLINE_RC / MM_DEAD_RC):
SOLO un rechazo REAL de banco/tarjeta = "rejected". Todo lo demás tiene su propio
status y JAMÁS se pinta "banco".
"""
from deposits import classify_deposit_status


# ── Rechazo REAL de banco → "rejected" (lo ÚNICO que puede pintarse "banco") ──
def test_bank_rejected_is_rejected():
    assert classify_deposit_status("BANK_REJECTED", False) == "rejected"


def test_bank_rejected_after_approve_is_rejected():
    assert classify_deposit_status("BANK_REJECTED_AFTER_APPROVE", False) == "rejected"


def test_pending_not_applied_is_rejected():
    # Robert lo cuenta como decline real (MM_REAL_DECLINE_RC).
    assert classify_deposit_status("PENDING_NOT_APPLIED", False) == "rejected"


def test_substring_declines_are_rejected():
    for rc in ("CARD_INSUF_FUNDS", "CARD_EXPIRED", "BANK_REJECT_TIMEOUT"):
        assert classify_deposit_status(rc, False) == "rejected", rc


# ── EL BUG REPORTADO: rate-limit NO es banco ─────────────────────────────────
def test_rate_limited_is_not_rejected():
    assert classify_deposit_status("RATE_LIMITED", False) == "rate_limited"


# ── Cuenta muerta (no banco) ─────────────────────────────────────────────────
def test_dead_account_codes_are_account_dead():
    for rc in ("AUTOEXCLUSION", "KYC_PENDING", "LOGIN_DENIED"):
        assert classify_deposit_status(rc, False) == "account_dead", rc


# ── Nuestro lado (login / captcha / gateway / timeout) — no banco ────────────
def test_login_codes_are_login_lost():
    for rc in ("LOGIN_FAILED", "CAPTCHA_POOL_EMPTY", "DEPS_MISSING"):
        assert classify_deposit_status(rc, False) == "login_lost", rc


def test_gateway_codes_are_gateway_error():
    for rc in ("BEGIN_ERROR", "PAYMENT_ERROR"):
        assert classify_deposit_status(rc, False) == "gateway_error", rc


def test_timeout_is_timeout():
    assert classify_deposit_status("TIMEOUT", False) == "timeout"


# ── Cargo ambiguo (pudo aplicarse, sin confirmar) — no banco ────────────────
def test_ambiguous_charge_codes():
    for rc in ("SUBMIT_ERROR", "UNKNOWN_TXN_STATUS_5"):
        assert classify_deposit_status(rc, False) == "ambiguous", rc


# ── Catch-all NEUTRAL (jamás "rejected") ─────────────────────────────────────
def test_unknown_codes_are_incomplete_not_rejected():
    for rc in ("ERROR", "VELOCITY_SKIP", "SOMETHING_NEW", "UNKNOWN", ""):
        st = classify_deposit_status(rc, False)
        assert st == "incomplete", f"{rc!r} -> {st!r}"
        assert st != "rejected", f"{rc!r} no debe pintarse banco"


# ── Éxito gana sobre cualquier code ──────────────────────────────────────────
def test_success_is_approved():
    assert classify_deposit_status("BANK_APPROVED", True) == "approved"
    assert classify_deposit_status("", True) == "approved"


# ── 3DS es estado propio, nunca banco ────────────────────────────────────────
def test_3ds_is_threeds():
    assert classify_deposit_status("3DS_REQUIRED", False) == "threeds"


# ── INVARIANTE GLOBAL: ningún no-banco cae en "rejected" ─────────────────────
def test_invariant_only_real_bank_declines_are_rejected():
    non_bank = [
        "RATE_LIMITED", "AUTOEXCLUSION", "KYC_PENDING", "LOGIN_DENIED",
        "LOGIN_FAILED", "CAPTCHA_POOL_EMPTY", "DEPS_MISSING", "BEGIN_ERROR",
        "PAYMENT_ERROR", "TIMEOUT", "SUBMIT_ERROR", "UNKNOWN_TXN_STATUS_5",
        "BALANCE_LIMIT_EXCEEDED", "ERROR", "VELOCITY_SKIP", "UNKNOWN", "",
    ]
    for rc in non_bank:
        assert classify_deposit_status(rc, False) != "rejected", rc
