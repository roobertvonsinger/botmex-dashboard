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


def test_precheck_card_liveness_live(monkeypatch):
    import card_checker as cc
    monkeypatch.setattr(cc, "ruthopia_bridge_check", lambda p: ("Approved", "Card Updated (Last4: 1111)"))
    ok, msg, data = cc.precheck_card_liveness("4111111111111111|1230|123")
    assert ok and data["liveness_kind"] == "live"

def test_precheck_card_liveness_tol_bin(monkeypatch):
    import card_checker as cc
    monkeypatch.setattr(cc, "ruthopia_bridge_check", lambda p: ("Declined", "Declined: Your card was declined"))
    ok, msg, data = cc.precheck_card_liveness("41691600000000070|1230|123")
    assert ok and data["liveness_kind"] == "tol_bin"

def test_precheck_card_liveness_tol_reason(monkeypatch):
    import card_checker as cc
    monkeypatch.setattr(cc, "ruthopia_bridge_check", lambda p: ("Error", "Error: Your card does not support this type of purchase."))
    ok, msg, data = cc.precheck_card_liveness("49156600000000030|1230|123")
    assert ok and data["liveness_kind"] == "tol_reason"

def test_precheck_card_liveness_dead(monkeypatch):
    import card_checker as cc
    monkeypatch.setattr(cc, "ruthopia_bridge_check", lambda p: ("Declined", "Declined: Your card was declined"))
    ok, msg, data = cc.precheck_card_liveness("45552900000000040|1230|123")
    assert not ok and data["liveness_kind"] == "dead"


def test_format_ruthopia_liveness_summary():
    items = [
        {"pipe": "4111111111111111|1230|123", "ok": True, "status_label": "🟢 LIVE"},
        {"pipe": "4111111111111112|1230|123", "ok": False, "status_label": "🔴 DECLINED"}
    ]
    summary = format_ruthopia_liveness_summary(items)
    assert "LIVE · 1" in summary
    assert "TIESAS · 1" in summary
    assert "Aceptadas: <b>1</b>" in summary
    assert "Descartadas: <b>1</b>" in summary


def test_ruthopia_bridge_check_post(monkeypatch):
    import card_checker as cc
    captured = {}
    class FakeResp:
        status_code = 200
        def json(self):
            return {"ok": True, "results": [{"card": "4111111111111111|12|28|123", "status": "Approved", "message": "Card Updated (Last4: 1111)", "elapsed_s": 1.0}]}
    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResp()
    monkeypatch.setattr(cc.requests, "post", fake_post)
    monkeypatch.setattr(cc, "_load_ruthopia_dashboard_token", lambda: "tok-test")
    status, msg = cc.ruthopia_bridge_check("4111111111111111|12|28|123")
    assert status == "Approved"
    assert "Card Updated" in msg
    assert captured["url"] == "http://172.16.3.1:8787/api/rw/check"
    assert captured["headers"]["Authorization"] == "Bearer tok-test"
    assert captured["json"] == {"cards": ["4111111111111111|12|28|123"]}


def test_ruthopia_bridge_check_maintenance(monkeypatch):
    import card_checker as cc
    class Fake503:
        status_code = 503
        def json(self):
            return {"ok": False, "error": "maintenance"}
    monkeypatch.setattr(cc.requests, "post", lambda *a, **k: Fake503())
    monkeypatch.setattr(cc, "_load_ruthopia_dashboard_token", lambda: "tok-test")
    status, msg = cc.ruthopia_bridge_check("4111111111111111|12|28|123")
    assert status == "Error" and "maintenance" in msg


def test_ruthopia_bridge_check_retries_infra_only(monkeypatch):
    import card_checker as cc
    calls = []
    class Fake503:
        status_code = 503
        def json(self):
            return {"ok": False, "error": "maintenance"}
    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(1)
        return Fake503()
    monkeypatch.setattr(cc.requests, "post", fake_post)
    monkeypatch.setattr(cc, "_load_ruthopia_dashboard_token", lambda: "tok-test")
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    status, msg = cc.ruthopia_bridge_check("4111111111111111|12|28|123")
    assert status == "Error" and len(calls) == cc._RUTHOPIA_BRIDGE_RETRIES + 1


def test_ruthopia_bridge_check_no_retry_on_decline(monkeypatch):
    import card_checker as cc
    calls = []
    class FakeDeclined:
        status_code = 200
        def json(self):
            return {"ok": True, "results": [{"card": "x", "status": "Declined", "message": "Declined: Your card was declined", "elapsed_s": 1.0}]}
    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(1)
        return FakeDeclined()
    monkeypatch.setattr(cc.requests, "post", fake_post)
    monkeypatch.setattr(cc, "_load_ruthopia_dashboard_token", lambda: "tok-test")
    status, msg = cc.ruthopia_bridge_check("4169160000000000|12|28|123")
    assert status == "Declined" and len(calls) == 1  # respuesta real → NO reintenta


def test_get_card_declines_24h_and_alert(monkeypatch, tmp_path):
    import sqlite3
    import card_checker as cc
    from datetime import datetime, timezone

    db_path = tmp_path / "test.db"
    con = sqlite3.connect(str(db_path))
    con.executescript("""
    CREATE TABLE deposit_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_email TEXT,
        amount REAL,
        status TEXT,
        rejection_reason TEXT,
        card_pipe TEXT,
        created_at TEXT
    );
    """)
    now_iso = datetime.now(timezone.utc).isoformat()
    # 4 declinaciones recientes para la tarjeta 4111...
    for i in range(4):
        con.execute(
            "INSERT INTO deposit_attempts (account_email, status, card_pipe, created_at) "
            "VALUES (?, 'rejected', '4111111111111111|1230|123', ?)",
            (f"acc{i}@test.com", now_iso),
        )
    con.commit()
    con.close()

    # Probar con conexión explícita
    con2 = sqlite3.connect(str(db_path))
    con2.row_factory = sqlite3.Row
    declines = cc.get_card_declines_24h("4111111111111111", db_conn=con2)
    assert declines == 4
    con2.close()


def test_check_ruthopia_db_liveness(monkeypatch, tmp_path):
    import sqlite3
    import card_checker as cc
    from datetime import datetime, timezone

    db_path = tmp_path / "ruthopia.db"
    con = sqlite3.connect(str(db_path))
    con.executescript("""
    CREATE TABLE check_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_full TEXT,
        gate TEXT,
        status TEXT,
        message TEXT,
        bin_brand TEXT,
        bin_type TEXT,
        bin_level TEXT,
        bin_bank TEXT,
        bin_country TEXT,
        ts TEXT
    );
    """)
    now_iso = datetime.now(timezone.utc).isoformat()
    con.execute(
        "INSERT INTO check_log (card_full, gate, status, message, bin_brand, bin_bank, ts) "
        "VALUES (?, 'Wabox', 'Approved', 'Card live', 'Visa', 'BBVA', ?)",
        ("4111111111111111|12|30|123", now_iso),
    )
    con.commit()
    con.close()

    monkeypatch.setattr(cc, "check_ruthopia_db_liveness", lambda pan: (True, "🟢 LIVE (Ruthopia Wabox OK)", {"status": "Approved"}))
    live_res = cc.check_ruthopia_db_liveness("4111111111111111")
    assert live_res is not None
    assert live_res[0] is True
    assert "LIVE" in live_res[1]


def test_precheck_card_liveness_superadmin_married(monkeypatch):
    import card_checker as cc
    class FakeDBContext:
        def __init__(self, write=False):
            pass
        def __enter__(self):
            class FakeCursor:
                def execute(self, q, params=()):
                    class FakeRow:
                        def fetchone(self):
                            if "account_cards" in q or "deposit_attempts" in q:
                                return {"account_email": "married_user@gmail.com"}
                            if "accounts" in q:
                                return {"status": "LIVE", "dead_reason": None}
                            return None
                        def fetchall(self):
                            return []
                    return FakeRow()
            return FakeCursor()
        def __exit__(self, *args):
            pass

    import app
    monkeypatch.setattr(app, "db", FakeDBContext)

    # SuperAdmin (Robert 1341812706)
    ok_sa, reason_sa, data_sa = cc.precheck_card_liveness("4111111111111111|1230|123", operator_id=1341812706)
    assert ok_sa is True
    assert data_sa["is_married_eligible"] is True
    assert data_sa["liveness_kind"] == "married"
    assert data_sa["married_account"] == "married_user@gmail.com"

    # Regular Operator (12345)
    ok_reg, reason_reg, data_reg = cc.precheck_card_liveness("4111111111111111|1230|123", operator_id=12345)
    assert ok_reg is False
    assert "MARRIED" in reason_reg

