#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Database Module v2
- SQLite con columna checked_by para aislamiento multiusuario
- Threading lock para escrituras concurrentes seguras
"""

import os
import sqlite3
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from betmexico_config import (
    now_mx, MX_TZ,
    SMART_FILTER_COOLDOWN_MIN, SMART_FILTER_STALE_CHECKS,
    SMART_FILTER_ACTIVITY_HOURS, SMART_FILTER_BALANCE_THRESHOLD,
    FILTER_RECENT_MINUTES, FILTER_RECENT_WAIT_MINUTES,
    FILTER_DAILY_LIMIT, FILTER_DAILY_WAIT_HOURS
)

logger = logging.getLogger(__name__)
DB_FILE = Path(os.getenv("BETMEX_DB", os.getenv("DB_PATH", "/data/betmexico_accounts.db" if Path("/data/betmexico_accounts.db").exists() else str(Path(__file__).resolve().parent / "betmexico_accounts.db"))))


class BetmexicoDB:
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """Inicializa la base de datos y crea/migra la tabla."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA cache_size=-64000")
        self.conn.execute("PRAGMA temp_store=MEMORY")

        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                fullname TEXT DEFAULT 'N/A',
                birthdate TEXT DEFAULT 'N/A',
                address TEXT DEFAULT 'N/A',
                phone TEXT DEFAULT 'N/A',
                curp TEXT DEFAULT 'N/A',
                balance_real REAL DEFAULT 0.0,
                balance_bonos REAL DEFAULT 0.0,
                balance_total REAL DEFAULT 0.0,
                last_deposit_amount REAL DEFAULT 0.0,
                last_deposit_date TEXT DEFAULT 'N/A',
                kyc_verified INTEGER DEFAULT 0,
                status TEXT DEFAULT 'LIVE',
                first_checked_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                check_count INTEGER DEFAULT 1,
                checked_by INTEGER DEFAULT 0,
                locked_by INTEGER DEFAULT NULL,
                locked_at TEXT DEFAULT NULL,
                stable_balance_count INTEGER DEFAULT 1,
                check_count_today INTEGER DEFAULT 0,
                last_check_date TEXT DEFAULT NULL,
                UNIQUE(email, password)
            )
        """)

        # Migraciones
        try:
            cursor.execute("SELECT checked_by FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN checked_by INTEGER DEFAULT 0"
            )

        try:
            cursor.execute("SELECT locked_by FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN locked_by INTEGER DEFAULT NULL"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN locked_at TEXT DEFAULT NULL"
            )

        try:
            cursor.execute("SELECT stable_balance_count FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN stable_balance_count INTEGER DEFAULT 1"
            )

        try:
            cursor.execute("SELECT check_count_today FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN check_count_today INTEGER DEFAULT 0"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN last_check_date TEXT DEFAULT NULL"
            )

        try:
            cursor.execute("SELECT grade FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN grade TEXT DEFAULT '?'"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN grade_score INTEGER DEFAULT 0"
            )

        try:
            cursor.execute("SELECT visible_to_users FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN visible_to_users INTEGER DEFAULT 0"
            )

        try:
            cursor.execute("SELECT phone FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN phone TEXT DEFAULT 'N/A'"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN curp TEXT DEFAULT 'N/A'"
            )

        try:
            cursor.execute("SELECT manual_grade FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN manual_grade TEXT DEFAULT NULL"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN manual_grade_reason TEXT DEFAULT NULL"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN manual_grade_by INTEGER DEFAULT NULL"
            )
            cursor.execute(
                "ALTER TABLE accounts ADD COLUMN manual_grade_at TEXT DEFAULT NULL"
            )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON accounts(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON accounts(status)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                mode TEXT DEFAULT 'human',
                proxies TEXT DEFAULT '',
                captcha_api_key TEXT DEFAULT '',
                captcha_service TEXT DEFAULT 'anticaptcha',
                last_human_use TEXT DEFAULT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT NOT NULL,
                account_password TEXT NOT NULL,
                card_number TEXT NOT NULL,
                card_expiry TEXT,
                card_cvv TEXT,
                amount REAL,
                result TEXT,
                tested_by INTEGER NOT NULL,
                notes TEXT,
                tested_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT NOT NULL,
                txn_date TEXT NOT NULL,
                amount REAL NO NULL,
                status INTEGER,
                txn_type INTEGER,
                gateway INTEGER,
                checked_by INTEGER,
                fetched_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT NOT NULL,
                account_password TEXT NOT NULL,
                amount REAL NOT NULL,
                bank TEXT,
                contact_info TEXT,
                notes TEXT,
                tested_by INTEGER NOT NULL,
                tested_at TEXT NOT NULL,
                beneficiary_id INTEGER,
                status TEXT DEFAULT 'PENDING'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_beneficiaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                contact_info TEXT,
                created_by INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(bank_name, account_number)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_wt_beneficiary ON withdrawal_tests(beneficiary_id)"
        )

        # Nueva tabla de notas (reemplaza payment_tests y withdrawal_tests)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT NOT NULL,
                account_password TEXT NOT NULL,
                note_type TEXT NOT NULL,
                card_number TEXT,
                card_expiry TEXT,
                card_cvv TEXT,
                note_text TEXT NOT NULL,
                amount REAL,
                created_by INTEGER NOT NULL,
                created_by_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_account ON account_notes(account_email, account_password)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_created_by ON account_notes(created_by)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_type ON account_notes(note_type)")

        # Tabla de marriage tarjeta-cuenta (automatización de depósitos)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT NOT NULL UNIQUE,
                card_expiry TEXT,
                card_cvv TEXT,
                account_email TEXT NOT NULL,
                account_password TEXT NOT NULL,
                registered_by INTEGER NOT NULL,
                registered_by_name TEXT,
                registered_at TEXT NOT NULL,
                last_used_at TEXT,
                total_deposits INTEGER DEFAULT 0,
                total_approved INTEGER DEFAULT 0,
                total_rejected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE'
            )
        """)
        try:
            cursor.execute("SELECT status FROM account_cards LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE account_cards ADD COLUMN status TEXT DEFAULT 'ACTIVE'")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_account ON account_cards(account_email, account_password)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_status ON account_cards(status)")

        # Historial acumulativo de uso (reemplaza la lógica de 6h de lock)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                marked_at TEXT NOT NULL,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','previous'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alock_email ON account_locks(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alock_user ON account_locks(user_id)")

        # Asignaciones admin → usuario (invisible para el usuario)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_by INTEGER NOT NULL,
                assigned_at TEXT NOT NULL,
                UNIQUE(email, user_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assign_user ON account_assignments(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assign_email ON account_assignments(email)")

        self._create_sessions_table()

        # ────────────────────────────────────────────────────────────
        # Migración 001 — JWT cache + Cards/Deposits/Missions/BIN/ProcessLog
        # Aditivo. Idempotente. Ejecuta en cada arranque.
        # ────────────────────────────────────────────────────────────

        # Bloque A — accounts: JWT cache columns
        try:
            cursor.execute("SELECT jwt_token FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE accounts ADD COLUMN jwt_token TEXT")
            cursor.execute("ALTER TABLE accounts ADD COLUMN jwt_expires_at INTEGER")
            cursor.execute("ALTER TABLE accounts ADD COLUMN jwt_user_id TEXT")

        # Bloque B — account_transactions: source/operator/card/attempt
        try:
            cursor.execute("SELECT source FROM account_transactions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE account_transactions ADD COLUMN source TEXT")
            cursor.execute("ALTER TABLE account_transactions ADD COLUMN operator_id INTEGER")
            cursor.execute("ALTER TABLE account_transactions ADD COLUMN card_id INTEGER")
            cursor.execute("ALTER TABLE account_transactions ADD COLUMN attempt_id TEXT")

        # Bloque C — cards
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                card_number TEXT NOT NULL,
                bin TEXT NOT NULL,
                last_4 TEXT NOT NULL,
                exp_month INTEGER NOT NULL,
                exp_year INTEGER NOT NULL,
                cvv TEXT,
                holder_name TEXT,
                status TEXT NOT NULL DEFAULT 'usable',
                total_attempts INTEGER NOT NULL DEFAULT 0,
                total_approved INTEGER NOT NULL DEFAULT 0,
                total_rejected INTEGER NOT NULL DEFAULT 0,
                total_amount_approved REAL NOT NULL DEFAULT 0.0,
                last_used_at TEXT,
                banned_at TEXT,
                banned_reason TEXT,
                notes TEXT,
                created_by_operator_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cardsv2_operator ON cards(created_by_operator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cardsv2_bin ON cards(bin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cardsv2_status ON cards(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cardsv2_last_used ON cards(last_used_at DESC)")

        # Bloque D — deposit_attempts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deposit_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id TEXT NOT NULL UNIQUE,
                batch_id TEXT,
                mission_id TEXT,
                account_email TEXT NOT NULL,
                card_id INTEGER,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                operator_id INTEGER,
                status TEXT NOT NULL,
                rejection_reason TEXT,
                gateway_response_raw TEXT,
                gateway_txn_id TEXT,
                balance_before REAL,
                balance_after REAL,
                duration_ms INTEGER,
                captcha_cost REAL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_account ON deposit_attempts(account_email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_card ON deposit_attempts(card_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_batch ON deposit_attempts(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_mission ON deposit_attempts(mission_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_operator ON deposit_attempts(operator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_created ON deposit_attempts(created_at DESC)")

        # Bloque E — missions (deposit missions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                operator_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                config_json TEXT NOT NULL,
                progress_json TEXT,
                started_at TEXT,
                paused_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_missions_operator ON missions(operator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_missions_type ON missions(type)")

        # Bloque F — bin_stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bin_stats (
                bin TEXT NOT NULL,
                gateway_name TEXT NOT NULL DEFAULT 'default',
                total_attempts INTEGER NOT NULL DEFAULT 0,
                total_approved INTEGER NOT NULL DEFAULT 0,
                total_rejected INTEGER NOT NULL DEFAULT 0,
                last_used_at TEXT,
                last_approved_at TEXT,
                last_rejected_at TEXT,
                status TEXT NOT NULL DEFAULT 'unknown',
                notes TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (bin, gateway_name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bin_stats_status ON bin_stats(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bin_stats_last_used ON bin_stats(last_used_at DESC)")

        # Bloque G — process_log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS process_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_id TEXT NOT NULL,
                process_type TEXT NOT NULL,
                phase TEXT NOT NULL,
                payload_json TEXT,
                duration_ms INTEGER,
                timestamp_ms INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proclog_process ON process_log(process_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proclog_type ON process_log(process_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proclog_timestamp ON process_log(timestamp_ms DESC)")

        # Vista resumen tarjetas (LEFT JOIN con attempts)
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS card_usage_summary AS
            SELECT
                c.id, c.fingerprint, c.bin, c.last_4, c.exp_month, c.exp_year,
                c.holder_name, c.status, c.created_by_operator_id,
                c.total_attempts, c.total_approved, c.total_rejected,
                c.total_amount_approved, c.last_used_at,
                COUNT(DISTINCT da.account_email) AS unique_accounts_used,
                MAX(da.created_at) AS last_attempt_at
            FROM cards c
            LEFT JOIN deposit_attempts da ON da.card_id = c.id
            GROUP BY c.id
        """)

        # ── Notifications (Tarea 3) ─────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_operator_id INTEGER,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                payload_json TEXT,
                severity TEXT NOT NULL DEFAULT 'info' CHECK(severity IN ('info','warn','error')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                read_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient_operator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_unread ON notifications(read_at) WHERE read_at IS NULL")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at DESC)")

        self.conn.commit()
        logger.info(f"[DB] Base de datos inicializada: {self.db_path}")

    def upsert_account(self, account_data: Dict, checked_by: int = 0) -> bool:
        """INSERT o UPDATE una cuenta."""
        with self._lock:
            try:
                email = account_data.get("email", "")
                password = account_data.get("password", "")
                if not email or not password:
                    return False

                details = account_data.get("account_details", {})

                # Helper: valor "vacío" = no tiene datos reales
                _EMPTY = (None, "", "N/A", "Sin dato")
                def _has_data(val):
                    return val not in _EMPTY

                fullname = details.get("fullname", "N/A")
                birthdate = details.get("birthdate", "N/A")
                address = details.get("address", "N/A")
                last_deposit_date = details.get("last_deposit_date", "N/A")
                balance_real = float(details.get("balance_real", 0.0) or 0.0)
                balance_bonos = float(details.get("balance_bonos", 0.0) or 0.0)
                balance_total = balance_real + balance_bonos
                last_deposit_amount = float(
                    details.get("last_deposit_amount", 0.0) or 0.0
                )
                phone = details.get("phone") or details.get("Phone") or "N/A"
                curp = details.get("curp") or details.get("CURP") or details.get("Curp") or "N/A"
                kyc_verified = 1 if details.get("verified", False) else 0

                payment_score = account_data.get("payment_score", {})
                # None = sin transacciones en este check → no sobreescribir grade existente
                has_new_scoring = bool(payment_score)
                grade = payment_score.get("grade", "?") if has_new_scoring else "?"
                grade_score = payment_score.get("score", 0) if has_new_scoring else 0

                now = now_mx()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                today_str = now.strftime("%Y-%m-%d")

                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, check_count, balance_total, last_checked_at, stable_balance_count, check_count_today, last_check_date, fullname, birthdate, address, last_deposit_date, last_deposit_amount, grade, grade_score, phone, curp FROM accounts WHERE email = ? AND password = ?",
                    (email, password),
                )
                existing = cursor.fetchone()

                if existing:
                    new_count = existing["check_count"] + 1
                    if existing["last_check_date"] == today_str:
                        new_count_today = (existing["check_count_today"] or 0) + 1
                    else:
                        new_count_today = 1

                    if abs(balance_total - existing["balance_total"]) < 0.01:
                        new_stable_count = (existing["stable_balance_count"] or 0) + 1
                    else:
                        new_stable_count = 1

                    # Merge robusto: NUNCA sobreescribir datos buenos con vacíos
                    if not _has_data(fullname) and _has_data(existing["fullname"]):
                        fullname = existing["fullname"]
                    if not _has_data(birthdate) and _has_data(existing["birthdate"]):
                        birthdate = existing["birthdate"]
                    if not _has_data(address) and _has_data(existing["address"]):
                        address = existing["address"]
                    if not _has_data(last_deposit_date) and _has_data(existing["last_deposit_date"]):
                        last_deposit_date = existing["last_deposit_date"]
                    if last_deposit_amount == 0.0 and (existing["last_deposit_amount"] or 0) > 0:
                        last_deposit_amount = existing["last_deposit_amount"]

                    # Proteger balance: si el API devolvió 0 pero ya teníamos saldo real, conservar
                    _ex_bal = existing["balance_real"] if "balance_real" in existing.keys() else None
                    if balance_real == 0.0 and (_ex_bal or 0) > 0:
                        balance_real = float(_ex_bal)
                        balance_bonos = float(existing["balance_bonos"] if "balance_bonos" in existing.keys() else 0.0 or 0.0)
                        balance_total = float(existing["balance_total"] if "balance_total" in existing.keys() else 0.0 or 0.0)
                        logger.debug(f"[DB] Balance 0 ignorado para {email} — conservando ${balance_total:.2f}")

                    # Preservar grade existente si este check no trajo transacciones
                    if not has_new_scoring:
                        grade = existing["grade"] or "?"
                        grade_score = existing["grade_score"] or 0

                    # V6 guard: proteger contra API intermitente de betmexico
                    # Si el algoritmo dice VIRGIN_CARD pero la BD ya tiene txns de tarjeta,
                    # la API falló en traer transacciones → conservar grade existente
                    is_virgin_card = payment_score and "VIRGIN_CARD" in (payment_score.get("flags") or [])
                    if is_virgin_card:
                        old_grade = existing["grade"] or "?"
                        c2 = self.conn.cursor()
                        c2.execute(
                            "SELECT 1 FROM account_transactions WHERE account_email = ? AND gateway = 1 LIMIT 1",
                            (email,),
                        )
                        if c2.fetchone():
                            # BD tiene txns de tarjeta → API mintió → conservar grade real
                            grade = old_grade if old_grade not in ("?", "", None) else "?"
                            grade_score = existing["grade_score"] or 0
                            has_new_scoring = False

                    cursor.execute(
                        """
                        UPDATE accounts SET
                            password = ?, fullname = ?, birthdate = ?, address = ?,
                            balance_real = ?, balance_bonos = ?, balance_total = ?,
                            last_deposit_amount = ?, last_deposit_date = ?,
                            kyc_verified = ?, status = 'LIVE',
                            last_checked_at = ?, check_count = ?, checked_by = ?,
                            stable_balance_count = ?, check_count_today = ?,
                            last_check_date = ?, grade = ?, grade_score = ?, phone = ?, curp = ?
                        WHERE id = ?
                    """,
                        (
                            password,
                            fullname,
                            birthdate,
                            address,
                            balance_real,
                            balance_bonos,
                            balance_total,
                            last_deposit_amount,
                            last_deposit_date,
                            kyc_verified,
                            now_str,
                            new_count,
                            checked_by,
                            new_stable_count,
                            new_count_today,
                            today_str,
                            grade,
                            grade_score,
                            phone,
                            curp,
                            existing["id"],
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO accounts (
                            email, password, fullname, birthdate, address,
                            balance_real, balance_bonos, balance_total,
                            last_deposit_amount, last_deposit_date, kyc_verified,
                            status, first_checked_at, last_checked_at, check_count, 
                            checked_by, stable_balance_count, check_count_today,
                            last_check_date, grade, grade_score, phone, curp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'LIVE', ?, ?, 1, ?, 1, 1, ?, ?, ?, ?, ?)
                    """,
                        (
                            email,
                            password,
                            fullname,
                            birthdate,
                            address,
                            balance_real,
                            balance_bonos,
                            balance_total,
                            last_deposit_amount,
                            last_deposit_date,
                            kyc_verified,
                            now_str,
                            now_str,
                            checked_by,
                            today_str,
                            grade,
                            grade_score,
                            phone,
                            curp,
                        ),
                    )

                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DB] Error upsert_account: {e}", exc_info=True)
                return False

    def get_account_by_combo(self, email: str, password: str) -> Optional[Dict]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM accounts WHERE email = ? AND password = ?",
                (email, password),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def get_user_settings(self, user_id: int) -> Dict:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"user_id": user_id, "mode": "human"}
        except Exception:
            return {"user_id": user_id, "mode": "human"}

    def save_user_settings(self, user_id: int, **kwargs) -> bool:
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO user_settings (user_id, updated_at) VALUES (?, ?)",
                        (user_id, now),
                    )
                for key, value in kwargs.items():
                    cursor.execute(
                        f"UPDATE user_settings SET {key} = ?, updated_at = ? WHERE user_id = ?",
                        (value, now, user_id),
                    )
                self.conn.commit()
                return True
            except Exception:
                return False

    def lock_account(self, email: str, user_id: int) -> bool:
        """Marca cuenta como En Uso. Acumulativo: múltiples usuarios pueden marcarla.
        La entrada anterior del mismo usuario queda como 'previous' (gris)."""
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                # La entrada anterior de este usuario pasa a 'previous'
                cursor.execute(
                    "UPDATE account_locks SET status='previous' WHERE email=? AND user_id=? AND status='active'",
                    (email, user_id)
                )
                # Nueva entrada activa
                cursor.execute(
                    "INSERT INTO account_locks (email, user_id, marked_at, status) VALUES (?, ?, ?, 'active')",
                    (email, user_id, now)
                )
                # accounts.locked_by apunta al último marcador activo
                cursor.execute(
                    "UPDATE accounts SET locked_by=?, locked_at=? WHERE email=?",
                    (user_id, now, email)
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def get_emails_recently_worked_by_operator(self, user_id: int, limit: int = 50) -> list:
        """Emails con actividad real del operador, ordenados por mas reciente. Retorna list[dict] con metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT email, MAX(activity_time) AS last_activity,
                   COUNT(*) AS activity_count,
                   MAX(CASE WHEN src='deposit' THEN 1 ELSE 0 END) AS has_deposits,
                   MAX(CASE WHEN src='card' THEN 1 ELSE 0 END) AS has_cards
            FROM (
                SELECT account_email AS email, tested_at AS activity_time, 'deposit' AS src
                FROM payment_tests WHERE tested_by = ?
                UNION ALL
                SELECT account_email AS email, registered_at AS activity_time, 'card' AS src
                FROM account_cards WHERE registered_by = ?
                UNION ALL
                SELECT account_email AS email, created_at AS activity_time, 'note' AS src
                FROM account_notes WHERE created_by = ?
                UNION ALL
                SELECT email, marked_at AS activity_time, 'lock' AS src
                FROM account_locks WHERE user_id = ?
            ) GROUP BY email ORDER BY last_activity DESC LIMIT ?
        """, (user_id, user_id, user_id, user_id, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_emails_recently_worked_all(self, limit: int = 50) -> list:
        """Emails con actividad de cualquier operador, ordenados por mas reciente. Retorna list[dict] con metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT email, MAX(activity_time) AS last_activity,
                   COUNT(*) AS activity_count,
                   MAX(CASE WHEN src='deposit' THEN 1 ELSE 0 END) AS has_deposits,
                   MAX(CASE WHEN src='card' THEN 1 ELSE 0 END) AS has_cards
            FROM (
                SELECT account_email AS email, tested_at AS activity_time, 'deposit' AS src
                FROM payment_tests
                UNION ALL
                SELECT account_email AS email, registered_at AS activity_time, 'card' AS src
                FROM account_cards
                UNION ALL
                SELECT account_email AS email, created_at AS activity_time, 'note' AS src
                FROM account_notes
                UNION ALL
                SELECT email, marked_at AS activity_time, 'lock' AS src
                FROM account_locks
            ) GROUP BY email ORDER BY last_activity DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def unlock_account(self, email: str, user_id: int = None) -> bool:
        """Libera el lock del usuario (o todos si user_id=None).
        Las entradas activas pasan a 'previous'; accounts.locked_by se actualiza al siguiente activo."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                if user_id:
                    cursor.execute(
                        "UPDATE account_locks SET status='previous' WHERE email=? AND user_id=? AND status='active'",
                        (email, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE account_locks SET status='previous' WHERE email=? AND status='active'",
                        (email,)
                    )
                # accounts.locked_by → siguiente activo o NULL
                cursor.execute(
                    "SELECT user_id FROM account_locks WHERE email=? AND status='active' ORDER BY marked_at DESC LIMIT 1",
                    (email,)
                )
                row = cursor.fetchone()
                if row:
                    cursor.execute(
                        "UPDATE accounts SET locked_by=? WHERE email=?",
                        (row["user_id"], email)
                    )
                else:
                    cursor.execute(
                        "UPDATE accounts SET locked_by=NULL, locked_at=NULL WHERE email=?",
                        (email,)
                    )
                self.conn.commit()
                return True
            except Exception:
                return False

    def cleanup_expired_locks(self, email: str = None) -> int:
        """Los locks son permanentes ahora — sin expiración automática."""
        return 0

    def _has_recent_activity(self, email: str, hours: int) -> bool:
        """
        Verifica si una cuenta tiene transacciones en las últimas N horas.
        
        Args:
            email: Email de la cuenta
            hours: Ventana de tiempo en horas
            
        Returns:
            True si hay transacciones recientes, False en caso contrario
        """
        try:
            cursor = self.conn.cursor()
            # Calcular fecha límite
            cutoff_time = (now_mx() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                """SELECT 1 FROM account_transactions 
                   WHERE account_email = ? AND txn_date >= ? 
                   LIMIT 1""",
                (email, cutoff_time),
            )
            return cursor.fetchone() is not None
        except Exception:
            return False

    def filter_combos_smart(
        self, combos: List[Tuple[str, str]], bypass_activity_check: bool = False
    ) -> Tuple[List[Tuple[str, str]], dict]:
        """
        Filtra combos aplicando reglas inteligentes.
        
        Smart Filter V2 - Activity Aware:
        - SIEMPRE respeta el cooldown (20 min)
        - Para cuentas con 3+ checks sin cambios:
          * Se omite SI NO hay actividad reciente (12h) Y balance < $10
          * Se permite SI hay actividad reciente O balance >= $10
        
        Args:
            combos: Lista de tuplas (email, password)
            bypass_activity_check: Si True, omite la verificación de actividad (para testing)
            
        Returns:
            Tuple de (combos_filtrados, estadísticas)
        """
        # Constantes desde config con cast por seguridad
        cooldown_min = int(SMART_FILTER_COOLDOWN_MIN)
        stale_limit = int(SMART_FILTER_STALE_CHECKS)
        activity_hours = int(SMART_FILTER_ACTIVITY_HOURS)
        balance_threshold = float(SMART_FILTER_BALANCE_THRESHOLD)

        valid_combos = []
        stats = {
            "total_input": len(combos),
            "passed": 0,
            "skipped_cooldown": 0,
            "skipped_stale": 0,
            "not_in_db": 0,
            "min_wait_minutes": 0,
            "passed_by_activity": 0,  # Nuevo: cuentas que pasaron por actividad reciente
        }
        now = now_mx()
        
        with self._lock:
            cursor = self.conn.cursor()
            for email, password in combos:
                cursor.execute(
                    "SELECT last_checked_at, balance_total, stable_balance_count, check_count_today FROM accounts WHERE email = ? AND password = ?",
                    (email, password),
                )
                account = cursor.fetchone()
                if not account:
                    valid_combos.append((email, password))
                    stats["not_in_db"] += 1
                    stats["passed"] += 1
                    continue

                # REGLA 1: Cooldown (SIEMPRE se respeta)
                try:
                    last_checked_dt = datetime.strptime(
                        account["last_checked_at"], "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=MX_TZ)
                    elapsed = now - last_checked_dt
                    cooldown = timedelta(minutes=cooldown_min)
                    if elapsed < cooldown:
                        stats["skipped_cooldown"] += 1
                        rest = int((cooldown - elapsed).total_seconds() / 60)
                        if (
                            stats["min_wait_minutes"] == 0
                            or rest < stats["min_wait_minutes"]
                        ):
                            stats["min_wait_minutes"] = rest
                        continue
                except Exception:
                    pass

                # REGLA 2: Stale checks con Activity-Aware logic
                stable_count = account["stable_balance_count"] or 0
                if stable_count >= stale_limit:
                    # Smart Filter V2: Verificar si hay actividad reciente antes de omitir
                    should_skip = True
                    
                    if not bypass_activity_check:
                        current_balance = account["balance_total"] or 0.0
                        
                        # Condición 1: Balance notable
                        if current_balance >= balance_threshold:
                            should_skip = False
                            stats["passed_by_activity"] += 1
                        else:
                            # Condición 2: Actividad reciente en transacciones
                            has_activity = self._has_recent_activity(email, activity_hours)
                            if has_activity:
                                should_skip = False
                                stats["passed_by_activity"] += 1
                    
                    if should_skip:
                        stats["skipped_stale"] += 1
                        continue

                valid_combos.append((email, password))
                stats["passed"] += 1
        return valid_combos, stats

    def filter_combos_inteligente(
        self, combos: List[Tuple[str, str]]
    ) -> Tuple[List[Tuple[str, str]], List[Dict], Dict]:
        """
        Filtro Inteligente V3 - Separa combos en:
        - listos_para_check: cuentas que pueden revisarse ahora
        - en_espera: cuentas en espera con info de disponibilidad
        
        Reglas:
        1. Si fue revisada hace menos de 10 minutos → esperar 10 minutos desde último check
        2. Si fue revisada 3+ veces hoy → esperar 3 horas desde último check
        
        Returns:
            (listos_para_check, en_espera, stats)
            - listos_para_check: List[Tuple[email, password]]
            - en_espera: List[Dict] con keys: combo, razon, disponible_en_minutos, disponible_a las
            - stats: Dict con totales
        """
        listos = []
        en_espera = []
        stats = {
            "total": len(combos),
            "listos": 0,
            "en_espera": 0,
            "en_espera_recientes": 0,  # Regla 1
            "en_espera_frecuentes": 0,  # Regla 2
        }
        
        if not combos:
            return listos, en_espera, stats
        
        now = now_mx()
        today_str = now.strftime("%Y-%m-%d")
        
        # Batch query: obtener todas las cuentas existentes de una vez
        emails = list(set(c[0] for c in combos))
        placeholders = ','.join('?' * len(emails))
        
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(f"""
                SELECT email, password, last_checked_at, check_count_today, last_check_date
                FROM accounts 
                WHERE email IN ({placeholders})
            """, emails)
            
            accounts_map = {}
            for row in cursor.fetchall():
                key = (row["email"], row["password"])
                accounts_map[key] = row
        
        # Procesar cada combo
        for email, password in combos:
            key = (email, password)
            account = accounts_map.get(key)
            
            # Si no existe en BD, está listo para revisar
            if not account:
                listos.append((email, password))
                stats["listos"] += 1
                continue
            
            # Calcular reglas
            try:
                last_checked = datetime.strptime(
                    account["last_checked_at"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=MX_TZ)
                minutos_desde_check = (now - last_checked).total_seconds() / 60
            except Exception:
                # Si hay error parseando fecha, dejar pasar
                listos.append((email, password))
                stats["listos"] += 1
                continue
            
            check_count_today = account["check_count_today"] or 0
            last_check_date = account["last_check_date"] or ""
            
            # Verificar si el contador es de hoy
            if last_check_date != today_str:
                check_count_today = 0  # Reset si es otro día
            
            # REGLA 2: 3+ checks hoy → esperar 3 horas
            if check_count_today >= FILTER_DAILY_LIMIT:
                minutos_espera = FILTER_DAILY_WAIT_HOURS * 60
                disponible_en = minutos_espera - minutos_desde_check
                
                if disponible_en > 0:
                    hora_disponible = (now + timedelta(minutes=disponible_en)).strftime("%H:%M")
                    en_espera.append({
                        "combo": (email, password),
                        "razon": "revisada_muchas_veces_hoy",
                        "disponible_en_minutos": int(disponible_en),
                        "disponible_a_las": hora_disponible,
                        "checks_hoy": check_count_today,
                    })
                    stats["en_espera"] += 1
                    stats["en_espera_frecuentes"] += 1
                    continue
            
            # REGLA 1: revisada hace menos de 10 min → esperar 10 min
            if minutos_desde_check < FILTER_RECENT_MINUTES:
                minutos_espera = FILTER_RECENT_WAIT_MINUTES
                disponible_en = minutos_espera - minutos_desde_check
                
                if disponible_en > 0:
                    hora_disponible = (now + timedelta(minutes=disponible_en)).strftime("%H:%M")
                    en_espera.append({
                        "combo": (email, password),
                        "razon": "revisada_recientemente",
                        "disponible_en_minutos": int(disponible_en),
                        "disponible_a_las": hora_disponible,
                        "minutos_desde_ultima": int(minutos_desde_check),
                    })
                    stats["en_espera"] += 1
                    stats["en_espera_recientes"] += 1
                    continue
            
            # Pasó todas las reglas
            listos.append((email, password))
            stats["listos"] += 1
        
        return listos, en_espera, stats

    def get_check_count_today(self, email: str) -> int:
        try:
            today = now_mx().strftime("%Y-%m-%d")
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT check_count_today FROM accounts WHERE email = ? AND last_check_date = ?",
                (email, today),
            )
            row = cursor.fetchone()
            return row["check_count_today"] if row else 0
        except Exception:
            return 0

    def get_total_checks(self, user_id: int) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as c FROM accounts WHERE checked_by = ?", (user_id,)
            )
            return cursor.fetchone()["c"]
        except Exception:
            return 0

    def get_stats(self, user_id: int = None) -> Dict:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status='LIVE' THEN 1 ELSE 0 END) as total_live,
                        SUM(CASE WHEN status='DEAD' THEN 1 ELSE 0 END) as total_dead,
                        SUM(CASE WHEN kyc_verified=1 THEN 1 ELSE 0 END) as total_verified,
                        COALESCE(SUM(balance_total), 0.0) as total_balance
                    FROM accounts WHERE checked_by = ?
                """,
                    (user_id,),
                )
            else:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN status='LIVE' THEN 1 ELSE 0 END) as total_live,
                        SUM(CASE WHEN status='DEAD' THEN 1 ELSE 0 END) as total_dead,
                        SUM(CASE WHEN kyc_verified=1 THEN 1 ELSE 0 END) as total_verified,
                        COALESCE(SUM(balance_total), 0.0) as total_balance
                    FROM accounts
                """)
            row = cursor.fetchone()
            if row:
                return {
                    "total_live": row["total_live"] or 0,
                    "total_dead": row["total_dead"] or 0,
                    "total_verified": row["total_verified"] or 0,
                    "total_balance": row["total_balance"] or 0.0,
                }
            return {
                "total_live": 0,
                "total_dead": 0,
                "total_verified": 0,
                "total_balance": 0.0,
            }
        except Exception as e:
            logger.error(f"[DB] Error get_stats: {e}")
            return {
                "total_live": 0,
                "total_dead": 0,
                "total_verified": 0,
                "total_balance": 0.0,
            }

    def get_member_since(self, user_id: int) -> str | None:
        """Return earliest created_at for a user's accounts."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT MIN(created_at) FROM accounts WHERE checked_by = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
        except Exception as e:
            logger.error(f"[DB] Error get_member_since: {e}")
            return None

    def get_all_accounts(self, user_id: int = None) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            if user_id:
                # Usuarios ven: sus propias cuentas (checked_by) + las marcadas visible_to_users=1 por admin
                cursor.execute(
                    """SELECT * FROM accounts
                       WHERE (checked_by = ? AND grade NOT IN ('A', 'A+') AND (locked_by IS NULL OR locked_by = ?))
                          OR visible_to_users = 1
                       ORDER BY last_checked_at DESC""",
                    (user_id, user_id),
                )
            else:
                cursor.execute("SELECT * FROM accounts ORDER BY last_checked_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def toggle_account_visibility(self, email: str) -> bool:
        """Toggle visible_to_users en una cuenta. Retorna el nuevo estado (True=visible)."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT visible_to_users FROM accounts WHERE email = ?", (email,))
                row = cursor.fetchone()
                if not row:
                    return False
                new_val = 0 if row["visible_to_users"] else 1
                cursor.execute("UPDATE accounts SET visible_to_users = ? WHERE email = ?", (new_val, email))
                self.conn.commit()
                return bool(new_val)
            except Exception as e:
                logger.error(f"[DB] Error toggle_account_visibility: {e}")
                return False

    def assign_accounts(self, emails: List[str], user_id: int, assigned_by: int) -> int:
        """Admin asigna cuentas a usuario. INSERT OR IGNORE (idempotente). Retorna cantidad nueva."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                count = 0
                for email in emails:
                    cursor.execute(
                        "INSERT OR IGNORE INTO account_assignments (email, user_id, assigned_by, assigned_at) VALUES (?, ?, ?, ?)",
                        (email, user_id, assigned_by, now),
                    )
                    count += cursor.rowcount
                self.conn.commit()
                return count
            except Exception as e:
                logger.error(f"[DB] Error assign_accounts: {e}")
                return 0

    def unassign_accounts(self, emails: List[str], user_id: int) -> int:
        """Admin quita asignación de cuentas a usuario. Retorna cantidad removida."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                placeholders = ",".join("?" * len(emails))
                cursor.execute(
                    f"DELETE FROM account_assignments WHERE email IN ({placeholders}) AND user_id = ?",
                    (*emails, user_id),
                )
                count = cursor.rowcount
                self.conn.commit()
                return count
            except Exception as e:
                logger.error(f"[DB] Error unassign_accounts: {e}")
                return 0

    def get_verified_accounts(self, user_id: int = None) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM accounts WHERE status='LIVE' AND kyc_verified=1 AND checked_by=? ORDER BY last_checked_at DESC",
                    (user_id,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM accounts WHERE status='LIVE' AND kyc_verified=1 ORDER BY last_checked_at DESC"
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_filtered_accounts(self, months: int = 6, user_id: int = None) -> List[Dict]:
        try:
            cutoff = (now_mx() - timedelta(days=months * 30)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM accounts WHERE last_checked_at >= ? AND checked_by = ? ORDER BY last_checked_at DESC",
                    (cutoff, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM accounts WHERE last_checked_at >= ? ORDER BY last_checked_at DESC",
                    (cutoff,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_account_by_email(self, email: str, user_id: int = None) -> Optional[Dict]:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM accounts WHERE email = ? AND checked_by = ? ORDER BY last_checked_at DESC LIMIT 1",
                    (email, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM accounts WHERE email = ? ORDER BY last_checked_at DESC LIMIT 1",
                    (email,),
                )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def search_accounts_multi(self, text: str, user_id: int = None) -> List[Dict]:
        try:
            p = f"%{text}%"
            cursor = self.conn.cursor()
            if user_id:
                # Usuarios solo ven sus cuentas: no Grade A/A+, no bloqueadas por otros
                cursor.execute(
                    "SELECT * FROM accounts WHERE (email LIKE ? OR fullname LIKE ? OR password LIKE ?) AND checked_by = ? AND grade NOT IN ('A', 'A+') AND (locked_by IS NULL OR locked_by = ?) ORDER BY last_checked_at DESC LIMIT 50",
                    (p, p, p, user_id, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM accounts WHERE email LIKE ? OR fullname LIKE ? OR password LIKE ? ORDER BY last_checked_at DESC LIMIT 50",
                    (p, p, p),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def search_payment_tests_by_card(
        self, digits: str, user_id: int = None
    ) -> List[Dict]:
        try:
            p = f"%{digits}%"
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM payment_tests WHERE card_number LIKE ? AND tested_by = ? ORDER BY tested_at DESC LIMIT 50",
                    (p, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM payment_tests WHERE card_number LIKE ? ORDER BY tested_at DESC LIMIT 50",
                    (p,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_card_stats(self, card_number: str, user_id: int = None) -> Dict:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM payment_tests WHERE card_number = ? AND tested_by = ? ORDER BY tested_at DESC",
                    (card_number, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM payment_tests WHERE card_number = ? ORDER BY tested_at DESC",
                    (card_number,),
                )
            tests = [dict(row) for row in cursor.fetchall()]
            results = {}
            for t in tests:
                r = t.get("result", "?")
                results[r] = results.get(r, 0) + 1
            return {"tests": tests, "total": len(tests), "results": results}
        except Exception:
            return {"tests": [], "total": 0, "results": {}}

    def get_lock_status(self, email: str) -> Dict:
        """Estado actual del lock: activos + previous, para el modal de detalle."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT user_id, marked_at, status FROM account_locks WHERE email=? ORDER BY marked_at DESC",
                (email,)
            )
            rows = cursor.fetchall()
            active = [{"user_id": r["user_id"], "marked_at": r["marked_at"]} for r in rows if r["status"] == "active"]
            previous = [{"user_id": r["user_id"], "marked_at": r["marked_at"]} for r in rows if r["status"] == "previous"]
            is_locked = len(active) > 0
            # locked_by = último activo (para compatibilidad Telegram)
            locked_by = active[0]["user_id"] if active else None
            locked_at = active[0]["marked_at"] if active else None
            return {
                "is_locked": is_locked,
                "locked_by": locked_by,
                "locked_at": locked_at,
                "active": active,
                "previous": previous,
            }
        except Exception:
            return {"is_locked": False, "locked_by": None, "locked_at": None, "active": [], "previous": []}

    def get_lock_data_batch(self, emails: List[str]) -> Dict[str, Dict]:
        """Batch: retorna {email: {active: [...], previous: [...]}} para una lista de emails."""
        if not emails:
            return {}
        try:
            cursor = self.conn.cursor()
            placeholders = ",".join("?" * len(emails))
            cursor.execute(
                f"SELECT email, user_id, marked_at, status FROM account_locks WHERE email IN ({placeholders}) ORDER BY marked_at DESC",
                emails
            )
            result: Dict[str, Dict] = {}
            for row in cursor.fetchall():
                em = row["email"]
                if em not in result:
                    result[em] = {"active": [], "previous": []}
                entry = {"user_id": row["user_id"], "marked_at": row["marked_at"]}
                result[em][row["status"]].append(entry)
            return result
        except Exception:
            return {}

    def get_emails_used_by(self, user_id: int) -> set:
        """Emails donde el usuario tiene algún registro en account_locks (activo o previo)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT email FROM account_locks WHERE user_id=?", (user_id,))
            return {row[0] for row in cursor.fetchall()}
        except Exception:
            return set()

    def count_active_locks_by_user(self, user_id: int) -> int:
        """Cuenta cuántas cuentas tiene bloqueadas activamente un usuario."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM account_locks WHERE user_id=? AND status='active'", (user_id,))
            row = cursor.fetchone()
            return row["c"] if row else 0
        except Exception:
            return 0

    def mark_as_dead(self, email: str, password: str, checked_by: int = 0) -> bool:
        with self._lock:
            try:
                now = now_mx()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                today_str = now.strftime("%Y-%m-%d")
                
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, check_count, check_count_today, last_check_date FROM accounts WHERE email = ? AND password = ?",
                    (email, password),
                )
                existing = cursor.fetchone()
                
                if existing:
                    new_count = (existing["check_count"] or 0) + 1
                    if existing["last_check_date"] == today_str:
                        new_count_today = (existing["check_count_today"] or 0) + 1
                    else:
                        new_count_today = 1
                        
                    cursor.execute(
                        "UPDATE accounts SET status='DEAD', last_checked_at=?, checked_by=?, check_count=?, check_count_today=?, last_check_date=? WHERE email=? AND password=?",
                        (now_str, checked_by, new_count, new_count_today, today_str, email, password),
                    )
                    self.conn.commit()
                return True
            except Exception:
                return False

    def update_account_grade(self, email: str, password: str, grade: str, score: int = 0) -> bool:
        """Actualiza el grade y score de una cuenta de forma directa."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE accounts SET grade = ?, grade_score = ? WHERE email = ? AND password = ?",
                    (grade, score, email, password),
                )
                self.conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] Error update_account_grade: {e}")
                return False

    def get_withdrawals_by_account(self, email: str, user_id: int = None) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM withdrawal_tests WHERE account_email = ? AND tested_by = ? ORDER BY tested_at DESC",
                    (email, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM withdrawal_tests WHERE account_email = ? ORDER BY tested_at DESC",
                    (email,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_payment_tests_by_account(
        self, email: str, user_id: int = None
    ) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM payment_tests WHERE account_email = ? AND tested_by = ? ORDER BY tested_at DESC",
                    (email, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM payment_tests WHERE account_email = ? ORDER BY tested_at DESC",
                    (email,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def add_payment_test(
        self,
        email: str,
        password: str,
        card_number: str,
        card_expiry: str = "",
        card_cvv: str = "",
        amount: float = 0.0,
        result: str = "PENDING",
        tested_by: int = 0,
        notes: str = "",
    ) -> int:
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT INTO payment_tests 
                       (account_email, account_password, card_number, card_expiry, card_cvv, amount, result, tested_by, notes, tested_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        email,
                        password,
                        card_number,
                        card_expiry,
                        card_cvv,
                        amount,
                        result,
                        tested_by,
                        notes,
                        now,
                    ),
                )
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"[DB] Error add_payment_test: {e}")
                return 0

    def add_withdrawal_test(
        self,
        email: str,
        password: str,
        amount: float,
        bank: str = "",
        contact_info: str = "",
        notes: str = "",
        tested_by: int = 0,
        beneficiary_id: int = None,
    ) -> int:
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT INTO withdrawal_tests 
                       (account_email, account_password, amount, bank, contact_info, notes, tested_by, tested_at, beneficiary_id, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
                    (
                        email,
                        password,
                        amount,
                        bank,
                        contact_info,
                        notes,
                        tested_by,
                        now,
                        beneficiary_id,
                    ),
                )
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"[DB] Error add_withdrawal_test: {e}")
                return 0

    def get_withdrawal_beneficiaries(self, active_only: bool = True) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT * FROM withdrawal_beneficiaries WHERE is_active = 1 ORDER BY created_at DESC"
                )
            else:
                cursor.execute(
                    "SELECT * FROM withdrawal_beneficiaries ORDER BY created_at DESC"
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_beneficiary_by_id(self, ben_id: int) -> Optional[Dict]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM withdrawal_beneficiaries WHERE id = ?", (ben_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def add_withdrawal_beneficiary(
        self,
        alias: str,
        bank_name: str,
        account_number: str,
        contact_info: str = "",
        created_by: int = 0,
    ) -> int:
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT OR IGNORE INTO withdrawal_beneficiaries 
                       (alias, bank_name, account_number, contact_info, created_by, is_active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (alias, bank_name, account_number, contact_info, created_by, now),
                )
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"[DB] Error add_withdrawal_beneficiary: {e}")
                return 0

    def save_account_transactions(
        self, email: str, transactions: List[Dict], checked_by: int
    ) -> int:
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                self.conn.execute(
                    "DELETE FROM account_transactions WHERE account_email = ? AND checked_by = ?",
                    (email, checked_by),
                )
                for txn in transactions:
                    self.conn.execute(
                        "INSERT INTO account_transactions (account_email, txn_date, amount, status, txn_type, gateway, checked_by, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            email,
                            txn.get("date", ""),
                            float(txn.get("amount", 0)),
                            int(txn.get("status", 0)),
                            int(txn.get("type", 0)),
                            int(txn.get("gateway", 0)),
                            checked_by,
                            now,
                        ),
                    )
                self.conn.commit()
                return len(transactions)
            except Exception:
                return 0

    def get_account_transactions(self, email: str, user_id: int = None) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT * FROM account_transactions WHERE account_email = ? AND checked_by = ? ORDER BY txn_date DESC",
                    (email, user_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM account_transactions WHERE account_email = ? ORDER BY txn_date DESC",
                    (email,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_accounts_sorted_by_recent_transactions(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        try:
            cursor = self.conn.cursor()
            # Join con accounts para obtener password de cuentas con transacciones recientes
            query = """
                SELECT a.email, a.password
                FROM accounts a
                JOIN (
                    SELECT account_email, MAX(txn_date) as last_txn
                    FROM account_transactions
                    GROUP BY account_email
                ) t ON a.email = t.account_email
                ORDER BY t.last_txn DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_accounts_sorted_by_recent_transactions: {e}")
            return []

    def count_accounts_with_transactions(self) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(DISTINCT account_email) as c FROM account_transactions"
            )
            row = cursor.fetchone()
            return row["c"] if row else 0
        except Exception:
            return 0

    def get_accounts_stale(self, checked_by: int, hours: int = 12) -> List[Dict]:
        """
        Retorna cuentas del usuario que no han sido revisadas en las últimas N horas
        o que nunca han sido revisadas (last_checked IS NULL).
        
        Args:
            checked_by: ID del usuario que revisó las cuentas
            hours: Ventana de tiempo en horas (default: 12)
            
        Returns:
            Lista de cuentas ordenadas por last_checked ASC (más viejas primero)
        """
        try:
            cursor = self.conn.cursor()
            cutoff_time = (now_mx() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                """
                SELECT email, password, last_checked_at, check_count
                FROM accounts 
                WHERE checked_by = ? 
                AND (last_checked_at IS NULL OR last_checked_at < ?)
                ORDER BY last_checked_at ASC NULLS FIRST
                """,
                (checked_by, cutoff_time),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_accounts_stale: {e}")
            return []

    def set_manual_grade(self, email: str, grade: str, reason: str, user_id: int) -> bool:
        """Sobreescribe el grade de una cuenta manualmente (feedback para el algoritmo)."""
        try:
            now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE accounts SET manual_grade = ?, manual_grade_reason = ?, manual_grade_by = ?, manual_grade_at = ? WHERE email = ?",
                    (grade, reason, user_id, now, email),
                )
                self.conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[DB] Error set_manual_grade: {e}")
            return False

    def close(self):
        if self.conn:
            self.conn.close()

    def _create_sessions_table(self):
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS active_sessions (session_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, total_combos INTEGER DEFAULT 0, processed_combos INTEGER DEFAULT 0, status TEXT DEFAULT 'running', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        self.conn.commit()

    def create_session(self, session_id: str, user_id: int, total_combos: int) -> bool:
        try:
            now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
            with self._lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO active_sessions (session_id, user_id, total_combos, processed_combos, status, created_at, updated_at) VALUES (?, ?, ?, 0, 'running', ?, ?)",
                    (session_id, user_id, total_combos, now, now),
                )
                self.conn.commit()
            return True
        except Exception:
            return False

    def update_session_progress(self, session_id: str, processed: int) -> bool:
        try:
            now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
            with self._lock:
                self.conn.execute(
                    "UPDATE active_sessions SET processed_combos = ?, updated_at = ? WHERE session_id = ?",
                    (processed, now, session_id),
                )
                self.conn.commit()
            return True
        except Exception:
            return False

    def complete_session(self, session_id: str) -> bool:
        try:
            now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
            with self._lock:
                self.conn.execute(
                    "UPDATE active_sessions SET status = 'completed', updated_at = ? WHERE session_id = ?",
                    (now, session_id),
                )
                self.conn.commit()
            return True
        except Exception:
            return False

    def get_interrupted_sessions(self, user_id: int) -> list:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM active_sessions WHERE user_id = ? AND status = 'running' ORDER BY created_at DESC",
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def increment_human_usage(self, user_id: int, count: int = 1) -> bool:
        return True

    def set_last_human_use(self, user_id: int) -> bool:
        now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
        return self.save_user_settings(user_id, last_human_use=now)

    # =========================================================================
    # ACCOUNT NOTES (Nuevo sistema de notas para depósitos y retiros)
    # =========================================================================

    def add_account_note(
        self,
        email: str,
        password: str,
        note_type: str,
        note_text: str,
        card_number: str = None,
        card_expiry: str = None,
        card_cvv: str = None,
        amount: float = None,
        created_by: int = 0,
        created_by_name: str = "",
    ) -> int:
        """Agrega una nueva nota (depósito o retiro)."""
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT INTO account_notes 
                       (account_email, account_password, note_type, card_number, card_expiry, card_cvv,
                        note_text, amount, created_by, created_by_name, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        email,
                        password,
                        note_type,
                        card_number,
                        card_expiry,
                        card_cvv,
                        note_text,
                        amount,
                        created_by,
                        created_by_name,
                        now,
                        now,
                    ),
                )
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"[DB] Error add_account_note: {e}")
                return 0

    def get_account_notes(
        self,
        email: str,
        password: str,
        user_id: int = None,
        note_type: str = None,
    ) -> List[Dict]:
        """Obtiene notas de una cuenta. Si user_id es None, devuelve todas (para admins)."""
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM account_notes WHERE account_email = ? AND account_password = ?"
            params = [email, password]
            
            if user_id is not None:
                query += " AND created_by = ?"
                params.append(user_id)
            
            if note_type:
                query += " AND note_type = ?"
                params.append(note_type)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_account_notes: {e}")
            return []

    def search_notes_by_text(
        self,
        search_text: str,
        user_id: int = None,
    ) -> List[Dict]:
        """Busca notas por texto (para admins)."""
        try:
            cursor = self.conn.cursor()
            pattern = f"%{search_text}%"
            
            if user_id is not None:
                # Usuario normal: solo sus notas
                cursor.execute(
                    """SELECT * FROM account_notes 
                       WHERE note_text LIKE ? AND created_by = ?
                       ORDER BY created_at DESC LIMIT 50""",
                    (pattern, user_id),
                )
            else:
                # Admin: todas las notas
                cursor.execute(
                    """SELECT * FROM account_notes 
                       WHERE note_text LIKE ?
                       ORDER BY created_at DESC LIMIT 50""",
                    (pattern,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error search_notes_by_text: {e}")
            return []

    def get_notes_by_card_number(
        self,
        card_number: str,
        user_id: int = None,
    ) -> List[Dict]:
        """Busca notas por número de tarjeta — LIKE para encontrar parciales/truncadas."""
        try:
            cursor = self.conn.cursor()
            pattern = f"%{card_number}%"
            if user_id is not None:
                cursor.execute(
                    """SELECT * FROM account_notes 
                       WHERE card_number LIKE ? AND note_type = 'DEPOSIT' AND created_by = ?
                       ORDER BY created_at DESC LIMIT 50""",
                    (pattern, user_id),
                )
            else:
                cursor.execute(
                    """SELECT * FROM account_notes 
                       WHERE card_number LIKE ? AND note_type = 'DEPOSIT'
                       ORDER BY created_at DESC LIMIT 50""",
                    (pattern,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_notes_by_card_number: {e}")
            return []

    def delete_account_note(self, note_id: int, user_id: int) -> bool:
        """Elimina una nota (solo el autor puede eliminarla)."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "DELETE FROM account_notes WHERE id = ? AND created_by = ?",
                    (note_id, user_id),
                )
                self.conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] Error delete_account_note: {e}")
                return False


    def get_notes_counts(self) -> Dict[str, int]:
        """Retorna conteo de notas por email para la tabla del dashboard web."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT account_email, COUNT(*) as c FROM account_notes GROUP BY account_email")
                return {row["account_email"]: row["c"] for row in cursor.fetchall()}
            except Exception as e:
                logger.error(f"[DB] Error get_notes_counts: {e}")
                return {}


    # =========================================================================
    # ACCOUNT CARDS (Marriage tarjeta-cuenta para automatización de depósitos)
    # =========================================================================

    def get_card_account(self, card_number: str) -> Optional[Dict]:
        """Retorna la cuenta a la que está ligada esta tarjeta (o None si libre)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM account_cards WHERE card_number = ?",
                (card_number,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[DB] Error get_card_account: {e}")
            return None

    def register_card_to_account(
        self,
        card_number: str,
        card_expiry: str,
        card_cvv: str,
        email: str,
        password: str,
        registered_by: int,
        registered_by_name: str = "",
    ) -> int:
        """Registra marriage tarjeta-cuenta. UNIQUE en card_number — retorna 0 si ya existe."""
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT OR IGNORE INTO account_cards
                       (card_number, card_expiry, card_cvv, account_email, account_password,
                        registered_by, registered_by_name, registered_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (card_number, card_expiry, card_cvv, email, password,
                     registered_by, registered_by_name, now),
                )
                self.conn.commit()
                return cursor.lastrowid if cursor.rowcount > 0 else 0
            except Exception as e:
                logger.error(f"[DB] Error register_card_to_account: {e}")
                return 0

    def get_account_cards(self, email: str, password: str = None, include_burned: bool = False) -> List[Dict]:
        """Retorna todas las tarjetas ligadas a una cuenta. Por defecto excluye las quemadas."""
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM account_cards WHERE account_email = ?"
            if not include_burned:
                query += " AND status = 'ACTIVE'"
            query += " ORDER BY registered_at DESC"
            cursor.execute(query, (email,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_account_cards: {e}")
            return []

    def get_cards_for_account_by_email(self, email: str) -> List[Dict]:
        """Retorna tarjetas ligadas a una cuenta por email (sin requerir password)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT card_number, registered_by_name, registered_at FROM account_cards WHERE account_email = ? ORDER BY registered_at DESC",
                (email,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_cards_for_account_by_email: {e}")
            return []

    def update_card_data(self, card_id: int, card_number: str, card_expiry: str, card_cvv: str) -> bool:
        """Actualiza número, expiración y CVV de una tarjeta por su ID."""
        with self._lock:
            try:
                cursor = self.conn.execute(
                    "UPDATE account_cards SET card_number=?, card_expiry=?, card_cvv=? WHERE id=?",
                    (card_number, card_expiry, card_cvv, card_id),
                )
                self.conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] update_card_data: {e}")
                return False

    def update_card_stats(self, card_number: str, approved: bool) -> bool:
        """Actualiza estadísticas de depósito de una tarjeta tras ejecución."""
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                if approved:
                    self.conn.execute(
                        "UPDATE account_cards SET total_deposits = total_deposits + 1, total_approved = total_approved + 1, last_used_at = ?, status = 'ACTIVE' WHERE card_number = ?",
                        (now, card_number),
                    )
                else:
                    self.conn.execute(
                        "UPDATE account_cards SET total_deposits = total_deposits + 1, total_rejected = total_rejected + 1, last_used_at = ? WHERE card_number = ?",
                        (now, card_number),
                    )
                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DB] Error update_card_stats: {e}")
                return False

    def burn_card(self, card_number: str, reason: str = "3DS_REQUIRED") -> bool:
        """Marca una tarjeta como quemada (no usable para depósitos automáticos)."""
        with self._lock:
            try:
                now = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                self.conn.execute(
                    "UPDATE account_cards SET status = ?, last_used_at = ? WHERE card_number = ?",
                    (reason, now, card_number),
                )
                self.conn.commit()
                logger.info(f"[DB] Tarjeta {card_number} QUEMADA. Razón: {reason}")
                return True
            except Exception as e:
                logger.error(f"[DB] Error burn_card: {e}")
                return False

    def update_account_grade(self, email: str, new_grade: str) -> bool:
        """Actualiza el grado de una cuenta (A/F/etc)."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE accounts SET grade = ? WHERE email = ?",
                    (new_grade, email),
                )
                self.conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] Error update_account_grade: {e}")
                return False

    def record_deposit_result(
        self,
        email: str,
        password: str,
        card_number: str,
        card_expiry: str,
        card_cvv: str,
        amount: float,
        result: str,
        tested_by: int,
        notes: str = "",
    ) -> int:
        """Guarda resultado de depósito automático en payment_tests."""
        return self.add_payment_test(
            email=email,
            password=password,
            card_number=card_number,
            card_expiry=card_expiry,
            card_cvv=card_cvv,
            amount=amount,
            result=result,
            tested_by=tested_by,
            notes=notes,
        )

    def update_account_balance(self, email: str, password: str, balance_real: float, balance_bonos: float) -> bool:
        """Actualiza solo el balance de una cuenta existente (post-depósito web)."""
        try:
            balance_total = balance_real + balance_bonos
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE accounts SET balance_real = ?, balance_bonos = ?, balance_total = ?
                   WHERE email = ? AND password = ?""",
                (balance_real, balance_bonos, balance_total, email, password),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[DB] Error update_account_balance: {e}")
            return False

    def update_account_post_deposit(
        self, email: str, password: str,
        balance_real: float, balance_bonos: float,
        deposit_amount: float, deposit_date: str,
    ) -> bool:
        """Actualiza balance + metadata del último depósito tras un depósito web exitoso."""
        try:
            balance_total = balance_real + balance_bonos
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE accounts SET
                   balance_real = ?, balance_bonos = ?, balance_total = ?,
                   last_deposit_amount = ?, last_deposit_date = ?
                   WHERE email = ? AND password = ?""",
                (balance_real, balance_bonos, balance_total,
                 deposit_amount, deposit_date, email, password),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[DB] Error update_account_post_deposit: {e}")
            return False

    def get_deposit_history(self, email: str, password: str) -> List[Dict]:
        """Historial de depósitos del bot para una cuenta (desde payment_tests)."""
        return self.get_payment_tests_by_account(email)

    def get_card_deposit_history(self, card_number: str) -> List[Dict]:
        """Historial de depósitos del bot con una tarjeta específica."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM payment_tests WHERE card_number = ? ORDER BY tested_at DESC",
                (card_number,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_card_deposit_history: {e}")
            return []

    def update_account_grade(self, email: str, password: str, grade: str, score: int = None):
        """Actualiza el grade y score calculado de una cuenta."""
        try:
            cursor = self.conn.cursor()
            # En la tabla, la columna se llama grade_score según migraciones (linea 118)
            cursor.execute(
                "UPDATE accounts SET grade = ?, grade_score = ?, last_checked_at = ? WHERE email = ? AND password = ?",
                (grade, score, now_mx().isoformat(), email, password),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"[DB] Error update_account_grade: {e}")
            return False

    def update_account_stats(self, email: str, password: str, **kwargs):
        """Actualiza múltiples campos de una cuenta (balance, last_deposit, etc)."""
        try:
            fields = []
            values = []
            # Mapeo de nombres de API a nombres de DB
            maper = {
                "balance_real": "balance_real",
                "balance_bonos": "balance_bonos",
                "balance_total": "balance_total",
                "last_deposit_date": "last_deposit_date",
                "last_deposit_amount": "last_deposit_amount",
                "last_deposit_status": "status", # o lo ignoramos si no hay columna
                "grade": "grade",
                "grade_score": "grade_score",
                "fullname": "fullname",
                "address": "address",
                "birthdate": "birthdate"
            }
            
            for k, v in kwargs.items():
                col = maper.get(k)
                if col:
                    fields.append(f"{col} = ?")
                    values.append(v)
            
            if not fields: return False
            
            fields.append("last_checked_at = ?")
            values.append(now_mx().isoformat())
            
            # WHERE clause
            values.append(email)
            values.append(password)
            
            sql = f"UPDATE accounts SET {', '.join(fields)} WHERE email = ? AND password = ?"
            cursor = self.conn.cursor()
            cursor.execute(sql, tuple(values))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"[DB] Error update_account_stats: {e}")
            return False

    def get_account_deposit_history(self, email: str, limit: int = 50) -> List[Dict]:
        """Historial de depósitos (payment_tests) para una cuenta. Usado por Web Dashboard."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM payment_tests WHERE account_email = ? ORDER BY tested_at DESC LIMIT ?",
                (email, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[DB] Error get_account_deposit_history: {e}")
            return []

    # ════════════════════════════════════════════════════════════════
    # MIGRATION 001 — JWT cache + Cards + Attempts + Missions + BIN stats
    # ════════════════════════════════════════════════════════════════

    # ─── JWT cache ────────────────────────────────────────────────
    def get_jwt_cache(self, email: str) -> Optional[Dict]:
        """Retorna {token, expires_at, user_id} si vigente (expires_at > now), None si expirado/inexistente."""
        with self._lock:
            try:
                import time as _time
                now = int(_time.time())
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT jwt_token, jwt_expires_at, jwt_user_id FROM accounts "
                    "WHERE email = ? AND jwt_token IS NOT NULL AND jwt_expires_at > ? "
                    "ORDER BY last_checked_at DESC LIMIT 1",
                    (email, now),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "token": row["jwt_token"],
                    "expires_at": row["jwt_expires_at"],
                    "user_id": row["jwt_user_id"],
                }
            except Exception as e:
                logger.error(f"[DB] get_jwt_cache error: {e}")
                return None

    def save_jwt_cache(self, email: str, token: str, expires_at_unix: int, user_id: Optional[str]) -> bool:
        """UPSERT del JWT en accounts (todas las filas con ese email)."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "UPDATE accounts SET jwt_token = ?, jwt_expires_at = ?, jwt_user_id = ? WHERE email = ?",
                    (token, int(expires_at_unix), str(user_id) if user_id else None, email),
                )
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] save_jwt_cache error: {e}")
                return False

    # ─── Cards ────────────────────────────────────────────────────
    def create_card(
        self,
        fingerprint: str, card_number: str, bin: str, last_4: str,
        exp_month: int, exp_year: int, cvv: Optional[str],
        holder_name: Optional[str], operator_id: int,
    ) -> Optional[int]:
        """INSERT OR IGNORE por fingerprint. Retorna el id (nuevo o existente)."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT OR IGNORE INTO cards "
                    "(fingerprint, card_number, bin, last_4, exp_month, exp_year, cvv, holder_name, created_by_operator_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fingerprint, card_number, bin, last_4, int(exp_month), int(exp_year),
                     cvv, holder_name, int(operator_id)),
                )
                self.conn.commit()
                cur.execute("SELECT id FROM cards WHERE fingerprint = ?", (fingerprint,))
                row = cur.fetchone()
                return row["id"] if row else None
            except Exception as e:
                logger.error(f"[DB] create_card error: {e}")
                return None

    def get_cards(self, operator_id: int, role: str) -> List[Dict]:
        """Lista cards visibles. SuperAdmin ve todas; otros solo las propias."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                if role == "superadmin":
                    cur.execute("SELECT * FROM card_usage_summary ORDER BY last_attempt_at DESC NULLS LAST, id DESC")
                else:
                    cur.execute(
                        "SELECT * FROM card_usage_summary WHERE created_by_operator_id = ? "
                        "ORDER BY last_attempt_at DESC NULLS LAST, id DESC",
                        (int(operator_id),),
                    )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_cards error: {e}")
                return []

    def get_card_by_id(self, card_id: int, operator_id: int, role: str) -> Optional[Dict]:
        """Retorna card si visible para operator. None en otro caso."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT * FROM cards WHERE id = ?", (int(card_id),))
                row = cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                if role != "superadmin" and int(d.get("created_by_operator_id") or 0) != int(operator_id):
                    return None
                return d
            except Exception as e:
                logger.error(f"[DB] get_card_by_id error: {e}")
                return None

    def get_card_usage(self, card_id: int) -> List[Dict]:
        """Lista deposit_attempts para esa tarjeta (ordenados desc)."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT * FROM deposit_attempts WHERE card_id = ? ORDER BY created_at DESC",
                    (int(card_id),),
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_card_usage error: {e}")
                return []

    def update_card_stats(self, card_id: int, approved: bool, amount: float) -> bool:
        """Incrementa counters atómicos en cards y last_used_at."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                if approved:
                    cur.execute(
                        "UPDATE cards SET total_attempts = total_attempts + 1, "
                        "total_approved = total_approved + 1, "
                        "total_amount_approved = total_amount_approved + ?, "
                        "last_used_at = datetime('now') WHERE id = ?",
                        (float(amount or 0.0), int(card_id)),
                    )
                else:
                    cur.execute(
                        "UPDATE cards SET total_attempts = total_attempts + 1, "
                        "total_rejected = total_rejected + 1, "
                        "last_used_at = datetime('now') WHERE id = ?",
                        (int(card_id),),
                    )
                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DB] update_card_stats error: {e}")
                return False

    def mark_card_status(self, card_id: int, status: str, reason: Optional[str] = None) -> bool:
        """status ∈ usable | exhausted | banned | expired"""
        with self._lock:
            try:
                cur = self.conn.cursor()
                if status == "banned":
                    cur.execute(
                        "UPDATE cards SET status = ?, banned_at = datetime('now'), banned_reason = ? WHERE id = ?",
                        (status, reason, int(card_id)),
                    )
                else:
                    cur.execute(
                        "UPDATE cards SET status = ? WHERE id = ?",
                        (status, int(card_id)),
                    )
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] mark_card_status error: {e}")
                return False

    def update_card_notes(self, card_id: int, notes: str) -> bool:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute("UPDATE cards SET notes = ? WHERE id = ?", (notes, int(card_id)))
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] update_card_notes error: {e}")
                return False

    # ─── Deposit attempts + BIN stats ─────────────────────────────
    def log_attempt(
        self,
        attempt_id: str,
        batch_id: Optional[str],
        account_email: str,
        card_id: Optional[int],
        amount: float,
        source: str,
        operator_id: Optional[int],
        status: str,
        gateway_response_raw: Optional[str] = None,
        gateway_txn_id: Optional[str] = None,
        balance_before: Optional[float] = None,
        balance_after: Optional[float] = None,
        duration_ms: Optional[int] = None,
        captcha_cost: float = 0.0,
        rejection_reason: Optional[str] = None,
        mission_id: Optional[str] = None,
        card_pipe: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """Inserta intento en deposit_attempts y actualiza card_stats + bin_stats si corresponde."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT INTO deposit_attempts "
                    "(attempt_id, batch_id, mission_id, account_email, card_id, amount, source, operator_id, "
                    "status, rejection_reason, gateway_response_raw, gateway_txn_id, "
                    "balance_before, balance_after, duration_ms, captcha_cost, card_pipe) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        attempt_id, batch_id, mission_id, account_email,
                        int(card_id) if card_id is not None else None,
                        float(amount or 0.0), source,
                        int(operator_id) if operator_id is not None else None,
                        status, rejection_reason, gateway_response_raw, gateway_txn_id,
                        balance_before, balance_after,
                        int(duration_ms) if duration_ms is not None else None,
                        float(captcha_cost or 0.0),
                        str(card_pipe) if card_pipe else None,
                    ),
                )

                # Card stats
                if card_id is not None:
                    if status == "approved":
                        cur.execute(
                            "UPDATE cards SET total_attempts = total_attempts + 1, "
                            "total_approved = total_approved + 1, "
                            "total_amount_approved = total_amount_approved + ?, "
                            "last_used_at = datetime('now') WHERE id = ?",
                            (float(amount or 0.0), int(card_id)),
                        )
                    elif status in ("rejected", "gateway_error", "timeout"):
                        cur.execute(
                            "UPDATE cards SET total_attempts = total_attempts + 1, "
                            "total_rejected = total_rejected + 1, "
                            "last_used_at = datetime('now') WHERE id = ?",
                            (int(card_id),),
                        )

                # BIN stats
                if card_id is not None and status in ("approved", "rejected"):
                    cur.execute("SELECT bin FROM cards WHERE id = ?", (int(card_id),))
                    bin_row = cur.fetchone()
                    if bin_row:
                        bin_v = bin_row["bin"]
                        approved_flag = (status == "approved")
                        if approved_flag:
                            cur.execute(
                                "INSERT INTO bin_stats (bin, gateway_name, total_attempts, total_approved, total_rejected, "
                                "last_used_at, last_approved_at) VALUES (?, 'default', 1, 1, 0, datetime('now'), datetime('now')) "
                                "ON CONFLICT(bin, gateway_name) DO UPDATE SET "
                                "total_attempts = total_attempts + 1, total_approved = total_approved + 1, "
                                "last_used_at = datetime('now'), last_approved_at = datetime('now')",
                                (bin_v,),
                            )
                        else:
                            cur.execute(
                                "INSERT INTO bin_stats (bin, gateway_name, total_attempts, total_approved, total_rejected, "
                                "last_used_at, last_rejected_at) VALUES (?, 'default', 1, 0, 1, datetime('now'), datetime('now')) "
                                "ON CONFLICT(bin, gateway_name) DO UPDATE SET "
                                "total_attempts = total_attempts + 1, total_rejected = total_rejected + 1, "
                                "last_used_at = datetime('now'), last_rejected_at = datetime('now')",
                                (bin_v,),
                            )

                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DB] log_attempt error: {e}")
                return False

    def update_bin_stats(self, bin: str, gateway_name: str, approved: bool) -> bool:
        """UPSERT bin_stats con incremento. Útil cuando no hay card_id pero sí BIN."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                if approved:
                    cur.execute(
                        "INSERT INTO bin_stats (bin, gateway_name, total_attempts, total_approved, total_rejected, "
                        "last_used_at, last_approved_at) VALUES (?, ?, 1, 1, 0, datetime('now'), datetime('now')) "
                        "ON CONFLICT(bin, gateway_name) DO UPDATE SET "
                        "total_attempts = total_attempts + 1, total_approved = total_approved + 1, "
                        "last_used_at = datetime('now'), last_approved_at = datetime('now')",
                        (bin, gateway_name),
                    )
                else:
                    cur.execute(
                        "INSERT INTO bin_stats (bin, gateway_name, total_attempts, total_approved, total_rejected, "
                        "last_used_at, last_rejected_at) VALUES (?, ?, 1, 0, 1, datetime('now'), datetime('now')) "
                        "ON CONFLICT(bin, gateway_name) DO UPDATE SET "
                        "total_attempts = total_attempts + 1, total_rejected = total_rejected + 1, "
                        "last_used_at = datetime('now'), last_rejected_at = datetime('now')",
                        (bin, gateway_name),
                    )
                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DB] update_bin_stats error: {e}")
                return False

    def get_bin_stats(self) -> List[Dict]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT * FROM bin_stats ORDER BY last_used_at DESC NULLS LAST")
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_bin_stats error: {e}")
                return []

    # ─── Missions ─────────────────────────────────────────────────
    def create_mission(self, mission_id: str, type: str, operator_id: int, config_json: str) -> Optional[str]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT INTO missions (mission_id, type, operator_id, config_json, status) "
                    "VALUES (?, ?, ?, ?, 'pending')",
                    (mission_id, type, int(operator_id), config_json),
                )
                self.conn.commit()
                return mission_id
            except Exception as e:
                logger.error(f"[DB] create_mission error: {e}")
                return None

    def update_mission_status(self, mission_id: str, status: str, progress_json: Optional[str] = None,
                              error_message: Optional[str] = None) -> bool:
        with self._lock:
            try:
                cur = self.conn.cursor()
                fields = ["status = ?"]
                values: List[Any] = [status]
                if progress_json is not None:
                    fields.append("progress_json = ?")
                    values.append(progress_json)
                if error_message is not None:
                    fields.append("error_message = ?")
                    values.append(error_message)
                if status == "running":
                    fields.append("started_at = COALESCE(started_at, datetime('now'))")
                if status == "paused":
                    fields.append("paused_at = datetime('now')")
                if status in ("done", "aborted", "error"):
                    fields.append("completed_at = datetime('now')")
                values.append(mission_id)
                cur.execute(f"UPDATE missions SET {', '.join(fields)} WHERE mission_id = ?", tuple(values))
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] update_mission_status error: {e}")
                return False

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"[DB] get_mission error: {e}")
                return None

    def get_missions(self, operator_id: int, role: str, status_filter: Optional[str] = None) -> List[Dict]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                clauses = []
                values: List[Any] = []
                if role != "superadmin":
                    clauses.append("operator_id = ?")
                    values.append(int(operator_id))
                if status_filter:
                    clauses.append("status = ?")
                    values.append(status_filter)
                where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
                cur.execute(f"SELECT * FROM missions{where} ORDER BY created_at DESC", tuple(values))
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_missions error: {e}")
                return []

    # ─── Process log ──────────────────────────────────────────────
    def log_process_phase(
        self,
        process_id: str,
        process_type: str,
        phase: str,
        payload_json: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> bool:
        with self._lock:
            try:
                import time as _time
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT INTO process_log (process_id, process_type, phase, payload_json, duration_ms, timestamp_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (process_id, process_type, phase, payload_json,
                     int(duration_ms) if duration_ms is not None else None,
                     int(_time.time() * 1000)),
                )
                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DB] log_process_phase error: {e}")
                return False

    def get_process_log(self, process_id: str) -> List[Dict]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT * FROM process_log WHERE process_id = ? ORDER BY timestamp_ms ASC",
                    (process_id,),
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_process_log error: {e}")
                return []

    def count_recent_process_log(
        self, process_type: str, operator_id: Optional[int], minutes: int
    ) -> int:
        """Cuenta filas en process_log del tipo dado en los últimos `minutes`. Si operator_id, filtra por payload."""
        with self._lock:
            try:
                import time as _time
                cutoff_ms = int((_time.time() - minutes * 60) * 1000)
                cur = self.conn.cursor()
                if operator_id is None:
                    cur.execute(
                        "SELECT COUNT(*) AS n FROM process_log WHERE process_type = ? AND timestamp_ms >= ?",
                        (process_type, cutoff_ms),
                    )
                else:
                    # Filtra payload que contenga operator_id (json substring match)
                    needle = f'"operator_id": {int(operator_id)}'
                    cur.execute(
                        "SELECT COUNT(*) AS n FROM process_log WHERE process_type = ? AND timestamp_ms >= ? "
                        "AND payload_json LIKE ?",
                        (process_type, cutoff_ms, f"%{needle}%"),
                    )
                row = cur.fetchone()
                return int(row["n"]) if row else 0
            except Exception as e:
                logger.error(f"[DB] count_recent_process_log error: {e}")
                return 0

    def get_recent_process_log(
        self, process_type: str, operator_id: Optional[int], limit: int = 10
    ) -> List[Dict]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                if operator_id is None:
                    cur.execute(
                        "SELECT * FROM process_log WHERE process_type = ? "
                        "ORDER BY timestamp_ms DESC LIMIT ?",
                        (process_type, int(limit)),
                    )
                else:
                    needle = f'"operator_id": {int(operator_id)}'
                    cur.execute(
                        "SELECT * FROM process_log WHERE process_type = ? AND payload_json LIKE ? "
                        "ORDER BY timestamp_ms DESC LIMIT ?",
                        (process_type, f"%{needle}%", int(limit)),
                    )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_recent_process_log error: {e}")
                return []

    # ─── Account balance upsert (pre-warm / watchdog) ─────────────
    def upsert_account_balance(self, email: str, details: Dict) -> bool:
        """Actualiza balance+last_checked en todas las filas con ese email. Tolera details parcial."""
        with self._lock:
            try:
                if not isinstance(details, dict):
                    return False
                br = float(details.get("balance_real") or 0.0)
                bb = float(details.get("balance_bonos") or 0.0)
                bt = br + bb
                now_str = now_mx().strftime("%Y-%m-%d %H:%M:%S")
                cur = self.conn.cursor()
                cur.execute(
                    "UPDATE accounts SET balance_real = ?, balance_bonos = ?, balance_total = ?, "
                    "last_checked_at = ? WHERE email = ?",
                    (br, bb, bt, now_str, email),
                )
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] upsert_account_balance error: {e}")
                return False

    # ─── Watchdog candidates ──────────────────────────────────────
    def get_watchdog_candidates(self, limit: int = 100) -> List[Dict]:
        """
        Devuelve cuentas elegibles para chequeo automático, con peso (priority):
          tier 1 (peso 3): LIVE AND (balance_total>=50 OR has_approved_deposit)
          tier 2 (peso 2): LIVE AND grade IN ('A','B') AND last_checked > 24h
          tier 3 (peso 1): resto de LIVE AND last_checked > 48h
        Excluye: status='DEAD', locked actualmente, checked manualmente últimas 2h.
        Ordena por priority desc, last_checked_at asc.
        """
        with self._lock:
            try:
                cur = self.conn.cursor()
                # has_approved_deposit: existe payment_tests con result LIKE 'BANK_APPROVED' o deposit_attempts approved
                cur.execute(
                    """
                    SELECT * FROM (
                        SELECT a.email, a.password, a.balance_total, a.grade,
                               a.last_checked_at, a.status, a.locked_by, a.locked_at,
                               CASE
                                   WHEN a.status = 'LIVE' AND (
                                       a.balance_total >= 50 OR
                                       EXISTS(SELECT 1 FROM deposit_attempts da
                                              WHERE da.account_email = a.email AND da.status='approved')
                                   ) THEN 3
                                   WHEN a.status = 'LIVE' AND a.grade IN ('A','B')
                                        AND (julianday('now') - julianday(a.last_checked_at)) * 24 > 24
                                        THEN 2
                                   WHEN a.status = 'LIVE'
                                        AND (julianday('now') - julianday(a.last_checked_at)) * 24 > 48
                                        THEN 1
                                   ELSE 0
                               END AS priority
                        FROM accounts a
                        WHERE a.status = 'LIVE'
                          AND (a.locked_by IS NULL OR a.locked_by = 0)
                          AND (a.last_checked_at IS NULL OR
                               (julianday('now') - julianday(a.last_checked_at)) * 24 > 2)
                    ) WHERE priority > 0
                    ORDER BY priority DESC, last_checked_at ASC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_watchdog_candidates error: {e}")
                return []

    # ─── Notifications ────────────────────────────────────────────
    def create_notification(
        self,
        type: str,
        title: str,
        description: Optional[str] = None,
        payload_json: Optional[str] = None,
        recipient_operator_id: Optional[int] = None,
        severity: str = "info",
    ) -> Optional[int]:
        with self._lock:
            try:
                if severity not in ("info", "warn", "error"):
                    severity = "info"
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT INTO notifications (recipient_operator_id, type, title, description, payload_json, severity) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        int(recipient_operator_id) if recipient_operator_id is not None else None,
                        type, title, description, payload_json, severity,
                    ),
                )
                self.conn.commit()
                return cur.lastrowid
            except Exception as e:
                logger.error(f"[DB] create_notification error: {e}")
                return None

    def get_notifications(
        self, operator_id: int, only_unread: bool = False, limit: int = 50
    ) -> List[Dict]:
        with self._lock:
            try:
                cur = self.conn.cursor()
                where = "(recipient_operator_id IS NULL OR recipient_operator_id = ?)"
                params: List[Any] = [int(operator_id)]
                if only_unread:
                    where += " AND read_at IS NULL"
                cur.execute(
                    f"SELECT * FROM notifications WHERE {where} ORDER BY created_at DESC LIMIT ?",
                    tuple(params + [int(limit)]),
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_notifications error: {e}")
                return []

    def mark_notification_read(self, notification_id: int, operator_id: int) -> bool:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "UPDATE notifications SET read_at = datetime('now') "
                    "WHERE id = ? AND (recipient_operator_id IS NULL OR recipient_operator_id = ?) "
                    "AND read_at IS NULL",
                    (int(notification_id), int(operator_id)),
                )
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.error(f"[DB] mark_notification_read error: {e}")
                return False

    def mark_all_read(self, operator_id: int) -> int:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "UPDATE notifications SET read_at = datetime('now') "
                    "WHERE (recipient_operator_id IS NULL OR recipient_operator_id = ?) "
                    "AND read_at IS NULL",
                    (int(operator_id),),
                )
                self.conn.commit()
                return cur.rowcount
            except Exception as e:
                logger.error(f"[DB] mark_all_read error: {e}")
                return 0

    def count_unread(self, operator_id: int) -> int:
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) AS n FROM notifications "
                    "WHERE (recipient_operator_id IS NULL OR recipient_operator_id = ?) AND read_at IS NULL",
                    (int(operator_id),),
                )
                row = cur.fetchone()
                return int(row["n"]) if row else 0
            except Exception as e:
                logger.error(f"[DB] count_unread error: {e}")
                return 0

    def get_missions_by_status(self, status: str) -> List[Dict]:
        """Lista misiones globalmente filtradas por status (para detección de huérfanas al startup)."""
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT * FROM missions WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                logger.error(f"[DB] get_missions_by_status error: {e}")
                return []


db = BetmexicoDB()
