#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_registry.py — Registro Unificado de Conexiones SQLite con Retry y WAL
=======================================================================
Desacopla el acceso a SQLite de app.py para eliminar importaciones circulares
entre app.py, deposits.py y auto_deposit.py.
"""

import os
import time
import sqlite3
import logging
import threading
import traceback
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

ROOT = Path(__file__).resolve().parent

# Cargar .env si existe para BETMEX_DB
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _s = _line.strip()
        if not _s or _s.startswith("#") or "=" not in _s:
            continue
        _k, _v = _s.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# Ruta canónica a la base de datos de cuentas
_default_db = ROOT.parent / "betmexico_accounts.db" if (ROOT.parent / "betmexico_accounts.db").exists() else ROOT / "betmexico_accounts.db"
DB_PATH = Path(os.environ.get("BETMEX_DB", str(_default_db)))

_db_write_registry: dict = {}
_db_write_registry_lock = threading.Lock()
_db_write_counter = 0


@contextmanager
def db(write: bool = False, db_path: Optional[str] = None):
    """Context manager para conexiones SQLite con WAL, busy timeout y tracking."""
    global _db_write_counter
    db_file = db_path or os.environ.get("BETMEX_DB", str(DB_PATH))
    conn = sqlite3.connect(str(db_file), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    entry_id = None
    stack = None
    t0 = time.time()
    if write:
        with _db_write_registry_lock:
            _db_write_counter += 1
            entry_id = _db_write_counter
            stack = "".join(traceback.format_stack()[:-1])
            _db_write_registry[entry_id] = (t0, stack)
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
                _dblg = logging.getLogger("betmexico.dashboard.db")
                if others:
                    held = "\n---\n".join(
                        f"[write#{k} abierto hace {time.time() - t:.1f}s, origen:]\n{s}"
                        for k, (t, s) in others.items()
                    )
                    _dblg.error(f"[db] LOCK — {len(others)} write(s) activos simultáneos AHORA:\n{held}")
                else:
                    _dblg.warning(
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
                logging.getLogger("betmexico.dashboard.db").warning(
                    f"[db] write#{entry_id} tardó {dt:.1f}s sosteniendo el writer global de SQLite — origen:\n{stack}"
                )
        conn.close()


def _db_write_with_retry(fn, *, attempts: int = 3, base_delay: float = 0.2):
    """Ejecuta `fn(conn)` dentro de `db(write=True)` con retry ante `database is locked`."""
    _lg = logging.getLogger("betmexico.dashboard.db")
    last = None
    for attempt in range(1, attempts + 1):
        try:
            with db(write=True) as c:
                return fn(c)
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e) or attempt == attempts:
                raise
            delay = base_delay * attempt
            _lg.warning(
                f"[db] write retry {attempt}/{attempts} chocó con lock, "
                f"reintentando en {delay:.1f}s"
            )
            time.sleep(delay)
    raise last
