"""
playdoit_db.py — Persistencia y consultas para cuentas de PlayDoit.
Usa db_registry.db() context manager con WAL, busy_timeout y write tracking.
Defaults en BD: 'Sin dato' (regla canonica de BetMexico/CLAUDE.md).
"""
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db_registry import db, _db_write_with_retry

logger = logging.getLogger("playdoit_db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS playdoit_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        fullname TEXT DEFAULT 'Sin dato',
        birthdate TEXT DEFAULT 'Sin dato',
        national_id TEXT DEFAULT 'Sin dato',
        balance_cash REAL DEFAULT 0.0,
        balance_promo REAL DEFAULT 0.0,
        balance_total REAL DEFAULT 0.0,
        total_deposits REAL DEFAULT 0.0,
        net_deposits REAL DEFAULT 0.0,
        deposit_count INTEGER DEFAULT 0,
        bank_details TEXT DEFAULT 'Sin dato',
        document_status TEXT DEFAULT 'Sin dato',
        status TEXT DEFAULT 'LIVE',
        dead_reason TEXT DEFAULT NULL,
        first_checked_at TEXT NOT NULL,
        last_checked_at TEXT NOT NULL,
        check_count INTEGER DEFAULT 1,
        checked_by INTEGER DEFAULT 0,
        platform TEXT DEFAULT 'playdoit',
        UNIQUE(email)
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_playdoit_email ON playdoit_accounts(email);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_playdoit_status ON playdoit_accounts(status);")


def init_playdoit_table(db_path: Optional[str] = None) -> None:
    """Crea la tabla playdoit_accounts si no existe."""
    with db(write=True, db_path=db_path) as c:
        _ensure_table(c)


def upsert_playdoit_account(data: Dict[str, Any], checked_by: int = 0, db_path: Optional[str] = None) -> int:
    """
    Inserta o actualiza una cuenta de PlayDoit.
    data debe contener al menos 'email' y 'password'.
    """
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    if not email or not password:
        raise ValueError("email y password son obligatorios")

    now = _now_iso()

    fullname = data.get("fullname") or "Sin dato"
    birthdate = data.get("birthdate") or "Sin dato"
    national_id = data.get("national_id") or "Sin dato"
    balance_cash = float(data.get("balance_cash") or data.get("cash") or 0.0)
    balance_promo = float(data.get("balance_promo") or data.get("promo") or 0.0)
    balance_total = float(data.get("balance_total") or data.get("balance") or (balance_cash + balance_promo))
    total_deposits = float(data.get("total_deposits") or data.get("totalDeposits") or 0.0)
    net_deposits = float(data.get("net_deposits") or data.get("netDeposits") or 0.0)
    deposit_count = int(data.get("deposit_count") or data.get("totalDepositCount") or 0)
    bank_details = str(data.get("bank_details") or "Sin dato")
    document_status = str(data.get("document_status") or data.get("documentStatus") or "Sin dato")
    status = str(data.get("status") or "LIVE").upper()
    dead_reason = data.get("dead_reason")

    def _execute(conn: sqlite3.Connection) -> int:
        _ensure_table(conn)
        cur = conn.execute(
            """
            INSERT INTO playdoit_accounts (
                email, password, fullname, birthdate, national_id,
                balance_cash, balance_promo, balance_total,
                total_deposits, net_deposits, deposit_count,
                bank_details, document_status, status, dead_reason,
                first_checked_at, last_checked_at, check_count, checked_by, platform
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, 1, ?, 'playdoit'
            )
            ON CONFLICT(email) DO UPDATE SET
                password=excluded.password,
                fullname=CASE WHEN excluded.fullname != 'Sin dato' THEN excluded.fullname ELSE playdoit_accounts.fullname END,
                birthdate=CASE WHEN excluded.birthdate != 'Sin dato' THEN excluded.birthdate ELSE playdoit_accounts.birthdate END,
                national_id=CASE WHEN excluded.national_id != 'Sin dato' THEN excluded.national_id ELSE playdoit_accounts.national_id END,
                balance_cash=excluded.balance_cash,
                balance_promo=excluded.balance_promo,
                balance_total=excluded.balance_total,
                total_deposits=excluded.total_deposits,
                net_deposits=excluded.net_deposits,
                deposit_count=excluded.deposit_count,
                bank_details=CASE WHEN excluded.bank_details != 'Sin dato' THEN excluded.bank_details ELSE playdoit_accounts.bank_details END,
                document_status=CASE WHEN excluded.document_status != 'Sin dato' THEN excluded.document_status ELSE playdoit_accounts.document_status END,
                status=excluded.status,
                dead_reason=excluded.dead_reason,
                last_checked_at=excluded.last_checked_at,
                check_count=playdoit_accounts.check_count + 1,
                checked_by=excluded.checked_by
            RETURNING id;
            """,
            (
                email, password, fullname, birthdate, national_id,
                balance_cash, balance_promo, balance_total,
                total_deposits, net_deposits, deposit_count,
                bank_details, document_status, status, dead_reason,
                now, now, checked_by
            ),
        )
        row = cur.fetchone()
        return row[0] if row else 0

    if db_path:
        with db(write=True, db_path=db_path) as c:
            return _execute(c)
    return _db_write_with_retry(_execute)


def mark_playdoit_dead(email: str, reason: str, db_path: Optional[str] = None) -> None:
    """Marca una cuenta de PlayDoit como DEAD con su motivo."""
    now = _now_iso()
    clean_email = str(email).strip().lower()

    def _execute(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE playdoit_accounts
            SET status='DEAD', dead_reason=?, last_checked_at=?
            WHERE LOWER(email)=LOWER(?);
            """,
            (reason, now, clean_email),
        )

    if db_path:
        with db(write=True, db_path=db_path) as c:
            _execute(c)
            return
    _db_write_with_retry(_execute)


def list_playdoit_accounts(
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Devuelve listado de cuentas PlayDoit filtradas."""
    query = "SELECT * FROM playdoit_accounts WHERE 1=1"
    params: List[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status.upper())

    if q:
        query += " AND (email LIKE ? OR fullname LIKE ? OR bank_details LIKE ?)"
        term = f"%{q.strip()}%"
        params.extend([term, term, term])

    query += " ORDER BY balance_total DESC, last_checked_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with db(write=False, db_path=db_path) as c:
        rows = c.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_playdoit_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Estadisticas agregadas de cuentas PlayDoit."""
    with db(write=False, db_path=db_path) as c:
        row = c.execute(
            """
            SELECT
                COUNT(*) AS total_accounts,
                COUNT(CASE WHEN status='LIVE' THEN 1 END) AS live_accounts,
                COUNT(CASE WHEN status='DEAD' THEN 1 END) AS dead_accounts,
                COALESCE(SUM(balance_total), 0.0) AS total_balance,
                COALESCE(SUM(balance_cash), 0.0) AS total_cash,
                COALESCE(SUM(balance_promo), 0.0) AS total_promo
            FROM playdoit_accounts;
            """
        ).fetchone()
        return dict(row) if row else {
            "total_accounts": 0, "live_accounts": 0, "dead_accounts": 0,
            "total_balance": 0.0, "total_cash": 0.0, "total_promo": 0.0
        }
