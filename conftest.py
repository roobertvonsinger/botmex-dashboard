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
                fullname TEXT, curp TEXT, phone TEXT,
                balance_real REAL DEFAULT 0, balance_bonos REAL DEFAULT 0, balance_total REAL DEFAULT 0,
                last_deposit_amount REAL DEFAULT 0, last_deposit_date TEXT DEFAULT 'N/A',
                status TEXT DEFAULT 'LIVE',
                first_checked_at TEXT NOT NULL, last_checked_at TEXT NOT NULL, check_count INTEGER DEFAULT 1,
                checked_by INTEGER DEFAULT 0,
                locked_by INTEGER DEFAULT NULL, locked_at TEXT DEFAULT NULL, locked_until TEXT DEFAULT NULL,
                published_to_pool INTEGER DEFAULT 1,
                dead_reason TEXT,
                dead_at TEXT,
                kyc_verified INTEGER DEFAULT 1,
                grade TEXT DEFAULT '?',
                grade_score REAL DEFAULT 0,
                cooldown_until INTEGER DEFAULT NULL,
                jwt_token TEXT DEFAULT NULL,
                jwt_expires_at INTEGER DEFAULT NULL
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS bin_stats (
                bin TEXT PRIMARY KEY,
                total_attempts INTEGER DEFAULT 0,
                total_approved INTEGER DEFAULT 0,
                total_rejected INTEGER DEFAULT 0,
                total_3ds INTEGER DEFAULT 0,
                last_3ds_at TEXT,
                updated_at TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT, txn_date TEXT, status INTEGER,
                txn_type INTEGER, gateway INTEGER, amount REAL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_touches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                account_email TEXT,
                actor_id INTEGER,
                touched_at TEXT,
                touched_date TEXT,
                UNIQUE(account_id, actor_id, touched_date)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                account_email TEXT,
                transaction_id TEXT UNIQUE NOT NULL,
                reference TEXT,
                amount REAL NOT NULL,
                account_digits TEXT,
                institution_name TEXT,
                status_api INTEGER,
                status_description TEXT,
                gateway INTEGER,
                last_modified_utc TEXT,
                disparado_por INTEGER,
                created_at TEXT NOT NULL
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


# ── Socket Guard Global (B-03 Enforcement) ──────────────────────────────────
import socket
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect

class OutgoingNetworkBlockedError(RuntimeError):
    """Bloqueo de seguridad: ningún test unitario debe emitir tráfico externo."""
    pass

@pytest.fixture(autouse=True)
def guard_external_network():
    """Bloquea conexiones salientes a IPs externas/proxies en toda la suite."""
    allowed_hosts = {"127.0.0.1", "localhost", "::1", "testserver"}
    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host in allowed_hosts or str(host).startswith("127.") or str(host).startswith("::1"):
            return _ORIGINAL_SOCKET_CONNECT(self, address)
        raise OutgoingNetworkBlockedError(
            f"SECURITY VIOLATION [B-03]: Test intentó conectar a red externa '{host}'. "
            f"Toda suite debe usar mocks locales o httpx.MockTransport."
        )
    socket.socket.connect = guarded_connect
    try:
        yield
    finally:
        socket.socket.connect = _ORIGINAL_SOCKET_CONNECT

