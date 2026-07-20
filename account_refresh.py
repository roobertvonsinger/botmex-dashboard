"""account_refresh.py — refresca balance/movimientos de cuentas con JWT VIGENTE.

PROBLEMA: fuera de login manual, post-depósito y jwt_keeper (que solo toca
cuentas por expirar), el balance en BD puede quedar horas desactualizado sin
que nadie lo note — La Pantalla muestra lo último que quedó en BD.

SOLUCIÓN: ciclo periódico que toma las cuentas cuyo JWT SIGUE vigente ahora
(lo opuesto a jwt_keeper, que ataca las por expirar) y les hace un fetch de
detalles REUSANDO ese JWT — sin login, sin captcha, sin tocar el semáforo
`_LOGIN_SEM` de login_orchestrator. Mismo patrón ya probado en prod por
`deposits._refresh_account_after_deposit`.

Medido en prod 2026-07-19 (KVM4, betmexico-web): 935 cuentas / 821 LIVE / 55
publicadas al pool / solo 18 con JWT vigente en ese momento — universo chico,
cabe entero en un batch por ciclo. Default 1 refresh/cuenta/hora (confirmado
con Robert).

Se engancha como bg-loop de uvicorn (`app._account_refresh_loop`), mismo
patrón que `jwt_keeper`. Config por env (`ACCOUNT_REFRESH_*`).
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("betmexico.dashboard.account_refresh")

DEFAULT_GRADES: Set[str] = {"A+", "A", "B"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def cfg() -> Dict[str, Any]:
    grades_raw = os.environ.get("ACCOUNT_REFRESH_GRADES", "A+,A,B")
    grades = {g.strip() for g in grades_raw.split(",") if g.strip()}
    return {
        "enabled": os.environ.get("ACCOUNT_REFRESH_ENABLED", "1") == "1",
        "interval_sec": _env_int("ACCOUNT_REFRESH_INTERVAL_SEC", 3600),  # 1h
        "batch_max": _env_int("ACCOUNT_REFRESH_BATCH", 40),  # headroom sobre las ~18 medidas
        "gap_min": _env_int("ACCOUNT_REFRESH_GAP_MIN_SEC", 8),
        "gap_max": _env_int("ACCOUNT_REFRESH_GAP_MAX_SEC", 20),
        "grades": grades or DEFAULT_GRADES,
    }


# ── Lógica pura de selección (testeable sin BD ni deps del bot) ───────────────
def select_refresh_candidates_healthy(
    rows: List[Dict[str, Any]],
    now: int,
    *,
    batch_max: int,
    grades: Set[str],
) -> List[Dict[str, Any]]:
    """Filtra + ordena + limita las cuentas a refrescar este ciclo.

    Regla: viva, útil (grade en `grades`, publicada), NO lockeada por un
    operador, y con JWT que SIGUE vigente ahora (lo opuesto a jwt_keeper:
    esas cuentas se consultan sin login; las por expirar las re-loguea el
    keeper). Orden: `last_checked_at` ascendente (la más desactualizada
    primero) — evita re-tocar una cuenta que un depósito acaba de refrescar.
    """
    out: List[Dict[str, Any]] = []
    for r in rows:
        if (r.get("status") or "") != "LIVE":
            continue
        grade = r.get("grade") or ""
        if grade not in grades:
            continue
        if not r.get("published_to_pool"):
            continue
        if r.get("locked_by") is not None:
            continue
        exp = _exp_int(r.get("jwt_expires_at"))
        if exp <= now:
            continue  # sin JWT vigente → no es candidata (la toca jwt_keeper)
        out.append(r)

    out.sort(key=lambda r: (r.get("last_checked_at") or ""))
    return out[:batch_max]


def _exp_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ── I/O de BD (aislado; usa el context manager de app) ────────────────────────
_SELECT_COLS = ("email", "status", "grade", "jwt_expires_at",
                "locked_by", "published_to_pool", "last_checked_at")


def _load_candidate_rows() -> List[Dict[str, Any]]:
    """Trae de la BD el universo grueso (LIVE + publicadas) para que la lógica
    pura afine. Filtra en SQL lo barato; el resto lo decide
    `select_refresh_candidates_healthy`."""
    import app  # lazy: evita ciclo de import
    with app.db() as conn:
        cur = conn.execute(
            f"SELECT {', '.join(_SELECT_COLS)} FROM accounts "
            "WHERE status='LIVE' AND published_to_pool=1"
        )
        return [dict(row) for row in cur.fetchall()]


# ── Ciclo (async) ─────────────────────────────────────────────────────────────
async def run_refresh_cycle(
    *,
    batch_max: int,
    grades: Set[str],
    gap_min: int,
    gap_max: int,
) -> Dict[str, Any]:
    """Un ciclo: selecciona el lote y refresca cada cuenta espaciada, REUSANDO
    su JWT vigente (sin captcha, sin login, sin tocar _LOGIN_SEM)."""
    now = int(time.time())
    rows = await asyncio.to_thread(_load_candidate_rows)
    cands = select_refresh_candidates_healthy(
        rows, now, batch_max=batch_max, grades=grades)
    stats: Dict[str, Any] = {
        "universe": len(rows), "selected": len(cands),
        "refreshed": 0, "skipped_no_jwt": 0, "skipped_no_proxy": 0, "failed": 0,
    }
    if not cands:
        logger.info(f"[account_refresh] nada que refrescar (universo={len(rows)})")
        return stats

    try:
        from betmexico_login_api import BetmexicoApiChecker
        from betmexico_db import db as _db
        from prewarm import _db_upsert_balance, _db_save_txns_and_recalc
        from proxy_pool import build_admin_proxy_url
    except Exception as e:
        logger.error(f"[account_refresh] deps del bot no disponibles: {e}")
        stats["failed"] = len(cands)
        return stats

    for i, r in enumerate(cands):
        if i > 0:
            await asyncio.sleep(random.uniform(gap_min, gap_max))
        email = r["email"]

        try:
            cached = await asyncio.to_thread(_db.get_jwt_cache, email)
        except Exception as e:
            logger.warning(f"[account_refresh] {email} cache lookup err: {e}")
            cached = None
        if not cached or not cached.get("token") or cached.get("expires_at", 0) <= time.time() + 60:
            stats["skipped_no_jwt"] += 1
            continue
        jwt = cached["token"]

        proxy_url = build_admin_proxy_url()
        if not proxy_url:
            # REGLA DURA (Robert): NUNCA proxyless en prod.
            stats["skipped_no_proxy"] += 1
            logger.warning(f"[account_refresh] {email} sin proxy disponible — skip")
            continue

        try:
            async with BetmexicoApiChecker(proxy=proxy_url) as checker:
                details = await asyncio.wait_for(
                    checker.fetch_account_details_parallel(jwt, fetch_mode="full"),
                    timeout=15.0,
                )
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"[account_refresh] {email} fetch falló: {str(e)[:160]}")
            continue

        if not details:
            # Posible 401/JWT muerto server-side pese a exp local vigente.
            # NO marcar dead, NO tocar jwt_expires_at — lo captura jwt_keeper
            # cuando expire localmente. Solo se cuenta como fallo del ciclo.
            stats["failed"] += 1
            logger.info(f"[account_refresh] {email} fetch vacío (posible JWT muerto server-side)")
            continue

        try:
            await asyncio.to_thread(_db_upsert_balance, email, details)
            await asyncio.to_thread(_db_save_txns_and_recalc, email, details, None)
            stats["refreshed"] += 1
            logger.info(f"[account_refresh] {email} balance fresco "
                        f"(balance_real={details.get('balance_real')})")
            try:
                from app import _broadcast, _resolve_who
                _broadcast({
                    "type": "activity", "kind": "account_refreshed",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "email": email, "target": email,
                    "balance_real": details.get("balance_real"),
                    "balance_total": (float(details.get("balance_real", 0) or 0)
                                      + float(details.get("balance_bonos", 0) or 0)),
                    **_resolve_who(None),
                })
            except Exception:
                pass
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"[account_refresh] {email} persist falló: {str(e)[:160]}")

    logger.info(f"[account_refresh] ciclo listo: {stats}")
    return stats


async def run_refresh_cycle_from_env() -> Dict[str, Any]:
    c = cfg()
    return await run_refresh_cycle(
        batch_max=c["batch_max"], grades=c["grades"],
        gap_min=c["gap_min"], gap_max=c["gap_max"])
