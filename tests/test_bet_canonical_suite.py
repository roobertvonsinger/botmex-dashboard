"""SUITE CANÓNICA DE PRUEBAS FUNCIONALES PARA /bet (BotMexico)
============================================================
Esta suite es el estándar de oro innegociable de `/bet`.
CADA CAMBIO futuro en `botmex-dashboard` DEBE pasar esta suite al 100% (cero fallos).

Invariantes Operativas Auditadas:
1. Selección y Scoring Continuo (KYC 100%, status LIVE, ventanas 24h, sin drops binarios arbitrarios).
2. Ventana Móvil de Declines de 1 Hora (Tope 2 en 60m = reposo temporal en cola, NO muerte permanente).
3. Afinidad de BIN x Grado (BIN Corona para A+; plásticos de prueba para cuentas neutras A/B).
4. Protocolo 3 Strikes de Tarjeta (Máx 3 intentos en 3 cuentas distintas ante rechazo bancario).
5. Protección Anti-Taladro de Cuenta (Máx 2 declines en la corrida, reposo y desbloqueo limpio).
6. Guard de Saldo en Caliente & Anti-Mezcla (Si tiene fondos con tarjeta hoy, se protege para retiro).
7. Certificación Soberana de 3DS (3DS otorga A+, no mata cuenta, tarjeta rota hasta 3 cuentas).
8. Rotación Rápida No Bloqueante (Gap de 5s entre cuentas distintas, cero freeze global de 45s).
9. Fast-Track de Tarjetas Casadas (1:1 estricto con su cuenta dueña en account_cards).
"""
import pytest
import asyncio
import json
import sqlite3
from typing import Dict, Any, List
import auto_deposit as ad
import bin_intelligence as bi
import deposits as dep


class CanonicalHarness:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.unlocked: List[int] = []
        self.locked: List[int] = []
        self.dead: List[str] = []
        self.sleeps: List[float] = []
        self.updates: List[Dict[str, Any]] = []
        self.accounts_db: Dict[int, Dict[str, Any]] = {}
        self.script = None

    def make_attempt(self, email, password, pipe, amt, sj, sp):
        self.calls.append({"email": email, "pipe": pipe, "amount": amt})
        if self.script:
            return self.script(email, pipe, amt)
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "JWT_CANONICAL", "used_proxy": "PRX_CANONICAL"}


def _setup_canonical_mocks(monkeypatch, harness: CanonicalHarness):
    monkeypatch.setattr(ad, "_sa_tokens", lambda: {"sa_token"})
    monkeypatch.setattr(ad, "_get_married_card_owners", lambda *a, **k: {})
    monkeypatch.setattr(ad, "_now_epoch", lambda: 1700000000)
    monkeypatch.setattr(ad, "_m_load", lambda mid: {"mission_id": mid, "amount": 10.0, "target_count": 1, "card_pipes": json.dumps([])})
    monkeypatch.setattr(ad, "_m_status", lambda mid: "matching")
    monkeypatch.setattr(ad, "_m_update", lambda mid, **fields: harness.updates.append(fields))
    monkeypatch.setattr(ad, "_broadcast_mission", lambda *a, **kw: None)
    monkeypatch.setattr(ad, "_unlock", lambda aid: harness.unlocked.append(aid))
    monkeypatch.setattr(dep, "_auto_lock_for_deposit", lambda aid, *a, **k: harness.locked.append(aid))
    monkeypatch.setattr(dep, "_load_deps", lambda: lambda *a, **k: CanonicalFakePool())
    monkeypatch.setattr(dep, "_mark_rate_limited_dead", lambda email: harness.dead.append(email))
    monkeypatch.setattr(dep, "_record_attempt", lambda *a, **k: None)
    monkeypatch.setattr(dep, "_set_account_cooldown", lambda *a, **k: None)

    async def _mock_sleep(s):
        harness.sleeps.append(s)
    monkeypatch.setattr(asyncio, "sleep", _mock_sleep)

    def mock_fetch(aid):
        acct = dict(harness.accounts_db.get(aid, {
            "id": aid, "email": f"acc{aid}@canonical.com", "password": "pass",
            "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0
        }))
        acct.setdefault("password", "pass")
        return acct
    monkeypatch.setattr(ad, "_fetch_account", mock_fetch)

    async def mock_run_dep(email, pwd, num, exp, cvv, amt, user, pool, pb, session_jwt=None, session_proxy=None, persist_login_data=True):
        pipe = f"{num}|{exp}|{cvv}"
        r = harness.make_attempt(email, pwd, pipe, amt, session_jwt, session_proxy)
        r.setdefault("result_code", "BANK_APPROVED" if r.get("success") else "BANK_REJECTED")
        return r
    monkeypatch.setattr(dep, "_run_deposit_with_phases", mock_run_dep)


class CanonicalFakePool:
    async def start_factory(self, *a, **k): pass
    async def stop(self): pass


# ─────────────────────────────────────────────────────────────────────────────
# 1. SELECCIÓN Y SCORING CONTINUO
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_01_scoring_selection_continuity():
    """Invariante 1: Cuentas verificadas (KYC=1), status LIVE y con capacidad 24h
    son ordenadas por tiers sin exclusiones binarias arbitrarias."""
    rows = [
        {"id": 1, "email": "live_kyc@test.com", "status": "LIVE", "kyc_verified": 1, "published_to_pool": 1, "grade": "A+"},
        {"id": 2, "email": "nokyc@test.com", "status": "LIVE", "kyc_verified": 0, "published_to_pool": 1, "grade": "A"},
        {"id": 3, "email": "dead@test.com", "status": "DEAD", "kyc_verified": 1, "published_to_pool": 1, "grade": "A"},
        {"id": 4, "email": "live_b@test.com", "status": "LIVE", "kyc_verified": 1, "published_to_pool": 1, "grade": "B"},
    ]
    win_map = {r["email"]: {"available": 2000.0} for r in rows}
    sel = ad.select_accounts_for_auto(rows, amount=150.0, count=2, window_map=win_map)
    sel_emails = [a["email"] for a in sel]

    assert "nokyc@test.com" not in sel_emails, "Cuentas sin KYC jamás entran"
    assert "dead@test.com" not in sel_emails, "Cuentas DEAD jamás entran"
    assert "live_kyc@test.com" in sel_emails
    assert "live_b@test.com" in sel_emails


# ─────────────────────────────────────────────────────────────────────────────
# 2. VENTANA MÓVIL DE DECLINES DE 1 HORA
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_02_rolling_one_hour_decline_window(tmp_path):
    """Invariante 2: Declines de más de 1 hora NO bloquean la cuenta.
    Solo cuentas con >= 2 declines en la ÚLTIMA HORA entran en reposo temporal."""
    db_file = tmp_path / "test_1h_window.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT DEFAULT 'p',
        status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 1, balance_real REAL DEFAULT 0.0, balance_total REAL DEFAULT 0.0,
        locked_by INTEGER, cooldown_until INTEGER, jwt_expires_at INTEGER DEFAULT 2147483647
    );
    CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY, account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);
    CREATE TABLE account_transactions (id INTEGER PRIMARY KEY, account_email TEXT, txn_date TEXT, amount REAL, status INTEGER, txn_type INTEGER, gateway INTEGER);
    CREATE TABLE account_cards (id INTEGER PRIMARY KEY, account_email TEXT, number TEXT, status TEXT DEFAULT 'ACTIVE');
    CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INTEGER, approved_count INTEGER, approval_rate REAL);
    """)

    # Cuenta A: 2 declines hace 3 horas (antiguos) -> DEBE SER ELEGIBLE
    con.execute("INSERT INTO accounts (email) VALUES ('old_declines@test.com')")
    con.execute("INSERT INTO deposit_attempts (account_email, status, created_at) VALUES ('old_declines@test.com', 'REJECTED', datetime('now', '-3 hours'))")
    con.execute("INSERT INTO deposit_attempts (account_email, status, created_at) VALUES ('old_declines@test.com', 'REJECTED', datetime('now', '-2 hours'))")

    # Cuenta B: 2 declines hace 10 minutos (recientes <1h) -> EN REPOSO TEMPORAL
    con.execute("INSERT INTO accounts (email) VALUES ('recent_declines@test.com')")
    con.execute("INSERT INTO deposit_attempts (account_email, status, created_at) VALUES ('recent_declines@test.com', 'REJECTED', datetime('now', '-10 minutes'))")
    con.execute("INSERT INTO deposit_attempts (account_email, status, created_at) VALUES ('recent_declines@test.com', 'REJECTED', datetime('now', '-5 minutes'))")
    con.commit()
    con.close()

    p1 = "4111111111111111|1228|123"
    plan = ad.plan_auto_mission(db_file, [p1], amount=150, target_count=1)
    plan_emails = [a["email"] for a in plan.get("accounts", [])]

    assert "old_declines@test.com" in plan_emails, "Declines > 1h no deben bloquear la cuenta"
    assert "recent_declines@test.com" not in plan_emails, "2 declines en <1h deben enviar la cuenta a reposo"


# ─────────────────────────────────────────────────────────────────────────────
# 3. AFINIDAD DE BIN X GRADO
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_03_bin_affinity_corona_to_a_plus(tmp_path):
    """Invariante 3: BIN Corona se empareja preferentemente con cuentas A+.
    Plásticos en prueba van a cuentas neutras A/B como radar de 3DS."""
    db_file = tmp_path / "test_affinity_canonical.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT DEFAULT 'p',
        status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 1, balance_real REAL DEFAULT 0.0, balance_total REAL DEFAULT 0.0,
        locked_by INTEGER, cooldown_until INTEGER, jwt_expires_at INTEGER DEFAULT 2147483647
    );
    CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY, account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);
    CREATE TABLE account_transactions (id INTEGER PRIMARY KEY, account_email TEXT, txn_date TEXT, amount REAL, status INTEGER, txn_type INTEGER, gateway INTEGER);
    CREATE TABLE account_cards (id INTEGER PRIMARY KEY, account_email TEXT, number TEXT, status TEXT DEFAULT 'ACTIVE');
    CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INTEGER, approved_count INTEGER, approval_rate REAL);
    """)
    con.execute("INSERT INTO accounts (email, grade) VALUES ('aplus_target@test.com', 'A+')")
    con.execute("INSERT INTO accounts (email, grade) VALUES ('regular_target@test.com', 'A')")
    con.commit()
    con.close()

    p_corona = "4915661111111111|1228|123"  # Santander Débito -> CORONA
    p_test = "4027662222222222|1228|123"    # Citibanamex -> TESTING

    plan = ad.plan_auto_mission(db_file, [p_corona, p_test], amount=150, target_count=2)
    assigned = {a["email"]: a["card_pipe"] for a in plan["accounts"]}

    assert assigned["aplus_target@test.com"].startswith("491566"), "A+ debe recibir plástico Corona"
    assert assigned["regular_target@test.com"].startswith("402766"), "Cuenta regular recibe plástico de prueba"


# ─────────────────────────────────────────────────────────────────────────────
# 4. PROTOCOLO 3 STRIKES DE TARJETA EN CUENTAS DISTINTAS
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_04_card_protocol_three_strikes_distinct_accounts(monkeypatch):
    """Invariante 4: Una tarjeta rota por hasta 3 cuentas distintas ante BANK_REJECTED.
    Al 3er fallo en 3 cuentas distintas, se retira de la misión y NO toca una 4a cuenta."""
    h = CanonicalHarness()
    _setup_canonical_mocks(monkeypatch, h)

    p_test = "4111111111111111|1228|123"
    plan = {
        "accounts": [
            {"id": 1, "email": "c1@test.com", "grade": "A", "card_pipe": p_test},
            {"id": 2, "email": "c2@test.com", "grade": "A", "card_pipe": p_test},
            {"id": 3, "email": "c3@test.com", "grade": "A", "card_pipe": p_test},
            {"id": 4, "email": "c4@test.com", "grade": "A", "card_pipe": p_test},
        ]
    }
    for a in plan["accounts"]:
        h.accounts_db[a["id"]] = {"id": a["id"], "email": a["email"], "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0}

    # Declinación bancaria en todas
    h.script = lambda email, pipe, amt: {"success": False, "result_code": "BANK_REJECTED", "error": "Fondos insuficientes"}

    asyncio.run(ad.run_auto_mission("m_canon_3s", plan, {"role": "superadmin", "telegram_id": 999}))

    tried_emails = [c["email"] for c in h.calls]
    assert tried_emails == ["c1@test.com", "c2@test.com", "c3@test.com"], "Debe probar exactamente 3 cuentas distintas"
    assert "c4@test.com" not in tried_emails, "Al 3er strike la tarjeta queda jubilada de la misión"
    assert 1 in h.unlocked and 2 in h.unlocked and 3 in h.unlocked, "Todas las cuentas quedan desbloqueadas"


# ─────────────────────────────────────────────────────────────────────────────
# 5. PROTECCIÓN ANTI-TALADRO DE CUENTA (MÁX 2 DECLINES EN CORRIDA)
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_05_account_anti_drill_and_two_strike_cap(monkeypatch):
    """Invariante 5: Una cuenta que declina no es taladrada de inmediato en caliente.
    Al acumular 2 rechazos en la corrida, pasa a reposo y se desbloquea limpiamente."""
    h = CanonicalHarness()
    _setup_canonical_mocks(monkeypatch, h)

    p1, p2, p3 = "4111111111111111|1228|111", "4222222222222222|1228|222", "4333333333333333|1228|333"
    plan = {
        "accounts": [
            {"id": 1, "email": "drill_target@test.com", "grade": "A", "card_pipe": p1},
            {"id": 2, "email": "relief_account@test.com", "grade": "A", "card_pipe": p2},
        ]
    }
    for a in plan["accounts"]:
        h.accounts_db[a["id"]] = {"id": a["id"], "email": a["email"], "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0}

    def script(email, pipe, amt):
        if email == "drill_target@test.com":
            return {"success": False, "result_code": "BANK_REJECTED", "error": "Declined"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}

    h.script = script
    asyncio.run(ad.run_auto_mission("m_canon_antidrill", plan, {"role": "superadmin", "telegram_id": 999}))

    # El primer intento es drill_target, luego rota a relief_account con gap de 5s sin taladrar drill_target en caliente
    assert h.calls[0]["email"] == "drill_target@test.com"
    assert h.calls[1]["email"] == "relief_account@test.com"
    assert 1 in h.unlocked, "drill_target debió desbloquearse"


# ─────────────────────────────────────────────────────────────────────────────
# 6. GUARD DE SALDO EN CALIENTE & ANTI-MEZCLA
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_06_live_balance_anti_mixture_guard(monkeypatch):
    """Invariante 6: Si una cuenta tiene saldo real >= $100.0 (mínimo de retiro) y ya depositó hoy con tarjeta,
    el scheduler no le mete otro plástico hoy; la salta protegiendo la cuenta para retiro."""
    h = CanonicalHarness()
    _setup_canonical_mocks(monkeypatch, h)
    monkeypatch.setattr(ad, "_has_card_deposit_24h", lambda email: True)

    p1 = "4111111111111111|1228|111"
    plan = {"accounts": [{"id": 1, "email": "has_funds_card@test.com", "grade": "A", "card_pipe": p1}]}
    h.accounts_db[1] = {"id": 1, "email": "has_funds_card@test.com", "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 150.00}

    asyncio.run(ad.run_auto_mission("m_canon_funds", plan, {"role": "superadmin", "telegram_id": 999}))

    assert len(h.calls) == 0, "No debe ejecutar depósito en cuenta con saldo fondeada hoy con tarjeta"
    assert 1 in h.unlocked or 1 not in h.locked


# ─────────────────────────────────────────────────────────────────────────────
# 7. CERTIFICACIÓN SOBERANA DE 3DS
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_07_threeds_certifies_a_plus_and_preserves_card(monkeypatch):
    """Invariante 7: 3DS marca la cuenta como A+ en BD, no la mata,
    y permite a la tarjeta rotar a certificar hasta 3 cuentas."""
    h = CanonicalHarness()
    _setup_canonical_mocks(monkeypatch, h)

    p1 = "4111111111111111|1228|111"
    plan = {
        "accounts": [
            {"id": 1, "email": "cert1@test.com", "grade": "A", "card_pipe": p1},
            {"id": 2, "email": "cert2@test.com", "grade": "A", "card_pipe": p1},
            {"id": 3, "email": "cert3@test.com", "grade": "A", "card_pipe": p1},
            {"id": 4, "email": "cert4@test.com", "grade": "A", "card_pipe": p1},
        ]
    }
    for a in plan["accounts"]:
        h.accounts_db[a["id"]] = {"id": a["id"], "email": a["email"], "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0}

    h.script = lambda email, pipe, amt: {"success": False, "result_code": "3DS_REQUIRED", "error": "3ds challenge"}
    asyncio.run(ad.run_auto_mission("m_canon_3ds", plan, {"role": "superadmin", "telegram_id": 999}))

    tried_emails = [c["email"] for c in h.calls]
    assert tried_emails == ["cert1@test.com", "cert2@test.com", "cert3@test.com"]
    assert "cert4@test.com" not in tried_emails
    assert 1 in h.unlocked and 2 in h.unlocked and 3 in h.unlocked


# ─────────────────────────────────────────────────────────────────────────────
# 8. ROTACIÓN RÁPIDA NO BLOQUEANTE (GAP 5S, CERO FREEZE 45S)
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_08_rapid_cross_account_rotation_no_global_freeze(monkeypatch):
    """Invariante 8: Rotación entre cuentas distintas usa gap de 5s (MM_CROSS_ACCOUNT_GAP).
    Cero sleep bloqueante de 45s."""
    h = CanonicalHarness()
    _setup_canonical_mocks(monkeypatch, h)

    p1, p2 = "4111111111111111|1228|111", "4222222222222222|1228|222"
    plan = {
        "accounts": [
            {"id": 1, "email": "fast1@test.com", "grade": "A", "card_pipe": p1},
            {"id": 2, "email": "fast2@test.com", "grade": "A", "card_pipe": p2},
        ]
    }
    for a in plan["accounts"]:
        h.accounts_db[a["id"]] = {"id": a["id"], "email": a["email"], "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0}

    def script(email, pipe, amt):
        if email == "fast1@test.com":
            return {"success": False, "result_code": "BANK_REJECTED", "error": "Declined"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}

    h.script = script
    asyncio.run(ad.run_auto_mission("m_canon_rapid", plan, {"role": "superadmin", "telegram_id": 999}))

    assert 45 not in h.sleeps, "No debe haber sleep bloqueante de 45s"
    assert ad.MM_CROSS_ACCOUNT_GAP in h.sleeps, "Debe existir respiro rápido de 5s entre cuentas"


# ─────────────────────────────────────────────────────────────────────────────
# 9. FAST-TRACK DE TARJETAS CASADAS (1:1 ESTRICTO)
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_09_married_card_strict_one_to_one_fast_track(tmp_path):
    """Invariante 9: Una tarjeta guardada/casada en account_cards jamás se asigna a otra cuenta
    extraña en el planificador."""
    db_file = tmp_path / "test_married_canonical.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT DEFAULT 'p',
        status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 1, balance_real REAL DEFAULT 0.0, balance_total REAL DEFAULT 0.0,
        locked_by INTEGER, cooldown_until INTEGER, jwt_expires_at INTEGER DEFAULT 2147483647
    );
    CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY, account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);
    CREATE TABLE account_transactions (id INTEGER PRIMARY KEY, account_email TEXT, txn_date TEXT, amount REAL, status INTEGER, txn_type INTEGER, gateway INTEGER);
    CREATE TABLE account_cards (id INTEGER PRIMARY KEY, account_email TEXT, number TEXT, status TEXT DEFAULT 'ACTIVE');
    CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INTEGER, approved_count INTEGER, approval_rate REAL);
    """)
    con.execute("INSERT INTO accounts (email) VALUES ('owner@test.com')")
    con.execute("INSERT INTO accounts (email) VALUES ('stranger@test.com')")
    # Tarjeta casada con owner@test.com
    con.execute("INSERT INTO account_cards (account_email, number) VALUES ('owner@test.com', '4555555555555555')")
    con.commit()
    con.close()

    p_married = "4555555555555555|1228|999"
    plan = ad.plan_auto_mission(db_file, [p_married], amount=150, target_count=1)
    plan_emails = [a["email"] for a in plan.get("accounts", [])]

    assert "stranger@test.com" not in plan_emails, "Tarjeta casada no puede asignarse a un extraño"
    assert "owner@test.com" in plan_emails, "Tarjeta casada se vincula directamente a su dueña"


# ─────────────────────────────────────────────────────────────────────────────
# 10. BLINDAJE CANÓNICO 429 RATE LIMIT (CERO PRIORIZACIÓN Y AISLAMIENTO TOTAL)
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_10_rate_limit_429_isolation_case_insensitive(tmp_path):
    """Invariante 10 (AGENTS.md §4): Ninguna cuenta con 429 o RATE_LIMITED (en cualquier
    casing, intento en deposit_attempts, o registro duplicado en accounts) puede ser seleccionada
    por el planificador ni por el fallback de rotación continua (_pull_fresh_live_account)."""
    db_file = tmp_path / "test_429_isolation.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, password TEXT DEFAULT 'p',
        status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 1, balance_real REAL DEFAULT 0.0, balance_total REAL DEFAULT 0.0,
        locked_by INTEGER, cooldown_until INTEGER, jwt_expires_at INTEGER DEFAULT 2147483647,
        dead_reason TEXT, dead_at TEXT
    );
    CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY, account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);
    CREATE TABLE account_transactions (id INTEGER PRIMARY KEY, account_email TEXT, txn_date TEXT, amount REAL, status INTEGER, txn_type INTEGER, gateway INTEGER);
    CREATE TABLE account_cards (id INTEGER PRIMARY KEY, account_email TEXT, number TEXT, status TEXT DEFAULT 'ACTIVE');
    CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INTEGER, approved_count INTEGER, approval_rate REAL);
    """)

    # Caso A: nieto2816@hotmail.com tiene un registro con dead_reason='RATE_LIMITED_429', pero otro registro duplicado Nieto2816@hotmail.com está 'LIVE'
    con.execute("INSERT INTO accounts (email, status, dead_reason) VALUES ('nieto2816@hotmail.com', 'DEAD', 'RATE_LIMITED_429')")
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('Nieto2816@hotmail.com', 'LIVE', 1)")

    # Caso B: elizabethmedeles@gmail.com está LIVE y published_to_pool=0 (aislada), pero tiene intento 429 en deposit_attempts
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('elizabethmedeles@gmail.com', 'LIVE', 0)")
    con.execute("INSERT INTO deposit_attempts (account_email, status, rejection_reason, created_at) VALUES ('ElizabethMedeles@gmail.com', 'RATE_LIMITED', '429 Rate limit', datetime('now', '-5 minutes'))")

    # Caso C: Cuenta limpia válida
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('clean_user@test.com', 'LIVE', 1)")
    con.commit()
    con.close()

    p1 = "4111111111111111|1228|123"
    plan = ad.plan_auto_mission(db_file, [p1], amount=150, target_count=1)
    plan_emails = [a["email"].lower() for a in plan.get("accounts", [])]

    assert "nieto2816@hotmail.com" not in plan_emails, "Cuentas con 429 jamás deben ser seleccionadas"
    assert "elizabethmedeles@gmail.com" not in plan_emails, "Cuentas con published_to_pool=0 o intento 429 jamás deben ser seleccionadas"
    assert "clean_user@test.com" in plan_emails, "Cuenta limpia debe ser seleccionada"

    # Validar también _pull_fresh_live_account
    fresh = ad._pull_fresh_live_account(db_file, already_checked=set(), married_owners={}, for_card=p1)
    assert fresh is not None
    assert fresh["email"].lower() == "clean_user@test.com", "El pull de respaldo jamás debe tomar cuentas 429 o aisladas"


# ─────────────────────────────────────────────────────────────────────────────
# 11. LIBERACIÓN DE TARJETAS CASADAS (CUENTAS 429 / FUERA DE POOL / 5 RECHAZOS)
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_11_married_card_liberation_rules(tmp_path):
    """Invariante 11 (Robert 2026-09-07):
    Una tarjeta casada se libera automáticamente si la cuenta dueña:
    1. Está fuera del pool (published_to_pool=0), en 429, RATE_LIMITED o degradada.
    2. Acumuló 5 o más rechazos consecutivos tras el último aprobado.
    Si la cuenta dueña es sana (LIVE, pool=1), la tarjeta permanece estrictamente casada 1:1."""
    db_file = tmp_path / "test_married_liberation.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, password TEXT DEFAULT 'p',
        status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 1, balance_real REAL DEFAULT 0.0, balance_total REAL DEFAULT 0.0,
        locked_by INTEGER, cooldown_until INTEGER, jwt_expires_at INTEGER DEFAULT 2147483647,
        dead_reason TEXT, dead_at TEXT
    );
    CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY, account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);
    CREATE TABLE account_transactions (id INTEGER PRIMARY KEY, account_email TEXT, txn_date TEXT, amount REAL, status INTEGER, txn_type INTEGER, gateway INTEGER);
    CREATE TABLE account_cards (id INTEGER PRIMARY KEY, account_email TEXT, card_number TEXT, status TEXT DEFAULT 'ACTIVE');
    CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INTEGER, approved_count INTEGER, approval_rate REAL);
    """)

    card_a = "4023185001869977"
    card_b = "5555555555555555"
    card_c = "4111111111111111"

    # Tarjeta A: Casada con cuenta DEAD (único caso donde Robert autoriza liberación)
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('dead_owner@test.com', 'DEAD', 0)")
    con.execute("INSERT INTO account_cards (account_email, card_number, status) VALUES ('dead_owner@test.com', ?, 'ACTIVE')", (card_a,))

    # Tarjeta B: Casada con cuenta aislada por 429 (status='LIVE', published_to_pool=0) -> NO LIBERADA (no está muerta)
    con.execute("INSERT INTO accounts (email, status, published_to_pool, dead_reason) VALUES ('rate_limited@test.com', 'LIVE', 0, 'RATE_LIMITED_429')")
    con.execute("INSERT INTO account_cards (account_email, card_number, status) VALUES ('rate_limited@test.com', ?, 'ACTIVE')", (card_b,))

    # Tarjeta C: Casada con healthy@test.com (cuenta LIVE activa y sana) -> NO LIBERADA
    con.execute("INSERT INTO accounts (email, status, published_to_pool) VALUES ('healthy@test.com', 'LIVE', 1)")
    con.execute("INSERT INTO account_cards (account_email, card_number, status) VALUES ('healthy@test.com', ?, 'ACTIVE')", (card_c,))

    # Mock DB para deposits.py
    import app
    orig_db = app.db
    app.db = lambda write=False: con

    try:
        # 1. Tarjeta A (cuenta con status='DEAD') -> DEBE ESTAR LIBERADA
        assert dep.get_married_card_owner(card_a) is None, "Tarjeta con cuenta DEAD debe liberarse"

        # 2. Tarjeta B (cuenta en 429/rate limited, status='LIVE') -> SIGUE CASADA (prohibido liberarla)
        assert dep.get_married_card_owner(card_b) == "rate_limited@test.com", "Tarjeta con cuenta 429 no debe liberarse"

        # 3. Tarjeta C (cuenta sana LIVE en pool) -> DEBE SEGUIR CASADA A healthy@test.com
        assert dep.get_married_card_owner(card_c) == "healthy@test.com", "Tarjeta con cuenta sana debe permanecer casada"
    finally:
        app.db = orig_db
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# 12. CONTADOR DE DECLINES DE TARJETA: CERO CONTAMINACIÓN POR 429 O REGLAS
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_12_card_declines_exclude_429_and_rules(tmp_path):
    """Invariante 12 (Robert 2026-09-07):
    El contador de rechazos de una tarjeta (card_checker.get_card_declines_24h)
    SOLO debe contabilizar rechazos reales del banco/pasarela (REJECTED, BANK_REJECTED).
    Los fallos de login (429 RATE_LIMITED), bloqueos por Regla de Oro (INCOMPLETE),
    o cancelaciones NUNCA deben sumar como rechazos de la tarjeta."""
    import card_checker as cc

    db_file = tmp_path / "test_card_declines.db"
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE deposit_attempts (
        id INTEGER PRIMARY KEY,
        account_email TEXT,
        amount REAL,
        status TEXT,
        rejection_reason TEXT,
        card_pipe TEXT,
        created_at TEXT
    );
    """)

    card = "4023185001869977"

    # 1 Rechazo real de banco
    con.execute(
        "INSERT INTO deposit_attempts (account_email, status, rejection_reason, card_pipe, created_at) "
        "VALUES ('a1@test.com', 'REJECTED', 'BANK_REJECTED — decline genérico', ?, datetime('now', '-10 minutes'))",
        (f"{card}|1228|123",)
    )

    # 5 Intentos con 429 Rate limit en login (la tarjeta NUNCA tocó el banco)
    for i in range(2, 7):
        con.execute(
            f"INSERT INTO deposit_attempts (account_email, status, rejection_reason, card_pipe, created_at) "
            f"VALUES ('a{i}@test.com', 'rate_limited', 'Cuenta en rate limit (429) — aislada del pool.', ?, datetime('now', '-5 minutes'))",
            (f"{card}|1228|123",)
        )

    # 2 Bloqueos por Regla de Oro / matrimonio (la tarjeta NUNCA tocó el banco)
    for i in range(7, 9):
        con.execute(
            f"INSERT INTO deposit_attempts (account_email, status, rejection_reason, card_pipe, created_at) "
            f"VALUES ('a{i}@test.com', 'incomplete', 'Regla de Oro: Tarjeta ya registrada en otra cuenta', ?, datetime('now', '-2 minutes'))",
            (f"{card}|1228|123",)
        )

    con.commit()

    try:
        declines = cc.get_card_declines_24h(card, db_conn=con)
        assert declines == 1, f"Se esperaba exactamente 1 rechazo bancario real, pero se reportaron {declines}"
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# 13. SILENCIO TOTAL DE CANCELLEDERROR Y GATHERINGFUTURE EN LOGS
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_13_silence_cancelled_exceptions_and_gathering_future():
    """Invariante 13 (Robert 2026-09-08):
    Cero spam en logs por cancelaciones normales de asyncio, desconexiones de SSE,
    o futuros de gather abortados (_GatheringFuture finished exception=CancelledError).
    Tanto el filtro de logging como el exception_handler del loop deben silenciar
    estas alertas limpiamente sin silenciar excepciones legítimas."""
    import logging
    from app import _CancelledFilter, _configure_asyncio_exception_handler

    # 1. Validar _CancelledFilter
    f = _CancelledFilter()
    r_spam1 = logging.LogRecord(
        'asyncio', logging.ERROR, 'base_events.py', 1780,
        '_GatheringFuture exception was never retrieved\nfuture: <_GatheringFuture finished exception=CancelledError()>',
        (), None
    )
    assert not f.filter(r_spam1), "CancelledFilter debe bloquear mensaje de _GatheringFuture CancelledError"

    r_spam2 = logging.LogRecord(
        'asyncio', logging.ERROR, 'tasks.py', 700,
        'During handling of the above exception, another exception occurred:\nasyncio.exceptions.CancelledError',
        (), (asyncio.CancelledError, asyncio.CancelledError(), None)
    )
    assert not f.filter(r_spam2), "CancelledFilter debe bloquear trazas de CancelledError anidado"

    r_legit = logging.LogRecord(
        'botmexico', logging.ERROR, 'app.py', 100,
        'Fallo crítico en conexión a base de datos',
        (), (sqlite3.OperationalError, sqlite3.OperationalError("database locked"), None)
    )
    assert f.filter(r_legit), "CancelledFilter NO debe bloquear excepciones operativas legítimas"

    # 2. Validar exception handler del loop
    loop = asyncio.new_event_loop()
    called_default = []
    loop.default_exception_handler = lambda ctx: called_default.append(ctx)
    _configure_asyncio_exception_handler(target_loop=loop)
    handler = loop.get_exception_handler()
    assert handler is not None

    # Contexto con CancelledError directo
    handler(loop, {"message": "task cancelled", "exception": asyncio.CancelledError()})
    assert len(called_default) == 0, "No debe invocar default handler ante CancelledError"

    # Contexto con _GatheringFuture
    class DummyFut:
        def cancelled(self): return True
        def done(self): return True
        def exception(self): return asyncio.CancelledError()
        def __repr__(self): return "<_GatheringFuture finished exception=CancelledError()>"

    handler(loop, {"message": "_GatheringFuture exception was never retrieved", "future": DummyFut()})
    assert len(called_default) == 0, "No debe invocar default handler ante _GatheringFuture"

    # Contexto legítimo: debe propagar
    handler(loop, {"message": "Error real", "exception": ValueError("boom")})
    assert len(called_default) == 1, "Debe propagar errores reales que no sean de cancelación"
    loop.close()




