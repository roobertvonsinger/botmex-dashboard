"""TDD — migración retroactiva: reclasificar los 'rejected' FALSOS ya en BD.

Bug 2026-07-06: rate-limit/autoexclusión/login/gateway/timeout se guardaron con
status='rejected' (= "Rechazado banco") y envenenan bin_stats. La migración los
reetiqueta a su status real POR EL TEXTO del rejection_reason (única señal en
registros viejos), SIN tocar los rechazos REALES de banco ni los approved.

Conservadora: solo reclasifica lo que casa con un patrón no-banco de ALTA
confianza; ante duda, se queda 'rejected'.
"""
import sqlite3
import pytest
from scripts.migrate_status_no_banco import reclassify


def _mkdb(rows):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, "
        "card_pipe TEXT, created_at TEXT)"
    )
    for st, reason in rows:
        con.execute(
            "INSERT INTO deposit_attempts (account_email,amount,status,rejection_reason,card_pipe,created_at) "
            "VALUES ('a@x.com',100,?,?,'411111|01|30|123','2026-07-06 18:05:00')",
            (st, reason),
        )
    con.commit()
    return con


def _statuses(con):
    return [r["status"] for r in con.execute(
        "SELECT status FROM deposit_attempts ORDER BY id").fetchall()]


def test_rate_limit_reclassified():
    con = _mkdb([("rejected", "BetMexico rate-limit (429) — cuenta enfriando 20 min")])
    reclassify(con)
    assert _statuses(con) == ["rate_limited"]


def test_rate_limit_raw_code_reclassified():
    con = _mkdb([("rejected", "RATE_LIMITED")])
    reclassify(con)
    assert _statuses(con) == ["rate_limited"]


def test_autoexclusion_reclassified():
    con = _mkdb([("rejected", "Cuenta autoexcluida en BetMexico — se reactiva el 01/08")])
    reclassify(con)
    assert _statuses(con) == ["account_dead"]


def test_login_and_gateway_reclassified():
    con = _mkdb([
        ("rejected", "LOGIN_FAILED"),
        ("rejected", "Gateway de pagos de BetMexico no responde tras 3 intentos"),
        ("rejected", "TIMEOUT"),
    ])
    reclassify(con)
    assert _statuses(con) == ["login_lost", "gateway_error", "timeout"]


def test_real_bank_decline_untouched():
    # Rechazo REAL de banco: NO se toca (conservador).
    con = _mkdb([
        ("rejected", "BANK_REJECTED — decline genérico"),
        ("rejected", "BANK_REJECTED_AFTER_APPROVE — fondos insuficientes"),
    ])
    reclassify(con)
    assert _statuses(con) == ["rejected", "rejected"]


def test_approved_untouched():
    con = _mkdb([("approved", None), ("approved", "BANK_APPROVED")])
    reclassify(con)
    assert _statuses(con) == ["approved", "approved"]


def test_idempotent():
    con = _mkdb([("rejected", "RATE_LIMITED"), ("rejected", "BANK_REJECTED — decline")])
    first = reclassify(con)
    after1 = _statuses(con)
    second = reclassify(con)
    after2 = _statuses(con)
    assert after1 == after2                     # correr de nuevo no cambia nada
    assert second["total"] == 0                 # segunda pasada no migra nada


def test_returns_counts_by_category():
    con = _mkdb([
        ("rejected", "RATE_LIMITED"),
        ("rejected", "BetMexico rate-limit (429)"),
        ("rejected", "Cuenta autoexcluida"),
        ("rejected", "BANK_REJECTED — decline"),
    ])
    res = reclassify(con)
    assert res["rate_limited"] == 2
    assert res["account_dead"] == 1
    assert res["total"] == 3                     # el banco real no cuenta
