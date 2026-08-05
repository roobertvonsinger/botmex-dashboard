#!/usr/bin/env python3
# BetMexico Web v2 — minimal dashboard sobre la BD existente.
# Lee betmexico_accounts.db (la misma que el bot TG). Sin lógica de polling.

from __future__ import annotations
import sqlite3, os, re, sys, time, traceback
import asyncio
import json as _json
import logging as _logging
import logging.handlers as _logging_handlers
import queue as _stdlib_queue
import threading
import urllib.request
import httpx
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from curp_utils import compute_curp, generate_curp_candidates
from renapo_validator import validate_renapo_curp

# ── FIX CRÍTICO: doble-import de este archivo ───────────────────────────────
# El container arranca con `python web/app.py` → este script se carga como
# `__main__`. Pero `deposits.py`, `prewarm.py` y otros hacen `from app import …`
# que carga el ARCHIVO DE NUEVO como módulo `app` (instancia distinta en
# sys.modules). Resultado: cada uno tiene su propio `_sse_queues`.
#
# Síntoma: clientes SSE se registran en `__main__._sse_queues`, pero las
# misiones Programado hacían `_broadcast` desde `app._sse_queues` (otra lista,
# siempre vacía). El frontend nunca recibía `scheduled_phase` aunque el
# backend los emitía correctamente.
#
# Fix: aliasear `sys.modules['app']` a este mismo módulo apenas arrancamos.
# Cuando `deposits.py` haga `from app import _broadcast`, Python encuentra
# 'app' ya en sys.modules y reutiliza esta instancia. Una sola lista
# `_sse_queues`, un solo `_broadcast`.
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])

# ── File logging para que /api/logs pueda servir desde Docker ─────────────────
# Antes el endpoint usaba `journalctl -u betmexico-web.service` pero en KVM4
# corremos en Docker (no hay systemd). Resultado: logs no se cargaban en el
# dashboard desde la migración 2026-05-11. Fix: agregar FileHandler que escriba
# a /data/logs/dashboard.log (volumen montado, persiste entre restarts) y leer
# de ahí en el endpoint.
_LOGS_DIR = Path("/data/logs")
try:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_FILE = _LOGS_DIR / "dashboard.log"
    _root_logger = _logging.getLogger()
    # Solo agregar si no existe ya (evita duplicar en hot-reload)
    if not any(isinstance(h, _logging_handlers.RotatingFileHandler)
               and getattr(h, "_dashboard_handler", False)
               for h in _root_logger.handlers):
        _fh = _logging_handlers.RotatingFileHandler(
            str(_LOG_FILE), maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        _fh._dashboard_handler = True  # marker
        _fh.setFormatter(_logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        ))
        _root_logger.addHandler(_fh)
        if _root_logger.level == _logging.NOTSET or _root_logger.level > _logging.INFO:
            _root_logger.setLevel(_logging.INFO)

    # Refrescos masivos (account_refresh + jwt_keeper) a SU PROPIO archivo,
    # NO al dashboard.log — Robert 2026-08-05: los refrescos masivos no deben
    # spamear el log operativo. propagate=False evita que además caigan al root.
    _refresh_loggers = [_logging.getLogger("betmexico.dashboard.account_refresh"),
                        _logging.getLogger("betmexico.dashboard.jwt_keeper")]
    for _rl in _refresh_loggers:
        _rl.propagate = False
        if not any(isinstance(h, _logging_handlers.RotatingFileHandler)
                   and getattr(h, "_refresh_handler", False)
                   for h in _rl.handlers):
            _rfh = _logging_handlers.RotatingFileHandler(
                str(_LOGS_DIR / "refresh.log"), maxBytes=10 * 1024 * 1024,
                backupCount=3, encoding="utf-8",
            )
            _rfh._refresh_handler = True  # marker
            _rfh.setFormatter(_logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
            ))
            _rl.addHandler(_rfh)
except Exception as _e:
    print(f"[boot] file logger init failed: {_e}")

# Permitir importar módulos del bot (betmexico_db, betmexico_login_service, etc.)
# que viven en el directorio padre cuando el VPS los tiene desplegados.
_HERE = Path(__file__).parent
_BOT_DIR = _HERE.parent
if (_BOT_DIR / "betmexico_db.py").exists() and str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

# Carga EAGER de deps del bot — antes que prewarm/deposits los importen lazy.
# Evita circular imports en betmexico_db (carga partial → crash).
BOT_DEPS_OK = False
BOT_MAKE_POOL = None
BOT_SCORE_PAYMENT = None
try:
    if (_BOT_DIR / "betmexico_db.py").exists():
        # Romper ciclo betmexico_db ↔ betmexico_config: cargar config primero
        # para que cuando betmexico_db haga `from betmexico_config import ...`
        # ya esté completo, y betmexico_config no necesite re-import betmexico_db.
        import betmexico_config as _bot_cfg_mod  # noqa
        import betmexico_db as _bot_db_mod  # noqa
        from betmexico_login_service import make_pool as BOT_MAKE_POOL  # noqa
        try:
            from betmexico_payment_analyzer import score_payment_readiness as BOT_SCORE_PAYMENT  # noqa
        except Exception:
            pass
        BOT_DEPS_OK = True
        print("[deps] bot modules loaded OK")
except Exception as _e:
    import traceback as _tb
    print(f"[deps] bot init failed: {_e}")
    _tb.print_exc()

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Union

import auth as _auth
from auth import require_session, require_operator_view
from prewarm import router as _prewarm_router
from deposits import router as _deposits_router
from withdrawals import (
    execute_withdrawal,
    get_pending_withdrawal,
    get_bank_transaction,
    NoApprovedWithdrawalAccount,
    MultipleApprovedAccounts,
    ConcurrentWithdrawalPending,
    InsufficientBalance,
    JwtExpired,
)

ROOT = Path(__file__).parent
STATIC = ROOT / "static"

# Load .env (manual mini-parser, no extra deps)
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _s = _line.strip()
        if not _s or _s.startswith("#") or "=" not in _s:
            continue
        _k, _v = _s.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# La BD vive donde corre el bot. Local: usa ENV BETMEX_DB. VPS: /opt/betmexico/bot/betmexico_accounts.db
DB_PATH = Path(os.environ.get("BETMEX_DB", str(ROOT.parent / "betmexico_accounts.db")))


# Instrumentación temporal (Robert, campo 2026-07-25: 2 retiros reales chocaron con
# "database is locked" sostenido en <20min, "no debe pasar" — necesitamos la causa
# raíz, no otro parche). Registro de writes activos + stack de apertura: si un write
# tarda de más o choca con lock, logueamos QUIÉN más estaba escribiendo al mismo
# tiempo y desde dónde. Costo ínfimo (dict + lock), quitar cuando se identifique
# y arregle el culpable real.
_db_write_registry: dict = {}
_db_write_registry_lock = threading.Lock()
_db_write_counter = 0


@contextmanager
def db(write: bool = False):
    global _db_write_counter
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    entry_id = None
    stack = None
    t0 = time.time()
    if write:
        with _db_write_registry_lock:
            _db_write_counter += 1
            entry_id = _db_write_counter
            stack = "".join(traceback.format_stack()[:-1])
            _db_write_registry[entry_id] = (t0, stack)
        conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        if write:
            conn.commit()
    except Exception as e:
        if write:
            conn.rollback()
            if isinstance(e, sqlite3.OperationalError) and "locked" in str(e):
                with _db_write_registry_lock:
                    others = {k: v for k, v in _db_write_registry.items() if k != entry_id}
                _dblg = _logging.getLogger("betmexico.dashboard.db")
                if others:
                    held = "\n---\n".join(
                        f"[write#{k} abierto hace {time.time() - t:.1f}s, origen:]\n{s}"
                        for k, (t, s) in others.items()
                    )
                    _dblg.error(f"[db] LOCK — {len(others)} write(s) activos simultáneos AHORA:\n{held}")
                else:
                    _dblg.error(
                        f"[db] LOCK sin otro write registrado en este proceso — el lock viene de "
                        f"fuera del registro (conexión huérfana o proceso externo). Origen de este write:\n{stack}"
                    )
        raise
    finally:
        dt = time.time() - t0
        if write:
            with _db_write_registry_lock:
                _db_write_registry.pop(entry_id, None)
            if dt > 2.0:
                _logging.getLogger("betmexico.dashboard.db").warning(
                    f"[db] write#{entry_id} tardó {dt:.1f}s sosteniendo el writer global de SQLite — origen:\n{stack}"
                )
        conn.close()


def _db_write_with_retry(fn, *, attempts: int = 3, base_delay: float = 0.2):
    """Ejecuta `fn(conn)` dentro de `db(write=True)` con retry ante `database is locked`.

    Robert, campo 2026-07-25: los writes triviales (UPDATE de cooldown / rl_streak /
    locked_by) mueren al primer lock sostenido y, por contención bot↔web + jwt_keeper
    corriendo su ciclo horario, tumbaban el depósito del operador. En vez de N copias
    del loop (revolvedero), UN helper.

    Backoff corto (no el de 5×10s del retiro — ese es para dinero real). Aquí 3 intentos
    con delays 0.2/0.5/1.0s: cada `db(write=True)` ya tiene su `timeout=10` interno, así
    que el primer intento espera hasta 10s; si aún así choca, un segundo intento rápido
    suele entrar en el gap que dejó el writer anterior. Si los 3 fallan, relanza — el
    caller decide (best-effort lo traga, crítico lo propaga).

    `fn` recibe la conexión y devuelve lo que quiera (rowcount, fila, None).
    """
    _lg = _logging.getLogger("betmexico.dashboard.db")
    last = None
    for attempt in range(1, attempts + 1):
        try:
            with db(write=True) as c:
                return fn(c)
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e) or attempt == attempts:
                raise
            delay = base_delay * attempt  # 0.2, 0.4, 0.6…
            _lg.warning(
                f"[db] write retry {attempt}/{attempts} chocó con lock, "
                f"reintentando en {delay:.1f}s"
            )
            time.sleep(delay)
    raise last  # inalcanzable (attempt==attempts ya relanzó arriba)


def _migrate():
    """Aditivo: locked_until + published_to_pool (default 1 = pool)."""
    for col, ddl in [
        ("locked_until", "ALTER TABLE accounts ADD COLUMN locked_until TEXT"),
        ("published_to_pool", "ALTER TABLE accounts ADD COLUMN published_to_pool INTEGER DEFAULT 1"),
        ("dead_reason", "ALTER TABLE accounts ADD COLUMN dead_reason TEXT"),
        ("dead_at", "ALTER TABLE accounts ADD COLUMN dead_at TEXT"),
        # Trazabilidad: tarjeta usada en cada intento (apruebado o no). Sin enmascarar.
        ("card_pipe", "ALTER TABLE deposit_attempts ADD COLUMN card_pipe TEXT"),
        # Watchdog auto-release: tracking de notifs enviadas (no spam).
        ("notif_pre24h_sent_at", "ALTER TABLE accounts ADD COLUMN notif_pre24h_sent_at TEXT"),
        ("notif_at24h_sent_at", "ALTER TABLE accounts ADD COLUMN notif_at24h_sent_at TEXT"),
        ("notif_at24h10_sent_at", "ALTER TABLE accounts ADD COLUMN notif_at24h10_sent_at TEXT"),
        # Tracking 3DS por BIN: cada vez que se detecta 3DS (explícito o implícito
        # por JWT cardinal + status Created), se incrementa total_3ds y se actualiza
        # last_3ds_at. Frontend consulta `/api/deposits/bin-check` antes del intento.
        ("total_3ds", "ALTER TABLE bin_stats ADD COLUMN total_3ds INTEGER DEFAULT 0"),
        ("last_3ds_at", "ALTER TABLE bin_stats ADD COLUMN last_3ds_at TEXT"),
        # Anti-rate-limit Capa 3 (spec 2026-06-28): tras un 429/BAN la cuenta
        # entra en "enfriamiento" hasta este epoch (segundos). Los flujos de
        # depósito la saltan mientras `cooldown_until > now`. Migración aditiva.
        ("cooldown_until", "ALTER TABLE accounts ADD COLUMN cooldown_until INTEGER"),
        # Ciclo de vida A+ (3DS): contador de rechazos REALES de banco CONSECUTIVOS
        # desde el A+ (Robert 2026-07-09: 3DS→A+; 2 declines de banco seguidas→B; un
        # aprobado resetea). Lo mantiene `web_grading.note_a_plus_outcome`. Aditiva.
        ("a_plus_decline_streak", "ALTER TABLE accounts ADD COLUMN a_plus_decline_streak INTEGER DEFAULT 0"),
        # jwt_keeper: racha de RATE_LIMITED consecutivos SIN éxito (forense 2026-07-11
        # tarde: cuentas como retrateriamty@gmail.com dieron 429 en 11/11 intentos a lo
        # largo de 22h — el cooldown de 6h NUNCA fue el problema, la cuenta está quemada
        # de forma permanente del lado de BetMexico, no transitoria). Se resetea a 0 en
        # cualquier login exitoso; a partir de rl_streak>=3 el keeper aplica cuarentena
        # larga en vez de seguir reintentando cada 6h para siempre. Aditiva.
        ("rl_streak", "ALTER TABLE accounts ADD COLUMN rl_streak INTEGER DEFAULT 0"),
        # jwt_token/jwt_expires_at: en prod ya existen (BD compartida con el bot,
        # que las migra). Aditivo aquí solo para que BD de test/local las tenga
        # (withdrawals.py y clabe_fetch.py las consumen para retiro/clabes).
        ("jwt_token", "ALTER TABLE accounts ADD COLUMN jwt_token TEXT"),
        ("jwt_expires_at", "ALTER TABLE accounts ADD COLUMN jwt_expires_at INTEGER"),
        # withdrawal_ready/withdrawal_institution: cachea si BetMexico tiene
        # cuenta de retiro aprobada (accountStatus==2, aparece tras un SPEI
        # acreditado) — antes esto SOLO existía como llamada viva en
        # withdrawals.get_bank_accounts (PASO1), sin nada persistido para
        # gatear el botón del portal sin round-trip. Poblado por account_refresh.py.
        ("withdrawal_ready", "ALTER TABLE accounts ADD COLUMN withdrawal_ready INTEGER DEFAULT 0"),
        ("withdrawal_institution", "ALTER TABLE accounts ADD COLUMN withdrawal_institution TEXT"),
        # last_updated_at: cuándo se persistió balance REAL por última vez. Difiere
        # de last_checked_at (que también se toca en fetchs fallidos, prewarm
        # _db_touch_last_checked) — para que la tabla muestre "Últ. update" real.
        # Lo escribe prewarm._db_upsert_balance. Aditiva.
        ("last_updated_at", "ALTER TABLE accounts ADD COLUMN last_updated_at TEXT"),
    ]:
        try:
            with db(write=True) as c:
                c.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e) and "no such table" not in str(e):
                raise
    # Marcador privado por usuario (spec 2026-06-29): apartar una cuenta para
    # trabajarla luego. NO bloquea, NO cambia visibilidad. Privado por user_key.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS account_marks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_key TEXT NOT NULL, account_email TEXT NOT NULL, "
                "created_at TEXT, UNIQUE(user_key, account_email))"
            )
    except sqlite3.OperationalError:
        pass
    # Backfill A1 (defensivo, idempotente): locks legacy sin locked_until quedan
    # eternos porque el janitor exige locked_until IS NOT NULL. Re-temporiza a
    # locked_at+24h. NO toca al SA (locked_until NULL = RESERVADA_SA perpetua).
    try:
        with db(write=True) as c:
            c.execute(
                "UPDATE accounts SET locked_until=datetime(locked_at,'+24 hours') "
                "WHERE locked_by IS NOT NULL AND locked_until IS NULL "
                "AND locked_at IS NOT NULL AND locked_by != '1341812706'"
            )
    except sqlite3.OperationalError as e:
        if "no such" not in str(e):
            raise
    # M8 (fix 2026-07-02): índice funcional para recalc_grade_from_db, que filtra
    # WHERE LOWER(account_email)=LOWER(?) sobre account_transactions en cada login/
    # check/depósito/watchdog. Sin índice = full-scan O(N) que crece con el historial.
    # El índice sobre LOWER(account_email) es sargable para ese WHERE (aditivo).
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_acct_txn_email_lower "
                "ON account_transactions(LOWER(account_email))"
            )
    except sqlite3.OperationalError as e:
        if "no such table" not in str(e):
            raise
    # Toque de cuenta (spec KPIs Fase 1): registra quién metió mano al abrir el
    # detalle de una cuenta. Dedup 1/día por usuario+cuenta vía UNIQUE. Aditiva.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS account_touches ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "account_id INTEGER NOT NULL, account_email TEXT NOT NULL, "
                "actor_id INTEGER NOT NULL, touched_at TEXT NOT NULL, "
                "touched_date TEXT NOT NULL, "
                "UNIQUE(account_id, actor_id, touched_date))"
            )
    except sqlite3.OperationalError:
        pass
    # Clabes de depósito SPEI (NVIO + STP) por cuenta. Se obtienen vía
    # POST /api/stp/BeginDeposit con JWT+proxy y son FIJAS por usuario → se
    # persisten UNA vez y se muestran desde BD (no se taladra la cuenta en cada
    # refresh — alimentaría el rate-limit de BetMexico). UNIQUE(account_id, clabe)
    # para idempotencia. Aditiva. Ver clabe_fetch.py + docs/RECON_BETMEX_API.md.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS account_deposit_clabes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "account_id INTEGER NOT NULL, account_email TEXT NOT NULL, "
                "reference TEXT, user_id TEXT, full_name TEXT, "
                "clabe TEXT NOT NULL, integration TEXT, "
                "clabe_order INTEGER, blocked INTEGER DEFAULT 0, "
                "fetched_at TEXT, "
                "UNIQUE(account_id, clabe))"
            )
    except sqlite3.OperationalError:
        pass

    # Tabla de bitácora de retiros automáticos (botón SA en La Pantalla).
    # UNIQUE(transaction_id) garantiza idempotencia. Aditiva.
    # Ver withdrawals.py + docs/superpowers/specs/2026-07-24-boton-retiro-automatico-design.md.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS account_withdrawals ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "account_id INTEGER NOT NULL, "
                "account_email TEXT, "
                "transaction_id TEXT UNIQUE NOT NULL, "
                "reference TEXT, "
                "amount REAL NOT NULL, "
                "account_digits TEXT, "
                "institution_name TEXT, "
                "status_api INTEGER, "
                "status_description TEXT, "
                "gateway INTEGER, "
                "last_modified_utc TEXT, "
                "disparado_por INTEGER, "
                "created_at TEXT NOT NULL)"
            )
    except sqlite3.OperationalError:
        pass

    # Índice para el EXISTS() de has_pending_withdrawal en account_refresh.py
    # (Task 4 del plan de retiro gateado) — sin esto, cada ciclo de 5min hace
    # un table scan de account_withdrawals por cada una de ~800 cuentas LIVE.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_account_withdrawals_account_id "
                "ON account_withdrawals(account_id)"
            )
    except sqlite3.OperationalError:
        pass

    # Modo auto-depósito V2: bitácora de corridas auto (misiones). UNIQUE(mission_id)
    # garantiza idempotencia. updated_at permite detectar misiones congeladas
    # (anti-zombie). Aditiva. Ver docs/superpowers/plans/2026-07-28-modo-auto-deposito-v2.md.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS auto_missions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "mission_id TEXT UNIQUE NOT NULL, "
                "operator_id INTEGER, "
                "card_pipes TEXT NOT NULL, "
                "amount REAL NOT NULL DEFAULT 150, "
                "target_count INTEGER NOT NULL DEFAULT 9, "
                "accounts_selected TEXT, "
                "matches TEXT, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "phase_detail TEXT, "
                "total_deposited REAL DEFAULT 0, "
                "total_approved INTEGER DEFAULT 0, "
                "total_failed INTEGER DEFAULT 0, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "completed_at TEXT)"
            )
            # Reaper de misiones zombie: las que quedaron vivas cuando murió el
            # proceso pasan a 'failed' (dinero real no espera). Fix auditor B2:
            # también libera los locks de cuentas de esas misiones (si no, quedan
            # lockeadas hasta que expire locked_until aunque nadie las use).
            zombies = c.execute(
                "SELECT mission_id, matches, accounts_selected FROM auto_missions "
                "WHERE status IN ('pending','matching','scheduling')"
            ).fetchall()
            c.execute(
                "UPDATE auto_missions SET status='failed', "
                "phase_detail='proceso reiniciado a mitad de misión', "
                "completed_at=? "
                "WHERE status IN ('pending','matching','scheduling')",
                (datetime.now(timezone.utc).isoformat(),),
            )
            for z in zombies:
                ids = {m.get("account_id") for m in _json.loads(z["matches"] or "[]")}
                ids |= set(_json.loads(z["accounts_selected"] or "[]"))
                for aid in filter(None, ids):
                    c.execute(
                        "UPDATE accounts SET locked_by=NULL, locked_until=NULL WHERE id=?",
                        (aid,),
                    )
    except sqlite3.OperationalError:
        pass

    # Tabla de tracking de penalizaciones y strikes por operador para el Bot de Telegram
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS operator_penalties ("
                "telegram_id INTEGER PRIMARY KEY, "
                "strikes_count INTEGER NOT NULL DEFAULT 0, "
                "penalty_until TEXT, "
                "last_attempts TEXT, "
                "updated_at TEXT NOT NULL)"
            )
    except sqlite3.OperationalError:
        pass

    _backfill_grades_v10_m7()


def _backfill_grades_v10_m7():
    """
    One-shot backfill (gateado por marker, NO corre en cada restart): aplica
    a las cuentas YA existentes el rebalanceo M7 del grading (2026-07-09, ver
    docs/ERRORS.md "Grade A+ se borraba solo"). Sin esto, una cuenta solo se
    recalcula en su PRÓXIMO login/check/depósito/prewarm — el fix quedaría
    invisible para cuentas inactivas hasta que alguien las toque, que en la
    práctica es "nunca" para el grueso de la BD (¡esto es justo lo que reportó
    Robert como "los colores no son fiables"!). Corre una sola vez por versión.
    """
    _lg = _logging.getLogger("betmexico.dashboard.grading")
    # Bump del marker = re-backfill una vez con las reglas nuevas. m8 agrega
    # "aprobación reciente sana → A" (Robert 2026-07-09) sobre el m7 (masacre→C).
    VERSION = "v10_m8_2026-07-09_recent_success"
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS grading_backfill_log ("
                "version TEXT PRIMARY KEY, applied_at TEXT, accounts_changed INTEGER)"
            )
            if c.execute(
                "SELECT 1 FROM grading_backfill_log WHERE version=?", (VERSION,)
            ).fetchone():
                return
    except sqlite3.OperationalError as e:
        _lg.warning(f"[grading backfill] no pude preparar marker: {e}")
        return

    try:
        from web_grading import _ANALYZER
        if not _ANALYZER:
            _lg.warning("[grading backfill] analyzer V10 no cargó, salto backfill")
            return
        score_fn = _ANALYZER.score_payment_readiness
    except Exception as e:
        _lg.warning(f"[grading backfill] no pude importar analyzer: {e}")
        return

    changed = 0
    try:
        with db(write=True) as c:
            accts = c.execute("SELECT id, email, grade FROM accounts").fetchall()
            for a in accts:
                if a["grade"] == "A+":
                    continue  # override manual (3DS) — nunca se pisa, ni en backfill
                txns = c.execute(
                    "SELECT txn_date, status, txn_type, gateway, amount "
                    "FROM account_transactions WHERE LOWER(account_email)=LOWER(?) "
                    "ORDER BY txn_date DESC",
                    (a["email"],),
                ).fetchall()
                if not txns:
                    continue
                details = {"transactions": {
                    "fetched": True,
                    "items": [dict(r) for r in txns],
                    "total_rows": len(txns),
                }}
                sc = score_fn(details)
                if sc and sc["grade"] != a["grade"]:
                    c.execute(
                        "UPDATE accounts SET grade=?, grade_score=? WHERE id=?",
                        (sc["grade"], sc["score"], a["id"]),
                    )
                    changed += 1
            c.execute(
                "INSERT INTO grading_backfill_log (version, applied_at, accounts_changed) VALUES (?,?,?)",
                (VERSION, datetime.now(timezone.utc).isoformat(), changed),
            )
        _lg.info(f"[grading backfill] {VERSION}: {changed} cuentas cambiaron de grade")
    except Exception as e:
        _lg.error(f"[grading backfill] falló: {e}")


_migrate()


def _resolve_operator(val):
    """Convierte locked_by/operator_id (string nombre o int telegram_id)
    al display name si lo encontramos en USERS. Si no, devuelve crudo."""
    if val is None:
        return None
    if isinstance(val, str):
        u = _auth.USERS.get(val.lower())
        if u:
            return u["display"]
        try:
            iv = int(val)
            for v in _auth.USERS.values():
                if v["telegram_id"] == iv:
                    return v["display"]
        except (TypeError, ValueError):
            pass
        return val
    try:
        iv = int(val)
        for v in _auth.USERS.values():
            if v["telegram_id"] == iv:
                return v["display"]
        return iv
    except (TypeError, ValueError):
        return val


def _is_sa(user: dict) -> bool:
    """True si el caller es superadmin (Robert). Único rol que ve TODO."""
    return user.get("role") == "superadmin"


def _visible_emails(user: dict, c) -> "set[str] | None":
    """Universo de cuentas que el caller puede ver. None = SA (sin restricción).

    Operador (admin/user): cuentas asignadas (account_assignments) ∪ las que
    tiene lockeadas (locked_by = su telegram_id o username). El acto de ganchar
    una cuenta del pool es lo que le da acceso a sus credenciales — frictionless
    a prueba de desmadre: no se exhibe lo ajeno, no se rafaguea.
    """
    if _is_sa(user):
        return None
    tg = int(user.get("telegram_id") or 0)
    uname = (user.get("username") or "__none__").lower()
    out: set[str] = set()
    try:
        for r in c.execute("SELECT email FROM account_assignments WHERE user_id=?", (tg,)):
            out.add(r["email"])
    except sqlite3.OperationalError:
        pass
    for r in c.execute(
        "SELECT email FROM accounts WHERE locked_by IN (?, ?)", (str(tg), uname)
    ):
        out.add(r["email"])
    return out


_sse_lock = threading.Lock()
_sse_queues: list = []  # list[tuple[queue.SimpleQueue, dict]]  (queue, user_ctx)


def _broadcast(event: dict) -> None:
    """Push event a los SSE clients VISIBLES para cada uno (whitelisting por rol)."""
    msg = f"data: {_json.dumps(event)}\n\n"
    with _sse_lock:
        targets = list(_sse_queues)            # snapshot de (q, ctx)
        n_clients = len(targets)
        q_ids = [id(q) for (q, _ctx) in targets]
    for q, ctx in targets:
        if _event_visible_to(event, ctx):
            q.put(msg)
    kind = event.get("kind") or event.get("type", "?")
    if kind in ("scheduled_started", "scheduled_phase", "scheduled",
                "scheduled_aborted", "scheduled_cancelled"):
        import logging as _lg
        _lg.getLogger("betmexico.dashboard.sse").info(
            f"[SSE broadcast] kind={kind} clients={n_clients} q_ids={q_ids} "
            f"sched_id={event.get('sched_id')} iter={event.get('iter')} "
            f"phase_name={event.get('name')}"
        )


def _dequeue_blocking(q, timeout: float) -> str:
    """Espera un mensaje, devuelve heartbeat si timeout."""
    try:
        return q.get(timeout=timeout)
    except _stdlib_queue.Empty:
        return ": heartbeat\n\n"


app = FastAPI(title="Botmexico v2")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


_MAINTENANCE_FLAG_FILE = Path("/data/maintenance.flag")

def _is_maintenance_active() -> bool:
    if os.environ.get("BMX_MAINTENANCE", "").strip() in ("1", "true", "True"):
        return True
    return _MAINTENANCE_FLAG_FILE.exists()

@app.middleware("http")
async def _maintenance_gate_middleware(request: Request, call_next):
    """Bloquea acceso a usuarios no SuperAdmin durante Modo Mantenimiento.

    Si BMX_MAINTENANCE=1 o /data/maintenance.flag existe:
    - SA (Robert / robertvs) mantiene acceso total e ininterrumpido.
    - Demás usuarios/sesiones son bloqueados antes de login o dashboard.
    - Se permite servir asset de mantenimiento, logo y favicon.
    """
    if _is_maintenance_active():
        path = request.url.path
        # Excepciones que siempre se sirven en mantenimiento
        allowed_paths = ("/maintenance", "/favicon.ico", "/static/assets/botmexico_logo.png", "/static/maintenance.html")
        if not any(path == p or path.startswith("/static/assets/") for p in allowed_paths):
            bmx_cookie = request.cookies.get("bmx_session")
            user_session = _auth.get_session(bmx_cookie) if bmx_cookie else None
            user_role = user_session.get("role") if user_session else None

            if user_role != "superadmin":
                # Exceptuar el portal y sus APIs si es operador en mantenimiento
                if user_role == "operator" and (path == "/portal" or path.startswith("/user/") or path.startswith("/api/operator/") or path.startswith("/static/portal")):
                    return await call_next(request)
                if path.startswith("/api/"):
                    return JSONResponse(
                        {"error": "Sistema en mantenimiento", "maintenance": True},
                        status_code=530
                    )
                return RedirectResponse("/maintenance", status_code=302)

    return await call_next(request)


@app.middleware("http")
async def _no_cache_static_assets(request, call_next):
    """Fuerza no-cache en .js/.css/.html servidos por StaticFiles.

    Sin esto, navegadores cachean agresivamente y los devs/operadores ven
    versiones viejas tras un deploy aunque el index ya use ?v=mtime cache-bust.
    """
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".css", ".html")) or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
app.include_router(_prewarm_router)
app.include_router(_deposits_router)

# Agente de soporte (b.soporte). SA-only; ver docs/AGENTE_SOPORTE.md.
try:
    from support_routes import router as _support_router
    app.include_router(_support_router)
except Exception as _e:  # nunca tumbar el dashboard por el agente
    _logging.getLogger("betmexico.dashboard").warning(f"[support] router no cargado: {_e}")


# ── Páginas ────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC / "assets" / "botmexico_logo.png", media_type="image/png")


@app.get("/maintenance")
def maintenance_page():
    return FileResponse(STATIC / "maintenance.html")


@app.get("/login")
def login_page(request: Request, bmx_session: str = Cookie(default=None)):
    if bmx_session and _auth.get_session(bmx_session):
        q = request.url.query
        return RedirectResponse(f"/?{q}" if q else "/", status_code=302)
    return FileResponse(STATIC / "login.html")


# Todo asset propio referenciado por index.html con cache-bust (?v=...). 2026-07-06:
# antes solo se trackeaban app.js+style.css — un deploy de pantalla.css/pantalla.js
# (u otro asset fuera de esta lista) NO cambiaba window.BMX_VERSION/`/api/version`,
# así que el auto-reload NUNCA disparaba para los operadores ya conectados (bug de
# campo: deploy hecho, md5 correcto en prod, pero nadie refrescaba solo). Agregar
# aquí CUALQUIER .css/.js nuevo que index.html cargue desde /static/.
FRONTEND_ASSETS = [
    "style.css", "depos.css", "pantalla.css", "soporte.css",
    "activity_logic.js", "pantalla_logic.js", "strip_logic.js",
    "app.js", "depos_logic.js", "depos_window.js", "depos.js", "pantalla.js",
    "soporte.js", "portal.js", "horizon.js",
]


def _asset_mtimes():
    mtimes = {}
    for name in FRONTEND_ASSETS:
        try:
            mtimes[name] = int((STATIC / name).stat().st_mtime)
        except Exception:
            mtimes[name] = 0
    return mtimes


def _frontend_version(mtimes=None):
    """Versión única = mtime MÁS RECIENTE entre todos los FRONTEND_ASSETS.
    Cambia si se toca CUALQUIERA de ellos → dispara el auto-reload global."""
    mtimes = mtimes if mtimes is not None else _asset_mtimes()
    return str(max(mtimes.values(), default=0))


def _own_portal_path(session: dict) -> str:
    return f"/user/{session.get('telegram_id')}"


def _render_frontend_html(path: Path) -> Response:
    """Sirve un HTML de frontend con cache-bust por mtime + `window.BMX_VERSION`
    inyectado, para que el auto-reload por versión (`/api/version`, ver
    FRONTEND_ASSETS) funcione. Compartido por `/dashboard` y `/user/{id}` —
    antes solo el dashboard SA lo tenía, dejando el portal del operador
    (flujo /bet) sirviendo JS/CSS potencialmente viejo tras un deploy sin
    que la pestaña abierta se enterara."""
    try:
        html = path.read_text(encoding="utf-8")
        mtimes = _asset_mtimes()
        for name, mt in mtimes.items():
            html = re.sub(
                rf'(src|href)="/static/{re.escape(name)}(\?[^"]*)?"',
                rf'\1="/static/{name}?v={mt}"',
                html,
            )
        html = html.replace(
            "<head>",
            f'<head>\n  <script>window.BMX_VERSION="{_frontend_version(mtimes)}";</script>',
            1,
        )
        return Response(content=html, media_type="text/html",
                        headers={"Cache-Control": "no-cache, must-revalidate"})
    except Exception:
        return FileResponse(path)


@app.get("/user/{user_id}")
def user_portal_page(user_id: int, request: Request, bmx_session: str = Cookie(default=None)):
    """Render del flujo /bet (portal.html) — scope por telegram_id.

    Cualquier operador que entre con un {user_id} que no es el suyo se
    canoniza a su propia URL (los endpoints /api/operator/* ya scopean por
    la sesión, no por este segmento — esto es solo coherencia de URL). SA
    puede navegar cualquier /user/{id} para supervisar en vivo.
    """
    session = _auth.get_session(bmx_session) if bmx_session else None
    if not session:
        q = request.url.query
        return RedirectResponse(f"/login?{q}" if q else "/login", status_code=302)
    if session.get("role") != "superadmin" and user_id != session.get("telegram_id"):
        q = request.url.query
        own = _own_portal_path(session)
        return RedirectResponse(f"{own}?{q}" if q else own, status_code=302)
    return _render_frontend_html(STATIC / "portal.html")


@app.get("/portal")
def portal_page(request: Request, bmx_session: str = Cookie(default=None)):
    """Alias de compatibilidad — links viejos (bot, bookmarks) siguen sirviendo."""
    session = _auth.get_session(bmx_session) if bmx_session else None
    q = request.url.query
    if not session:
        return RedirectResponse(f"/login?{q}" if q else "/login", status_code=302)
    target = "/dashboard" if session.get("role") == "superadmin" else _own_portal_path(session)
    return RedirectResponse(f"{target}?{q}" if q else target, status_code=302)


@app.get("/dashboard")
def dashboard_page(request: Request, bmx_session: str = Cookie(default=None)):
    session = _auth.get_session(bmx_session) if bmx_session else None
    if not session:
        q = request.url.query
        return RedirectResponse(f"/login?{q}" if q else "/login", status_code=302)
    if session.get("role") != "superadmin":
        q = request.url.query
        own = _own_portal_path(session)
        return RedirectResponse(f"{own}?{q}" if q else own, status_code=302)
    # Cache-bust: añadir mtime de cada asset a su propio src/href para forzar
    # re-fetch tras deploy. Regex (no string fijo): index.html ya trae un
    # `?v=YYYYMMDDx` hardcodeado a mano, así que un replace de string exacto
    # nunca hacía match — quedaba muerto en silencio. El regex pisa CUALQUIER
    # query string existente, por archivo, usando FRONTEND_ASSETS (arriba).
    return _render_frontend_html(STATIC / "index.html")


@app.get("/")
def index(request: Request, bmx_session: str = Cookie(default=None)):
    """Root = puro gate de auth. botmexico.net/ nunca renderiza contenido
    directamente: exige login y reenvía a /dashboard (SA) o /user/{id} (resto),
    preservando query string (ej. ?match={mission_id} del handoff de /bet)."""
    session = _auth.get_session(bmx_session) if bmx_session else None
    q = request.url.query
    if not session:
        return RedirectResponse(f"/login?{q}" if q else "/login", status_code=302)
    target = "/dashboard" if session.get("role") == "superadmin" else _own_portal_path(session)
    return RedirectResponse(f"{target}?{q}" if q else target, status_code=302)


@app.get("/api/version")
def api_version(user: dict = Depends(require_session)):
    """Versión actual de TODOS los FRONTEND_ASSETS (mtime más reciente entre
    ellos). El frontend la compara contra `window.BMX_VERSION` (fijada al
    cargar la página) para auto-recargar pestañas viejas tras un deploy —
    sin que el operador dependa de Ctrl+Shift+R."""
    try:
        v = _frontend_version()
    except Exception:
        v = ""
    return Response(content=f'{{"v":"{v}"}}', media_type="application/json",
                     headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


# ── Auth endpoints ─────────────────────────────────────────────────────────────

from fastapi.responses import Response as _Response


@app.post("/api/auth/login")
async def auth_login(request: Request, response: _Response):
    body = await request.json()
    username = (body.get("username") or "").strip().lower()
    password = body.get("password") or ""

    if username not in _auth.USERS:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    passwords = _auth.load_passwords()
    stored = passwords.get(username)

    if stored is None:
        return JSONResponse({"first_time": True, "display": _auth.USERS[username]["display"]})

    # M6 (fix 2026-07-02): rechazar password vacío SIEMPRE y aceptar el master solo
    # si está configurado. Antes, con BMX_MASTER sin definir (default ""), un
    # password vacío pasaba ("" == master == "") = login como cualquiera, incl. el
    # superadmin. Hoy prod tiene BMX_MASTER seteado (no explotable), pero el default
    # era fail-open: un redeploy sin la env var reabría el agujero.
    master = os.environ.get("BMX_MASTER", "")
    pwd_ok = _auth.sha256(password) == stored or (bool(master) and password == master)
    if not password or not pwd_ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    token = _auth.create_session(username)
    response.set_cookie(
        "bmx_session", token,
        httponly=True, samesite="lax",
        max_age=_auth.session_max_age(username),
    )
    u = _auth.USERS[username]
    return {"username": u["display"], "role": u["role"]}


@app.post("/api/auth/set-password")
async def auth_set_password(request: Request, response: _Response):
    body = await request.json()
    username = (body.get("username") or "").strip().lower()
    new_pwd = body.get("password") or ""

    if username not in _auth.USERS:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    if len(new_pwd) < 4:
        raise HTTPException(status_code=400, detail="Contraseña muy corta (mínimo 4 caracteres)")

    passwords = _auth.load_passwords()
    if passwords.get(username) is not None:
        raise HTTPException(status_code=400, detail="Ya tienes contraseña")

    passwords[username] = _auth.sha256(new_pwd)
    _auth.save_passwords(passwords)

    token = _auth.create_session(username)
    response.set_cookie(
        "bmx_session", token,
        httponly=True, samesite="lax",
        max_age=_auth.session_max_age(username),
    )
    u = _auth.USERS[username]
    return {"username": u["display"], "role": u["role"]}


@app.post("/api/auth/logout")
def auth_logout(response: _Response, bmx_session: str = Cookie(default=None)):
    if bmx_session:
        _auth.delete_session(bmx_session)
    response.delete_cookie("bmx_session")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(require_session)):
    return {
        "username": user["display"],
        "role": user["role"],
        "telegram_id": user.get("telegram_id"),
    }


# ── API — protegida con sesión ─────────────────────────────────────────────────

@app.get("/api/health")
def health(user: dict = Depends(require_session)):
    try:
        with db() as c:
            n = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        return {"ok": True, "db": str(DB_PATH), "accounts": n}
    except Exception as e:
        return JSONResponse({"ok": False, "db": str(DB_PATH), "error": str(e)}, status_code=500)


def _build_search_clause(q):
    """WHERE multi-campo + multi-término para el buscador de cuentas (criterio de
    dominio). Cada palabra de `q` debe matchear en ALGÚN campo (OR) y TODAS las
    palabras deben matchear (AND) — así "Andrea García" cae en el nombre completo,
    y "418928 A" filtra por BIN + algo más. Los términos numéricos se normalizan
    (se les quitan espacios/-/ / /) para matchear `card_number` (guardado sin
    separadores) por número completo, BIN (primeros dígitos) o terminación
    (últimos). Busca en: email, nombre del titular, CURP, teléfono, password
    (combo), dirección, tarjetas guardadas (account_cards) + tarjetas/texto de
    notas (account_notes). Devuelve (sql_fragment, params); ("", []) si no hay nada.
    """
    import re
    terms = [t for t in (q or "").split() if t.strip()]
    if not terms:
        return "", []
    clauses, params = [], []
    for t in terms:
        # "a partir de un separador, ignorar lo demás" (Robert): si el término es
        # un dato pegado con separadores de estructura — pipe NUM|EXP|CVV o combo
        # email:password — usar SOLO el 1er segmento identificante (número/email),
        # ignorando expiry/cvv/password. Así un copy-paste de pipe o combo completo
        # cae en la cuenta correcta. El resultado SIEMPRE es la cuenta completa.
        t = re.split(r"[|:]", t, 1)[0].strip() or t
        if not t:
            continue
        like = f"%{t}%"
        digits = re.sub(r"[^0-9]", "", t)
        # Para card_number usamos la versión sin separadores si el término trae
        # dígitos (≥3 para no matchear ruido); si no, el texto tal cual.
        card_like = f"%{digits}%" if len(digits) >= 3 else like
        ors = [
            "a.email LIKE ?",
            "a.fullname LIKE ?",
            "a.curp LIKE ?",
            "a.phone LIKE ?",
            "a.password LIKE ?",
            "a.address LIKE ?",
            "EXISTS (SELECT 1 FROM account_cards ac WHERE ac.account_email=a.email "
            "AND ac.card_number LIKE ?)",
            "EXISTS (SELECT 1 FROM account_notes an WHERE an.account_email=a.email "
            "AND (COALESCE(an.note_text,'') LIKE ? OR COALESCE(an.card_number,'') LIKE ?))",
        ]
        params.extend([like, like, like, like, like, like, card_like, like, card_like])
        clauses.append("(" + " OR ".join(ors) + ")")
    return " AND ".join(clauses), params


@app.get("/api/accounts")
def list_accounts(
    status: str = Query("LIVE"),
    grade: Optional[str] = None,
    q: Optional[str] = None,
    cards_only: bool = Query(False),
    limit: int = Query(500, le=2000),
    user: dict = Depends(require_session),
):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Acceso acotado: endpoints de lectura de cuentas solo para SuperAdmin")
    where, params = [], []
    if status != "all":
        where.append("a.status = ?"); params.append(status)
    if grade:
        where.append("a.grade = ?"); params.append(grade)
    # Filtro: solo cuentas con al menos 1 tarjeta (en account_cards o account_notes con card)
    if cards_only:
        where.append(
            "(EXISTS (SELECT 1 FROM account_cards ac WHERE ac.account_email=a.email) "
            " OR EXISTS (SELECT 1 FROM account_notes an WHERE an.account_email=a.email "
            "            AND an.card_number IS NOT NULL AND TRIM(an.card_number) != ''))"
        )

    # Búsqueda inteligente multi-campo + multi-término (criterio de dominio):
    # email · nombre · CURP · teléfono · combo (password) · dirección · tarjeta
    # (número/BIN/terminación, con o sin separadores) · notas. Ver _build_search_clause.
    if q:
        clause, sparams = _build_search_clause(q)
        if clause:
            where.append(clause)
            params.extend(sparams)

    role = user.get("role", "user")
    user_tg = int(user.get("telegram_id") or 0)

    # Trastienda: non-SA solo ve cuentas publicadas a la pool
    if role != "superadmin":
        where.append("COALESCE(a.published_to_pool, 1) = 1")
        # Lock-aware: non-SA solo ve cuentas libres O lockeadas por ellos mismos.
        # Si otro operador la tiene, NO la ve. SA ve todo.
        # `locked_by` se guarda como string del telegram_id (ver lock_account).
        where.append("(a.locked_by IS NULL OR a.locked_by = ? OR a.locked_by = ?)")
        params.append(str(user_tg))
        params.append(user.get("username", "__none__"))

    base_cols = (
        "a.id, a.email, a.password, a.fullname, a.curp, a.phone, "
        "a.balance_total, a.balance_real, "
        "a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, "
        "a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, a.check_count, "
        "a.jwt_expires_at, a.dead_reason, a.cooldown_until, a.rl_streak, "
        "a.last_updated_at, "
        "COALESCE(a.published_to_pool, 1) AS published_to_pool, "
        "(SELECT COUNT(*) FROM account_cards ac WHERE ac.account_email=a.email) AS cards_count, "
        "(SELECT COUNT(*) FROM account_notes an WHERE an.account_email=a.email "
        " AND COALESCE(an.note_text,'') != '') AS notes_count"
    )
    # Normal user: solo cuentas asignadas a su user_id
    if role == "user" and user_tg:
        sql = (
            f"SELECT {base_cols} FROM accounts a "
            "INNER JOIN account_assignments ass ON ass.email = a.email "
            "WHERE ass.user_id = ?"
        )
        params.insert(0, user_tg)
    else:
        sql = f"SELECT {base_cols} FROM accounts a"
        if where:
            sql += " WHERE " + " AND ".join(where)
            where = []  # ya consumidos

    if where:  # caso user-filter con extras
        sql += " AND " + " AND ".join(where)
    sql += " ORDER BY a.balance_total DESC, a.last_checked_at DESC LIMIT ?"
    params.append(limit)
    try:
        with db() as c:
            rows = [dict(r) for r in c.execute(sql, params).fetchall()]
            for r in rows:
                op = r.get("locked_by")
                # Color del operador (para borde lateral en fila)
                tg_id = None
                if op is not None:
                    try:
                        tg_id = int(op)
                    except (TypeError, ValueError):
                        u = _auth.USERS.get(str(op).lower())
                        tg_id = u["telegram_id"] if u else None
                r["locked_by"] = _resolve_operator(op)
                r["locked_color"] = _auth.USER_COLORS.get(tg_id) if tg_id else None
                # JWT vivo = reutilizable sin captcha (gentle_login cache-hit exige
                # exp > now+60s). Alimenta el badge 🟢/🔑 de la lista. Ver jwt_keeper.
                # SOLO-SA: es un internal operativo → NO se filtra al operador (ley de
                # capas operador/SA). Se quita SIEMPRE el epoch crudo del payload.
                _exp = r.pop("jwt_expires_at", None)
                # Cuarentena: se quitan SIEMPRE los crudos del payload (no
                # filtrar internals al operador — ley capas). Los flags
                # computados (jwt_alive, needs_reset, cooldown_min) SÍ van a
                # TODOS: son guardarriles visuales, no internals.
                _dr = r.pop("dead_reason", None)
                _cd = r.pop("cooldown_until", None)
                # rl_streak es internal operativo → SOLO-SA. Non-SA nunca debe
                # saber que existe rate-limit (Robert 2026-08-05: pedo interno
                # del backend, se resuelve en silencio). Pop siempre, expongo
                # solo al SA como flag de gestión.
                _rl = r.pop("rl_streak", None)
                if role == "superadmin":
                    r["rl_streak"] = int(_rl or 0)
                r["jwt_alive"] = bool(
                    _exp not in (None, "")
                    and int(_exp) > datetime.now(timezone.utc).timestamp() + 60)
                # needs_reset: cuenta DEAD por login terminal recuperable con
                # reset de contraseña (attempt-limit / credenciales) — la
                # distingue de una muerte real (AUTOEXCLUSION / KYC).
                r["needs_reset"] = bool(
                    r.get("status") == "DEAD"
                    and str(_dr or "") in ("LOGIN_DENIED", "ATTEMPT_LIMIT"))
                # cooldown_min: minutos que le faltan para enfriar (0 si no aplica).
                _now = datetime.now(timezone.utc).timestamp()
                try:
                    r["cooldown_min"] = max(0, round((int(_cd) - _now) / 60)) if _cd not in (None, "") and int(_cd) > _now else 0
                except (TypeError, ValueError):
                    r["cooldown_min"] = 0
            return rows
    except sqlite3.OperationalError as e:
        if "account_assignments" in str(e):
            # Si no hay tabla account_assignments todavía (setup nuevo, sin asignaciones)
            return []
        # Cualquier otro OperationalError (p.ej. "no such table: accounts") es una
        # BD rota, no "cero cuentas" — no tragar en silencio (vacío != roto).
        raise HTTPException(500, f"DB: {e}")


# ─── Asignaciones / Liberador ──────────────────────────────────────────────────

@app.get("/api/users")
def list_users(user: dict = Depends(require_session)):
    """Lista los usuarios del sistema (para asignar cuentas).
    Solo visible para superadmin/admin."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    return [
        {"username": k, "display": v["display"], "telegram_id": v["telegram_id"], "role": v["role"]}
        for k, v in _auth.USERS.items()
    ]


@app.get("/api/assignments")
def list_assignments(
    user_id: Optional[int] = None,
    user: dict = Depends(require_session),
):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    try:
        with db() as c:
            if user_id is not None:
                rows = c.execute(
                    "SELECT email, user_id, assigned_by, assigned_at "
                    "FROM account_assignments WHERE user_id=? ORDER BY assigned_at DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT email, user_id, assigned_by, assigned_at "
                    "FROM account_assignments ORDER BY assigned_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


class AssignRequest(BaseModel):
    emails: list[str]
    user_id: int


@app.post("/api/assignments/assign")
def assign_accounts(req: AssignRequest, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    if not req.emails or not req.user_id:
        raise HTTPException(400, "emails y user_id requeridos")
    assigned_by = int(user.get("telegram_id") or 0)
    now = datetime.now(timezone.utc).isoformat()
    ok = 0
    with db(write=True) as c:
        for email in req.emails:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO account_assignments "
                    "(email, user_id, assigned_by, assigned_at) VALUES (?,?,?,?)",
                    (email, req.user_id, assigned_by, now),
                )
                ok += c.rowcount
            except Exception as e:
                print(f"[assign] error {email}: {e}")
    return {"assigned": ok, "requested": len(req.emails)}


@app.post("/api/assignments/unassign")
def unassign_accounts(req: AssignRequest, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    removed = 0
    with db(write=True) as c:
        for email in req.emails:
            cur = c.execute(
                "DELETE FROM account_assignments WHERE email=? AND user_id=?",
                (email, req.user_id),
            )
            removed += cur.rowcount
    return {"removed": removed, "requested": len(req.emails)}


@app.get("/api/stats")
def stats(_user: dict = Depends(require_session)):
    with db() as c:
        live = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE'").fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        balance = c.execute("SELECT COALESCE(SUM(balance_total),0) FROM accounts WHERE status='LIVE'").fetchone()[0]
        with_balance = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE' AND balance_total > 0").fetchone()[0]
        in_use = c.execute("SELECT COUNT(*) FROM accounts WHERE locked_by IS NOT NULL").fetchone()[0]
    return {"live": live, "total": total, "totalBalance": balance, "withBalance": with_balance, "inUse": in_use}


# ── Proxy pool health (cache 30s) — pool activo IPRoyal/NodeMaven ───────────────
_proxy_cache: dict = {"ts": 0.0, "data": None}
_PROXY_TTL = 1800.0     # cache si OK (30 min). NO bajar: el health NO debe quemar
                        # el plan de proxy. A 30s barría los 52 contra ipinfo cada
                        # 30s = ~1 GB/semana del plan residencial (Claude 2026-06-28,
                        # responsabilidad: lo metí yo, lo reparo).
_PROXY_TTL_FAIL = 120.0 # cache si falló (2 min — antes 5s = ráfaga que quemaba más)

_wsai_cache: dict = {"ts": 0.0, "data": None}
_WSAI_TTL = 120.0       # 2 min — el balance no cambia tan seguido


def _wsai_status() -> dict:
    """Status de WebScraping.ai (cache 2min)."""
    import time as _t
    now = _t.time()
    if _wsai_cache["data"] and (now - _wsai_cache["ts"]) < _WSAI_TTL:
        return _wsai_cache["data"]
    key = os.environ.get("WSAI_API_KEY", "e338d7e4-3c48-4b65-937c-8508c405ba6f")
    try:
        req = urllib.request.Request(
            f"https://api.webscraping.ai/account?api_key={key}",
            headers={"User-Agent": "curl/8.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = _json.loads(resp.read())
        out = {
            "ok": True,
            "remaining": int(body.get("remaining_api_calls", 0)),
            "concurrency": int(body.get("remaining_concurrency", 0)),
            "email": body.get("email", "?"),
            "resets_at": body.get("resets_at"),
            "error": None,
        }
    except Exception as e:
        out = {"ok": False, "error": str(e)[:80]}
    _wsai_cache.update({"ts": now, "data": out})
    return out

# Dedup de alertas push: kind → último timestamp broadcast (anti-spam)
_alert_last_sent: dict = {}
_ALERT_DEDUP_SEC = 5 * 60  # no repetir la misma alerta < 5 min


def _maybe_alert_broadcast(alert: dict) -> None:
    """Broadcast una alerta crítica como notif push, deduplicando por kind."""
    import time as _t
    kind = alert.get("kind", "alert")
    now = _t.time()
    last = _alert_last_sent.get(kind, 0)
    if now - last < _ALERT_DEDUP_SEC:
        return
    _alert_last_sent[kind] = now
    icon = {"capmonster_low": "💸", "proxy_down": "🔌", "prewarm_errors": "🔥"}.get(kind, "⚠️")
    _broadcast({
        "type": "alert",
        "kind": kind,
        "severity": alert.get("severity", "warn"),
        "icon": icon,
        "msg": alert.get("msg", ""),
        "ts": alert.get("ts"),
    })


def _check_one_proxy(proxy_url: str, timeout: float = 6.0) -> dict:
    """Chequea conectividad de UN proxy (GET a endpoint de IP). Devuelve
    {ok, ip, country, latency_ms, host, error}. host sin credenciales."""
    import time as _time
    host = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(handler)
    last_err = "sin respuesta"
    # SOLO api.ipify (≈50 bytes). ipinfo.io/json pesa ~6.6 KB y quemaba el plan
    # residencial (1 GB/sem en health checks). El país se asume MX (el pool es MX).
    for endpoint, parse in [
        ("https://api.ipify.org?format=json", lambda b: (b.get("ip"), "MX")),
    ]:
        t0 = _time.time()
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "curl/8.0"})
            with opener.open(req, timeout=timeout) as resp:
                body = _json.loads(resp.read())
            ip, country = parse(body)
            return {"ok": True, "ip": ip, "country": country or "MX",
                    "latency_ms": int((_time.time() - t0) * 1000),
                    "host": host, "error": None}
        except Exception as e:
            last_err = str(e)[:100]
            continue
    return {"ok": False, "host": host, "error": last_err,
            "ip": None, "country": None, "latency_ms": None}


def _proxy_health() -> dict:
    """Salud del pool de proxies EN USO (IPRoyal/NodeMaven — los mismos que usan
    login y depósito). Chequea TODOS y reporta `alive/total`.

    Antes chequeaba LitPort hardcodeado, EXCLUIDO del pool por estar quemado → el
    indicador decía "caído" siempre aunque el sistema operara bien (Robert
    2026-05-29: "para qué me sirve saber de un proxy que no se está usando").
    Mide CONECTIVIDAD (no reputación ante BetMexico). Cache 30s."""
    import time as _time
    now = _time.time()
    if _proxy_cache["data"]:
        ttl = _PROXY_TTL if _proxy_cache["data"].get("ok") else _PROXY_TTL_FAIL
        if (now - _proxy_cache["ts"]) < ttl:
            return _proxy_cache["data"]

    try:
        from proxy_pool import shuffled_proxy_urls
        urls = shuffled_proxy_urls()
    except Exception as e:
        urls = []
        print(f"[proxy_health] shuffled_proxy_urls err: {e}")
    if not urls:
        out = {"ok": False, "error": "pool de proxies vacío", "host": "pool",
               "alive": 0, "total": 0}
        _proxy_cache.update({"ts": now, "data": out})
        return out

    # Muestra de máx 3 (no los 52). Barrer todo el pool cada ciclo quemaba el plan.
    import random as _rnd
    sample = urls if len(urls) <= 3 else _rnd.sample(urls, 3)
    results = [_check_one_proxy(u) for u in sample]
    alive = [r for r in results if r.get("ok")]
    best = min(alive, key=lambda r: r["latency_ms"]) if alive else None
    out = {
        "ok": len(alive) > 0,
        "alive": len(alive),
        "total": len(results),
        "pool_size": len(urls),   # tamaño real del pool (la muestra es de 3)
        "country": (best or {}).get("country"),
        "latency_ms": (best or {}).get("latency_ms"),
        "ip": (best or {}).get("ip"),
        "host": (best or results[0]).get("host"),
        "error": None if alive else (results[0].get("error") if results else "sin proxies"),
        # Detalle por proxy para el tooltip del UI.
        "hosts": [{"host": r["host"], "ok": r.get("ok"),
                   "latency_ms": r.get("latency_ms"), "error": r.get("error")}
                  for r in results],
    }
    _proxy_cache.update({"ts": now, "data": out})
    return out


def _capmonster_balance() -> dict:
    # Misma key que usa el bot (api.py / betmexico_login_api.py)
    key = (os.environ.get("CAPMONSTER_KEY")
           or os.environ.get("BMX_CAPMONSTER_KEY")
           or "a9040840fdb3828ecc6090a6010afcad")
    if not key:
        return {"balance": None, "error": "CAPMONSTER_KEY not set"}
    try:
        req = urllib.request.Request(
            "https://api.capmonster.cloud/getBalance",
            data=_json.dumps({"clientKey": key}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = _json.loads(resp.read())
        if body.get("errorId") == 0:
            return {"balance": body["balance"], "error": None}
        return {"balance": None, "error": body.get("errorDescription", "API error")}
    except Exception as e:
        return {"balance": None, "error": str(e)}


# ─── KPIs L invertida (spec chat2) ─────────────────────────────────────────────

def _operator_color(tg_id):
    """Color del operador para acentos de UI (borde lateral, badges).
    Acepta int/str numérico (telegram_id) o string username (locked_by /
    operator_id legacy o manual, ej. 'op') — NUNCA truena el request; sin
    match conocido devuelve None (2026-07-07: `int(tg_id)` a secas crasheaba
    activity_feed con `ValueError` en cuanto locked_by traía un username)."""
    if not tg_id:
        return None
    if isinstance(tg_id, str):
        u = _auth.USERS.get(tg_id.lower())
        if u:
            return _auth.USER_COLORS.get(u["telegram_id"])
    try:
        return _auth.USER_COLORS.get(int(tg_id))
    except (TypeError, ValueError):
        return None


def _resolve_who(val):
    """Para broadcasts SSE: {who, who_color, who_id}. who_id = telegram_id del
    actor (para filtrado server-side por rol)."""
    wid = None
    try:
        wid = int(val)
    except (TypeError, ValueError):
        u = _auth.USERS.get(str(val).lower()) if val is not None else None
        wid = u.get("telegram_id") if u else None
    return {
        "who": _resolve_operator(val),
        "who_color": _operator_color(val),
        "who_id": wid,
    }


def _event_visible_to(event: dict, ctx: dict) -> bool:
    """Whitelisting de visibilidad para SSE/feeds. SA ve todo; admin/user ven
    SOLO lo suyo. Las acciones del SA no aparecen para nadie más (fix bug
    'admin ve actividad de Robert')."""
    if event.get("kind") == "account_touch":
        who_id = event.get("who_id")
        my = ctx.get("telegram_id")
        if who_id is not None and my is not None and str(who_id) == str(my):
            return False
    if ctx.get("role") == "superadmin":
        return True
    my = ctx.get("telegram_id")
    # 1) Eventos con actor (who_id telegram_id) -> solo los propios.
    who_id = event.get("who_id")
    if who_id is not None and my is not None:
        return str(who_id) == str(my)
    # 2) Fallback por display name resuelto.
    who = event.get("who")
    if who is not None and ctx.get("display") is not None:
        return who == ctx.get("display")
    # 3) Eventos de servicio dirigidos (window_*, release_*): solo al destinatario.
    for k in ("operator_id", "target_user"):
        v = event.get(k)
        if v is not None and my is not None and str(v) == str(my):
            return True
    # 4) Eventos sin actor ni destinatario (alertas globales) -> solo SA (ya retornó arriba).
    return False


@app.get("/api/superadmin/kpis")
def superadmin_kpis(user: dict = Depends(require_session)):
    """L invertida del SuperAdmin (spec chat2):
      1. Online: operadores con actividad < 5 min, lista con dot status
      2. Activity feed (últimos 30 eventos: deposit/lock/prewarm)
      3. Alertas: bulk masivo, prewarm errors, login fallidos, capmonster bajo
      4. Pool stats: pool / en_uso / trastienda / rebotadas

    Roles:
      - superadmin: respuesta completa
      - admin: solo capmonster_balance + proxy (vista premium del sidebar)
      - user: 403
    """
    role = user.get("role")
    if role == "user":
        raise HTTPException(403, "Solo superadmin/admin")
    # Admin: respuesta mínima (solo lo que pinta el sidebar premium)
    if role == "admin":
        cm = _capmonster_balance()
        return {
            "capmonster_balance": cm.get("balance"),
            "capmonster_error": cm.get("error"),
            "proxy": _proxy_health(),
        }
    now = datetime.now(timezone.utc)
    out: dict = {}
    with db() as c:
        # ── 1. ONLINE NOW ──
        # Operador "online" = tiene lock activo o evento < 5 min
        online_ids: set = set()
        try:
            for r in c.execute(
                "SELECT DISTINCT locked_by FROM accounts WHERE locked_by IS NOT NULL"
            ).fetchall():
                online_ids.add(str(r["locked_by"]))
            for r in c.execute(
                "SELECT DISTINCT operator_id FROM deposit_attempts "
                "WHERE created_at >= datetime('now','-5 minutes')"
            ).fetchall():
                if r["operator_id"]:
                    online_ids.add(str(r["operator_id"]))
        except sqlite3.OperationalError:
            pass

        operators = []
        for username, u in _auth.USERS.items():
            tg = u["telegram_id"]
            is_online = str(tg) in online_ids or username in online_ids
            # idle si activo en últimos 30 min pero no ahora
            try:
                idle = c.execute(
                    "SELECT 1 FROM deposit_attempts WHERE operator_id=? "
                    "AND created_at >= datetime('now','-30 minutes') LIMIT 1",
                    (tg,)
                ).fetchone() is not None
            except sqlite3.OperationalError:
                idle = False
            # cuántas cuentas tiene en uso ahora
            try:
                in_use = c.execute(
                    "SELECT COUNT(*) FROM accounts WHERE locked_by IN (?, ?)",
                    (str(tg), username)
                ).fetchone()[0]
            except sqlite3.OperationalError:
                in_use = 0
            operators.append({
                "username": username,
                "display": u["display"],
                "role": u["role"],
                "telegram_id": tg,
                "color": _auth.USER_COLORS.get(tg),
                "status": "online" if is_online else ("idle" if idle else "offline"),
                "in_use": in_use,
            })
        out["online"] = {
            "operators": operators,
            "active": sum(1 for o in operators if o["status"] == "online"),
            "total": len(operators),
        }

        # ── 2. ACTIVITY FEED (últimos 20 eventos mezclados) ──
        feed = []
        kpi_pw_cache: dict[str, str] = {}
        def _kpi_combo(email: str) -> str:
            if not email: return ""
            if email not in kpi_pw_cache:
                row = c.execute("SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
                kpi_pw_cache[email] = row["password"] if row else ""
            pw = kpi_pw_cache.get(email) or ""
            return f"{email}:{pw}" if pw else email

        try:
            for r in c.execute(
                "SELECT account_email, amount, status, operator_id, created_at "
                "FROM deposit_attempts ORDER BY id DESC LIMIT 15"
            ).fetchall():
                feed.append({
                    "kind": "deposit",
                    "ts": r["created_at"],
                    "who": _resolve_operator(r["operator_id"]),
                    "who_color": _operator_color(r["operator_id"]),
                    "target": _kpi_combo(r["account_email"]),
                    "amount": r["amount"],
                    "status": r["status"],
                })
        except sqlite3.OperationalError:
            pass

        for r in c.execute(
            "SELECT email, locked_by, locked_at FROM accounts "
            "WHERE locked_by IS NOT NULL ORDER BY locked_at DESC LIMIT 15"
        ).fetchall():
            tg = None
            try: tg = int(r["locked_by"])
            except (TypeError, ValueError):
                u = _auth.USERS.get(str(r["locked_by"]).lower())
                tg = u["telegram_id"] if u else None
            feed.append({
                "kind": "lock",
                "ts": r["locked_at"],
                "who": _resolve_operator(r["locked_by"]),
                "who_color": _auth.USER_COLORS.get(tg) if tg else None,
                "target": _kpi_combo(r["email"]),
            })

        feed.sort(key=lambda e: str(e.get("ts", "")), reverse=True)
        out["feed"] = feed[:20]

        # ── 3. ALERTAS REALES ──
        alerts = []
        # bulk: alguien tocó >20 cuentas en <1 min (locks)
        try:
            bulk = c.execute(
                "SELECT locked_by, COUNT(*) as n, MIN(locked_at) as t0, MAX(locked_at) as t1 "
                "FROM accounts WHERE locked_by IS NOT NULL "
                "AND locked_at >= datetime('now','-5 minutes') "
                "GROUP BY locked_by HAVING n >= 20"
            ).fetchall()
            for r in bulk:
                alerts.append({
                    "kind": "bulk", "severity": "warn",
                    "msg": f"{_resolve_operator(r['locked_by'])} lockeó {r['n']} cuentas en <5 min",
                    "ts": r["t1"],
                })
        except sqlite3.OperationalError:
            pass
        # prewarm errors recientes
        try:
            err = c.execute(
                "SELECT COUNT(*) FROM process_log "
                "WHERE process_type='prewarm' AND phase IN ('error','timeout') "
                "AND created_at >= datetime('now','-30 minutes')"
            ).fetchone()[0]
            if err >= 3:
                alerts.append({
                    "kind": "prewarm_errors", "severity": "warn",
                    "msg": f"{err} prewarms fallidos en 30 min",
                    "ts": now.isoformat(),
                })
        except sqlite3.OperationalError:
            pass
        # capmonster bajo
        cm = _capmonster_balance()
        if cm.get("balance") is not None and cm["balance"] < 5:
            alerts.append({
                "kind": "capmonster_low", "severity": "danger",
                "msg": f"CapMonster bajo: ${cm['balance']:.2f}",
                "ts": now.isoformat(),
            })
        # proxy caído
        ph = _proxy_health()
        if ph and not ph.get("ok"):
            alerts.append({
                "kind": "proxy_down", "severity": "danger",
                "msg": f"Proxy pool caído: {ph.get('error') or 'sin respuesta'}",
                "ts": now.isoformat(),
            })
        out["alerts"] = alerts

        # Broadcast alertas críticas como notif push (deduplicado por kind+severity en 5min)
        for a in alerts:
            if a.get("severity") == "danger":
                _maybe_alert_broadcast(a)

        # ── 4. POOL STATS (Pool · En uso · Trastienda · Rebotadas) ──
        live = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE'").fetchone()[0]
        in_use = c.execute(
            "SELECT COUNT(*) FROM accounts WHERE locked_by IS NOT NULL"
        ).fetchone()[0]
        # Trastienda = LIVE con published_to_pool=0 (las que tú aún no soltaste a la pool)
        trastienda = c.execute(
            "SELECT COUNT(*) FROM accounts "
            "WHERE status='LIVE' AND COALESCE(published_to_pool, 1) = 0"
        ).fetchone()[0]
        # Pool = LIVE publicadas y libres
        pool = c.execute(
            "SELECT COUNT(*) FROM accounts "
            "WHERE status='LIVE' AND COALESCE(published_to_pool, 1) = 1 "
            "AND locked_by IS NULL"
        ).fetchone()[0]
        try:
            # Rebotadas hoy: lock vencido sin depósito aprobado en últimas 24h
            rebotadas = c.execute(
                "SELECT COUNT(DISTINCT a.email) FROM accounts a "
                "WHERE a.locked_until IS NOT NULL "
                "AND a.locked_until <= datetime('now') "
                "AND NOT EXISTS (SELECT 1 FROM deposit_attempts d "
                "  WHERE d.account_email=a.email AND d.status='approved' "
                "  AND d.created_at >= datetime('now','-24 hours'))"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            rebotadas = 0
        out["pool"] = {
            "pool": pool,
            "in_use": in_use,
            "trastienda": trastienda,
            "rebotadas": rebotadas,
        }

        # ── Sistema (resumen rápido) ──
        try:
            dep24 = c.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved, "
                "COALESCE(SUM(CASE WHEN status='approved' THEN amount ELSE 0 END),0) AS amount "
                "FROM deposit_attempts WHERE created_at >= datetime('now','-24 hours')"
            ).fetchone()
            out["deposits_24h"] = {
                "total": dep24[0] or 0,
                "approved": dep24[1] or 0,
                "amount": dep24[2] or 0.0,
            }
        except sqlite3.OperationalError:
            out["deposits_24h"] = {"total": 0, "approved": 0, "amount": 0.0}

        out["capmonster_balance"] = cm.get("balance")
        out["capmonster_error"] = cm.get("error")

        # ── Proxies (pool activo health check) ──
        out["proxy"] = _proxy_health()

        # ── WebScraping.ai (saldo de API calls) ──
        out["wsai"] = _wsai_status()

    return out


# ─── Refresh visible (re-lectura de DB) ────────────────────────────────────────

class RefreshRequest(BaseModel):
    ids: list[int]


@app.post("/api/accounts/refresh")
def accounts_refresh(req: RefreshRequest, _user: dict = Depends(require_session)):
    """Re-lee del DB las cuentas indicadas. NOTA: el re-check live (login + balance)
    contra BetMexico requiere las deps del bot — se hace via /api/prewarm/select.
    Este endpoint solo refresca lo que el bot ya puso en BD."""
    if not req.ids:
        return {"rows": []}
    placeholders = ",".join("?" * len(req.ids))
    with db() as c:
        rows = c.execute(
            f"SELECT a.id, a.email, a.password, a.balance_total, a.balance_real, "
            f"a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, "
            f"a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, a.check_count, "
            f"(SELECT COUNT(*) FROM account_cards ac WHERE ac.account_email=a.email) AS cards_count "
            f"FROM accounts a WHERE a.id IN ({placeholders})",
            req.ids,
        ).fetchall()
    out = [dict(r) for r in rows]
    for r in out:
        r["locked_by"] = _resolve_operator(r.get("locked_by"))
    return {"rows": out}


# ─── Logs en tiempo real ───────────────────────────────────────────────────────

_LOG_NOISE_PATTERNS: list[re.Pattern] = [
    # uvicorn request lines: "GET /api/x 200" / "POST /api/x 304"
    re.compile(r'^\S+ \d+:\d+:\d+,\d+ - (GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD) /'),
    # SSE /api/events connections
    re.compile(r'^\S+ \d+:\d+:\d+,\d+ - connection open$', re.IGNORECASE),
    re.compile(r'^\S+ \d+:\d+:\d+,\d+ - connection closed$', re.IGNORECASE),
    # Health check internal pings (GET /api/health/*)
    re.compile(r'^\S+ \d+:\d+:\d+,\d+ - (GET|POST) /api/health'),
    # Import checks / module loads
    re.compile(r'^\S+ \d+:\d+:\d+,\d+ - import\b', re.IGNORECASE),
    # Spam de KYC de BetMexico
    re.compile(r'\[KYC.*?\]', re.IGNORECASE),
]


def _tail_log_file(log_file: Path, limit: int = 200, since: Optional[str] = None,
                    level: Optional[str] = None) -> list[str]:
    """Lee las últimas N líneas filtradas de un archivo de log rotado.
    Filtra ruido (uvicorn requests, health checks, SSE heartbeats, imports).
    Param `level`: ERROR | WARNING | WARN | CRITICAL | INFO | ALL (default ALL).
    Reusado por /api/logs (dashboard) y /api/logs/telegram (bots)."""
    if not log_file.exists():
        return ["(log file no creado todavía — esperar primer flush)"]
    n = max(1, min(int(limit or 200), 2000))
    # Lee tail eficiente: lee últimos ~512KB y toma últimas N líneas
    size = log_file.stat().st_size
    with log_file.open("rb") as f:
        if size > 524288:
            f.seek(-524288, 2)
            f.readline()  # descarta línea parcial
        data = f.read().decode("utf-8", errors="replace")
    lines = data.splitlines()[-n:]
    if since:
        lines = [ln for ln in lines if ln[:19] >= since[:19]]
    # Filtrar ruido de uvicorn/health/SSE/imports
    lines = [ln for ln in lines
             if not any(p.search(ln) for p in _LOG_NOISE_PATTERNS)]
    # Filtrar por nivel si se pide
    lvl = (level or '').upper().strip()
    if lvl and lvl != 'ALL':
        if lvl in ('WARN',):
            lvl = 'WARNING'
        lines = [ln for ln in lines if lvl in ln.upper()]
    return lines


@app.get("/api/logs")
def get_logs(limit: int = 200, since: Optional[str] = None,
             level: Optional[str] = None,
             user: dict = Depends(require_session)):
    """Lee las últimas N líneas filtradas del log del dashboard.
    Fix 2026-05-23: lee `/data/logs/dashboard.log` (RotatingFileHandler de app.py)."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    try:
        return {"lines": _tail_log_file(Path("/data/logs/dashboard.log"), limit, since, level)}
    except Exception as e:
        return {"lines": [f"Error leyendo log: {e}"]}


_TELEGRAM_LOG_FILES = {
    "main": Path("/data/logs/telegram_bot.log"),
    "mock": Path("/data/logs/telegram_mock_bot.log"),
}


@app.get("/api/logs/telegram")
def get_logs_telegram(bot: str = "main", limit: int = 300, since: Optional[str] = None,
                       level: Optional[str] = None,
                       user: dict = Depends(require_session)):
    """Lee las últimas N líneas del log de uno de los 2 bots de Telegram de
    BetMexico (main=bot real, mock=bot de pruebas). Ambos containers montan
    el mismo volumen /data que betmexico-web — lectura directa a archivo,
    sin red ni docker exec (2026-07-31, vista dual de Logs)."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    log_file = _TELEGRAM_LOG_FILES.get(bot)
    if log_file is None:
        raise HTTPException(400, f"bot inválido: {bot!r} (usar 'main' o 'mock')")
    try:
        return {"lines": _tail_log_file(log_file, limit, since, level)}
    except Exception as e:
        return {"lines": [f"Error leyendo log: {e}"]}


# ─── Health check ──────────────────────────────────────────────────────────────

_health_state: dict = {"last_run": None, "ok": True, "issues": []}


def _run_health_checks() -> dict:
    issues: list[str] = []
    # 1. DB accesible
    try:
        with db() as c:
            c.execute("SELECT 1 FROM accounts LIMIT 1").fetchone()
    except Exception as e:
        issues.append(f"DB: {e}")
    # 2. CapMonster balance
    cm = _capmonster_balance()
    if cm.get("error"):
        issues.append(f"CapMonster: {cm['error']}")
    elif cm.get("balance") is not None and cm["balance"] < 5:
        issues.append(f"CapMonster bajo: ${cm['balance']:.2f}")
    # 3. Cuentas DEAD masivas
    try:
        with db() as c:
            recent_dead = c.execute(
                "SELECT COUNT(*) FROM accounts WHERE status='DEAD' "
                "AND last_checked_at >= datetime('now','-1 hours')"
            ).fetchone()[0]
        if recent_dead >= 10:
            issues.append(f"{recent_dead} cuentas DEAD en última hora")
    except Exception:
        pass
    # 4. Bot deps — solo informativo, NO genera issue (en dev local los deps
    #    no están y eso es esperado; el VPS los tiene siempre).
    # try: import betmexico_db
    # → eliminado del check; la ausencia no rompe el dashboard, solo /api/deposits/execute.

    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "ok": len(issues) == 0,
        "issues": issues,
    }
    _health_state.update(state)
    return state


@app.get("/api/health/full")
def health_full(_user: dict = Depends(require_session)):
    return _run_health_checks()


# ── Panel de controles backend (SA only) ─────────────────────────────────────

import subprocess as _sp


def _require_sa(user: dict):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")


@app.get("/api/admin/diag")
def admin_diag(user: dict = Depends(require_session)):
    """Diagnóstico completo del sistema."""
    _require_sa(user)
    out = {"ts": datetime.now(timezone.utc).isoformat(), "checks": []}
    # DB
    try:
        with db() as c:
            n = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        out["checks"].append({"name": "BD SQLite", "ok": True, "info": f"{n} cuentas"})
    except Exception as e:
        out["checks"].append({"name": "BD SQLite", "ok": False, "error": str(e)[:120]})
    # CapMonster
    cm = _capmonster_balance()
    if cm.get("balance") is not None:
        out["checks"].append({"name": "CapMonster", "ok": cm["balance"] >= 5,
                              "info": f"${cm['balance']:.2f}"})
    else:
        out["checks"].append({"name": "CapMonster", "ok": False, "error": cm.get("error", "?")})
    # Proxy
    p = _proxy_health()
    out["checks"].append({"name": "Proxy pool", "ok": p.get("ok", False),
                          "info": f"{p.get('country','?')} · {p.get('latency_ms','?')}ms" if p.get("ok") else None,
                          "error": p.get("error") if not p.get("ok") else None})
    # Bot deps
    try:
        from app import BOT_DEPS_OK
        out["checks"].append({"name": "Bot deps", "ok": bool(BOT_DEPS_OK),
                              "info": "loaded" if BOT_DEPS_OK else None,
                              "error": "no cargan" if not BOT_DEPS_OK else None})
    except Exception:
        pass
    return out


@app.post("/api/admin/ping")
def admin_ping(user: dict = Depends(require_session)):
    """Ping a hosts críticos."""
    _require_sa(user)
    targets = ["betmexico.mx", "api.capmonster.cloud", "hub-us-7.litport.net"]
    results = []
    for host in targets:
        try:
            r = _sp.run(["ping", "-c", "1", "-W", "2", host],
                        capture_output=True, text=True, timeout=5)
            ok = r.returncode == 0
            # Extrae tiempo
            lat = None
            for line in r.stdout.splitlines():
                if "time=" in line:
                    try:
                        lat = float(line.split("time=")[1].split()[0])
                    except Exception:
                        pass
            results.append({"host": host, "ok": ok, "latency_ms": lat})
        except Exception as e:
            results.append({"host": host, "ok": False, "error": str(e)[:100]})
    return {"results": results}


@app.post("/api/admin/refresh-proxy")
def admin_refresh_proxy(user: dict = Depends(require_session)):
    """Invalida cache de proxy_health para forzar re-check inmediato."""
    _require_sa(user)
    _proxy_cache["ts"] = 0.0
    _proxy_cache["data"] = None
    p = _proxy_health()
    return {"ok": p.get("ok"), "country": p.get("country"), "latency_ms": p.get("latency_ms"),
            "error": p.get("error")}


@app.post("/api/admin/services/restart")
def admin_services_restart(target: str, user: dict = Depends(require_session)):
    """Reinicia bot, web, mock o todos.

    Antes usaba `systemctl restart`, que en KVM4 no existe: corremos en Docker
    sin systemd, así que este endpoint devolvía ok=False en silencio desde la
    migración. Misma causa raíz que el bug de los logs (ver arriba, L40).
    Ahora va por el docker-socket-proxy, que solo permite listar y reiniciar
    contenedores — el socket nunca se monta en este contenedor.
    """
    _require_sa(user)
    grupos = {"bot": ["betmexico-bot"], "web": ["betmexico-web"],
              "mock": ["betmexico-mock-bot"],
              "all": ["betmexico-bot", "betmexico-mock-bot", "betmexico-web"]}
    if target not in grupos:
        raise HTTPException(400, f"target debe ser {'|'.join(grupos)}")
    import support_tools as _stools
    out = []
    for s in grupos[target]:
        r = _stools._exec_reiniciar_servicio({"nombre": s}, {"user": user.get("display")})
        out.append({"service": s, "ok": bool(r.get("ok")),
                    "detalle": r.get("detalle") or r.get("error")})
    return {"restarted": out}


@app.get("/api/admin/export-logs")
def admin_export_logs(lines: int = Query(500, le=5000),
                      user: dict = Depends(require_session)):
    """Descarga logs recientes (text/plain)."""
    _require_sa(user)
    # Antes: journalctl. KVM4 es Docker sin systemd → siempre devolvía vacío.
    # Ahora se sirve el mismo archivo que alimenta /api/logs.
    try:
        with open(str(_LOG_FILE), "r", encoding="utf-8", errors="replace") as f:
            body = "".join(f.readlines()[-lines:])
        if not body:
            body = "(el log está vacío)"
    except FileNotFoundError:
        body = f"No existe {_LOG_FILE} todavía."
    except Exception as e:
        body = f"Error: {e}"
    return Response(content=body, media_type="text/plain",
                    headers={"Content-Disposition": "attachment; filename=betmexico-logs.txt"})


# Estado de pausa global de procesos (SA puede pausar prewarms/deposits para todos)
_GLOBAL_PAUSE = {"paused": False, "since": None, "by": None, "reason": None}


@app.get("/api/admin/pause-state")
def admin_pause_state(user: dict = Depends(require_session)):
    _require_sa(user)
    return _GLOBAL_PAUSE


@app.post("/api/admin/pause")
def admin_pause(user: dict = Depends(require_session), reason: str = ""):
    """Pausa global: bloquea nuevos prewarms y depósitos para TODOS los users."""
    _require_sa(user)
    _GLOBAL_PAUSE.update({
        "paused": True,
        "since": datetime.now(timezone.utc).isoformat(),
        "by": user.get("display"),
        "reason": reason or "manual",
    })
    _broadcast({"type": "alert", "kind": "global_pause", "severity": "warn",
                "icon": "⏸", "msg": f"Sistema pausado por {user.get('display')}",
                "ts": datetime.now(timezone.utc).isoformat()})
    return _GLOBAL_PAUSE


@app.post("/api/admin/resume")
def admin_resume(user: dict = Depends(require_session)):
    _require_sa(user)
    _GLOBAL_PAUSE.update({"paused": False, "since": None, "by": None, "reason": None})
    _broadcast({"type": "alert", "kind": "global_resume", "severity": "info",
                "icon": "▶", "msg": f"Sistema reanudado por {user.get('display')}",
                "ts": datetime.now(timezone.utc).isoformat()})
    return _GLOBAL_PAUSE


@app.post("/api/admin/emergency-stop")
def admin_emergency_stop(user: dict = Depends(require_session)):
    """Paro de emergencia: pausa global + cancela todos los prewarms y schedules activos."""
    _require_sa(user)
    _GLOBAL_PAUSE.update({
        "paused": True,
        "since": datetime.now(timezone.utc).isoformat(),
        "by": user.get("display"),
        "reason": "EMERGENCY_STOP",
    })
    cancelled_pw = 0
    cancelled_sched = 0
    try:
        from prewarm import _PREWARM_TASKS
        for k, t in list(_PREWARM_TASKS.items()):
            if not t.done():
                t.cancel()
                cancelled_pw += 1
    except Exception:
        pass
    try:
        from deposits import _active_schedules, _active_mm_runs
        for sid, info in list(_active_schedules.items()):
            try:
                info["task"].cancel()
                cancelled_sched += 1
            except Exception:
                pass
        for run_id, ev in list(_active_mm_runs.items()):
            ev.set()
    except Exception:
        pass
    _broadcast({"type": "alert", "kind": "emergency_stop", "severity": "danger",
                "icon": "🛑", "msg": f"PARO DE EMERGENCIA por {user.get('display')}",
                "ts": datetime.now(timezone.utc).isoformat()})
    return {"paused": True, "cancelled_prewarms": cancelled_pw,
            "cancelled_schedules": cancelled_sched}


@app.post("/api/admin/vps-reboot")
def admin_vps_reboot(user: dict = Depends(require_session), confirm: str = ""):
    """Reboot del VPS — requiere confirmación."""
    _require_sa(user)
    if confirm != "REBOOT":
        raise HTTPException(400, "Pasa confirm=REBOOT para confirmar")
    try:
        _sp.Popen(["shutdown", "-r", "+1", "Reboot solicitado por SA"])
        _broadcast({"type": "alert", "kind": "vps_reboot", "severity": "danger",
                    "icon": "🔄", "msg": "VPS reboot programado en 1 min",
                    "ts": datetime.now(timezone.utc).isoformat()})
        return {"scheduled": True, "in": "1 minute"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/health/last")
def health_last(_user: dict = Depends(require_session)):
    return _health_state


@app.post("/api/health/dismiss")
def health_dismiss(_user: dict = Depends(require_session)):
    """Limpia el estado de salud — re-corre el check ahora.
    Si los issues siguen presentes, vuelven a aparecer; si se resolvieron, quedan limpios."""
    return _run_health_checks()


@app.get("/api/marks")
def api_marks_list(user: dict = Depends(require_session)):
    uk = str(user.get("telegram_id"))
    with db() as c:
        rows = c.execute(
            "SELECT account_email FROM account_marks WHERE user_key=? ORDER BY id DESC",
            (uk,),
        ).fetchall()
    return {"marks": [r["account_email"] for r in rows]}


@app.post("/api/marks/toggle")
def api_marks_toggle(payload: dict, user: dict = Depends(require_session)):
    email = (payload or {}).get("email")
    if not email:
        raise HTTPException(status_code=400, detail="email requerido")
    uk = str(user.get("telegram_id"))
    with db(write=True) as c:
        existing = c.execute(
            "SELECT id FROM account_marks WHERE user_key=? AND account_email=?",
            (uk, email),
        ).fetchone()
        if existing:
            c.execute("DELETE FROM account_marks WHERE id=?", (existing["id"],))
            return {"marked": False}
        c.execute(
            "INSERT INTO account_marks (user_key, account_email, created_at) "
            "VALUES (?,?,datetime('now'))",
            (uk, email),
        )
    return {"marked": True}


@app.get("/api/recent")
def api_recent(user: dict = Depends(require_session)):
    is_sa = user.get("role") == "superadmin"
    my = user.get("telegram_id")
    uk = str(my)
    recent: dict = {}  # email -> {email, combo, last_ts, reason}
    with db() as c:
        def _combo(email):
            row = c.execute("SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
            pw = (row["password"] if row else "") or ""
            return f"{email}:{pw}" if pw else email

        def _add(email, ts, reason):
            if not email:
                return
            cur = recent.get(email)
            if cur is None or str(ts or "") > str(cur["last_ts"] or ""):
                recent[email] = {"email": email, "combo": _combo(email),
                                 "last_ts": ts, "reason": reason}

        # depósitos propios (o los de SA = también los suyos; vista global = /api/activity)
        dsql = "SELECT account_email, created_at FROM deposit_attempts "
        dargs: tuple = ()
        if not is_sa:
            dsql += "WHERE operator_id=? "
            dargs = (my,)
        else:
            dsql += "WHERE operator_id=? "
            dargs = (my,)
        dsql += "ORDER BY id DESC LIMIT 50"
        try:
            for r in c.execute(dsql, dargs).fetchall():
                _add(r["account_email"], r["created_at"], "deposit")
        except sqlite3.OperationalError:
            pass

        # locks propios (en uso)
        for r in c.execute(
            "SELECT email, locked_at FROM accounts WHERE locked_by=? ORDER BY locked_at DESC LIMIT 50",
            (str(my),),
        ).fetchall():
            _add(r["email"], r["locked_at"], "lock")

        # marcadas
        for r in c.execute(
            "SELECT account_email, created_at FROM account_marks WHERE user_key=? ORDER BY id DESC LIMIT 50",
            (uk,),
        ).fetchall():
            _add(r["account_email"], r["created_at"], "mark")

        # Ley del pool: el operador NO ve combos de cuentas fuera de su universo.
        # (marcar una cuenta no la expone; SA sin restricción.)
        vis = _visible_emails(user, c)
        if vis is not None:
            recent = {e: v for e, v in recent.items() if e in vis}

        # stats del día (por operador)
        try:
            st = c.execute(
                "SELECT COUNT(*) n, "
                "SUM(CASE WHEN lower(status)='approved' THEN 1 ELSE 0 END) ok, "
                "SUM(CASE WHEN lower(status)='approved' THEN amount ELSE 0 END) amt "
                "FROM deposit_attempts WHERE operator_id=? AND created_at >= date('now')",
                (my,),
            ).fetchone()
            attempts = st["n"] or 0
            approved = st["ok"] or 0
            amount = float(st["amt"] or 0)
        except sqlite3.OperationalError:
            attempts = approved = 0
            amount = 0.0
    rec = sorted(recent.values(), key=lambda x: str(x["last_ts"] or ""), reverse=True)[:20]
    rate = round(100.0 * approved / attempts, 1) if attempts else 0.0
    return {"recent": rec, "stats": {"attempts": attempts, "approved": approved, "amount": amount, "rate": rate}}


@app.get("/api/accounts/at-hand")
def api_accounts_at_hand(user: dict = Depends(require_session)):
    """KPI Cuentas a la mano: pineadas (marks del usuario) + recientes,
    enriquecidas con id/status/balance/grade/combo y filtradas por rol.
    Un solo origen de verdad server-side (evita 3 llamadas del front +
    resolver email->id, que /api/recent no da)."""
    my = user.get("telegram_id")
    uk = str(my)
    with db() as c:
        # base_cols de list_accounts (app.py ~558) trae fullname/curp/phone que
        # en algunas BD (incl. el harness de tests) no existen todavia -> el
        # SELECT se arma dinamico contra el schema real, sin romper ninguno.
        cols_present = {r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()}
        enrich_cols = ["id", "email", "password", "status", "balance_total",
                       "balance_real", "grade", "locked_by", "locked_until"]
        for optional in ("fullname",):
            if optional in cols_present:
                enrich_cols.append(optional)
        sql_cols = ", ".join(enrich_cols)

        def _combo(email, pw=None):
            if pw is None:
                row = c.execute("SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
                pw = (row["password"] if row else "") or ""
            return f"{email}:{pw}" if pw else email

        # ── pineadas: marks del usuario, orden id DESC (igual que /api/marks) ──
        pinned_emails = [
            r["account_email"] for r in c.execute(
                "SELECT account_email FROM account_marks WHERE user_key=? ORDER BY id DESC",
                (uk,),
            ).fetchall()
        ]

        # ── recientes: misma recoleccion que /api/recent (deposits propios,
        # locks propios, marcadas), dedup por email, last_ts DESC ──
        recent: dict = {}

        def _add(email, ts, reason):
            if not email:
                return
            cur = recent.get(email)
            if cur is None or str(ts or "") > str(cur["last_ts"] or ""):
                recent[email] = {"email": email, "last_ts": ts, "reason": reason}

        dsql = "SELECT account_email, created_at FROM deposit_attempts WHERE operator_id=? ORDER BY id DESC LIMIT 50"
        try:
            for r in c.execute(dsql, (my,)).fetchall():
                _add(r["account_email"], r["created_at"], "deposit")
        except sqlite3.OperationalError:
            pass

        for r in c.execute(
            "SELECT email, locked_at FROM accounts WHERE locked_by=? ORDER BY locked_at DESC LIMIT 50",
            (str(my),),
        ).fetchall():
            _add(r["email"], r["locked_at"], "lock")

        for r in c.execute(
            "SELECT account_email, created_at FROM account_marks WHERE user_key=? ORDER BY id DESC LIMIT 50",
            (uk,),
        ).fetchall():
            _add(r["account_email"], r["created_at"], "mark")

        # Ley del pool (misma que /api/recent): non-SA no ve combos fuera de su
        # universo visible, ni siquiera de cuentas que el marco.
        vis = _visible_emails(user, c)
        if vis is not None:
            pinned_emails = [e for e in pinned_emails if e in vis]
            recent = {e: v for e, v in recent.items() if e in vis}

        # recent no duplica lo que ya esta en pinned (dos listas limpias)
        pinned_set = set(pinned_emails)
        recent_rows = [v for e, v in recent.items() if e not in pinned_set]
        recent_rows.sort(key=lambda x: str(x["last_ts"] or ""), reverse=True)
        recent_rows = recent_rows[:20]

        # ── enrich con UNA query: email -> fila de accounts ──
        all_emails = list(pinned_set | {r["email"] for r in recent_rows})
        by_email: dict = {}
        if all_emails:
            qmarks = ",".join("?" * len(all_emails))
            for row in c.execute(
                f"SELECT {sql_cols} FROM accounts a WHERE a.email IN ({qmarks})",
                all_emails,
            ).fetchall():
                by_email[row["email"]] = dict(row)

        def _build(email, extra=None):
            base = by_email.get(email)
            item = {
                "id": base["id"] if base else None,
                "email": email,
                "combo": _combo(email, base["password"] if base else None),
                "fullname": base.get("fullname") if base else None,
                "status": base["status"] if base else None,
                "balance_total": base["balance_total"] if base else None,
                "balance_real": base["balance_real"] if base else None,
                "grade": base["grade"] if base else None,
                "locked_by": base["locked_by"] if base else None,
                "locked_until": base["locked_until"] if base else None,
            }
            if extra:
                item.update(extra)
            return item

        pinned = [_build(e) for e in pinned_emails]
        recent_out = [_build(r["email"], {"last_ts": r["last_ts"], "reason": r["reason"]}) for r in recent_rows]

    return {"pinned": pinned, "recent": recent_out}


async def _health_loop():
    """Cada 6 horas corre el check. Si falla, broadcast SSE."""
    await asyncio.sleep(60)  # primer check al minuto del start
    while True:
        try:
            res = await asyncio.to_thread(_run_health_checks)
            if not res["ok"]:
                _broadcast({"type": "health_warning", "issues": res["issues"]})
        except Exception as e:
            print(f"[health] error: {e}")
        await asyncio.sleep(6 * 3600)


def _release_account(c, account_id, email, reason, prev_locked_by,
                     kind="unlock_auto", who="janitor"):
    """Liberador canónico ÚNICO (A1). Atómico y uniforme: limpia lock + notif_*,
    SIEMPRE republica al pool (published_to_pool=1) y emite 1 solo broadcast.
    Reemplaza las 3 variantes inconsistentes (janitor / window_watcher / release_watchdog)
    que liberaban la misma cuenta desde 3 orígenes de tiempo distintos.
    `c` = conexión abierta en modo write (el caller maneja el `with db(write=True)`).
    NO toca cuentas con locked_until NULL salvo que el caller lo decida: el guard
    `locked_until IS NOT NULL` vive en quien selecciona (janitor), no aquí."""
    c.execute(
        "UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL, "
        "notif_pre24h_sent_at=NULL, notif_at24h_sent_at=NULL, notif_at24h10_sent_at=NULL, "
        "published_to_pool=1 WHERE id=?",
        (account_id,),
    )
    _broadcast({
        "type": "activity", "kind": kind,
        "ts": datetime.now(timezone.utc).isoformat(),
        "who": who, "who_id": _resolve_who(prev_locked_by)["who_id"],
        "target": email, "id": account_id,
        "prev_locked_by": prev_locked_by, "reason": reason,
    })


def _run_lock_janitor() -> int:
    """Auto-unlock (spec chat2):
      - Lock vencido (locked_until < now) Y sin depósito aprobado en últimas 24h → liberar
      - Si hay depósito/tarjeta nueva en últimas 24h → mantener 24h desde ese evento
    Retorna cuántas se liberaron.
    """
    freed = 0
    try:
        with db(write=True) as c:
            # Cuentas con lock vencido
            rows = c.execute(
                "SELECT id, email, locked_by, locked_at, locked_until "
                "FROM accounts WHERE locked_by IS NOT NULL "
                "AND locked_until IS NOT NULL "
                "AND locked_until <= datetime('now')"
            ).fetchall()
            for r in rows:
                # ¿Hubo depósito aprobado o tarjeta nueva en últimas 24h?
                try:
                    sticky = c.execute(
                        "SELECT 1 FROM deposit_attempts "
                        "WHERE account_email=? AND status='approved' "
                        "AND created_at >= datetime('now','-24 hours') LIMIT 1",
                        (r["email"],)
                    ).fetchone()
                    if not sticky:
                        sticky = c.execute(
                            "SELECT 1 FROM account_cards WHERE account_email=? "
                            "AND registered_at >= datetime('now','-24 hours') LIMIT 1",
                            (r["email"],)
                        ).fetchone()
                except sqlite3.OperationalError:
                    sticky = None

                if sticky:
                    # Extender 24h desde ahora (sticky)
                    new_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                    c.execute(
                        "UPDATE accounts SET locked_until=? WHERE id=?",
                        (new_until, r["id"])
                    )
                else:
                    # A1: liberador canónico ÚNICO. Republica + limpia notif_* + 1 broadcast.
                    _release_account(c, r["id"], r["email"],
                                     "lock vencido sin trabajo 24h", r["locked_by"])
                    freed += 1
    except Exception as e:
        print(f"[janitor] error: {e}")
    return freed


async def _janitor_loop():
    """Limpia locks vencidos cada 5 minutos."""
    await asyncio.sleep(30)
    while True:
        try:
            n = await asyncio.to_thread(_run_lock_janitor)
            if n:
                print(f"[janitor] auto-unlock {n} cuentas")
        except Exception as e:
            print(f"[janitor] error: {e}")
        await asyncio.sleep(5 * 60)


# ── Watcher de ventanas de depósito 24h (A1: notificador puro) ────────────
# Emite notif al operador cuando su window 24h está por cerrar (~30 min antes)
# Emite notif "ya cerró, vuelve" cuando expira.
# NO libera (A1): el único liberador automático es el janitor (_release_account).
_window_notified: dict = {}  # email → set de fases ya notificadas

def _run_window_watcher() -> dict:
    """Revisa cuentas con depósitos aprobados últimas 25h y emite alertas."""
    out = {"warned": 0, "expired": 0, "released": 0}
    try:
        with db() as c:
            # Para cada cuenta con dep aprobado en últimas 25h, calcula window
            rows = c.execute(
                "SELECT account_email, MIN(created_at) AS first_at, "
                "  MAX(operator_id) AS operator_id, COUNT(*) AS n, "
                "  COALESCE(SUM(amount),0) AS total "
                "FROM deposit_attempts "
                "WHERE status='approved' "
                "  AND created_at >= datetime('now','-25 hours') "
                "GROUP BY account_email"
            ).fetchall()
        now = datetime.now(timezone.utc)
        for r in rows:
            email = r["account_email"]
            # A1: no notificar sobre RESERVADA_SA (lock perpetuo del SA: locked_until NULL)
            try:
                with db() as c2:
                    lk = c2.execute(
                        "SELECT locked_by, locked_until FROM accounts WHERE email=?",
                        (email,),
                    ).fetchone()
                if lk and lk["locked_by"] is not None and lk["locked_until"] is None:
                    continue
            except Exception:
                pass
            try:
                first_at = datetime.fromisoformat(r["first_at"].replace(" ", "T"))
                if first_at.tzinfo is None:
                    first_at = first_at.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            expires_at = first_at + timedelta(hours=24)
            mins_left = (expires_at - now).total_seconds() / 60
            operator_id = r["operator_id"]
            phases = _window_notified.setdefault(email, set())

            # Fase 1: 30 min antes
            if 0 < mins_left <= 30 and "warning" not in phases:
                phases.add("warning")
                _broadcast({
                    "type": "window_warning",
                    "email": email, "operator_id": operator_id,
                    "mins_left": int(mins_left), "used": float(r["total"]),
                    "expires_at": expires_at.isoformat(),
                })
                out["warned"] += 1

            # Fase 2: window cerró (acaba de pasar)
            if -60 < mins_left <= 0 and "expired" not in phases:
                phases.add("expired")
                _broadcast({
                    "type": "window_expired",
                    "email": email, "operator_id": operator_id,
                    "used_24h": float(r["total"]),
                    "expires_at": expires_at.isoformat(),
                    "deadline": (expires_at + timedelta(hours=1)).isoformat(),
                })
                out["expired"] += 1

            # A1: fase 3 (auto-release a 25h) ELIMINADA. El janitor es el único
            # liberador (vía _release_account). window_watcher = notificador puro.

        # Limpia tracking de cuentas viejas (> 26h sin actividad)
        for email in list(_window_notified.keys()):
            if email not in [r["account_email"] for r in rows]:
                _window_notified.pop(email, None)
    except Exception as e:
        print(f"[window_watcher] error: {e}")
    return out


async def _window_watcher_loop():
    await asyncio.sleep(45)
    while True:
        try:
            r = await asyncio.to_thread(_run_window_watcher)
            if r["warned"] or r["expired"] or r["released"]:
                print(f"[window_watcher] {r}")
        except Exception as e:
            print(f"[window_watcher] error: {e}")
        await asyncio.sleep(2 * 60)  # cada 2 min


def _release_watchdog_tick():
    """Watchdog post-depósito: SOLO notifs progresivas (A1: ya no auto-libera).

    Timeline desde `last_deposit_date`:
    - T+23h55m → notif "disponible en 5 min" (info)
    - T+24h    → notif "ya puedes volver a depositar" (warn) + acciones [deposit, release]
    - T+24h10m → notif "segundo aviso" (warn) + acciones [deposit, release]
    (El auto-release a 27h se ELIMINÓ en A1: el janitor es el único liberador,
     con origen de tiempo = locked_until. Guard locked_until IS NOT NULL = no toca RESERVADA_SA.)

    Las notifs son por-usuario (target_user = locked_by). El frontend filtra para
    mostrar solo al operador dueño del lock. SA siempre las ve.
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    # last_deposit_date está en hora MX (UTC-6) sin tzinfo. Asumir MX.
    mx_tz = timezone(timedelta(hours=-6))

    try:
        with db(write=True) as c:
            rows = c.execute(
                "SELECT id, email, locked_by, last_deposit_date, "
                "notif_pre24h_sent_at, notif_at24h_sent_at, notif_at24h10_sent_at "
                "FROM accounts "
                "WHERE locked_by IS NOT NULL "
                "AND locked_until IS NOT NULL "          # A1: no notificar a RESERVADA_SA (SA perpetuo)
                "AND last_deposit_date IS NOT NULL "
                "AND last_deposit_date != 'N/A' "
                "AND TRIM(last_deposit_date) != ''"
            ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"[release_watchdog] db error: {e}")
        return

    for r in rows:
        try:
            dt = datetime.strptime(r["last_deposit_date"], "%d/%m/%Y %H:%M")
            dt_mx = dt.replace(tzinfo=mx_tz)
        except ValueError:
            continue

        delta = now - dt_mx
        hours = delta.total_seconds() / 3600.0
        if hours < 0:
            continue  # depósito en futuro? skip

        acc_id = r["id"]
        email = r["email"]
        owner = r["locked_by"]
        now_iso = now.isoformat()

        # A1: caso 1 (auto-release a 27h) ELIMINADO. El janitor es el único liberador
        # (origen de tiempo = locked_until, vía _release_account). Aquí solo notifs.

        # Caso 2: 24h+10m → segundo aviso con acciones
        if hours >= 24.166 and not r["notif_at24h10_sent_at"]:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET notif_at24h10_sent_at=? WHERE id=?",
                    (now_iso, acc_id),
                )
            _broadcast({
                "type": "notification", "kind": "release_available_again",
                "severity": "warn", "icon": "⏰",
                "msg": f"{email}: 2do aviso — deposita o libera. Auto-release a las 27h.",
                "target_user": owner, "account_id": acc_id,
                "actions": ["deposit", "release"],
            })
            continue

        # Caso 3: 24h cumplidas → primer aviso con acciones
        if hours >= 24 and not r["notif_at24h_sent_at"]:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET notif_at24h_sent_at=? WHERE id=?",
                    (now_iso, acc_id),
                )
            _broadcast({
                "type": "notification", "kind": "release_available",
                "severity": "warn", "icon": "🟢",
                "msg": f"{email}: ya puedes depositar de nuevo (24h cumplidas)",
                "target_user": owner, "account_id": acc_id,
                "actions": ["deposit", "release"],
            })
            continue

        # Caso 4: 5 min antes de 24h → pre-aviso (info)
        if 23.917 <= hours < 24 and not r["notif_pre24h_sent_at"]:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET notif_pre24h_sent_at=? WHERE id=?",
                    (now_iso, acc_id),
                )
            mins_left = max(0, int((24 - hours) * 60))
            _broadcast({
                "type": "notification", "kind": "release_warning_5min",
                "severity": "info", "icon": "⏳",
                "msg": f"{email}: disponible en ~{mins_left} min para volver a depositar",
                "target_user": owner, "account_id": acc_id,
            })


async def _release_watchdog_loop():
    """Loop infinito del watchdog. Tick cada 60s."""
    await asyncio.sleep(15)  # esperar a que app arranque
    while True:
        try:
            _release_watchdog_tick()
        except Exception as e:
            print(f"[release_watchdog] tick error: {e}")
        await asyncio.sleep(60)


async def _jwt_keepalive_loop():
    """Mantiene vivos los JWT de sesión (7 días fijos) re-logueando de forma
    proactiva y ESPACIADA solo las cuentas por expirar/expiradas de mejor grado.
    Baja el 429: menos JWT muertos = menos logins forzados = menos rate-limit.
    Config por env JWT_KEEPER_* (ver jwt_keeper.cfg). Tick cada JWT_KEEPER_INTERVAL_SEC.

    Sleep = `_jwt_wakeup.wait()` con timeout: si account_refresh detecta un JWT
    muerto server-side (401 silencioso) invalida la cache y hace `_wake_jwt_keeper()`
    → este loop despierta y re-loguea YA, sin esperar el tick horario (FUGA #1)."""
    import jwt_keeper
    c = jwt_keeper.cfg()
    if not c["enabled"]:
        print("[jwt_keeper] deshabilitado (JWT_KEEPER_ENABLED!=1)")
        return
    await asyncio.sleep(90)  # dejar que la app + pool de proxies arranquen
    while True:
        try:
            stats = await jwt_keeper.run_keepalive_cycle_from_env()
            print(f"[jwt_keeper] ciclo: {stats}")
        except Exception as e:
            print(f"[jwt_keeper] error de ciclo: {e}")
        # Dormir hasta el próximo tick horario, o despertar antes si el refresh
        # invalidó JWT muertos (wake). Debounce de la señal está en _wake_jwt_keeper.
        try:
            await asyncio.wait_for(_jwt_wakeup.wait(), timeout=jwt_keeper.cfg()["interval_sec"])
        except asyncio.TimeoutError:
            pass
        finally:
            _jwt_wakeup.clear()


_jwt_wakeup = asyncio.Event()
_jwt_wakeup_last = 0.0


def _wake_jwt_keeper() -> None:
    """Despierta a `_jwt_keepalive_loop` para que re-loguee YA las cuentas cuyo
    JWT murió server-side (las invalidó account_refresh). Debounce de 5 min:
    si ya se despertó hace poco, el event ya está seteado y el keeper corre al
    terminar su ciclo — no hay que repetir. No rafagea: el ciclo del keeper
    siempre espacia los logins (gap configurable) y el event solo adelanta tick."""
    global _jwt_wakeup_last
    now = time.time()
    if now - _jwt_wakeup_last < 300:
        return
    _jwt_wakeup_last = now
    _jwt_wakeup.set()


async def _account_refresh_loop():
    """Refresca balance/movimientos de cuentas con JWT VIGENTE (opuesto a
    jwt_keeper: esas cuentas no necesitan login, solo un fetch reusando el
    JWT — sin captcha, sin rate-limit). Mantiene el dashboard actualizado
    sin intervención del operador. Config por env ACCOUNT_REFRESH_*
    (ver account_refresh.cfg). Tick cada ACCOUNT_REFRESH_INTERVAL_SEC."""
    import account_refresh
    c = account_refresh.cfg()
    if not c["enabled"]:
        print("[account_refresh] deshabilitado (ACCOUNT_REFRESH_ENABLED!=1)")
        return
    await asyncio.sleep(120)  # arrancar después del jwt_keeper (90s)
    while True:
        try:
            stats = await account_refresh.run_refresh_cycle_from_env()
            print(f"[account_refresh] ciclo: {stats}")
        except Exception as e:
            print(f"[account_refresh] error de ciclo: {e}")
        await asyncio.sleep(account_refresh.cfg()["interval_sec"])


ROBERT_CHAT_ID = 1341812706  # ID exclusivo de Robert (SuperAdmin)


def _bot_token() -> str | None:
    """Token del bot Telegram LEGACY (`betmexico-bot`) — el canal de avisos.

    Ojo: hasta 2026-08-01 esto leía `TELEGRAM_BOT_TOKEN`, variable que NUNCA ha
    existido en el .env de KVM4 (ahí están `BMX_BOT_TOKEN` y `BMX_MOCK_BOT_TOKEN`).
    El `if not token: return` silencioso hacía que la notificación de arranque
    jamás se enviara desde la migración a Docker. Se acepta el nombre viejo como
    alias por si algún entorno lo define.
    """
    return os.environ.get("BMX_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")


def _notify_robert(msg: str, parse_mode: str | None = "HTML") -> dict:
    """Manda un mensaje al Telegram de Robert por el bot legacy. Punto único."""
    token = _bot_token()
    if not token:
        return {"ok": False, "error": "BMX_BOT_TOKEN no configurado"}
    payload = {"chat_id": ROBERT_CHAT_ID, "text": msg}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                       json=payload, timeout=10.0)
        if r.status_code != 200:
            return {"ok": False, "error": f"Telegram HTTP {r.status_code}: {r.text[:160]}"}
        return {"ok": True, "detalle": "aviso enviado por el bot legacy"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


async def _startup_telegram_notify():
    """Notificación de inicio al Telegram personal de Robert (SuperAdmin)."""
    bot_token = _bot_token()
    target_chat_id = ROBERT_CHAT_ID
    if not bot_token:
        _logging.getLogger("betmexico.dashboard").warning(
            "[telegram_startup_notify] sin BMX_BOT_TOKEN: no se notifica el arranque")
        return
    msg = (
        "◢ ━━━━━━━ ◣\n"
        "  ∷ ʙ.ᴏᴛᴍᴇxɪᴄᴏ ∷  ◎\n"
        "◥ ━━━━━━━ ◤\n\n"
        "✓ runtime online\n\n"
        "Online. Gates listos.\n"
        "Otra sesión sin aviso previo. Muy tú.\n\n"
        "⊢ ʙ.ᴏᴛᴍᴇx"
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": target_chat_id, "text": msg, "parse_mode": "HTML"}
            )
    except Exception as e:
        print(f"[telegram_startup_notify] Error notificando inicio: {e}")


@app.on_event("startup")
async def _start_bg_tasks():
    asyncio.create_task(_health_loop())
    asyncio.create_task(_janitor_loop())
    asyncio.create_task(_window_watcher_loop())
    asyncio.create_task(_release_watchdog_loop())
    asyncio.create_task(_jwt_keepalive_loop())
    asyncio.create_task(_account_refresh_loop())
    asyncio.create_task(_startup_telegram_notify())


class LockRequest(BaseModel):
    operator: str
    hours: int = 2


@app.post("/api/accounts/{account_id}/lock")
def lock_account(account_id: int, req: LockRequest, _user: dict = Depends(require_session)):
    now = datetime.now(timezone.utc)
    locked_at = now.isoformat()
    is_sa = _user.get("role") == "superadmin"
    # A1: SA → lock perpetuo (RESERVADA_SA, locked_until NULL) + override de cualquier lock,
    # igual que _auto_lock_for_deposit. Operador → temporal (Nh) y SIN override (409 si ocupada).
    locked_until = None if is_sa else (now + timedelta(hours=req.hours)).isoformat()
    with db(write=True) as c:
        if is_sa:
            cur = c.execute(
                "UPDATE accounts SET locked_by=?, locked_at=?, locked_until=? WHERE id=?",
                (req.operator, locked_at, locked_until, account_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Account not found")
        else:
            cur = c.execute(
                "UPDATE accounts SET locked_by=?, locked_at=?, locked_until=?"
                " WHERE id=? AND locked_by IS NULL",
                (req.operator, locked_at, locked_until, account_id),
            )
            if cur.rowcount == 0:
                row = c.execute(
                    "SELECT id, locked_by FROM accounts WHERE id=?", (account_id,)
                ).fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Account not found")
                raise HTTPException(
                    status_code=409,
                    detail=f"Already locked by {row['locked_by']}",
                )
        email = c.execute(
            "SELECT email FROM accounts WHERE id=?", (account_id,)
        ).fetchone()["email"]
    _broadcast({
        "type": "activity", "kind": "lock",
        "ts": locked_at, **_resolve_who(req.operator), "target": email,
        "id": account_id, "locked_until": locked_until,
    })
    return {"id": account_id, "locked_by": req.operator, "locked_until": locked_until}


class PublishRequest(BaseModel):
    ids: list[int]
    publish: bool  # true = a la pool (visible), false = a trastienda (oculta)


@app.post("/api/accounts/publish")
def publish_accounts(req: PublishRequest, user: dict = Depends(require_session)):
    """SA mueve cuentas entre Pool (visible para todos) y Trastienda (oculta).
    El que pediste para 'dosificar' las 900 cuentas."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    if not req.ids:
        return {"changed": 0}
    placeholders = ",".join("?" * len(req.ids))
    with db(write=True) as c:
        if req.publish:
            cur = c.execute(
                f"UPDATE accounts SET published_to_pool=1 WHERE id IN ({placeholders})",
                [*req.ids],
            )
        else:
            # Sacar a trastienda (SA) LIBERA de paso la RESERVADA_SA perpetua
            # (locked_until IS NULL) — el auto-lock del propio SA al depositar dejaba la
            # cuenta pegada al pool y este guardrail la saltaba en silencio (Robert
            # 2026-07-17: "no puedo sacar las cuentas del pool hacia trastienda"). Los
            # locks TEMPORALES de operador (locked_until NOT NULL = trabajo activo) SÍ se
            # respetan: esas NO se ocultan (evita el fantasma published=0 + lock ajeno).
            cur = c.execute(
                f"UPDATE accounts SET published_to_pool=0, "
                f"locked_by=NULL, locked_at=NULL, locked_until=NULL "
                f"WHERE id IN ({placeholders}) "
                f"AND (locked_by IS NULL OR locked_until IS NULL)",
                [*req.ids],
            )
        changed = cur.rowcount
    return {"changed": changed, "publish": req.publish}


@app.post("/api/accounts/hide-all")
def hide_all_accounts(user: dict = Depends(require_session)):
    """SA oculta TODAS las cuentas LIVE de la pool (mueve todo a Trastienda).
    Punto de partida para empezar a publicar selectivamente."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    with db(write=True) as c:
        cur = c.execute(
            "UPDATE accounts SET published_to_pool=0, "
            "locked_by=NULL, locked_at=NULL, locked_until=NULL "
            "WHERE status='LIVE' AND COALESCE(published_to_pool,1)=1 "
            # libera la RESERVADA_SA perpetua al ocultar (Robert 2026-07-17); respeta el
            # lock temporal de operador activo (locked_until NOT NULL → no se oculta).
            "AND (locked_by IS NULL OR locked_until IS NULL)"
        )
        changed = cur.rowcount
    return {"hidden": changed}


@app.get("/api/pool/accounts")
def pool_accounts(user: dict = Depends(require_session)):
    """Cuentas actualmente publicadas a la pool (visibles para los operadores).
    Solo SA — vista de control."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    with db() as c:
        rows = c.execute(
            "SELECT a.id, a.email, a.password, a.balance_total, a.balance_real, "
            "a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, a.grade_score, "
            "a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, "
            "(SELECT COUNT(*) FROM account_assignments ass WHERE ass.email=a.email) AS assigned_to "
            "FROM accounts a "
            "WHERE a.status='LIVE' AND COALESCE(a.published_to_pool,1)=1 "
            "ORDER BY a.balance_total DESC LIMIT 1000"
        ).fetchall()
        out = [dict(r) for r in rows]
        for r in out:
            r["locked_by"] = _resolve_operator(r.get("locked_by"))
        return out


@app.get("/api/pool/split")
def api_pool_split(user: dict = Depends(require_session)):
    """SA: split LIVE accounts into inside (published) vs outside (trastienda)."""
    if not _is_sa(user):
        raise HTTPException(status_code=403, detail="solo superadmin")
    def _combo(email, pw):
        return f"{email}:{pw}" if pw else email
    inside, outside = [], []
    with db() as c:
        for r in c.execute(
            "SELECT email, password, COALESCE(published_to_pool,1) p FROM accounts "
            "WHERE status='LIVE' ORDER BY email"
        ).fetchall():
            item = {"email": r["email"], "combo": _combo(r["email"], r["password"])}
            (inside if r["p"] == 1 else outside).append(item)
    return {"inside": inside, "outside": outside}


@app.post("/api/pool/publish")
def api_pool_publish(payload: dict, user: dict = Depends(require_session)):
    """SA: bulk set published_to_pool by email list. publish=True → 1, False → 0."""
    if not _is_sa(user):
        raise HTTPException(status_code=403, detail="solo superadmin")
    emails = (payload or {}).get("emails") or []
    publish = 1 if (payload or {}).get("publish") else 0
    if not emails:
        return {"moved": 0}
    with db(write=True) as c:
        qmarks = ",".join("?" for _ in emails)
        if publish:
            c.execute(
                f"UPDATE accounts SET published_to_pool=1 WHERE email IN ({qmarks})",
                (*emails,),
            )
        else:
            # Al OCULTAR del pool se LIBERA la RESERVADA_SA perpetua (locked_until IS NULL)
            # y se oculta; el lock TEMPORAL de operador activo (locked_until NOT NULL) se
            # respeta (no se oculta). Antes se saltaba TODO lock, dejando la cuenta pegada
            # al pool (Robert 2026-07-17). Mismo criterio que /accounts/publish y /hide-all.
            c.execute(
                f"UPDATE accounts SET published_to_pool=0, "
                f"locked_by=NULL, locked_at=NULL, locked_until=NULL "
                f"WHERE email IN ({qmarks}) "
                f"AND (locked_by IS NULL OR locked_until IS NULL)",
                (*emails,),
            )
        moved = c.execute("SELECT changes()").fetchone()[0]
    _broadcast({
        "type": "activity", "kind": "pool_move",
        "publish": bool(publish), "count": len(emails),
        "ts": datetime.now(timezone.utc).isoformat(),
        **_resolve_who(user.get("telegram_id")),
    })
    return {"moved": moved}


@app.post("/api/accounts/{account_id}/unlock")
def unlock_account(account_id: int, user: dict = Depends(require_session)):
    with db(write=True) as c:
        row = c.execute(
            "SELECT id, email, locked_by FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        prev_locked_by = row["locked_by"]
        # Autorización: SA puede unlock cualquier cuenta; otros solo si son quien la bloqueó
        if user.get("role") != "superadmin":
            tg = str(user.get("telegram_id") or "")
            uname = str(user.get("username") or "").lower()
            owner = str(prev_locked_by or "").lower()
            if not prev_locked_by or (owner != tg and owner != uname):
                raise HTTPException(403, "Solo puedes desbloquear cuentas que tú bloqueaste")
        # A1: liberar SIEMPRE vía el liberador canónico (republica + limpia notif + broadcast).
        _release_account(c, account_id, row["email"], "unlock manual", prev_locked_by,
                         kind="unlock", who=user.get("username"))
    return {"id": account_id, "locked_by": None, "locked_until": None}


async def _sse_generator(ctx: dict):
    q = _stdlib_queue.SimpleQueue()
    q_id = id(q)
    import logging as _lg
    _sse_log = _lg.getLogger("betmexico.dashboard.sse")
    with _sse_lock:
        _sse_queues.append((q, ctx))
        n_after_join = len(_sse_queues)
        all_ids = [id(x) for (x, _c) in _sse_queues]
    _sse_log.info(f"[SSE] cliente conectado q_id={q_id} role={ctx.get('role')} total={n_after_join} all_ids={all_ids}")
    try:
        yield ": heartbeat\n\n"
        while True:
            msg = await asyncio.get_running_loop().run_in_executor(
                None, _dequeue_blocking, q, 25.0
            )
            yield msg
    except Exception as e:
        _sse_log.warning(f"[SSE] q_id={q_id} excepción no-Cancelled: {type(e).__name__}: {e}")
        raise
    finally:
        with _sse_lock:
            before = len(_sse_queues)
            _sse_queues[:] = [(qq, cc) for (qq, cc) in _sse_queues if qq is not q]
            n_after_leave = len(_sse_queues)
            all_ids = [id(x) for (x, _c) in _sse_queues]
        _sse_log.info(f"[SSE] cliente desconectado q_id={q_id} removed={before - n_after_leave} total={n_after_leave} all_ids={all_ids}")


@app.get("/api/events")
async def events(user: dict = Depends(require_operator_view)):
    ctx = {
        "role": user.get("role"),
        "telegram_id": user.get("telegram_id"),
        "display": user.get("display") or user.get("username"),
    }
    return StreamingResponse(
        _sse_generator(ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/accounts/{account_id}/cards-pipe")
def account_cards_pipe(account_id: int, _user: dict = Depends(require_session)):
    """Devuelve solo las tarjetas en formato pipe (para tooltip rápido)."""
    with db() as c:
        acc = c.execute("SELECT email FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        try:
            rows = c.execute(
                "SELECT card_number, card_expiry, card_cvv, total_approved, total_deposits "
                "FROM account_cards WHERE account_email=? "
                "ORDER BY last_used_at DESC, registered_at DESC LIMIT 20",
                (acc["email"],),
            ).fetchall()
        except sqlite3.OperationalError:
            return {"cards": []}
    from web_utils import canonical_card_pipe
    out = []
    for r in rows:
        if not (r["card_number"] and r["card_expiry"] and r["card_cvv"]):
            continue
        out.append({
            # pipe CANÓNICO único: NNNN|MM|YY|CVV (web_utils.canonical_card_pipe)
            "pipe": canonical_card_pipe(r["card_number"], r["card_expiry"], r["card_cvv"]),
            "approved": r["total_approved"] or 0,
            "deposits": r["total_deposits"] or 0,
        })
    return {"cards": out}


@app.get("/api/accounts/{account_id}/notes-summary")
def account_notes_summary(account_id: int, user: dict = Depends(require_session)):
    """Notas resumidas para tooltip — filtradas por user/SA."""
    role = user.get("role", "user")
    my_tg = int(user.get("telegram_id") or 0)
    with db() as c:
        acc = c.execute("SELECT email FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        try:
            if role == "superadmin":
                rows = c.execute(
                    "SELECT note_text, created_by_name, created_at FROM account_notes "
                    "WHERE account_email=? AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 10",
                    (acc["email"],),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT note_text, created_by_name, created_at FROM account_notes "
                    "WHERE account_email=? AND created_by=? AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 10",
                    (acc["email"], my_tg),
                ).fetchall()
        except sqlite3.OperationalError:
            return {"notes": []}
    return {"notes": [dict(r) for r in rows]}


def _record_account_touch(account_id: int, account_email: str, actor_id) -> bool:
    """Persiste el toque de auditoría (quién abrió La Pantalla de qué cuenta).

    Dedup 1/día por (account_id, actor_id, touched_date) — la constraint UNIQUE
    de `account_touches` lo garantiza a nivel BD; el INSERT OR IGNORE es idempotente.

    Es una operación de escritura trivial pero, al correr en el path síncrono de
    `account_details` (read de alta concurrencia), choca con writes sostenidos por
    el bot TG sobre la BD compartida → `database is locked` sostenido (caza 2026-07-25,
    instrumentación commit 3b59fe7). Por eso el caller la despacha fire-and-forget en
    un thread daemon: el request de account_details NO espera al touch.

    Devuelve True si el toque fue NUEVO (para que el caller decida broadcast SSE).
    Traga OperationalError (lock) en silencio: perder un toque de bitácora es
    aceptable; bloquear la lectura de La Pantalla no.
    """
    try:
        from zoneinfo import ZoneInfo
        now_mx = datetime.now(ZoneInfo("UTC")).astimezone(ZoneInfo("America/Mexico_City"))
    except Exception:
        now_mx = datetime.utcnow() - timedelta(hours=6)  # MX = UTC-6 fijo (sin DST desde 2022)
    touched_at = now_mx.strftime("%Y-%m-%d %H:%M:%S")
    touched_date = touched_at[:10]
    try:
        with db(write=True) as c2:
            cur = c2.execute(
                "INSERT OR IGNORE INTO account_touches "
                "(account_id, account_email, actor_id, touched_at, touched_date) "
                "VALUES (?,?,?,?,?)",
                (account_id, account_email, int(actor_id), touched_at, touched_date),
            )
        return bool(cur.rowcount)
    except sqlite3.OperationalError:
        return False


@app.get("/api/accounts/find-id")
def account_find_id(email: str, _user: dict = Depends(require_session)):
    """Resuelve el id numérico de una cuenta por email — usado por la consola
    de Logs para redirigir al detalle de cuenta al hacer click en una línea
    (2026-07-31, click-through intuitivo desde logs)."""
    with db() as c:
        row = c.execute("SELECT id FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
    return {"id": row["id"] if row else None}


@app.get("/api/accounts/{account_id}/details")
def account_details(account_id: int, _user: dict = Depends(require_session)):
    with db() as c:
        acc = c.execute(
            "SELECT id, email, password, balance_total, balance_real, "
            "last_deposit_amount, last_deposit_date, status, grade, grade_score, "
            "locked_by, locked_at, locked_until, last_checked_at, check_count, "
            "first_checked_at, "
            "fullname, birthdate, address, phone, curp, kyc_verified "
            "FROM accounts WHERE id=? LIMIT 1",
            (account_id,),
        ).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        result = dict(acc)

        # Si no hay CURP guardado o es 'N/A', calcular e iniciar autovalidación RENAPO en backend
        curp_stored = result.get("curp")
        if not curp_stored or curp_stored == "N/A":
            calc_curp = compute_curp(
                fullname=result.get("fullname", ""),
                birthdate=result.get("birthdate", ""),
                address=result.get("address", "")
            )
            result["curp_calc"] = calc_curp
            result["curp_candidates"] = generate_curp_candidates(
                fullname=result.get("fullname", ""),
                birthdate=result.get("birthdate", ""),
                address=result.get("address", "")
            )

            # Tarea asíncrona en segundo plano para validar con RENAPO vía proxies y guardar en BD
            def _async_val_renapo(acc_id, fn, bd, addr):
                try:
                    val_curp = validate_renapo_curp(fn, bd, addr)
                    if val_curp:
                        with db(write=True) as c_val:
                            c_val.execute("UPDATE accounts SET curp=? WHERE id=?", (val_curp, acc_id))
                        _broadcast({
                            "type": "account_updated",
                            "kind": "curp_validated",
                            "account_id": acc_id,
                            "curp": val_curp
                        })
                except Exception as ex_renapo:
                    _logging.getLogger("betmexico.dashboard").warning(f"Error autovalidando RENAPO para acc {acc_id}: {ex_renapo}")

            threading.Thread(
                target=_async_val_renapo,
                args=(account_id, result.get("fullname", ""), result.get("birthdate", ""), result.get("address", "")),
                daemon=True
            ).start()
        else:
            result["curp_calc"] = None
            result["curp_candidates"] = []

        # Tarjetas guardadas
        try:
            rows = c.execute(
                "SELECT id, card_number, card_expiry, card_cvv, registered_at, "
                "last_used_at, total_deposits, total_approved, total_rejected, status "
                "FROM account_cards WHERE account_email=? "
                "ORDER BY last_used_at DESC, registered_at DESC LIMIT 50",
                (acc["email"],),
            ).fetchall()
            result["cards"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["cards"] = []

        # Transacciones recientes
        try:
            rows = c.execute(
                "SELECT id, txn_date, amount, status, txn_type, gateway, fetched_at "
                "FROM account_transactions WHERE account_email=? "
                "ORDER BY txn_date DESC LIMIT 30",
                (acc["email"],),
            ).fetchall()
            result["transactions"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["transactions"] = []

        # Intentos de depósito hechos desde el dashboard (con tarjeta usada)
        try:
            rows = c.execute(
                "SELECT attempt_id, amount, status, rejection_reason, card_pipe, "
                "       duration_ms, operator_id, created_at "
                "FROM deposit_attempts WHERE account_email=? "
                "ORDER BY id DESC LIMIT 30",
                (acc["email"],),
            ).fetchall()
            result["deposit_attempts"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["deposit_attempts"] = []

        # Notas — non-SA solo ve las propias; SA ve todas
        role = _user.get("role", "user")
        my_tg = int(_user.get("telegram_id") or 0)
        try:
            if role == "superadmin":
                rows = c.execute(
                    "SELECT id, note_text, created_at, created_by, created_by_name "
                    "FROM account_notes WHERE account_email=? AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 50",
                    (acc["email"],),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, note_text, created_at, created_by, created_by_name "
                    "FROM account_notes WHERE account_email=? AND created_by=? "
                    "AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 50",
                    (acc["email"], my_tg),
                ).fetchall()
            result["notes"] = [dict(r) for r in rows]
            for n in result["notes"]:
                n["mine"] = (n.get("created_by") == my_tg)
        except sqlite3.OperationalError:
            result["notes"] = []

        # ── Movimientos UNIFICADOS (dashboard + betmex) ─────────────────────
        # Mezcla deposit_attempts (nuestros, source="dashboard") con
        # account_transactions (de la página, source="betmex"). Normaliza a un
        # shape común y ordena por fecha DESC. NO sustituye a transactions/
        # deposit_attempts (se conservan arriba para compat); esto es additivo.
        #
        # Shape de cada item:
        #   {when, source, kind, method, amount, state, who, card_pipe, reason}
        #     when      : ISO TEXT (created_at | txn_date)
        #     source    : "dashboard" | "betmex"
        #     kind      : "deposit" | "withdrawal"
        #     method    : "Pago con tarjeta" | "SPEI" | "OXXO" | None
        #     amount    : float
        #     state     : "ok" | "fail" | "pending" | "wd"
        #     who       : nombre operador (solo dashboard) | None
        #     card_pipe : pipe COMPLETO sin enmascarar (solo dashboard) | None
        #     reason    : rejection_reason si fail | None
        try:
            # Resolver telegram_id -> nombre operador (como deposits.py:464)
            try:
                from web_auth import WEB_USERS_RAW as _USERS_RAW
            except Exception:
                _USERS_RAW = {}

            def _op_name(op_id):
                if not op_id:
                    return None
                try:
                    op_id_int = int(op_id)
                except (TypeError, ValueError):
                    return None
                for uname, u in _USERS_RAW.items():
                    if u.get("telegram_id") == op_id_int:
                        return uname
                return None

            movimientos = []

            # created_at de deposit_attempts se guarda en UTC naïve (datetime.now(utc)/
            # datetime('now') de SQLite). El frontend trata los timestamps naïve como
            # hora local MX → mostraba las nuestras +6h. txn_date de BetMexico YA viene
            # en hora MX (verificado: SPEI en BD coinciden con la franja horaria de la
            # página). Por eso convertimos SOLO created_at: UTC → MX. Bonus: el sort por
            # `when` deja de mezclar UTC y MX (antes desordenaba entre fuentes).
            def _utc_to_mx(ts):
                if not ts:
                    return ts
                try:
                    s = str(ts).replace("T", " ")
                    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in s else "%Y-%m-%d %H:%M:%S"
                    dt = datetime.strptime(s, fmt)
                    try:
                        from zoneinfo import ZoneInfo
                        dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/Mexico_City"))
                    except Exception:
                        dt = dt - timedelta(hours=6)  # MX = UTC-6 fijo (sin DST desde 2022)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return ts

            # Parseo laxo de timestamp → datetime (para deduplicar por monto+tiempo).
            def _parse_when(ts):
                if not ts:
                    return None
                s = _mv_re0.sub("", str(ts).replace("T", " "))   # quita microsegundos
                try:
                    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    try:
                        return datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
                    except Exception:
                        return None
            import re as _mv_re0_mod
            _mv_re0 = _mv_re0_mod.compile(r"\.\d+")

            # DEDUP: un depósito con tarjeta hecho DESDE el dashboard (deposit_attempt)
            # también aparece luego en el historial de BetMexico como txn de tarjeta →
            # doble registro del mismo evento. Aplica a APROBADOS (status 6) y RECHAZADOS
            # (status -4) por igual. Guardamos la firma de cada intento nuestro (monto +
            # hora MX) para omitir su eco de BetMexico más abajo, emparejando por cercanía
            # y CONSUMIENDO cada firma (montos repetidos no se dedup de más).
            # "Es uno u otro": conservamos el NUESTRO (tiene operador + tarjeta usada).
            _dash_sigs = []   # [(amount_float, datetime_mx)]

            # deposit_attempts → siempre deposit, source dashboard
            for a in result.get("deposit_attempts", []):
                st = (a.get("status") or "").lower()
                reason_txt = a.get("rejection_reason") or ""
                # 3DS = estado propio (ámbar): NO se acreditó pero NO es rechazo del
                # banco — el procesador pidió autenticación (Robert 2026-05-29).
                # Guardamos/mostramos aunque BetMexico no liste la txn en su historial.
                is_3ds = "3ds" in reason_txt.lower() or st == "threeds"
                if st == "approved":
                    state = "ok"
                elif is_3ds:
                    state = "threeds"
                elif st == "rejected":
                    state = "fail"                      # SOLO rechazo REAL de banco
                elif st in ("rate_limited", "account_dead", "login_lost",
                            "gateway_error", "timeout", "ambiguous",
                            "incomplete", "error"):
                    # No-banco (rate-limit/infra/cuenta/nuestro lado): NO se atribuye
                    # al banco ni se firma como txn (no llegó al gateway). El `reason`
                    # da el detalle operativo (bug 2026-07-06).
                    state = "incomplete"
                else:
                    state = "pending"
                when_mx = _utc_to_mx(a.get("created_at"))
                movimientos.append({
                    "when": when_mx,
                    "source": "dashboard",
                    "kind": "deposit",
                    "method": "Pago con tarjeta",
                    "amount": a.get("amount"),
                    "state": state,
                    "who": _op_name(a.get("operator_id")),
                    "card_pipe": a.get("card_pipe"),
                    "reason": reason_txt if state in ("fail", "threeds", "incomplete") else None,
                })
                # Firma para dedup: aprobados y rechazados se reflejan en BetMexico
                # (status 6 y -4). Los 3DS/pending no generan txn → no se firman.
                # Guardamos también el ESTADO (ok/fail): el eco debe COINCIDIR en estado.
                # Sin esto, una firma 'fail' podía consumir un depósito APROBADO real y
                # ocultarlo de la vista (fix 2026-07-03, auditoría hallazgo #2).
                if state in ("ok", "fail"):
                    try:
                        _dash_sigs.append((float(a.get("amount") or 0), _parse_when(when_mx), state))
                    except (TypeError, ValueError):
                        pass

            # account_transactions → betmex. txn_type 1=dep, 2=retiro.
            # gateway 1=tarjeta, 2=SPEI, 3=OXXO. status 6=ok,0=pending,-4/5=fail.
            _gw_method = {1: "Pago con tarjeta", 2: "SPEI", 3: "OXXO"}
            # Resolver etiquetas de integración para SPEI si existen en clabes
            spei_integrations = []
            for c_item in (result.get("clabes") or []):
                integ = str(c_item.get("integration") or "").upper() if isinstance(c_item, dict) else ""
                ord_v = c_item.get("clabe_order") if isinstance(c_item, dict) else None
                if integ:
                    label = f"SPEI · {integ}" + (f" · {ord_v}" if ord_v else "")
                    if label not in spei_integrations:
                        spei_integrations.append(label)
            spei_default_label = spei_integrations[0] if spei_integrations else "SPEI · STP"

            for t in result.get("transactions", []):
                is_wd = t.get("txn_type") == 2
                kind = "withdrawal" if is_wd else "deposit"
                gw = t.get("gateway")
                if is_wd:
                    state = "wd"
                    method_label = "TARJETA" if gw == 1 else spei_default_label
                else:
                    s = t.get("status")
                    if s == 6:
                        state = "ok"
                    elif s == 0:
                        state = "pending"
                    elif s in (-4, 5):
                        state = "fail"
                    else:
                        state = "pending"
                    method_label = _gw_method.get(gw)

                # DEDUP: si este depósito con tarjeta coincide (mismo monto + hora ±3min
                # + MISMO ESTADO) con un intento hecho desde el dashboard, es el MISMO
                # evento → omitir el eco de BetMexico (ya está como movimiento nuestro).
                # La coincidencia de ESTADO es clave: sin ella una firma 'fail' podía
                # consumir un depósito APROBADO real y ocultarlo (fix 2026-07-03, hallazgo
                # #2). Empareja con la firma MÁS CERCANA en tiempo del MISMO estado y la consume.
                if (not is_wd and gw == 1 and state in ("ok", "fail") and _dash_sigs):
                    _tw = _parse_when(t.get("txn_date"))
                    try:
                        _ta = float(t.get("amount") or 0)
                    except (TypeError, ValueError):
                        _ta = None
                    if _tw is not None and _ta is not None:
                        _best, _best_dt = None, None
                        for _k, (_da, _ds, _dst) in enumerate(_dash_sigs):
                            if _ds is None or _dst != state or abs(_ta - _da) >= 0.01:
                                continue
                            _dsec = abs((_tw - _ds).total_seconds())
                            if _dsec <= 180 and (_best is None or _dsec < _best_dt):
                                _best, _best_dt = _k, _dsec
                        if _best is not None:
                            _dash_sigs.pop(_best)
                            continue
                movimientos.append({
                    "when": t.get("txn_date"),
                    "source": "betmex",
                    "kind": kind,
                    "method": method_label,
                    "gateway": gw,
                    "amount": t.get("amount"),
                    "state": state,
                    "who": None,
                    "card_pipe": None,
                    "reason": None,
                })

            # Orden DESC por fecha. Normaliza antes del sort: 'T'→espacio y
            # microsegundos a 6 dígitos (la BD tiene casos con 5 dígitos como
            # '.94907' que rompen el orden lexicográfico crudo entre fuentes).
            import re as _mv_re
            def _mv_sort_key(m):
                w = (m.get("when") or "").replace("T", " ")
                return _mv_re.sub(r"\.(\d+)", lambda x: "." + (x.group(1) + "000000")[:6], w)
            movimientos.sort(key=_mv_sort_key, reverse=True)
            result["movimientos"] = movimientos
        except Exception as _mv_err:
            _logging.getLogger("betmexico.dashboard").warning(
                f"[Details] movimientos merge failed: {_mv_err}"
            )
            result["movimientos"] = []

        # Toque de cuenta (vigilancia: quién metió mano) — dedup 1/día por usuario+cuenta.
        # Fire-and-forget: el touch es un write de auditoría que NO debe bloquear la
        # lectura de La Pantalla. Antes vivía síncrono en `db(write=True)` y, bajo
        # contención con el bot TG sobre la BD compartida, lanzaba `database is locked`
        # sostenido (caza 2026-07-25, commit 3b59fe7). Ahora corre en un thread daemon:
        # el request sigue de inmediato; el touch persiste (o se pierde si hay lock —
        # aceptable, es bitácora, no transacción). El broadcast SSE va dentro del thread
        # para que solo dispare si el toque realmente entró.
        actor_id = _user.get("telegram_id")
        if actor_id is not None:
            _acc_email = acc["email"]
            def _touch_task():
                ts = _record_account_touch(account_id, _acc_email, actor_id)
                if ts:
                    _broadcast({"type": "activity", "kind": "account_touch",
                                "target": _acc_email, "id": account_id,
                                **_resolve_who(actor_id)})
            threading.Thread(target=_touch_task, daemon=True).start()

        # Clabes de depósito SPEI (NVIO + STP) persistidas en BD. Se muestran en
        # La Pantalla sin enmascarar (feedback_no_masking). NO se taladra la cuenta
        # aquí: solo se lee lo guardado; el fetch manual vive en POST .../clabes/refresh.
        try:
            rows = c.execute(
                "SELECT clabe, integration, clabe_order, blocked, fetched_at, "
                "reference, user_id, full_name "
                "FROM account_deposit_clabes WHERE account_id=? "
                "ORDER BY clabe_order ASC",
                (account_id,),
            ).fetchall()
            result["clabes"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["clabes"] = []

        # Retiro más reciente (SA-only en frontend; el dato en sí no es sensible).
        # Permite reabrir La Pantalla y ver/retomar el estado sin re-disparar.
        try:
            wd = c.execute(
                "SELECT transaction_id, reference, amount, account_digits, "
                "institution_name, status_api, gateway, last_modified_utc, created_at "
                "FROM account_withdrawals WHERE account_id=? "
                "ORDER BY id DESC LIMIT 1",
                (account_id,),
            ).fetchone()
            result["last_withdrawal"] = dict(wd) if wd else None
        except sqlite3.OperationalError:
            result["last_withdrawal"] = None

    return result


class NoteCreate(BaseModel):
    text: str


@app.post("/api/accounts/{account_id}/notes")
def create_note(account_id: int, req: NoteCreate, user: dict = Depends(require_session)):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "Texto vacío")
    if len(text) > 2000:
        raise HTTPException(400, "Nota muy larga (máx 2000)")
    tg = int(user.get("telegram_id") or 0)
    name = user.get("display") or user.get("username") or "?"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db(write=True) as c:
        acc = c.execute(
            "SELECT email, password FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        cur = c.execute(
            "INSERT INTO account_notes "
            "(account_email, account_password, note_type, note_text, "
            " created_by, created_by_name, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (acc["email"], acc["password"] or "", "USER", text, tg, name, now, now),
        )
        note_id = cur.lastrowid
    _broadcast({
        "type": "activity", "kind": "note",
        "ts": now, "who": name, "who_id": tg,
        "target": acc["email"], "id": note_id,
        "text": text[:120],
    })
    return {"id": note_id, "created_at": now}


class CurpUpdate(BaseModel):
    curp: str


@app.post("/api/accounts/{account_id}/curp")
def update_curp(account_id: int, req: CurpUpdate, _user: dict = Depends(require_session)):
    """Guarda CURP validado manualmente por el operador."""
    curp = (req.curp or "").strip().upper()
    # Validación básica: 18 chars, formato general
    import re
    if not re.match(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$", curp):
        raise HTTPException(400, "CURP inválido (formato 18 chars)")
    with db(write=True) as c:
        cur = c.execute("UPDATE accounts SET curp=? WHERE id=?", (curp, account_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Cuenta no encontrada")
    return {"id": account_id, "curp": curp}


# ── Clabes de depósito SPEI (NVIO + STP) ──────────────────────────────────────
# Lectura desde BD (lo guardado por BeginDeposit). Accionable: el operador ve
# las clabes en La Pantalla sin enmascarar, copiables con un click. El fetch
# manual (POST .../clabes/refresh) lo dispara a propósito el operador — NUNCA se
# llama BeginDeposit en cada refresh (alimentaría el rate-limit de BetMexico;
# las clabes son FIJAS por usuario). Ver clabe_fetch.py + docs/RECON_BETMEX_API.md.
@app.get("/api/accounts/{account_id}/clabes")
def get_clabes(account_id: int, _user: dict = Depends(require_session)):
    with db() as c:
        rows = c.execute(
            "SELECT clabe, integration, clabe_order, blocked, fetched_at, "
            "reference, user_id, full_name "
            "FROM account_deposit_clabes WHERE account_id=? "
            "ORDER BY clabe_order ASC",
            (account_id,),
        ).fetchall()
        return {"clabes": [dict(r) for r in rows]}


@app.post("/api/accounts/{account_id}/clabes/refresh")
async def refresh_clabes(account_id: int, _user: dict = Depends(require_session)):
    """Dispara BeginDeposit con JWT+proxy y persiste las clabes en BD.
    Acción manual del operador (no automática en cada refresh)."""
    try:
        import clabe_fetch as _cf
        result = await _cf.refresh_clabes_for_account(str(DB_PATH), account_id)
    except Exception as e:
        raise HTTPException(500, f"Error obteniendo clabes: {e}")
    if not result.get("ok"):
        raise HTTPException(409, result.get("error") or "No se pudieron obtener las clabes")
    return result


# ── Retiro automático (botón SA en La Pantalla) ───────────────────────────────
# 5 pasos vía withdrawals.py. bug#1: cuenta de retiro puede cambiar por depósito
# SPEI reciente (NUNCA cachear). bug#2: status:6 de BetMexico != aterrizó en el
# banco (reportar 2 fases). bug#3: puede aterrizar en tarjeta en vez de SPEI.
# Ver docs/superpowers/specs/2026-07-24-boton-retiro-automatico-design.md.

def _persist_withdrawal(account_id: int, disparado_por, result: dict) -> None:
    # Robert, campo 2026-07-25: BetMexico YA ejecutó el retiro real (execute_withdrawal,
    # arriba en withdraw()) antes de que esta función corra — este INSERT es el ÚNICO
    # rastro local de un movimiento de dinero real. Un "database is locked" transitorio
    # aquí (el connect-level timeout=10s de db() ya expiró una vez en prod, ver
    # docs/ERRORS.md) NO puede tirar el registro silenciosamente: perderíamos la
    # trazabilidad de un retiro que sí salió, dejando al operador viendo un 500 sin
    # saber si el dinero se movió. Retry con backoff — cada intento abre su propia
    # conexión (su propio timeout=10s), dándole varios intentos de 10s a un writer
    # que sostiene el lock más tiempo del normal, en vez de rendirse a la primera.
    now = datetime.now(timezone.utc).isoformat()
    _lg = _logging.getLogger("betmexico.dashboard.withdrawals")
    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            with db(write=True) as c:
                c.execute(
                    "INSERT OR IGNORE INTO account_withdrawals "
                    "(account_id, account_email, transaction_id, reference, amount, "
                    " account_digits, institution_name, disparado_por, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        account_id,
                        result.get("account_email"),
                        result["transactionId"],
                        result.get("reference"),
                        result["amount"],
                        result.get("accountDigits"),
                        result.get("institutionName"),
                        int(disparado_por) if disparado_por is not None else None,
                        now,
                    ),
                )
            return
        except sqlite3.OperationalError as e:
            if "database is locked" not in str(e) or attempt == attempts:
                _lg.error(
                    f"[withdraw] PERSIST FAILED tras {attempt} intento(s) — retiro real "
                    f"transactionId={result.get('transactionId')} amount={result.get('amount')} "
                    f"account_id={account_id} SIN registrar en account_withdrawals: {e}"
                )
                raise
            _lg.warning(
                f"[withdraw] persist intento {attempt}/{attempts} chocó con lock, "
                f"reintentando en {attempt}s — transactionId={result.get('transactionId')}"
            )
            time.sleep(attempt)


@app.post("/api/accounts/{account_id}/withdraw")
async def withdraw(account_id: int, payload: dict, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    from withdrawals import _refresh_account_after_withdrawal
    with db() as c:
        acc = c.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        raise HTTPException(404, "Cuenta no encontrada")
    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(400, "amount inválido")
    if amount <= 0:
        raise HTTPException(400, "amount debe ser > 0")
    try:
        result = await execute_withdrawal(str(DB_PATH), account_id, amount)
    except JwtExpired:
        raise HTTPException(409, "JWT expirado, requiere refresh")
    except InsufficientBalance as e:
        raise HTTPException(409, str(e))
    except NoApprovedWithdrawalAccount:
        raise HTTPException(409, "Sin cuenta de retiro aprobada: requiere SPEI de depósito primero")
    except MultipleApprovedAccounts as e:
        raise HTTPException(409, str(e))
    except ConcurrentWithdrawalPending:
        raise HTTPException(409, "Ya hay un retiro pendiente en esta cuenta")
    # A partir de aquí el retiro YA SE EJECUTÓ de verdad en BetMexico (execute_withdrawal
    # ya corrió) — lo que sigue es solo nuestro registro local. Si _persist_withdrawal
    # agota sus reintentos (bug de campo 2026-07-25: "database is locked" tumbó el INSERT
    # y el operador vio un 500 sin saber si el dinero se movió), NO devolvemos un 500
    # genérico que lee como "el retiro falló" — el retiro SÍ salió. Devolvemos 200 con
    # persisted:false + el transactionId real para que el operador pueda reconciliar a
    # mano, en vez de dejarlo a ciegas.
    persisted = True
    try:
        _persist_withdrawal(account_id, user.get("telegram_id"), result)
    except sqlite3.OperationalError:
        persisted = False
    # Refresh post-retiro (handoff 2026-08-05 §2.3): el retiro ya se ejecutó en
    # BetMexico — traemos el saldo post-retiro a BD de inmediato reusando el JWT
    # que ya tiene execute_withdrawal (sin gastar captcha). No-throws.
    await _refresh_account_after_withdrawal(
        result.get("account_email"), result.get("_jwt"),
        result.get("_proxy_url"), user.get("telegram_id") or 0)
    if persisted:
        _broadcast({
            "type": "activity", "kind": "withdrawal",
            "ts": datetime.now(timezone.utc).isoformat(),
            "target": result.get("account_email"), "id": account_id,
            "amount": amount, "transactionId": result["transactionId"],
            **_resolve_who(user.get("telegram_id")),
        })
    return {**result, "persisted": persisted}


@app.get("/api/accounts/{account_id}/withdraw/status/{tx_id}")
async def withdraw_status(account_id: int, tx_id: str, user: dict = Depends(require_session)):
    with db() as c:
        acc = c.execute(
            "SELECT id, email, jwt_token FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if user.get("role") != "superadmin":
            vis = _visible_emails(user, c)
            if not acc or (vis is not None and acc["email"] not in vis):
                raise HTTPException(403, "No tienes permiso sobre esta cuenta")
        row = c.execute(
            "SELECT * FROM account_withdrawals WHERE transaction_id=? AND account_id=?",
            (tx_id, account_id),
        ).fetchone()
    if not acc or not row:
        raise HTTPException(404, "Retiro no encontrado")

    jwt = acc["jwt_token"]
    proxy_url = None
    try:
        import proxy_pool as _pp
        proxy_url = _pp.build_admin_proxy_url()
    except Exception:
        pass

    expected_digits = row["account_digits"]
    prev_status = row["status_api"]
    pending = None
    if jwt:
        try:
            pending = await get_pending_withdrawal(jwt, proxy_url)
        except Exception:
            pending = None

    out = {
        "transactionId": tx_id,
        "accountDigits": expected_digits,
        "alerts": {"gatewayMismatch": False, "digitsMismatch": False},
    }

    if pending is not None:
        status_api = pending.get("transactionStatus")
        out["transactionStatus"] = status_api
        if status_api == 6:
            # bug#2: status:6 = BetMexico lo ejecutó, NO que aterrizó en el banco.
            # Confirmar rail externo vía PASO5 antes de reportar "delivered".
            bank_tx = None
            if jwt:
                try:
                    bank_tx = await get_bank_transaction(
                        jwt, proxy_url, tx_id, expected_digits=expected_digits
                    )
                except Exception:
                    bank_tx = None
            out["status"] = "successful"
            out["phase"] = "executed"
            out["description"] = "Ejecutado por BetMexico — confirma en tu banco"
            if bank_tx is not None:
                out["lastModifiedUtc"] = bank_tx.get("lastModifiedUtc")
                out["gateway"] = bank_tx.get("gateway")
                out["alerts"]["gatewayMismatch"] = bool(bank_tx.get("gateway_mismatch"))
                out["alerts"]["digitsMismatch"] = bool(bank_tx.get("digits_mismatch"))
                with db(write=True) as c:
                    c.execute(
                        "UPDATE account_withdrawals SET status_api=?, gateway=?, "
                        "last_modified_utc=? WHERE transaction_id=?",
                        (status_api, bank_tx.get("gateway"), bank_tx.get("lastModifiedUtc"), tx_id),
                    )
            else:
                with db(write=True) as c:
                    c.execute(
                        "UPDATE account_withdrawals SET status_api=? WHERE transaction_id=?",
                        (status_api, tx_id),
                    )
        else:
            out["status"] = "pending"
            out["phase"] = "pending"
            out["description"] = pending.get("transactionStatusDescription") or "Pendiente"
            with db(write=True) as c:
                c.execute(
                    "UPDATE account_withdrawals SET status_api=? WHERE transaction_id=?",
                    (status_api, tx_id),
                )
    elif prev_status == 6:
        out["status"] = "completed"
        out["phase"] = "completed"
        out["transactionStatus"] = prev_status
        out["lastModifiedUtc"] = row["last_modified_utc"]
        out["gateway"] = row["gateway"]
    elif prev_status is not None and prev_status < 0:
        out["status"] = "failed"
        out["phase"] = "failed"
        out["transactionStatus"] = prev_status
        out["lastModifiedUtc"] = row["last_modified_utc"]
        out["gateway"] = row["gateway"]
    else:
        # Root cause (2026-07-26, medido con tx real 232b8814...): BetMexico saca
        # el retiro de PendingWithdrawal (PASO4→None) en cuanto se resuelve — MUCHO
        # antes de que este endpoint vuelva a mirar el rail externo. status_api en
        # BD quedaba pegado al último valor intermedio que reportó PASO4 mientras
        # aún aparecía ahí (ej. 2), y sin este PASO5 el status caía en "idle" para
        # siempre: el frontend nunca ve un estado terminal → "Retiro en proceso"
        # colgado eternamente aunque BetMexico ya lo haya ejecutado. PASO5 es la
        # única fuente que sigue teniendo el desenlace real una vez que cae de la
        # lista de pendientes.
        bank_tx = None
        if jwt:
            try:
                bank_tx = await get_bank_transaction(
                    jwt, proxy_url, tx_id, expected_digits=expected_digits
                )
            except Exception:
                bank_tx = None
        if bank_tx is not None and bank_tx.get("transactionStatus") == 6:
            out["status"] = "successful"
            out["phase"] = "executed"
            out["description"] = "Ejecutado por BetMexico — confirma en tu banco"
            out["transactionStatus"] = 6
            out["lastModifiedUtc"] = bank_tx.get("lastModifiedUtc")
            out["gateway"] = bank_tx.get("gateway")
            out["alerts"]["gatewayMismatch"] = bool(bank_tx.get("gateway_mismatch"))
            out["alerts"]["digitsMismatch"] = bool(bank_tx.get("digits_mismatch"))
            with db(write=True) as c:
                c.execute(
                    "UPDATE account_withdrawals SET status_api=?, gateway=?, "
                    "last_modified_utc=? WHERE transaction_id=?",
                    (6, bank_tx.get("gateway"), bank_tx.get("lastModifiedUtc"), tx_id),
                )
        elif bank_tx is not None:
            # El rail respondió pero sin status 6 — reporta lo que dice, no lo
            # pisamos con un valor inventado.
            out["status"] = "pending"
            out["phase"] = "pending"
            out["transactionStatus"] = bank_tx.get("transactionStatus")
            out["lastModifiedUtc"] = bank_tx.get("lastModifiedUtc")
            out["gateway"] = bank_tx.get("gateway")
        else:
            # Ni PASO4 ni PASO5 confirman nada ahora mismo — de verdad desconocido,
            # NO se disfraza de completado ni de fallido sin evidencia. El próximo
            # poll lo vuelve a intentar.
            out["status"] = "idle"
            out["phase"] = "idle"
            out["transactionStatus"] = prev_status
            out["lastModifiedUtc"] = row["last_modified_utc"]
            out["gateway"] = row["gateway"]

    # SSE broadcast cuando el status cambia a terminal (Task #12): permite que
    # otros clientes/tabs/feed vean el cambio sin tener que hacer poll.
    _WD_TERMINAL = {6}  # status_api 6 = ejecutado
    new_status_api = out.get("transactionStatus")
    new_terminal = new_status_api in _WD_TERMINAL or out.get("status") in ("successful", "completed", "failed")
    was_terminal = prev_status in _WD_TERMINAL
    if new_terminal and not was_terminal:
        _broadcast({
            "type": "activity", "kind": "withdrawal_status",
            "ts": datetime.now(timezone.utc).isoformat(),
            "target": row["account_email"], "id": account_id,
            "transactionId": tx_id, "status": out["status"],
            "amount": row["amount"],
        })

    return out


@app.delete("/api/accounts/{account_id}/notes/{note_id}")
def delete_note(account_id: int, note_id: int, user: dict = Depends(require_session)):
    tg = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")
    with db(write=True) as c:
        row = c.execute(
            "SELECT id, created_by, account_email FROM account_notes WHERE id=?", (note_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Nota no encontrada")
        if role != "superadmin" and row["created_by"] != tg:
            raise HTTPException(403, "Solo puedes borrar tus propias notas")
        c.execute("DELETE FROM account_notes WHERE id=?", (note_id,))
    return {"deleted": note_id}


class CombosRequest(BaseModel):
    ids: list[int]


@app.post("/api/accounts/combos")
def accounts_combos(req: CombosRequest, user: dict = Depends(require_session)):
    if not req.ids:
        return {"combos": []}
    placeholders = ",".join("?" * len(req.ids))
    with db() as c:
        vis = _visible_emails(user, c)   # None = SA; set = universo del operador
        rows = c.execute(
            f"SELECT id, email, password FROM accounts WHERE id IN ({placeholders})",
            req.ids,
        ).fetchall()
    return {"combos": [
        {"id": r["id"], "email": r["email"], "password": r["password"]}
        for r in rows if vis is None or r["email"] in vis
    ]}


@app.get("/api/accounts/pass-map")
def accounts_pass_map(user: dict = Depends(require_session)):
    """Mapa email→password acotado al universo del caller (SA = todos)."""
    with db() as c:
        vis = _visible_emails(user, c)
        rows = c.execute("SELECT email, password FROM accounts WHERE password IS NOT NULL").fetchall()
    return {r["email"]: r["password"] for r in rows if vis is None or r["email"] in vis}


@app.get("/api/cards/all")
def list_all_cards(user: dict = Depends(require_session)):
    """Lista unificada de tarjetas (account_cards + account_notes con card).

    Devuelve pipe completo sin enmascarar. Dedupe por (card_number, account_email).
    `source` indica origen ('card' = formalmente registrada, 'note' = solo en nota).
    """
    from web_utils import canonical_card_pipe
    out = []
    seen = set()
    with db() as c:
        vis = _visible_emails(user, c)   # None = SA (ve todo); set = universo del operador
        # 1) account_cards (registradas formalmente)
        try:
            rows = c.execute(
                "SELECT card_number, card_expiry, card_cvv, account_email, account_password, "
                "registered_by, registered_by_name, registered_at, last_used_at, "
                "total_deposits, total_approved, total_rejected, status "
                "FROM account_cards ORDER BY registered_at DESC"
            ).fetchall()
            for r in rows:
                if vis is not None and r["account_email"] not in vis:
                    continue
                key = (r["card_number"], r["account_email"])
                seen.add(key)
                out.append({
                    "source": "card",
                    "card_pipe": canonical_card_pipe(r["card_number"], r["card_expiry"], r["card_cvv"]),
                    "card_number": r["card_number"],
                    "card_expiry": r["card_expiry"],
                    "card_cvv": r["card_cvv"],
                    "account_email": r["account_email"],
                    "account_password": r["account_password"],
                    "registered_by": r["registered_by_name"] or r["registered_by"],
                    "registered_at": r["registered_at"],
                    "last_used_at": r["last_used_at"],
                    "total_deposits": r["total_deposits"] or 0,
                    "total_approved": r["total_approved"] or 0,
                    "total_rejected": r["total_rejected"] or 0,
                    "status": r["status"] or "ACTIVE",
                })
        except sqlite3.OperationalError:
            pass
        # 2) account_notes con card (no duplicados ya en account_cards)
        try:
            rows = c.execute(
                "SELECT card_number, card_expiry, card_cvv, account_email, account_password, "
                "created_by, created_by_name, created_at, note_type, note_text "
                "FROM account_notes "
                "WHERE card_number IS NOT NULL AND TRIM(card_number) != '' "
                "ORDER BY created_at DESC"
            ).fetchall()
            for r in rows:
                if vis is not None and r["account_email"] not in vis:
                    continue
                key = (r["card_number"], r["account_email"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "source": "note",
                    "card_pipe": f"{r['card_number']}|{r['card_expiry'] or ''}|{r['card_cvv'] or ''}",
                    "card_number": r["card_number"],
                    "card_expiry": r["card_expiry"],
                    "card_cvv": r["card_cvv"],
                    "account_email": r["account_email"],
                    "account_password": r["account_password"],
                    "registered_by": r["created_by_name"] or r["created_by"],
                    "registered_at": r["created_at"],
                    "last_used_at": None,
                    "total_deposits": 0,
                    "total_approved": 0,
                    "total_rejected": 0,
                    "status": r["note_type"] or "note",
                })
        except sqlite3.OperationalError:
            pass
    return {"rows": out, "total": len(out)}


@app.get("/api/activity")
def activity_feed(
    limit: int = Query(150, le=500),
    operator_id: Optional[int] = None,
    user: dict = Depends(require_session),
):
    """Feed unificado: depósitos + locks activos + prewarms.
    SA ve todo por defecto; user/admin ve solo lo suyo (su bitácora personal).
    SA puede pasar operator_id para filtrar."""
    events: list[dict] = []
    role = user.get("role", "user")
    if role == "superadmin":
        op_filter = operator_id  # SA puede filtrar manualmente
    else:
        # Non-SA: forzado a sus propios eventos (no acepta operator_id ajeno)
        op_filter = int(user.get("telegram_id") or 0)

    with db() as c:
        # Cache email → password para target=combo
        pw_cache: dict[str, str] = {}
        def _combo(email: str) -> str:
            if not email: return ""
            if email not in pw_cache:
                row = c.execute(
                    "SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)
                ).fetchone()
                pw_cache[email] = row["password"] if row else ""
            pw = pw_cache.get(email) or ""
            return f"{email}:{pw}" if pw else email

        # Depósitos
        try:
            sql = (
                "SELECT account_email, amount, status, rejection_reason, "
                "operator_id, duration_ms, created_at FROM deposit_attempts "
            )
            params: list = []
            if op_filter is not None:
                sql += "WHERE operator_id = ? "
                params.append(op_filter)
            sql += "ORDER BY id DESC LIMIT ?"
            params.append(limit)
            for r in c.execute(sql, params).fetchall():
                events.append({
                    "kind": "deposit", "ts": r["created_at"],
                    "who": _resolve_operator(r["operator_id"]),
                    "who_color": _operator_color(r["operator_id"]), "who_id": r["operator_id"],
                    "target": _combo(r["account_email"]),
                    "amount": r["amount"], "status": r["status"],
                    "reason": r["rejection_reason"], "duration_ms": r["duration_ms"],
                })
        except sqlite3.OperationalError:
            pass

        # Locks activos (ACCOUNTS — solo los actualmente bloqueados)
        sql = "SELECT email, locked_by, locked_at FROM accounts WHERE locked_by IS NOT NULL "
        params = []
        if op_filter is not None:
            sql += "AND locked_by = ? "
            params.append(op_filter)
        sql += "ORDER BY locked_at DESC LIMIT ?"
        params.append(limit)
        for r in c.execute(sql, params).fetchall():
            events.append({
                "kind": "lock", "ts": r["locked_at"],
                "who": _resolve_operator(r["locked_by"]),
                "who_color": _operator_color(r["locked_by"]), "who_id": r["locked_by"],
                "target": _combo(r["email"]),
            })

        # Notas (de los usuarios — bitácora visible para uno mismo, SA ve todas)
        try:
            sql = (
                "SELECT id, account_email, note_text, created_by, created_by_name, created_at "
                "FROM account_notes WHERE COALESCE(note_text,'') != '' "
            )
            params = []
            if op_filter is not None:
                sql += "AND created_by = ? "
                params.append(op_filter)
            sql += "ORDER BY id DESC LIMIT ?"
            params.append(limit)
            for r in c.execute(sql, params).fetchall():
                events.append({
                    "kind": "note", "ts": r["created_at"],
                    "who": r["created_by_name"] or _resolve_operator(r["created_by"]),
                    "who_color": _operator_color(r["created_by"]), "who_id": r["created_by"],
                    "target": _combo(r["account_email"]),
                    "text": (r["note_text"] or "")[:160],
                    "id": r["id"],
                })
        except sqlite3.OperationalError:
            pass

        # Prewarms eliminados del feed (2026-07-26): ruido operacional interno.
        # Quedan en process_log para auditoría; no se sirven en el feed.

    events.sort(key=lambda e: str(e.get("ts", "")), reverse=True)
    return {"feed": events[:limit]}


@app.get("/api/deposits")
def list_deposits(
    status: Optional[str] = None,
    operator_id: Optional[int] = None,
    limit: int = Query(100, le=500),
    user: dict = Depends(require_session),
):
    where, params = [], []
    # Non-SA: forzado a sus propios depositos (ignora operator_id ajeno). Frictionless:
    # cada quien ve su bitacora, sin roces ni ruido ajeno.
    if user.get("role") != "superadmin":
        operator_id = int(user.get("telegram_id") or 0)
    if status:
        where.append("status = ?"); params.append(status)
    if operator_id is not None:
        where.append("operator_id = ?"); params.append(operator_id)
    sql = (
        "SELECT id, attempt_id, account_email, card_id, amount, status, "
        "rejection_reason, balance_before, balance_after, duration_ms, "
        "captcha_cost, operator_id, created_at "
        "FROM deposit_attempts"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    try:
        with db() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        return []


@app.get("/api/deposits/stats")
def deposits_stats(_user: dict = Depends(require_session)):
    try:
        with db() as c:
            total = c.execute("SELECT COUNT(*) FROM deposit_attempts").fetchone()[0]
            approved = c.execute(
                "SELECT COUNT(*) FROM deposit_attempts WHERE status='approved'"
            ).fetchone()[0]
            rejected = c.execute(
                "SELECT COUNT(*) FROM deposit_attempts WHERE status='rejected'"
            ).fetchone()[0]
            amount = c.execute(
                "SELECT COALESCE(SUM(amount),0) FROM deposit_attempts WHERE status='approved'"
            ).fetchone()[0]
        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "pending": total - approved - rejected,
            "success_rate": round(approved / total * 100, 1) if total > 0 else 0.0,
            "total_amount_approved": amount,
        }
    except sqlite3.OperationalError:
        return {
            "total": 0, "approved": 0, "rejected": 0, "pending": 0,
            "success_rate": 0.0, "total_amount_approved": 0.0,
        }


# ─── Modo auto-depósito V2 (Task C) ─────────────────────────────────────────
# Plan: docs/superpowers/plans/2026-07-28-modo-auto-deposito-v2.md.
# Imports de auto_deposit/deposits SIEMPRE lazy dentro del body (regla 10 del
# plan — evita el ciclo app → auto_deposit → deposits → app).

def _persist_auto_mission(mission_id, operator_id, card_pipes, amount,
                          target_count, plan):
    """INSERT de la misión auto en `auto_missions` (tabla creada en `_migrate()`,
    Task A). status='pending' — el orquestador la mueve a matching/scheduling/
    completed. Las listas van serializadas a JSON (card_pipes pegados,
    accounts_selected = ids, matches = {account_id, card_pipe, email})."""
    now = datetime.now(timezone.utc).isoformat()
    accounts = plan.get("accounts", [])
    with db(write=True) as c:
        c.execute(
            "INSERT INTO auto_missions ("
            "mission_id, operator_id, card_pipes, amount, target_count, "
            "accounts_selected, matches, status, created_at, updated_at"
            ") VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                mission_id,
                operator_id,
                _json.dumps(card_pipes),
                amount,
                target_count,
                _json.dumps([a.get("id") for a in accounts]),
                _json.dumps([
                    {"account_id": a.get("id"), "card_pipe": a.get("card_pipe"),
                     "email": a.get("email")}
                    for a in accounts
                ]),
                "pending",
                now,
                now,
            ),
        )


@app.get("/api/admin/maintenance-state")
def admin_maintenance_state(user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    return {"enabled": _is_maintenance_active()}


class MaintenanceToggleRequest(BaseModel):
    enabled: bool


@app.post("/api/admin/maintenance")
def admin_maintenance_toggle(req: MaintenanceToggleRequest, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    enabled = req.enabled
    os.environ["BMX_MAINTENANCE"] = "1" if enabled else "0"
    try:
        if enabled:
            _MAINTENANCE_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
            _MAINTENANCE_FLAG_FILE.write_text("1\n", encoding="utf-8")
        else:
            if _MAINTENANCE_FLAG_FILE.exists():
                _MAINTENANCE_FLAG_FILE.unlink()
    except Exception as e:
        print(f"[maintenance] error guardando flag file: {e}")

    _broadcast({
        "type": "activity", "kind": "maintenance_toggle",
        "enabled": enabled,
        "ts": datetime.now(timezone.utc).isoformat(),
        **_resolve_who(user.get("telegram_id")),
    })
    return {"enabled": enabled}


@app.post("/api/deposits/auto")
async def auto_deposit_create(request: Request,
                              user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    # Lazy: caps + semáforo de misiones (necesarios para validación)
    from deposits import DEP_MAX_PER_TXN, DEP_MAX_24H, _mission_sem, _parse_pipe  # noqa: F401
    body = await request.json()
    card_pipes = body.get("card_pipes", [])
    amount = float(body.get("amount", 150))
    target_count = int(body.get("target_count", 9))
    if not card_pipes:
        raise HTTPException(400, "Se requieren tarjetas (card_pipes)")
    if amount < 1 or amount > DEP_MAX_PER_TXN:              # V2: cap por txn
        raise HTTPException(400, f"Monto debe ser $1-${DEP_MAX_PER_TXN:.0f}")
    if target_count < 1 or target_count > 20:               # V2: cota razonable
        raise HTTPException(400, "target_count debe ser 1-20")
    if amount * target_count > DEP_MAX_24H:
        raise HTTPException(400, f"Total ${amount * target_count} excede cap 24h ${DEP_MAX_24H}")
    if _mission_sem.locked():                               # fail-fast, no encolar
        raise HTTPException(429, "Misiones activas — intenta cuando terminen")
    # Lazy: planner + orquestador (run_auto_mission la implementa Task D)
    from auto_deposit import plan_auto_mission, run_auto_mission
    plan = plan_auto_mission(DB_PATH, card_pipes, amount, target_count)
    if not plan["feasible"]:
        raise HTTPException(409, plan["reason"])
    from uuid import uuid4
    mission_id = str(uuid4())[:8]
    operator_id = user.get("telegram_id")                   # V2: modo open no tiene (S8)
    _persist_auto_mission(mission_id, operator_id, card_pipes, amount,
                          target_count, plan)
    asyncio.create_task(run_auto_mission(mission_id, plan, user))
    _broadcast({"type": "activity", "kind": "auto_mission",
                "ts": datetime.now(timezone.utc).isoformat(),
                "mission_id": mission_id, "status": "started",
                "accounts": len(plan["accounts"]), **_resolve_who(operator_id)})
    return {"mission_id": mission_id, "accounts_selected": len(plan["accounts"]),
            "total_estimated": plan["total_estimated"], "status": "matching"}


@app.post("/api/deposits/auto/{mission_id}/cancel")
def auto_deposit_cancel(mission_id: str,
                        user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    with db(write=True) as c:
        row = c.execute(
            "SELECT status FROM auto_missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Misión no encontrada")
        if row["status"] in ("completed", "cancelled", "failed"):
            # Ya terminal — no-op idempotente (el orquestador ya cerró)
            return {"mission_id": mission_id, "status": row["status"],
                    "changed": False}
        # Cancel cooperativo: el orquestador lee este status entre iteraciones
        # y sale limpio (release sem + unlock de cuenta), regla 4 del plan.
        now = datetime.now(timezone.utc).isoformat()
        c.execute(
            "UPDATE auto_missions SET status='cancelled', updated_at=?, "
            "completed_at=? WHERE mission_id=?",
            (now, now, mission_id),
        )
    _broadcast({"type": "activity", "kind": "auto_mission",
                "ts": datetime.now(timezone.utc).isoformat(),
                "mission_id": mission_id, "status": "cancelled",
                **_resolve_who(user.get("telegram_id"))})
    return {"mission_id": mission_id, "status": "cancelled", "changed": True}


@app.get("/api/operator/my-accounts")
def operator_my_accounts(user: dict = Depends(require_operator_view)):
    """Cuentas del operador: en proceso (lockeadas por él) o con depósito aprobado
    Y saldo real > 0 todavía retirable. Depósito fallido o cuenta ya retirada por
    completo desaparecen de su vista/control (regla de producto, Robert 2026-08-05).
    Nota: balance_real se actualiza síncrono en el depósito pero NO en el retiro
    (ver withdrawals.py) — hay lag hasta el próximo ciclo de account_refresh.py
    entre "se retiró todo" y que la cuenta desaparezca de este endpoint."""
    operator_id = user.get("telegram_id") or 0
    is_sa = user.get("role") == "superadmin"
    with db() as c:
        if is_sa:
            rows = c.execute(
                "SELECT DISTINCT a.id, a.email, a.balance_real, a.balance_bonos, "
                "a.last_deposit_amount, a.last_deposit_date, a.grade, "
                "a.locked_by, a.locked_until, a.status, "
                "a.withdrawal_ready, a.withdrawal_institution, a.curp, "
                "c.clabe AS clabe_stp "
                "FROM accounts a "
                "LEFT JOIN deposit_attempts d ON d.account_email = a.email "
                "LEFT JOIN account_deposit_clabes c ON (a.id = c.account_id AND (c.integration = 'STP' OR c.integration = '2')) "
                "WHERE (d.status='approved' OR a.locked_by IS NOT NULL) "
                "ORDER BY a.last_deposit_date DESC"
            ).fetchall()
        else:
            op_str = str(operator_id)
            rows = c.execute(
                "SELECT DISTINCT a.id, a.email, a.balance_real, a.balance_bonos, "
                "a.last_deposit_amount, a.last_deposit_date, a.grade, "
                "a.locked_by, a.locked_until, a.status, "
                "a.withdrawal_ready, a.withdrawal_institution, a.curp, "
                "c.clabe AS clabe_stp "
                "FROM accounts a "
                "LEFT JOIN deposit_attempts d ON d.account_email = a.email "
                "LEFT JOIN account_deposit_clabes c ON (a.id = c.account_id AND (c.integration = 'STP' OR c.integration = '2')) "
                "WHERE ( (d.operator_id=? AND d.status='approved' AND COALESCE(a.balance_real,0) > 0) "
                "OR (a.locked_by=? OR a.locked_by=?) ) "
                "ORDER BY a.last_deposit_date DESC",
                (operator_id, op_str, user.get("username") or "")
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["is_locked"] = bool(d.get("locked_by"))
            d["withdrawal_ready"] = bool(d.get("withdrawal_ready"))
            d.pop("locked_by", None)
            d.pop("locked_until", None)
            result.append(d)
    return {"ok": True, "accounts": result}


@app.post("/api/operator/accounts/{account_id}/release")
def operator_release_account(account_id: int,
                             user: dict = Depends(require_operator_view)):
    """Libera el lock de una cuenta propia (operador) o cualquiera (SA). Sin password."""
    with db() as c:
        acc = c.execute(
            "SELECT email, locked_by FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
    if not acc:
        raise HTTPException(404, "Cuenta no encontrada")
    if user.get("role") != "superadmin":
        vis = _visible_emails(user, c)
        if vis is not None and acc["email"] not in vis:
            raise HTTPException(403, "No tienes permiso sobre esta cuenta")
    prev_locked_by = acc["locked_by"] if acc else None
    with db(write=True) as c:
        _release_account(c, account_id, acc["email"], "release operador",
                         prev_locked_by, kind="unlock", who=user.get("username"))
    return {"ok": True, "account_id": account_id, "released": True}


@app.post("/api/operator/accounts/{account_id}/withdraw")
async def operator_withdraw(account_id: int,
                           payload: dict,
                           user: dict = Depends(require_operator_view)):
    """Retiro sin password — valida ownership, usa JWT en BD."""
    from withdrawals import (
        execute_withdrawal, JwtExpired, InsufficientBalance,
        NoApprovedWithdrawalAccount, MultipleApprovedAccounts,
        ConcurrentWithdrawalPending, _refresh_account_after_withdrawal,
    )
    with db() as c:
        acc = c.execute(
            "SELECT id, email FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
    if not acc:
        raise HTTPException(404, "Cuenta no encontrada")
    if user.get("role") != "superadmin":
        with db() as c:
            vis = _visible_emails(user, c)
        if vis is not None and acc["email"] not in vis:
            raise HTTPException(403, "No tienes permiso sobre esta cuenta")
    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(400, "amount inválido")
    if amount <= 0:
        raise HTTPException(400, "amount debe ser > 0")
    try:
        result = await execute_withdrawal(str(DB_PATH), account_id, amount)
    except JwtExpired:
        raise HTTPException(409, "JWT expirado, requiere refresh")
    except InsufficientBalance as e:
        raise HTTPException(409, str(e))
    except NoApprovedWithdrawalAccount:
        raise HTTPException(409, "Sin cuenta de retiro aprobada: requiere SPEI de depósito primero")
    except MultipleApprovedAccounts as e:
        raise HTTPException(409, str(e))
    except ConcurrentWithdrawalPending:
        raise HTTPException(409, "Ya hay un retiro pendiente en esta cuenta")
    persisted = True
    try:
        _persist_withdrawal(account_id, user.get("telegram_id"), result)
    except sqlite3.OperationalError:
        persisted = False
    # Refresh post-retiro (handoff 2026-08-05 §2.3): el retiro ya se ejecutó en
    # BetMexico — traemos el saldo post-retiro a BD de inmediato reusando el JWT
    # que ya tiene execute_withdrawal (sin gastar captcha). No-throws: un fallo
    # acá no debe afectar el resultado del retiro ya emitido.
    await _refresh_account_after_withdrawal(
        result.get("account_email"), result.get("_jwt"),
        result.get("_proxy_url"), user.get("telegram_id") or 0)
    if persisted:
        _broadcast({
            "type": "activity", "kind": "withdrawal",
            "ts": datetime.now(timezone.utc).isoformat(),
            "target": result.get("account_email"), "id": account_id,
            "amount": amount, "transactionId": result["transactionId"],
            **_resolve_who(user.get("telegram_id")),
        })
    return {**result, "persisted": persisted}


@app.get("/api/operator/missions")
def operator_missions(user: dict = Depends(require_operator_view)):
    """Misiones del operador (o todas si SA)."""
    operator_id = user.get("telegram_id") or 0
    is_sa = user.get("role") == "superadmin"
    with db() as c:
        if is_sa:
            rows = c.execute(
                "SELECT mission_id, status, phase_detail, total_deposited, "
                "total_approved, total_failed, created_at, completed_at, operator_id "
                "FROM auto_missions ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT mission_id, status, phase_detail, total_deposited, "
                "total_approved, total_failed, created_at, completed_at, operator_id "
                "FROM auto_missions WHERE operator_id=? ORDER BY created_at DESC LIMIT 20",
                (operator_id,)
            ).fetchall()
    return {"ok": True, "missions": [dict(r) for r in rows]}


@app.get("/api/deposits/auto/{mission_id}/status")
def auto_deposit_status(mission_id: str,
                        _user: dict = Depends(require_session)):
    with db() as c:
        row = c.execute(
            "SELECT * FROM auto_missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Misión no encontrada")
    d = dict(row)
    for k in ("card_pipes", "accounts_selected", "matches"):
        d[k] = _json.loads(d.get(k) or "[]")
    return d


def register_operator_strike(operator_id: int, reason: str = "bank_rejected"):
    """Registra o incrementa strikes para un operador (1 strike = 3 declines acumulados o 3 spams)."""
    if not operator_id:
        return
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    with db(write=True) as c:
        row = c.execute(
            "SELECT strikes_count, penalty_until, last_attempts FROM operator_penalties WHERE telegram_id=?",
            (operator_id,)
        ).fetchone()
        if not row:
            strikes = 1 if reason == "spam" else 0
            attempts = 1
            pen_until = (now_dt + timedelta(minutes=5)).isoformat() if reason == "spam" else None
            c.execute(
                "INSERT INTO operator_penalties (telegram_id, strikes_count, penalty_until, last_attempts, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (operator_id, strikes, pen_until, str(attempts), now_iso)
            )
        else:
            strikes = row["strikes_count"]
            attempts = (int(row["last_attempts"] or 0)) + 1
            pen_until = row["penalty_until"]
            if reason == "spam":
                strikes += 1
                pen_until = (now_dt + timedelta(minutes=5)).isoformat()
            elif attempts >= 3:
                strikes += 1
                attempts = 0
            c.execute(
                "UPDATE operator_penalties SET strikes_count=?, penalty_until=?, last_attempts=?, updated_at=? WHERE telegram_id=?",
                (strikes, pen_until, str(attempts), now_iso, operator_id)
            )


@app.get("/api/bot/start")
def bot_start_info(user: dict = Depends(require_session)):
    """Menú principal /start adaptado con saludos dinámicos y comandos limitados."""
    import random
    greetings = [
        "Un día más en la trinchera. A darle con fe.",
        "Listos para mover cuentas y mantener la pasarela limpia.",
        "Monitoreo activo. La disciplina le gana al desmadre.",
        "Otra sesión sin aviso previo. Muy tú.",
        "Todo listo para la acción. Vamos por esos matches."
    ]
    greeting = random.choice(greetings)
    tg_id = user.get("telegram_id") or 0
    display_name = user.get("display") or user.get("username") or "Operador"

    msg = (
        f"┏ 🌵🇲🇽 <b>Botmexico.net</b> 🇲🇽🌵━┓\n\n"
        f"Hola, {display_name} 🌮\n"
        f"Telegram ID: <code>{tg_id}</code>\n\n"
        f"<i>\"{greeting}\"</i>\n\n"
        f"📎 <b>Comandos Habilitados:</b>\n"
        f"• <b>/start</b>: Inicia el panel principal.\n"
        f"• <b>/check</b>: Ingresar y alimentar cuentas con chequeo (Mín: 10, Máx texto: 100, Máx archivo: 1000).\n"
        f"• <b>/bet</b>: Iniciar el proceso de matchmaking y depósitos automáticos (1 a 4 tarjetas por intento).\n"
        f"• <b>/info</b>: Ver tus estadísticas personales de depósitos exitosos, BINes efectivos y cuentas alimentadas.\n"
        f"• <b>/help</b>: Guía informativa y consejos operativos sobre el uso responsable de captchas y proxies.\n"
        f"• <b>/cancel</b>: Aborta el proceso o misión activa actual.\n\n"
        f"⚠️ <b>Límites de Carga:</b>\n"
        f"• Mínimo 10 combos por check.\n"
        f"• Máximo 100 combos pegados en texto.\n"
        f"• Máximo 1,000 combos en archivos (.txt/.csv).\n\n"
        f"📊 <b>Estados de Cuentas:</b>\n"
        f"• <b>LIVE ✅</b>: Cuenta activa y verificada, lista para trabajar.\n"
        f"• <b>DEAD ❌</b>: No sirve (login falló o bloqueada por pasarela).\n\n"
        f"🌐 <b>Web Dashboard:</b>\n"
        f"Búsqueda, historial, depósitos y gestión completa desde https://botmexico.net"
    )
    return {"ok": True, "message": msg}


@app.get("/api/bot/info")
def bot_operator_info(user: dict = Depends(require_session)):
    """Estadísticas operativas personalizadas para /info (resumen compacto sin internals)."""
    operator_id = user.get("telegram_id") or 0
    with db() as c:
        # Cuentas con depósitos exitosos del operador
        dep_rows = c.execute(
            "SELECT COUNT(DISTINCT account_email) as count, COALESCE(SUM(amount), 0) as total "
            "FROM deposit_attempts WHERE operator_id=? AND status='approved'",
            (operator_id,)
        ).fetchone()

        # Cuentas alimentadas/checkeadas
        live_count = c.execute("SELECT COUNT(*) as c FROM accounts WHERE status='LIVE'").fetchone()["c"]

        # Penalizaciones/strikes actuales
        pen_row = c.execute(
            "SELECT strikes_count FROM operator_penalties WHERE telegram_id=?", (operator_id,)
        ).fetchone()
        strikes_used = pen_row["strikes_count"] if pen_row else 0

        # Top 3 BINes con mejor tasa de aprobación histórica
        top_bines = c.execute(
            "SELECT bin, approved_count, total_attempts, "
            "(CAST(approved_count AS FLOAT) / MAX(total_attempts, 1)) * 100 as rate "
            "FROM bin_stats WHERE total_attempts >= 3 ORDER BY rate DESC, approved_count DESC LIMIT 3"
        ).fetchall()

    bines_text = ", ".join([f"<code>{b['bin']}</code> ({int(b['rate'])}%)" for b in top_bines]) if top_bines else "Sin data suficiente"

    msg = (
        f"📊 <b>ESTADÍSTICAS DEL OPERADOR</b>\n"
        f"----------------------------------------\n"
        f"👤 <b>Telegram ID:</b> <code>{operator_id}</code>\n"
        f"✅ <b>Cuentas depositadas exitosamente:</b> <b>{dep_rows['count']}</b> (${dep_rows['total']:,.2f} MXN)\n"
        f"⚡ <b>BINes más efectivos:</b> {bines_text}\n"
        f"🌐 <b>Cuentas LIVE disponibles en Pool:</b> <b>{live_count}</b>\n"
        f"🎯 <b>Strikes usados hoy:</b> <b>{strikes_used}/5</b>\n"
        f"----------------------------------------"
    )
    return {"ok": True, "message": msg}


@app.get("/api/bot/help")
def bot_help_info(user: dict = Depends(require_session)):
    """Guía informativa /help orientada al uso operativo responsable."""
    msg = (
        f"💡 <b>GUÍA INFORMATIVA OPERATIVA (/help)</b>\n"
        f"----------------------------------------\n"
        f"<b>1. ¿Qué hace el /check?</b>\n"
        f"Verifica las credenciales de las cuentas contra BetMexico. Cada check consume recursos (resolución de captchas y rotación de proxies de alta calidad).\n\n"
        f"<b>2. Buenas prácticas para cuidar el sistema:</b>\n"
        f"• <b>No espamear:</b> Hacer más de 3 intentos inválidos o en ráfaga rápida provocará una penalización automática de 5 minutos.\n"
        f"• <b>Formatos aceptados:</b> Envía mínimo 10 combos en texto (máx 100) o adjunta un archivo .txt/.csv (máx 1,000).\n"
        f"• <b>Limpieza de Tarjetas:</b> Antes de depositar con /bet, las tarjetas pasan por un liveness check. Si una tarjeta ya está en la BD, se descartará automáticamente para no duplicar intentos.\n\n"
        f"<b>3. Transparencia y Sincronización Web:</b>\n"
        f"Cualquier cuenta verificable (LIVE) cargada mediante el bot se reflejará en tiempo real en el Dashboard Web (https://botmexico.net)."
    )
    return {"ok": True, "message": msg}


@app.post("/api/bot/pause")
def bot_pause_mission(user: dict = Depends(require_session)):
    """Pausa la misión activa del operador y devuelve resumen corto de avance."""
    operator_id = user.get("telegram_id") or 0
    now = datetime.now(timezone.utc).isoformat()
    with db(write=True) as c:
        cur = c.execute(
            "UPDATE auto_missions SET status='paused', updated_at=? "
            "WHERE operator_id=? AND status='running'",
            (now, operator_id)
        )
        row = c.execute(
            "SELECT mission_id, target_count, current_count, approved_count, failed_count "
            "FROM auto_missions WHERE operator_id=? ORDER BY id DESC LIMIT 1",
            (operator_id,)
        ).fetchone()

    stats_msg = ""
    if row:
        stats_msg = (
            f"\n\n📊 <b>Resumen de Avance:</b>\n"
            f"• Misión: <code>{row['mission_id']}</code>\n"
            f"• Aprobados: {row['approved_count'] or 0} / {row['target_count']}\n"
            f"• Rechazos: {row['failed_count'] or 0}"
        )

    _broadcast({
        "type": "activity", "kind": "telegram_bot_pause",
        "ts": now, **_resolve_who(operator_id)
    })
    return {"ok": True, "paused": True, "message": f"⏸ <b>PROCESO PAUSADO</b>{stats_msg}\n\n<i>Usa /resume o presiona Reanudar para continuar.</i>"}


@app.post("/api/bot/resume")
def bot_resume_mission(user: dict = Depends(require_session)):
    """Reanuda la misión pausada del operador."""
    operator_id = user.get("telegram_id") or 0
    now = datetime.now(timezone.utc).isoformat()
    with db(write=True) as c:
        cur = c.execute(
            "UPDATE auto_missions SET status='running', updated_at=? "
            "WHERE operator_id=? AND status='paused'",
            (now, operator_id)
        )
        resumed = cur.rowcount > 0

    _broadcast({
        "type": "activity", "kind": "telegram_bot_resume",
        "ts": now, **_resolve_who(operator_id)
    })
    if resumed:
        return {"ok": True, "resumed": True, "message": "▶ <b>PROCESO REANUDADO</b>. El matchmaking continuará con los depósitos."}
    return {"ok": True, "resumed": False, "message": "ℹ️ No tienes misiones pausadas por reanudar."}


@app.post("/api/bot/stop")
@app.post("/api/bot/cancel")
def bot_cancel_mission(user: dict = Depends(require_session)):
    """Aborta cualquier proceso o misión activa de inmediato y devuelve resumen de avance."""
    operator_id = user.get("telegram_id") or 0
    now = datetime.now(timezone.utc).isoformat()
    cancelled_count = 0
    with db(write=True) as c:
        row = c.execute(
            "SELECT mission_id, target_count, current_count, approved_count, failed_count "
            "FROM auto_missions WHERE operator_id=? AND status IN ('pending', 'running', 'paused') ORDER BY id DESC LIMIT 1",
            (operator_id,)
        ).fetchone()

        cur = c.execute(
            "UPDATE auto_missions SET status='cancelled', updated_at=?, completed_at=? "
            "WHERE operator_id=? AND status IN ('pending', 'running', 'paused')",
            (now, now, operator_id)
        )
        cancelled_count = cur.rowcount

    stats_msg = ""
    if row:
        stats_msg = (
            f"\n\n📊 <b>Resumen Final de Avance:</b>\n"
            f"• Misión: <code>{row['mission_id']}</code>\n"
            f"• Aprobados: {row['approved_count'] or 0} / {row['target_count']}\n"
            f"• Rechazos: {row['failed_count'] or 0}"
        )

    if cancelled_count > 0:
        _broadcast({
            "type": "activity", "kind": "telegram_bot_cancel",
            "ts": now, **_resolve_who(operator_id)
        })
        return {"ok": True, "message": f"🛑 <b>PROCESO DETENIDO DE INMEDIATO</b>{stats_msg}\n\n<i>Gestiona tus cuentas en https://botmexico.net</i>"}
    else:
        return {"ok": True, "message": "ℹ️ No tienes ninguna misión ni proceso de matchmaking activo por detener."}


@app.post("/api/bot/bet")
async def bot_bet_create(request: Request, user: dict = Depends(require_session)):
    """Endpoint para el comando /bet del bot de Telegram.

    Reglas operativas actualizadas:
    - 1 INTENTO = 1 iniciación completa del flujo en automático (no por tarjeta individual).
    - Límite de STRIKES = 5 por día por operador (1 strike = 3 tarjetas con 3 rechazos fallidos acumulados, O 3 intentos de spam/ráfaga).
    - Descarte de Tarjetas Repetidas: Si la tarjeta ya existe en BD (account_cards), se descarta antes de iniciar.
    - Confirmación previa con resumen e información de strikes restantes.
    """
    from card_checker import precheck_card_liveness, format_ruthopia_liveness_summary
    from auto_deposit import plan_auto_mission, run_auto_mission
    from deposits import _mission_sem, DEP_MAX_PER_TXN, DEP_MAX_24H

    body = await request.json()
    card_pipes = body.get("card_pipes", [])
    amount = float(body.get("amount", 150))
    target_count = int(body.get("target_count", 9))
    confirmed = body.get("confirmed", False)
    operator_id = user.get("telegram_id") or body.get("telegram_id") or 0

    if not card_pipes or len(card_pipes) > 4:
        raise HTTPException(400, "Se requieren de 1 a 4 tarjetas por intento (card_pipes)")

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # Guardarraíl 1: Verificación de Strikes (Máximo 5 strikes por día por operador)
    MAX_DAILY_STRIKES = 5
    with db(write=True) as c:
        row = c.execute(
            "SELECT strikes_count, penalty_until, last_attempts FROM operator_penalties WHERE telegram_id=?",
            (operator_id,)
        ).fetchone()
        strikes_count = row["strikes_count"] if row else 0
        penalty_until = row["penalty_until"] if row else None
        if penalty_until:
            try:
                p_dt = datetime.fromisoformat(penalty_until)
                if p_dt > now_dt:
                    secs_left = int((p_dt - now_dt).total_seconds())
                    mins_left = max(1, secs_left // 60)
                    raise HTTPException(
                        429, f"Operador en penalización por spam (1 strike acumulado). Intenta en {mins_left} min."
                    )
            except ValueError:
                pass

        if strikes_count >= MAX_DAILY_STRIKES:
            raise HTTPException(
                403, f"Límite de {MAX_DAILY_STRIKES} strikes diarios alcanzado (3 rechazos fallidos o spam = 1 strike). Solicita reset al SuperAdmin."
            )

    # Guardarraíl 2: Comprobar si las tarjetas YA existen asociadas en BD (account_cards)
    existing_cards = set()
    try:
        with db() as c:
            rows = c.execute("SELECT card_number FROM account_cards").fetchall()
            for r in rows:
                if r["card_number"]:
                    existing_cards.add(str(r["card_number"]).strip())
    except Exception:
        pass

    # Guardarraíl 3: Pre-check de Liveness con descartes por duplicidad + liveness
    valid_pipes = []
    liveness_records = []
    for pipe in card_pipes:
        parts = [p.strip() for p in str(pipe).split("|") if p.strip()]
        card_num = parts[0] if parts else ""
        if card_num and card_num in existing_cards:
            liveness_records.append({
                "pipe": pipe,
                "ok": False,
                "status_label": "🔴 DESCARTADA - Tarjeta ya existe asociada a otra cuenta en la BD"
            })
            continue

        ok, reason, parsed = precheck_card_liveness(pipe)
        liveness_records.append({
            "pipe": pipe,
            "ok": ok,
            "status_label": reason
        })
        if ok:
            valid_pipes.append(parsed["pipe_3parts"])
            bin_code = parsed["bin"]
            try:
                with db(write=True) as c:
                    c.execute(
                        "INSERT INTO bin_stats (bin, total_attempts, updated_at) VALUES (?, 1, ?) "
                        "ON CONFLICT(bin) DO UPDATE SET total_attempts = total_attempts + 1, updated_at = ?",
                        (bin_code, now_iso, now_iso)
                    )
            except Exception:
                pass

    summary_text = format_ruthopia_liveness_summary(liveness_records)
    strikes_left = MAX_DAILY_STRIKES - strikes_count

    if not valid_pipes:
        raise HTTPException(400, f"Ninguna tarjeta superó las validaciones iniciales:\n\n{summary_text}")

    # Si NO ha confirmado, solicita la última confirmación amigable
    if not confirmed:
        confirm_msg = (
            f"<b>⚠️ ÚLTIMA CONFIRMACIÓN REQUERIDA ANTES DE INICIAR</b>\n\n"
            f"• <b>Flujo:</b> 1 intento automático de matchmaking con {len(valid_pipes)} tarjeta(s) válida(s).\n"
            f"• <b>Strikes del Operador:</b> Tienes derecho a {MAX_DAILY_STRIKES} strikes/día. Te quedan <b>{strikes_left}</b> strike(s).\n"
            f"• <b>Regla:</b> Cada 3 rechazos con 3 fallos acumulados = 1 strike. Cada 3 ráfagas de spam = 1 strike.\n\n"
            f"{summary_text}\n\n"
            f"<i>Responde o envía la confirmación con `confirmed: true` para iniciar los depósitos.</i>"
        )
        return {
            "require_confirmation": True,
            "strikes_left": strikes_left,
            "valid_cards_count": len(valid_pipes),
            "liveness_summary": summary_text,
            "message": confirm_msg
        }

    # Guardarraíl 4: Concurrencia (máximo 1 intento a la vez)
    if _mission_sem.locked():
        raise HTTPException(429, "Ya hay un intento de matchmaking activo en el sistema.")

    plan = plan_auto_mission(DB_PATH, valid_pipes, amount, target_count)
    if not plan["feasible"]:
        raise HTTPException(409, plan["reason"])

    from uuid import uuid4
    mission_id = str(uuid4())[:8]
    _persist_auto_mission(mission_id, operator_id, valid_pipes, amount, target_count, plan)
    asyncio.create_task(run_auto_mission(mission_id, plan, user))

    # Log para la pestaña de logs de Telegram Bot
    _broadcast({
        "type": "activity",
        "kind": "telegram_bot_bet",
        "ts": now_iso,
        "mission_id": mission_id,
        "card_count": len(valid_pipes),
        "status": "started",
        "liveness_summary": summary_text,
        "accounts": [a.get("email") for a in plan.get("accounts", [])],
        **_resolve_who(operator_id)
    })

    top_bines = []
    try:
        with db() as c:
            rows = c.execute(
                "SELECT bin, total_approved, total_attempts FROM bin_stats "
                "WHERE total_attempts >= 2 ORDER BY (total_approved * 1.0 / total_attempts) DESC LIMIT 3"
            ).fetchall()
            top_bines = [r["bin"] for r in rows if r["bin"]]
    except Exception:
        pass

    matched_emails = [a.get("email") for a in plan.get("accounts", [])]
    return {
        "ok": True,
        "mission_id": mission_id,
        "accounts_selected": len(matched_emails),
        "matched_emails": matched_emails,
        "total_estimated": plan["total_estimated"],
        "recommended_bines": top_bines,
        "strikes_left": strikes_left,
        "liveness_summary": summary_text,
        "dashboard_link": f"https://botmexico.net/?match={mission_id}",
        "message": f"🚀 Intento automático /bet INICIADO con {len(valid_pipes)} tarjeta(s).\n\n{summary_text}"
    }


def filter_and_sanitize_check_combos(combos: list[str]) -> dict:
    total_received = len(combos)
    seen_combos = set()
    cleaned_combos = []
    dupes_count = 0

    for line in combos:
        raw = str(line).strip()
        if not raw:
            continue
        if raw in seen_combos:
            dupes_count += 1
            continue
        seen_combos.add(raw)
        cleaned_combos.append(raw)

    existing_emails = set()
    existing_cards = set()

    with db() as c:
        rows_m = c.execute("SELECT email FROM accounts WHERE email IS NOT NULL AND email != ''").fetchall()
        for r in rows_m:
            existing_emails.add(str(r["email"]).strip().lower())

        rows_c = c.execute("SELECT card_number FROM account_cards WHERE card_number IS NOT NULL AND card_number != ''").fetchall()
        for r in rows_c:
            existing_cards.add(str(r["card_number"]).strip())

    in_db_emails = []
    in_db_cards = []
    invalid_cards = []
    valid_combos = []

    from card_checker import precheck_card_liveness

    for item in cleaned_combos:
        parts = [p.strip() for p in item.split(":") if p.strip()]
        if not parts:
            continue
        email = parts[0].lower()
        password = parts[1] if len(parts) > 1 else ""

        # Si la línea tiene 4 partes separadas por ':', el card_pipe se reconstruye con ':'
        card_pipe = ""
        if len(parts) >= 6:
            # Format: email:password:card:MM:YY:CVV -> card_pipe = card|MM|YY|CVV
            card_pipe = f"{parts[2]}|{parts[3]}|{parts[4]}|{parts[5]}"
        elif len(parts) > 2:
            card_pipe = ":".join(parts[2:])

        card_num = ""
        if card_pipe:
            c_parts = [cp.strip() for cp in card_pipe.replace(":", "|").split("|") if cp.strip()]
            card_num = c_parts[0] if c_parts else ""

        if email in existing_emails:
            in_db_emails.append(email)
            if card_num and card_num in existing_cards:
                in_db_cards.append(card_num)
            continue

        if card_num and card_num in existing_cards:
            in_db_cards.append(card_num)
            continue

        if card_pipe:
            ok, reason, parsed = precheck_card_liveness(card_pipe)
            if not ok:
                invalid_cards.append({"pipe": card_pipe, "reason": reason})
                continue

        valid_combos.append({
            "raw": item,
            "email": email,
            "password": password,
            "card_pipe": card_pipe
        })

    return {
        "total_received": total_received,
        "dupes_count": dupes_count,
        "in_db_emails": in_db_emails,
        "in_db_cards": in_db_cards,
        "invalid_cards": invalid_cards,
        "valid_combos": valid_combos
    }


class BotCheckRequest(BaseModel):
    operator_id: Union[int, str]
    combos: list[str]
    source_type: Optional[str] = "text"  # "text" o "file"
    confirmed: Optional[bool] = False

@app.post("/api/bot/check")
async def bot_check(req: BotCheckRequest, user: dict = Depends(require_session)):
    op_id = req.operator_id
    SUPERADMIN_ID = 1341812706
    if str(op_id) != str(SUPERADMIN_ID):
        now_dt = datetime.now(timezone.utc)
        MAX_DAILY_STRIKES = 5
        with db(write=True) as c:
            row = c.execute(
                "SELECT strikes_count, penalty_until FROM operator_penalties WHERE telegram_id=?",
                (op_id,)
            ).fetchone()
            strikes_count = row["strikes_count"] if row else 0
            penalty_until = row["penalty_until"] if row else None
            if penalty_until:
                try:
                    p_dt = datetime.fromisoformat(penalty_until)
                    if p_dt > now_dt:
                        secs_left = int((p_dt - now_dt).total_seconds())
                        mins_left = max(1, secs_left // 60)
                        raise HTTPException(
                            429, f"Operador en penalización por spam. Intenta en {mins_left} min."
                        )
                except ValueError:
                    pass

            if strikes_count >= MAX_DAILY_STRIKES:
                raise HTTPException(
                    403, f"Límite de {MAX_DAILY_STRIKES} strikes diarios alcanzado. Solicita reset al SuperAdmin."
                )

    combos = req.combos or []
    stype = (req.source_type or "text").lower()

    if stype == "text" and len(combos) > 100:
        raise HTTPException(400, "El mensaje supera el límite de 100 combos en chat plano. Por favor adjunta un archivo .txt con hasta 5,000 líneas.")

    if len(combos) > 5000:
        raise HTTPException(400, "El archivo excede el límite máximo de 5,000 combos.")

    if not combos:
        raise HTTPException(400, "No se recibieron combos para procesar.")

    filtered = filter_and_sanitize_check_combos(combos)
    valid_list = filtered["valid_combos"]

    if not valid_list:
        summary_msg = (
            f"<b>❌ NINGÚN COMBO SUPERÓ LAS VALIDACIONES</b>\n\n"
            f"• <b>Recibidos:</b> {filtered['total_received']}\n"
            f"• <b>Duplicados:</b> {filtered['dupes_count']}\n"
            f"• <b>Pre-existentes en BD (Correo):</b> {len(filtered['in_db_emails'])}\n"
            f"• <b>Pre-existentes en BD (Tarjeta):</b> {len(filtered['in_db_cards'])}\n"
            f"• <b>Tarjetas Inválidas:</b> {len(filtered['invalid_cards'])}\n\n"
            f"💡 <i>Las cuentas ya registradas se pueden consultar y gestionar en https://botmexico.net</i>"
        )
        raise HTTPException(400, summary_msg)

    if not req.confirmed:
        confirm_msg = (
            f"<b>⚠️ CONFIRMACIÓN DE CHECK SOLICITADA</b>\n\n"
            f"• <b>Combos Recibidos:</b> {filtered['total_received']}\n"
            f"• <b>Descartados (Duplicados):</b> {filtered['dupes_count']}\n"
            f"• <b>Descartados (Ya existen en BD):</b> {len(filtered['in_db_emails']) + len(filtered['in_db_cards'])}\n"
            f"• <b>Tarjetas Inválidas / Luhn:</b> {len(filtered['invalid_cards'])}\n"
            f"• <b>Combos Válidos a Verificar:</b> {len(valid_list)}\n\n"
            f"💡 <i>Las cuentas omitidas por ya existir en BD se gestionan directamente en https://botmexico.net</i>\n\n"
            f"<i>Responde o envía la confirmación con `confirmed: true` para iniciar la verificación.</i>"
        )
        return {
            "require_confirmation": True,
            "total_received": filtered["total_received"],
            "valid_count": len(valid_list),
            "message": confirm_msg,
            "dashboard_link": "https://botmexico.net"
        }

    return {
        "ok": True,
        "valid_count": len(valid_list),
        "message": f"🚀 Verificación /check INICIADA para {len(valid_list)} combo(s) nuevos.\n\nDashboard: https://botmexico.net",
        "dashboard_link": "https://botmexico.net"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BMX_WEB_PORT", "5001"))
    print(f"BD: {DB_PATH} (existe: {DB_PATH.exists()})")
    uvicorn.run(app, host="0.0.0.0", port=port)
