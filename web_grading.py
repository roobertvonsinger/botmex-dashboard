"""
Helpers para mantener `accounts.grade` y `accounts.grade_score` SIEMPRE en sync
con `account_transactions`. Cada vez que el dashboard guarda txns nuevas
(login, check, depósito, watchdog), debe llamar `recalc_grade_from_db(email)`.

El analyzer canónico vive en `shared/betmexico_payment_analyzer.py` (V10).
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("betmexico.web.grading")

# ── Importar analyzer canónico (V10) ─────────────────────────────
_HERE = Path(__file__).resolve().parent
_ANALYZER_CANDIDATES = [
    _HERE / "shared" / "betmexico_payment_analyzer.py",     # dev local
    Path("/app/web/shared/betmexico_payment_analyzer.py"),  # KVM4 (si se monta)
    Path("/app/betmexico_payment_analyzer.py"),             # KVM4 (deploy directo en root del bot)
]


def _load_analyzer():
    for p in _ANALYZER_CANDIDATES:
        if p.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("analyzer_v10", str(p))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError(f"No encuentro betmexico_payment_analyzer.py en {_ANALYZER_CANDIDATES}")


try:
    _ANALYZER = _load_analyzer()
    score_payment_readiness = _ANALYZER.score_payment_readiness
except Exception as e:
    logger.error(f"[grading] No pude cargar analyzer: {e}")
    _ANALYZER = None
    score_payment_readiness = None


def recalc_grade_from_db(email: str, db_path: str = "/data/betmexico_accounts.db") -> Optional[dict]:
    """
    Lee las transacciones actuales de la cuenta en BD y recalcula su grade.
    Actualiza accounts.grade y accounts.grade_score in-place.
    Devuelve el resultado del analyzer (o None si no se pudo calcular).

    Llamar DESPUÉS de save_account_transactions / upsert_account / cualquier
    operación que pueda haber agregado/modificado transacciones de la cuenta.
    """
    if not score_payment_readiness:
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT txn_date, status, txn_type, gateway, amount "
            "FROM account_transactions WHERE LOWER(account_email)=LOWER(?) "
            "ORDER BY txn_date DESC",
            (email,),
        ).fetchall()
        if not rows:
            conn.close()
            return None
        details = {"transactions": {
            "fetched": True,
            "items": [dict(r) for r in rows],
            "total_rows": len(rows),
        }}
        sc = score_payment_readiness(details)
        if not sc:
            conn.close()
            return None
        conn.execute(
            "UPDATE accounts SET grade=?, grade_score=? WHERE LOWER(email)=LOWER(?)",
            (sc["grade"], sc["score"], email),
        )
        conn.commit()
        conn.close()
        return sc
    except Exception as e:
        logger.warning(f"[grading] recalc failed para {email}: {e}")
        return None


def recalc_grade_from_details(email: str, details: dict, db_path: str = "/data/betmexico_accounts.db") -> Optional[dict]:
    """
    Recalcula grade usando un payload de account_details ya en mano (evita query a BD).
    Persiste el grade en accounts.
    Útil después de un login fresh donde ya tenemos las txns en memoria.
    """
    if not score_payment_readiness:
        return None
    try:
        sc = score_payment_readiness(details)
        if not sc:
            return None
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE accounts SET grade=?, grade_score=? WHERE LOWER(email)=LOWER(?)",
            (sc["grade"], sc["score"], email),
        )
        conn.commit()
        conn.close()
        return sc
    except Exception as e:
        logger.warning(f"[grading] recalc_from_details failed para {email}: {e}")
        return None
