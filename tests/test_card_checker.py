# test_card_checker.py
"""Tests unitarios para el pre-checker de tarjetas card_checker.py."""
import pytest
import card_checker
from card_checker import check_luhn, parse_and_validate_card_pipe, precheck_card_liveness, format_ruthopia_liveness_summary


def test_check_luhn_valid():
    # Tarjeta de prueba Visa estándar (Luhn válido)
    assert check_luhn("4111111111111111") is True


def test_check_luhn_invalid():
    assert check_luhn("4111111111111112") is False
    assert check_luhn("1234") is False
    assert check_luhn("abc") is False


def test_parse_and_validate_card_pipe_3parts():
    valid, parsed, reason = parse_and_validate_card_pipe("4111111111111111|1230|123")
    assert valid is True
    assert reason == "OK"
    assert parsed["card_number"] == "4111111111111111"
    assert parsed["card_expiry"] == "1230"
    assert parsed["card_cvv"] == "123"
    assert parsed["bin"] == "411111"


def test_parse_and_validate_card_pipe_4parts():
    valid, parsed, reason = parse_and_validate_card_pipe("4111111111111111|12|2030|123")
    assert valid is True
    assert parsed["card_expiry"] == "1230"


def test_parse_and_validate_card_pipe_expired():
    valid, parsed, reason = parse_and_validate_card_pipe("4111111111111111|0120|123")
    assert valid is False
    assert "vencida" in reason.lower()


def test_precheck_card_liveness(monkeypatch):
    # Mockear perform_wabox_liveness_check para pruebas unitarias sin dependencias externas
    monkeypatch.setattr(card_checker, "perform_wabox_liveness_check", lambda c: (True, "🟢 LIVE (Tokenized)", {}))
    ok, msg, data = precheck_card_liveness("4111111111111111|1230|123")
    assert ok is True
    assert data["bin"] == "411111"

    ok_invalid, msg_invalid, _ = precheck_card_liveness("4111111111111112|1230|123")
    assert ok_invalid is False
    assert "luhn" in msg_invalid.lower()


def test_format_ruthopia_liveness_summary():
    items = [
        {"pipe": "4111111111111111|1230|123", "ok": True, "status_label": "🟢 LIVE"},
        {"pipe": "4111111111111112|1230|123", "ok": False, "status_label": "🔴 DECLINED"}
    ]
    summary = format_ruthopia_liveness_summary(items)
    assert "ʀ.ᴜᴛʜᴏᴘɪᴀ ɢᴀᴛᴇ /ʀᴡ" in summary
    assert "Aceptadas: <b>1</b>" in summary
    assert "Descartadas: <b>1</b>" in summary
