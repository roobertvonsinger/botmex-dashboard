# tests/test_auto_deposit.py
"""Tests del motor de selección del modo auto (auto_deposit.py — Task B)."""
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from auto_deposit import (
    plan_auto_mission,
    select_accounts_for_auto,
    _max_accounts_for_cards,
)


# ── helpers B1 (función pura: rows = dicts, sin BD) ──────────────────────────
def _row(email, **kw):
    r = {
        "id": None, "email": email, "status": "LIVE", "grade": "A",
        "grade_score": 50, "balance_total": 0.0, "balance_real": 0.0, "published_to_pool": 1,
        "kyc_verified": 1,
        "locked_by": None, "cooldown_until": None,
        "jwt_expires_at": int(time.time()) + 3600,
    }
    r.update(kw)
    return r


def _win(*emails, available=2000.0):
    return {e: {"available": available} for e in emails}


# ── B1 — select_accounts_for_auto ────────────────────────────────────────────
def test_select_filters_unverified_kyc():
    rows = [_row("live_kyc@t.com", kyc_verified=1), _row("nokyc@t.com", kyc_verified=0), _row("nonekyc@t.com", kyc_verified=None)]
    sel = select_accounts_for_auto(rows, 150, 9, _win("live_kyc@t.com", "nokyc@t.com", "nonekyc@t.com"))
    assert [r["email"] for r in sel] == ["live_kyc@t.com"]


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


def test_select_prioritizes_jwt_not_excludes():
    # Robert 2026-08-05: JWT vivo NO excluye — prioriza. Sin JWT va al último
    # tier (Login Full), nunca se bloquea el matchmaker por falta de sesión.
    rows = [
        _row("ok@t.com"),
        _row("nojwt@t.com", jwt_expires_at=None),
        _row("exp@t.com", jwt_expires_at=int(time.time()) - 10),
    ]
    sel = select_accounts_for_auto(rows, 150, 9, _win("ok@t.com", "nojwt@t.com", "exp@t.com"))
    assert sel and sel[0]["email"] == "ok@t.com"  # 🟢 primero
    got = [r["email"] for r in sel]
    assert "nojwt@t.com" in got and "exp@t.com" in got  # 🔑 incluida, no excluida


def test_select_low_tier_prefers_jwt_alive_over_needs_login():
    # Robert 2026-08-05: dentro de LOW (mezcla de JWT-vivo degradado + 🔑 sin
    # JWT), preferencia leve por 🟢 — más barato de probar (sin captcha/login),
    # mismo riesgo de tarjeta. NO excluye: 🔑 sigue entrando, solo después.
    # grade C (JWT vivo) cae a LOW por grade; grade A+ SIN jwt cae a LOW pese
    # a ser mejor grade — el JWT manda sobre el grade dentro del tier.
    rows = [
        _row("alive_low@t.com", grade="C", grade_score=10),
        _row("needs_login@t.com", grade="A+", grade_score=99, jwt_expires_at=None),
    ]
    sel = select_accounts_for_auto(
        rows, 150, 2, _win("alive_low@t.com", "needs_login@t.com")
    )
    assert [r["email"] for r in sel] == ["alive_low@t.com", "needs_login@t.com"]


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


def test_select_stratified_quota_2_2_2():
    """RF5 (Robert 2026-08-13): count=6 -> cuota 40/40/20 = 2 top, 2 mid, 2 low.
    Reemplaza el round-robin 1-1-1 viejo por la disposición por tier."""
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
    # Cuota 2-2-2: 2 top, 2 mid, 2 low
    assert sum(1 for e in selected_emails if e.startswith("top_")) == 2
    assert sum(1 for e in selected_emails if e.startswith("mid_")) == 2
    assert sum(1 for e in selected_emails if e.startswith("low_")) == 2


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


# ── B3 — plan_auto_mission (BD temporal vía fixture seed_db) ─────────────────
def _add_account(db_path, email, grade="A", grade_score=50, balance=0.0, kyc_verified=1):
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO accounts (email,password,balance_total,balance_real,status,grade,grade_score,"
            "kyc_verified,published_to_pool,cooldown_until,jwt_expires_at,first_checked_at,last_checked_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (email, "x", balance, balance, "LIVE", grade, grade_score, kyc_verified, 1, None,
             int(time.time()) + 3600, "2026-07-01 00:00:00", "2026-07-01 00:00:00"))
        con.commit()
    finally:
        con.close()


def test_select_filters_accounts_with_funds():
    """Cuentas con saldo real o total >= $10.0 quedan excluidas para no arriesgar fondos en uso."""
    rows = [
        _row("empty@t.com", balance_real=0.0, balance_total=0.0),
        _row("rich@t.com", balance_real=598.49, balance_total=598.49),
        _row("cents@t.com", balance_real=0.54, balance_total=0.54),
    ]
    win = _win("empty@t.com", "rich@t.com", "cents@t.com")
    sel = select_accounts_for_auto(rows, 150, 9, win)
    sel_emails = [r["email"] for r in sel]
    assert "rich@t.com" not in sel_emails
    assert "empty@t.com" in sel_emails
    assert "cents@t.com" in sel_emails


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


def test_plan_never_uses_married_card(seed_db):
    """Robert 2026-08-05: el automático NUNCA usa una tarjeta ya guardada en
    la cuenta (account_cards) — solo el pool que entregó el operador. Bug
    real: el matchmaker tomó una tarjeta married mientras Robert corría un
    depósito automático con 4 tarjetas propias."""
    _add_account(seed_db, "m@t.com")
    _add_card(seed_db, "4111111111111111", "m@t.com")  # married — no debe usarse

    # Sin pool: aunque exista married, la cuenta queda sin tarjeta asignada
    plan_empty_pool = plan_auto_mission(seed_db, [], amount=150, target_count=9)
    assert "m@t.com" not in [a["email"] for a in plan_empty_pool["accounts"]]

    # Con pool: se asigna la del pool, jamás la married
    plan_with_pool = plan_auto_mission(seed_db, ["4333333333333333|0131|999"], amount=150, target_count=9)
    m_entry = next(a for a in plan_with_pool["accounts"] if a["email"] == "m@t.com")
    assert m_entry["card_pipe"] == "4333333333333333|0131|999"


def test_plan_assigns_pool_cards(seed_db):
    _add_account(seed_db, "p@t.com")
    plan = plan_auto_mission(seed_db, ["4333333333333333|0131|999"], amount=150, target_count=9)
    assert plan["feasible"] is True
    assert plan["accounts"][0]["card_pipe"] == "4333333333333333|0131|999"


def test_plan_normalizes_4part_pool_cards(seed_db):
    _add_account(seed_db, "p2@t.com")
    plan = plan_auto_mission(seed_db, ["4333333333333333|01|2031|999"], amount=150, target_count=9)
    assert plan["feasible"] is True
    assert plan["accounts"][0]["card_pipe"] == "4333333333333333|0131|999"


def test_plan_feasibility_check(seed_db):
    # seed base: a@ lockeada, c@ DEAD → solo b@ (LIVE, sin JWT) es candidata.
    plan = plan_auto_mission(seed_db, ["4555555555555555|1230|123"], amount=150, target_count=9)
    assert plan["feasible"] is True
    assert any(r["email"] == "b@test.com" for r in plan["accounts"])


def test_plan_estimates_total(seed_db):
    _add_account(seed_db, "t1@t.com")
    _add_account(seed_db, "t2@t.com")
    # 3 tarjetas distintas para 3 cuentas (1:1 estricto)
    cards = ["4999999999999999|0130|999", "4888888888888888|0130|999", "4777777777777777|0130|999"]
    plan = plan_auto_mission(seed_db, cards, amount=150, target_count=9)
    assert len(plan["accounts"]) == 3
    assert plan["total_estimated"] == 150 * 9 * 3
    assigned_pipes = [a["card_pipe"] for a in plan["accounts"]]
    assert len(set(assigned_pipes)) == 3  # Cada cuenta tiene su propia tarjeta única


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
    _add_rejected_attempt(seed_db, "burned@t.com", hours_ago=1)
    _add_rejected_attempt(seed_db, "burned@t.com", hours_ago=2)
    plan = plan_auto_mission(seed_db, ["4999999999999999|0130|999"], amount=150, target_count=9)
    assert "burned@t.com" not in [r["email"] for r in plan["accounts"]]
    assert plan["accounts"]  # b@ del seed sigue entrando (sin declines)


def test_plan_max_accounts_scales_with_card_count(seed_db):
    """Regla: 1 tarjeta = 1 cuenta (máximo tantas cuentas como tarjetas disponibles)."""
    for i in range(6):
        _add_account(seed_db, f"u{i}@t.com")
    plan_1card = plan_auto_mission(seed_db, ["4999999999999999|0130|999"],
                                    amount=150, target_count=9)
    plan_3cards = plan_auto_mission(
        seed_db,
        ["4999999999999999|0130|999", "4888888888888888|0130|999",
         "4777777777777777|0130|999"],
        amount=150, target_count=9)
    assert len(plan_1card["accounts"]) == 1  # 1 tarjeta -> 1 cuenta
    assert len(plan_3cards["accounts"]) == 3  # 3 tarjetas -> 3 cuentas


def test_plan_max_accounts_hard_cap_at_10(seed_db):
    """Regla Robert: tope duro de 10 cuentas por corrida y 1:1 tarjeta/cuenta."""
    for i in range(15):
        _add_account(seed_db, f"v{i}@t.com")
    many_cards = [f"49{i:014d}|0130|999" for i in range(12)]  # 12 tarjetas distintas -> tope 10
    plan = plan_auto_mission(seed_db, many_cards, amount=10, target_count=20, max_accounts=10)
    assert len(plan["accounts"]) == 10
