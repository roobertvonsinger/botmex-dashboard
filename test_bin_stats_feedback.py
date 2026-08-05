"""bin_stats approved/rejected feedback (Robert 2026-08-05).

Hallazgo: `_bot_db.log_attempt` solo toca bin_stats si recibe un `card_id`
resuelto, y `_record_attempt` (los 3 flujos: single/matchmaker/scheduled)
SIEMPRE llama con card_id=None — verificado contra prod: bin_stats con 3
filas, las 3 en total_attempts=0. `_record_attempt` ahora escribe bin_stats
directo (mismo patrón que `_record_bin_3ds`), para que
`auto_deposit._rank_key`/`_approval_rate` tengan señal real.
"""
import importlib
import sqlite3

import deposits


def _reload_app():
    """app.DB_PATH se resuelve al importar — sin reload, un test posterior
    hereda el DB_PATH (y la conexión potencialmente ya cerrada/bloqueada) del
    test anterior. Mismo patrón que la fixture `client` de conftest.py."""
    import app as app_mod
    importlib.reload(app_mod)
    return app_mod


def _bin_row(db_path, bin6):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM bin_stats WHERE bin = ?", (bin6,)).fetchone()
    con.close()
    return dict(row) if row else None


def test_record_attempt_approved_increments_bin_stats(seed_db, monkeypatch):
    app = _reload_app()
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    pipe = "4111111111111111|1230|123"
    deposits._record_attempt(
        attempt_id="bin-1", email="a@test.com", amount=150.0,
        status="approved", rejection_reason=None, duration_ms=500,
        operator_id=1341812706, card_pipe=pipe,
    )

    row = _bin_row(seed_db, "411111")
    assert row is not None
    assert row["total_attempts"] == 1
    assert row["total_approved"] == 1
    assert row["total_rejected"] == 0


def test_record_attempt_rejected_increments_bin_stats(seed_db, monkeypatch):
    app = _reload_app()
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    pipe = "4222222222222222|1230|123"
    deposits._record_attempt(
        attempt_id="bin-2", email="a@test.com", amount=150.0,
        status="rejected", rejection_reason="BANK_REJECTED", duration_ms=500,
        operator_id=1341812706, card_pipe=pipe,
    )

    row = _bin_row(seed_db, "422222")
    assert row is not None
    assert row["total_attempts"] == 1
    assert row["total_approved"] == 0
    assert row["total_rejected"] == 1


def test_record_attempt_accumulates_across_attempts(seed_db, monkeypatch):
    app = _reload_app()
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    pipe = "4333333333333333|1230|123"
    for i, status in enumerate(["approved", "rejected", "approved"]):
        deposits._record_attempt(
            attempt_id=f"bin-3-{i}", email="a@test.com", amount=150.0,
            status=status, rejection_reason=None, duration_ms=500,
            operator_id=1341812706, card_pipe=pipe,
        )

    row = _bin_row(seed_db, "433333")
    assert row["total_attempts"] == 3
    assert row["total_approved"] == 2
    assert row["total_rejected"] == 1


def test_record_attempt_ignores_non_bank_status(seed_db, monkeypatch):
    """rate_limited/login_lost/gateway_error/timeout/ambiguous NUNCA tocan
    bin_stats — ley de classify_deposit_status (no envenenar el BIN con
    ruido de nuestro lado)."""
    app = _reload_app()
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    pipe = "4444444444444444|1230|123"
    for status in ["rate_limited", "login_lost", "gateway_error", "timeout", "ambiguous", "account_dead"]:
        deposits._record_attempt(
            attempt_id=f"bin-4-{status}", email="a@test.com", amount=150.0,
            status=status, rejection_reason=None, duration_ms=500,
            operator_id=1341812706, card_pipe=pipe,
        )

    assert _bin_row(seed_db, "444444") is None


def test_record_attempt_skips_bin_stats_without_pipe(seed_db, monkeypatch):
    app = _reload_app()
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    deposits._record_attempt(
        attempt_id="bin-5", email="a@test.com", amount=150.0,
        status="approved", rejection_reason=None, duration_ms=500,
        operator_id=1341812706, card_pipe=None,
    )
    # No explota, y no hay ningún bin nuevo (seed_db no trae bin_stats precargado).
    con = sqlite3.connect(seed_db)
    n = con.execute("SELECT COUNT(*) FROM bin_stats").fetchone()[0]
    con.close()
    assert n == 0
