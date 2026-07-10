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
        # A+ es un override manual (3DS detectado por el matchmaker, no lo calcula
        # el analyzer V10) — un recalc de rutina (login/check/depósito/prewarm) NUNCA
        # lo pisa. La ÚNICA vía de salida de A+ es `note_a_plus_outcome` (abajo): 2
        # rechazos REALES de banco consecutivos → B. Por eso el UPDATE excluye A+.
        conn.execute(
            "UPDATE accounts SET grade=?, grade_score=? "
            "WHERE LOWER(email)=LOWER(?) AND COALESCE(grade,'') != 'A+'",
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
        # Ver nota en recalc_grade_from_db: un recalc de rutina no pisa A+; solo
        # note_a_plus_outcome (2 declines de banco consecutivas) lo baja a B.
        conn.execute(
            "UPDATE accounts SET grade=?, grade_score=? "
            "WHERE LOWER(email)=LOWER(?) AND COALESCE(grade,'') != 'A+'",
            (sc["grade"], sc["score"], email),
        )
        conn.commit()
        conn.close()
        return sc
    except Exception as e:
        logger.warning(f"[grading] recalc_from_details failed para {email}: {e}")
        return None


def note_a_plus_outcome(email: str, status: str, db_path: str = "/data/betmexico_accounts.db") -> None:
    """
    Ciclo de vida del grade A+ (override 3DS). Regla de Robert (2026-07-09):
      - 3DS marca A+ (lo hace el matchmaker/scheduled en `deposits.py`, no aquí).
      - 2 rechazos REALES de banco CONSECUTIVOS (sin un aprobado en medio) tras el
        A+ → la cuenta baja a B. Un aprobado resetea el contador (la pasarela
        sigue jugando, se le perdona el decline aislado).
      - `status` no-banco (rate_limited/login_lost/gateway_error/timeout/threeds/
        ambiguous/incomplete) NO cuenta como decline ni resetea — es ruido ajeno a
        la tarjeta (misma ley que `classify_deposit_status`: solo "rejected" = banco).

    Llamar en `_record_attempt` DESPUÉS de `recalc_grade_from_db` (que salta A+),
    para que el eventual set a 'B' sea la última palabra del flujo. Si la cuenta no
    está en A+, es no-op. Tras bajar a B, la cuenta vuelve a reglas V10 normales en
    su siguiente actividad (ya no está protegida).

    `status` es el que produce `deposits.classify_deposit_status` (approved /
    rejected / threeds / rate_limited / ...).
    """
    if status not in ("approved", "rejected"):
        return  # no-banco / 3DS → ni incrementa ni resetea el streak
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT COALESCE(grade,'') AS grade, COALESCE(a_plus_decline_streak,0) AS streak "
            "FROM accounts WHERE LOWER(email)=LOWER(?)",
            (email,),
        ).fetchone()
        if not row or row["grade"] != "A+":
            conn.close()
            return
        if status == "approved":
            conn.execute(
                "UPDATE accounts SET a_plus_decline_streak=0 WHERE LOWER(email)=LOWER(?)",
                (email,),
            )
        else:  # "rejected" = rechazo real de banco
            new_streak = int(row["streak"]) + 1
            if new_streak >= 2:
                b_score = _ANALYZER.SCORE_FLOOR.get("B", 60) if _ANALYZER else 60
                conn.execute(
                    "UPDATE accounts SET grade='B', grade_score=?, a_plus_decline_streak=0 "
                    "WHERE LOWER(email)=LOWER(?)",
                    (b_score, email),
                )
                logger.info(f"[grading] {email}: A+ → B (2 rechazos de banco consecutivos)")
            else:
                conn.execute(
                    "UPDATE accounts SET a_plus_decline_streak=? WHERE LOWER(email)=LOWER(?)",
                    (new_streak, email),
                )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[grading] note_a_plus_outcome failed para {email}: {e}")
