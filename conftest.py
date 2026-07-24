# conftest.py
import sqlite3, tempfile, os, pytest
from pathlib import Path
from fastapi.testclient import TestClient
import httpx

@pytest.fixture
def seed_db(tmp_path, monkeypatch):
    """BD SQLite temporal con 3 cuentas seed (1 LIVE A, 1 LIVE B, 1 DEAD C)."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("BETMEX_DB", str(db))
    monkeypatch.setenv("BMX_WEB_AUTH_MODE", "open")
    con = sqlite3.connect(db)
    try:
        con.execute("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL, password TEXT NOT NULL,
                balance_real REAL DEFAULT 0, balance_bonos REAL DEFAULT 0, balance_total REAL DEFAULT 0,
                last_deposit_amount REAL DEFAULT 0, last_deposit_date TEXT DEFAULT 'N/A',
                status TEXT DEFAULT 'LIVE',
                first_checked_at TEXT NOT NULL, last_checked_at TEXT NOT NULL, check_count INTEGER DEFAULT 1,
                checked_by INTEGER DEFAULT 0,
                locked_by INTEGER DEFAULT NULL, locked_at TEXT DEFAULT NULL, locked_until TEXT DEFAULT NULL,
                published_to_pool INTEGER DEFAULT 1,
                grade TEXT DEFAULT '?'
            )
        """)
        rows = [
            ("a@test.com", "x", 100.0, "2026-05-05 10:00:00", "LIVE", "A", 50.0),
            ("b@test.com", "x", 50.5,  "2026-05-04 12:00:00", "LIVE", "B", 25.0),
            ("c@test.com", "x", 0.0,   "N/A",                 "DEAD", "C", 0.0),
        ]
        for email, pwd, bal, dep_date, status, grade, dep_amt in rows:
            con.execute(
                "INSERT INTO accounts (email,password,balance_total,last_deposit_date,status,grade,last_deposit_amount,first_checked_at,last_checked_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (email, pwd, bal, dep_date, status, grade, dep_amt, "2026-05-01 00:00:00", "2026-05-05 11:00:00")
            )
        con.execute("""
            CREATE TABLE IF NOT EXISTS deposit_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id TEXT, batch_id TEXT, mission_id TEXT,
                account_email TEXT, card_id INTEGER, amount REAL,
                source TEXT, operator_id INTEGER, status TEXT,
                rejection_reason TEXT, gateway_response_raw TEXT,
                gateway_txn_id TEXT, balance_before REAL, balance_after REAL,
                duration_ms INTEGER, captcha_cost REAL, created_at TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT, card_expiry TEXT, card_cvv TEXT,
                account_email TEXT, account_password TEXT,
                registered_by INTEGER, registered_by_name TEXT, registered_at TEXT,
                last_used_at TEXT,
                total_deposits INTEGER DEFAULT 0,
                total_approved INTEGER DEFAULT 0,
                total_rejected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE'
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT, user_id INTEGER, assigned_by INTEGER,
                assigned_at TEXT, UNIQUE(email, user_id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT,
                account_password TEXT, note_type TEXT, card_number TEXT,
                card_expiry TEXT, card_cvv TEXT, note_text TEXT, amount REAL,
                created_by INTEGER, created_by_name TEXT, created_at TEXT, updated_at TEXT
            )
        """)
        # Seed A2.1: a@ asignada al operador 555; c@ lockeada por 555; b@ ajena (del SA)
        con.execute("INSERT INTO account_assignments (email,user_id,assigned_by,assigned_at) VALUES (?,?,?,?)",
                    ("a@test.com", 555, 1341812706, "2026-06-01 00:00:00"))
        con.execute("UPDATE accounts SET locked_by='555' WHERE email='a@test.com' OR email='c@test.com'")
        con.execute("INSERT INTO account_cards (card_number,card_expiry,card_cvv,account_email,account_password,registered_by,registered_at) VALUES (?,?,?,?,?,?,?)",
                    ("4111111111111111","1230","123","a@test.com","x",555,"2026-06-01"))
        con.execute("INSERT INTO account_cards (card_number,card_expiry,card_cvv,account_email,account_password,registered_by,registered_at) VALUES (?,?,?,?,?,?,?)",
                    ("4222222222222222","1230","321","b@test.com","x",1341812706,"2026-06-01"))
        con.execute("INSERT INTO deposit_attempts (account_email,amount,status,operator_id,created_at) VALUES (?,?,?,?,?)",
                    ("a@test.com", 50, "APPROVED", 555, "2026-06-10 10:00:00"))
        con.execute("INSERT INTO deposit_attempts (account_email,amount,status,operator_id,created_at) VALUES (?,?,?,?,?)",
                    ("b@test.com", 99, "APPROVED", 1341812706, "2026-06-10 11:00:00"))
        con.commit()
    finally:
        con.close()
    return db

@pytest.fixture
def client(seed_db):
    """TestClient con BD seed apuntada."""
    import importlib, app as app_mod
    importlib.reload(app_mod)
    return TestClient(app_mod.app)

@pytest.fixture
def make_client(seed_db):
    """TestClient con rol inyectado (el modo `open` del conftest fuerza SA;
    aquí override por test para simular admin/user)."""
    import importlib, app as app_mod
    importlib.reload(app_mod)
    def _make(role="superadmin", telegram_id=1341812706, username="robertvs"):
        app_mod.app.dependency_overrides[app_mod.require_session] = lambda: {
            "role": role, "telegram_id": telegram_id,
            "username": username, "display": username,
        }
        return TestClient(app_mod.app)
    yield _make
    app_mod.app.dependency_overrides.clear()


@pytest.fixture
def mock_bmx_transport():
    """Factory: retorna (httpx.MockTransport, received_requests_dict).
    Uso: transport, reqs = mock_bmx_transport(handler); await fn(..., transport=transport)."""
    def make(handler):
        reqs = {"calls": []}
        def wrap(request):
            reqs["calls"].append({"method": request.method, "url": str(request.url),
                                   "headers": dict(request.headers), "body": request.content})
            return handler(request)
        return httpx.MockTransport(wrap), reqs
    return make
