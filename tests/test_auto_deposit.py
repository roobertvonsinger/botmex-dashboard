# tests/test_auto_deposit.py
"""Tests del motor de selección del modo auto (auto_deposit.py — Task B)."""
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from auto_deposit import (
    plan_auto_mission,
    select_accounts_for_auto,
    select_card_for_account,
)


# ── helpers B1 (función pura: rows = dicts, sin BD) ──────────────────────────
def _row(email, **kw):
    r = {
        "id": None, "email": email, "status": "LIVE", "grade": "A",
        "grade_score": 50, "balance_total": 100.0, "published_to_pool": 1,
        "locked_by": None, "cooldown_until": None,
        "jwt_expires_at": int(time.time()) + 3600,
    }
    r.update(kw)
    return r


def _win(*emails, available=2000.0):
    return {e: {"available": available} for e in emails}


# ── B1 — select_accounts_for_auto ────────────────────────────────────────────
def test_select_filters_dead_accounts():
    rows = [_row("live@t.com"), _row("dead@t.com", status="DEAD")]
    sel = select_accounts_for_auto(rows, 150, 9, _win("live@t.com", "dead@t.com"))
    assert [r["email"] for r in sel] == ["live@t.com"]


def test_select_filters_locked():
    rows = [_row("free@t.com"), _row("locked@t.com", locked_by=555)]
    sel = select_accounts_for_auto(rows, 150, 9, _win("free@t.com", "locked@t.com"))
    assert [r["email"] for r in sel] == ["free@t.com"]


def test_select_filters_cooldown():
    rows = [_row("ok@t.com"), _row("cd@t.com", cooldown_until=int(time.time()) + 600)]
    sel = select_accounts_for_auto(rows, 150, 9, _win("ok@t.com", "cd@t.com"))
    assert [r["email"] for r in sel] == ["ok@t.com"]


def test_select_filters_no_jwt():
    rows = [
        _row("ok@t.com"),
        _row("nojwt@t.com", jwt_expires_at=None),
        _row("exp@t.com", jwt_expires_at=int(time.time()) - 10),
    ]
    sel = select_accounts_for_auto(rows, 150, 9, _win("ok@t.com", "nojwt@t.com", "exp@t.com"))
    assert [r["email"] for r in sel] == ["ok@t.com"]


def test_select_filters_insufficient_cap():
    # 9 * $150 = $1350 → la cuenta con available $500 no alcanza el cap 24h
    rows = [_row("rich@t.com"), _row("poor@t.com")]
    win = {"rich@t.com": {"available": 1499.0}, "poor@t.com": {"available": 500.0}}
    sel = select_accounts_for_auto(rows, 150, 9, win)
    assert [r["email"] for r in sel] == ["rich@t.com"]


def test_select_orders_by_grade_then_score():
    rows = [
        _row("b@t.com", grade="B", grade_score=99),
        _row("a_low@t.com", grade="A", grade_score=10),
        _row("ap@t.com", grade="A+", grade_score=1),
        _row("a_high@t.com", grade="A", grade_score=90),
    ]
    emails = [r["email"] for r in rows]
    # Con count=2 (count <= 3), no estratifica en round-robin y devuelve las mejores absolutas
    sel = select_accounts_for_auto(rows, 150, 2, _win(*emails))
    assert [r["email"] for r in sel] == ["ap@t.com", "a_high@t.com"]


def test_select_stratified_round_robin():
    rows = [
        _row(f"top_{i}@t.com", grade="A+", grade_score=90) for i in range(3)
    ] + [
        _row(f"mid_{i}@t.com", grade="A", grade_score=50) for i in range(3)
    ] + [
        _row(f"low_{i}@t.com", grade="B", grade_score=10) for i in range(3)
    ]
    emails = [r["email"] for r in rows]
    sel = select_accounts_for_auto(rows, 150, 6, _win(*emails))
    selected_emails = [r["email"] for r in sel]
    # Debe intercalar un Top, un Mid, un Low
    assert selected_emails[0].startswith("top_")
    assert selected_emails[1].startswith("mid_")
    assert selected_emails[2].startswith("low_")


def test_select_respects_count():
    rows = [_row(f"u{i}@t.com") for i in range(5)]
    sel = select_accounts_for_auto(rows, 150, 2, _win(*[r["email"] for r in rows]))
    assert len(sel) == 2


def test_select_empty_when_none_eligible():
    rows = [_row("d@t.com", status="DEAD"), _row("l@t.com", locked_by=1)]
    assert select_accounts_for_auto(rows, 150, 9, {}) == []


def test_select_filters_recent_declines():
    """Regla Robert 2026-07-28: cuenta con >=2 declines en las últimas 12h
    queda fuera de la selección auto (aunque cumpla el resto de filtros)."""
    rows = [_row("clean@t.com"), _row("burned@t.com")]
    win = _win("clean@t.com", "burned@t.com")
    declines = {"burned@t.com": 2, "clean@t.com": 1}
    sel = select_accounts_for_auto(rows, 150, 9, win, decline_map=declines)
    assert [r["email"] for r in sel] == ["clean@t.com"]


def test_select_ignores_decline_map_when_absent():
    """Sin decline_map (llamadas existentes/backward-compat), no filtra por declines."""
    rows = [_row("a@t.com")]
    sel = select_accounts_for_auto(rows, 150, 9, _win("a@t.com"))
    assert [r["email"] for r in sel] == ["a@t.com"]


# ── B2 — select_card_for_account ─────────────────────────────────────────────
def _card(number, email="a@t.com", status="ACTIVE"):
    return {"card_number": number, "card_expiry": "1230", "card_cvv": "123",
            "account_email": email, "status": status}


def test_prefers_married_card():
    cards = [_card("5555555555555555", email="otro@t.com"), _card("4111111111111111")]
    stats = {"555555": {"total_attempts": 100, "total_approved": 99}}
    pipe = select_card_for_account("a@t.com", cards, stats, 150)
    assert pipe == "4111111111111111|1230|123"


def test_avoids_3ds_bin():
    cards = [_card("4111111111111111"), _card("4222222222222222")]
    stats = {
        "411111": {"total_attempts": 10, "total_approved": 9, "total_3ds": 2,
                    "last_3ds_at": datetime.now(timezone.utc).isoformat()},
        "422222": {"total_attempts": 10, "total_approved": 5, "total_3ds": 0,
                    "last_3ds_at": None},
    }
    pipe = select_card_for_account("a@t.com", cards, stats, 150)
    assert pipe.startswith("422222")


def test_best_approval_rate():
    # approval_rate se COMPUTA (total_approved/total_attempts) — no es columna
    cards = [_card("4222222222222222"), _card("4111111111111111")]
    stats = {
        "411111": {"total_attempts": 10, "total_approved": 9},   # 90%
        "422222": {"total_attempts": 10, "total_approved": 5},   # 50%
    }
    pipe = select_card_for_account("a@t.com", cards, stats, 150)
    assert pipe.startswith("411111")


def test_no_card_returns_none():
    assert select_card_for_account("a@t.com", [], {}, 150) is None


def test_skips_retired_card():
    cards = [_card("4111111111111111", status="RETIRED")]
    assert select_card_for_account("a@t.com", cards, {}, 150) is None


# ── B3 — plan_auto_mission (BD temporal vía fixture seed_db) ─────────────────
def _add_account(db_path, email, grade="A", grade_score=50, balance=100.0):
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO accounts (email,password,balance_total,status,grade,grade_score,"
            "published_to_pool,cooldown_until,jwt_expires_at,first_checked_at,last_checked_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (email, "x", balance, "LIVE", grade, grade_score, 1, None,
             int(time.time()) + 3600, "2026-07-01 00:00:00", "2026-07-01 00:00:00"))
        con.commit()
    finally:
        con.close()


def _add_card(db_path, number, email, status="ACTIVE"):
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO account_cards (card_number,card_expiry,card_cvv,"
            "account_email,account_password,status) VALUES (?,?,?,?,?,?)",
            (number, "1230", "123", email, "x", status))
        con.commit()
    finally:
        con.close()


def test_plan_assigns_married_cards(seed_db):
    _add_account(seed_db, "m@t.com")
    _add_card(seed_db, "4111111111111111", "m@t.com")
    plan = plan_auto_mission(seed_db, [], amount=150, target_count=9)
    assert plan["feasible"] is True
    assert plan["accounts"][0]["email"] == "m@t.com"
    assert plan["accounts"][0]["card_pipe"] == "4111111111111111|1230|123"


def test_plan_assigns_pool_cards(seed_db):
    _add_account(seed_db, "p@t.com")
    plan = plan_auto_mission(seed_db, ["4333333333333333|0131|999"], amount=150, target_count=9)
    assert plan["feasible"] is True
    assert plan["accounts"][0]["card_pipe"] == "4333333333333333|0131|999"


def test_plan_feasibility_check(seed_db):
    # seed base: a@ lockeada, b@ sin JWT vivo, c@ DEAD → ninguna elegible
    plan = plan_auto_mission(seed_db, ["4111111111111111|1230|123"], amount=150, target_count=9)
    assert plan["feasible"] is False
    assert plan["accounts"] == []
    assert plan["reason"]


def test_plan_estimates_total(seed_db):
    _add_account(seed_db, "t1@t.com")
    _add_account(seed_db, "t2@t.com")
    _add_card(seed_db, "4111111111111111", "t1@t.com")
    _add_card(seed_db, "4222222222222222", "t2@t.com")
    plan = plan_auto_mission(seed_db, [], amount=150, target_count=9)
    assert len(plan["accounts"]) == 2
    assert plan["total_estimated"] == 150 * 9 * 2


def _add_rejected_attempt(db_path, email, hours_ago=1):
    con = sqlite3.connect(str(db_path))
    try:
        ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        con.execute(
            "INSERT INTO deposit_attempts (attempt_id,account_email,amount,status,"
            "rejection_reason,source,created_at) VALUES (?,?,?,?,?,?,?)",
            ("x" + str(time.time_ns()), email, 10.0, "rejected", "BANK_REJECTED",
             "auto", ts.strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
    finally:
        con.close()


def test_plan_excludes_accounts_with_recent_declines(seed_db):
    """Regla Robert: cuenta con 2 declines en las últimas 12h NO entra al plan
    aunque cumpla el resto de filtros (no taladrar cuentas ya quemadas)."""
    _add_account(seed_db, "burned@t.com")
    _add_card(seed_db, "4111111111111111", "burned@t.com")
    _add_rejected_attempt(seed_db, "burned@t.com", hours_ago=1)
    _add_rejected_attempt(seed_db, "burned@t.com", hours_ago=2)
    plan = plan_auto_mission(seed_db, [], amount=150, target_count=9)
    assert plan["feasible"] is False
    assert plan["accounts"] == []


def test_plan_max_accounts_scales_with_card_count(seed_db):
    """Regla Robert: 3 cuentas para la 1a tarjeta + 1 extra por tarjeta
    adicional (no taladrar todo el pool para lograr el match)."""
    for i in range(6):
        _add_account(seed_db, f"u{i}@t.com")
        _add_card(seed_db, f"411111111111{i:04d}", f"u{i}@t.com")
    plan_1card = plan_auto_mission(seed_db, ["4999999999999999|0130|999"],
                                    amount=150, target_count=9)
    plan_3cards = plan_auto_mission(
        seed_db,
        ["4999999999999999|0130|999", "4888888888888888|0130|999",
         "4777777777777777|0130|999"],
        amount=150, target_count=9)
    assert len(plan_1card["accounts"]) == 3
    assert len(plan_3cards["accounts"]) == 5
