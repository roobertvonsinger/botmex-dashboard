"""Unit tests para el Scheduler Continuo de Auto-Depósito, Afinidad de BIN y Protocolo 3 Strikes.
Valida:
1. Afinidad de BIN: Cuentas A+ prefieren plásticos CORONA; plásticos en prueba van a cuentas neutrales.
2. Protocolo 3 Strikes de Tarjeta: La tarjeta rota por hasta 3 cuentas distintas antes de retirarse.
3. Protección de Cuenta: Máximo 2 declines en 1h; una cuenta con 1 decline rota la tarjeta sin recibir taladro en caliente.
4. Rotación limpia con MM_CROSS_ACCOUNT_GAP (5s) sin sleep bloqueante de 45s entre cuentas distintas.
5. Guard de saldo en vivo: Si una cuenta tiene o actualiza balance_real >= 10.0, no se le ensarta otra tarjeta.
"""
import pytest
import asyncio
import json
from typing import Dict, Any, List
import auto_deposit as ad
import bin_intelligence as bi
import deposits as dep


class MockHarness:
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
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "JWT_OK", "used_proxy": "PRX"}


def _setup_ad_mocks(monkeypatch, harness: MockHarness):
    monkeypatch.setattr(ad, "_sa_tokens", lambda: {"sa_token"})
    monkeypatch.setattr(ad, "_get_married_card_owners", lambda *a, **k: {})
    monkeypatch.setattr(ad, "_now_epoch", lambda: 1700000000)
    monkeypatch.setattr(ad, "_m_load", lambda mid: {"mission_id": mid, "amount": 10.0, "target_count": 1, "card_pipes": json.dumps([])})
    monkeypatch.setattr(ad, "_m_status", lambda mid: "matching")
    monkeypatch.setattr(ad, "_m_update", lambda mid, **fields: harness.updates.append(fields))
    monkeypatch.setattr(ad, "_broadcast_mission", lambda *a, **kw: None)
    monkeypatch.setattr(ad, "_unlock", lambda aid: harness.unlocked.append(aid))
    monkeypatch.setattr(dep, "_auto_lock_for_deposit", lambda aid, *a, **k: harness.locked.append(aid))
    monkeypatch.setattr(dep, "_load_deps", lambda: lambda *a, **k: MockPool())
    monkeypatch.setattr(dep, "_mark_rate_limited_dead", lambda email: harness.dead.append(email))
    monkeypatch.setattr(dep, "_record_attempt", lambda *a, **k: None)
    monkeypatch.setattr(dep, "_set_account_cooldown", lambda *a, **k: None)

    async def _mock_sleep(s):
        harness.sleeps.append(s)
    monkeypatch.setattr(asyncio, "sleep", _mock_sleep)

    def mock_fetch(aid):
        return harness.accounts_db.get(aid, {
            "id": aid, "email": f"acc{aid}@test.com", "password": "pass",
            "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0
        })
    monkeypatch.setattr(ad, "_fetch_account", mock_fetch)

    async def mock_run_dep(email, pwd, num, exp, cvv, amt, user, pool, pb, session_jwt=None, session_proxy=None, persist_login_data=True):
        pipe = f"{num}|{exp}|{cvv}"
        r = harness.make_attempt(email, pwd, pipe, amt, session_jwt, session_proxy)
        r.setdefault("result_code", "BANK_APPROVED" if r.get("success") else "BANK_REJECTED")
        return r
    monkeypatch.setattr(dep, "_run_deposit_with_phases", mock_run_dep)


class MockPool:
    def __init__(self):
        self.started = 0
    async def start_factory(self, *a, **k):
        self.started += 1
    async def stop(self):
        pass


def test_card_protocol_3_strikes_across_distinct_accounts(monkeypatch):
    """Regla Robert: Una tarjeta rota por hasta 3 cuentas distintas ante rechazos bancarios.
    Al 3er rechazo en la 3a cuenta, se jubila de la misión y NO toca una 4a cuenta."""
    h = MockHarness()
    _setup_ad_mocks(monkeypatch, h)

    pipe_test = "4111111111111111|1228|123"
    plan = {
        "accounts": [
            {"id": 1, "email": "acc1@test.com", "grade": "A", "card_pipe": pipe_test},
            {"id": 2, "email": "acc2@test.com", "grade": "A", "card_pipe": pipe_test},
            {"id": 3, "email": "acc3@test.com", "grade": "A", "card_pipe": pipe_test},
            {"id": 4, "email": "acc4@test.com", "grade": "A", "card_pipe": pipe_test},
        ]
    }
    for a in plan["accounts"]:
        h.accounts_db[a["id"]] = {
            "id": a["id"], "email": a["email"], "password": "pass",
            "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0
        }

    # Banco declina en todas
    h.script = lambda email, pipe, amt: {"success": False, "result_code": "BANK_REJECTED", "error": "Fondos insuficientes"}

    asyncio.run(ad.run_auto_mission("m_3strikes", plan, {"role": "superadmin", "telegram_id": 999}))

    calls = h.calls
    attempted_emails = [c["email"] for c in calls]
    # Debió haber intentado exactamente en acc1, acc2 y acc3 (3 strikes), y JAMÁS en acc4
    assert attempted_emails == ["acc1@test.com", "acc2@test.com", "acc3@test.com"]
    assert "acc4@test.com" not in attempted_emails
    assert 1 in h.unlocked and 2 in h.unlocked and 3 in h.unlocked


def test_account_not_drilled_consecutively_after_decline(monkeypatch):
    """Regla Robert: Si una cuenta recibe BANK_REJECTED, la tarjeta rota a otra cuenta.
    La cuenta que declinó NO debe recibir otra tarjeta de inmediato en caliente."""
    h = MockHarness()
    _setup_ad_mocks(monkeypatch, h)

    p1 = "4111111111111111|1228|111"
    p2 = "4222222222222222|1228|222"
    plan = {
        "accounts": [
            {"id": 1, "email": "acc1@test.com", "grade": "A", "card_pipe": p1},
            {"id": 2, "email": "acc2@test.com", "grade": "A", "card_pipe": p2},
        ]
    }
    for a in plan["accounts"]:
        h.accounts_db[a["id"]] = {
            "id": a["id"], "email": a["email"], "password": "pass",
            "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 0.0
        }

    def script(email, pipe, amt):
        if email == "acc1@test.com" and pipe == p1:
            return {"success": False, "result_code": "BANK_REJECTED", "error": "Decline"}
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "J", "used_proxy": "P"}

    h.script = script
    asyncio.run(ad.run_auto_mission("m_nodrill", plan, {"role": "superadmin", "telegram_id": 999}))

    # El siguiente intento debió ser acc2 (con p2 o p1), NO acc1 inmediatamente
    assert len(h.calls) >= 2
    assert h.calls[0]["email"] == "acc1@test.com"
    assert h.calls[1]["email"] == "acc2@test.com"


def test_live_balance_guard_skips_deposit(monkeypatch):
    """Regla Robert: Si una cuenta tiene balance_real >= 10.0 en BD o se actualiza en vivo,
    el scheduler no le mete otra tarjeta a depositar; la salta protegiendo la cuenta."""
    h = MockHarness()
    _setup_ad_mocks(monkeypatch, h)
    monkeypatch.setattr(ad, "_has_card_deposit_24h", lambda email: True)

    p1 = "4111111111111111|1228|111"
    plan = {
        "accounts": [
            {"id": 1, "email": "acc_funded@test.com", "grade": "A", "card_pipe": p1},
        ]
    }
    # Cuenta con saldo activo en BD
    h.accounts_db[1] = {
        "id": 1, "email": "acc_funded@test.com", "password": "pass",
        "status": "LIVE", "grade": "A", "kyc_verified": 1, "balance_real": 10.12
    }

    asyncio.run(ad.run_auto_mission("m_bal_guard", plan, {"role": "superadmin", "telegram_id": 999}))

    # Cero depósitos ejecutados en cuenta con saldo
    assert len(h.calls) == 0
    assert 1 in h.unlocked or 1 not in h.locked


def test_bin_affinity_corona_prefers_a_plus(tmp_path, monkeypatch):
    """Afinidad BIN: Cuentas A+ se emparejan preferentemente con BIN Corona (Santander 491566).
    Tarjetas en prueba van a cuentas A o B para no arriesgar la cuenta dorada."""
    db_file = tmp_path / "test_affinity.db"
    import sqlite3
    con = sqlite3.connect(str(db_file))
    con.executescript("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT DEFAULT 'pass',
        status TEXT DEFAULT 'LIVE',
        grade TEXT DEFAULT 'A',
        kyc_verified INTEGER DEFAULT 1,
        published_to_pool INTEGER DEFAULT 1,
        balance_real REAL DEFAULT 0.0,
        balance_total REAL DEFAULT 0.0,
        locked_by INTEGER,
        cooldown_until INTEGER,
        jwt_expires_at INTEGER DEFAULT 2147483647
    );
    CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY, account_email TEXT, amount REAL, status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);
    CREATE TABLE account_transactions (id INTEGER PRIMARY KEY, account_email TEXT, txn_date TEXT, amount REAL, status INTEGER, txn_type INTEGER, gateway INTEGER);
    CREATE TABLE account_cards (id INTEGER PRIMARY KEY, account_email TEXT, number TEXT, status TEXT DEFAULT 'ACTIVE');
    CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INTEGER, approved_count INTEGER, approval_rate REAL);
    """)
    # 1 cuenta A+ y 1 cuenta A
    con.execute("INSERT INTO accounts (email, grade) VALUES ('aplus@test.com', 'A+')")
    con.execute("INSERT INTO accounts (email, grade) VALUES ('regular@test.com', 'A')")
    con.commit()
    con.close()

    p_corona = "4915660000000000|1228|123"  # Santander débito -> CORONA
    p_test = "4027660000000000|1228|123"    # Citibanamex en pruebas

    plan = ad.plan_auto_mission(db_file, [p_corona, p_test], amount=150, target_count=2)
    accs = {a["email"]: a["card_pipe"] for a in plan["accounts"]}

    # aplus@test.com debió recibir p_corona por afinidad
    assert "aplus@test.com" in accs
    assert accs["aplus@test.com"].startswith("491566")
