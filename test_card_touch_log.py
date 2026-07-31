"""[CARD_TOUCH] — log de auditoría de tarjetas sin mask (Robert 2026-07-31).

_record_attempt es el único punto que llaman los 3 flujos (single/matchmaker/
scheduled) — un solo test cubre la instrumentación para los tres. Ley de
Robert: cero asteriscos, cero truncado — el pipe completo debe quedar en el
log tal cual se recibió.
"""
import logging

import deposits


def test_record_attempt_logs_card_touch_full_pipe_no_mask(seed_db, monkeypatch, caplog):
    import app
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    pipe = "4111111111111111|12|2030|123"
    with caplog.at_level(logging.INFO, logger="betmexico.dashboard.deposits"):
        deposits._record_attempt(
            attempt_id="test-attempt-1",
            email="a@test.com",
            amount=150.0,
            status="approved",
            rejection_reason=None,
            duration_ms=800,
            operator_id=1341812706,
            card_pipe=pipe,
        )

    touch_lines = [r.message for r in caplog.records if "[CARD_TOUCH]" in r.message]
    assert touch_lines, "no se emitió la línea [CARD_TOUCH]"
    line = touch_lines[0]

    # Pipe completo, sin truncar ni enmascarar (ley no-masking).
    assert pipe in line
    assert "***" not in line
    assert "..." not in line
    # Contexto de auditoría completo: quién, en qué cuenta, con qué resultado.
    assert "account=a@test.com" in line
    assert "status=approved" in line
    assert "amount=$150.00" in line


def test_record_attempt_skips_card_touch_when_no_pipe(seed_db, monkeypatch, caplog):
    import app
    monkeypatch.setattr(app, "_broadcast", lambda ev: None)

    with caplog.at_level(logging.INFO, logger="betmexico.dashboard.deposits"):
        deposits._record_attempt(
            attempt_id="test-attempt-2",
            email="b@test.com",
            amount=10.0,
            status="rate_limited",
            rejection_reason="RATE_LIMITED",
            duration_ms=200,
            operator_id=1341812706,
            card_pipe=None,
        )

    touch_lines = [r.message for r in caplog.records if "[CARD_TOUCH]" in r.message]
    assert not touch_lines, "no debe loguear CARD_TOUCH sin tarjeta"
