"""jwt_keeper.py — mantiene vivos los JWT de sesión de BetMexico.

PROBLEMA (medido 2026-07-11): el JWT de BetMexico con `extendedSession=True` dura
7 días FIJOS. No se renueva con uso — solo un login nuevo emite uno fresco. En prod
había 648/740 JWT expirados (88%): cada toque de una cuenta sin JWT vigente forzaba
un login, y el login es lo que dispara el 429 (rate-limit POR CUENTA, cooldown 45min,
ver `deposits._set_account_cooldown`). Resultado: ~49% de los intentos morían en
`rate_limited`.

SOLUCIÓN: re-loguear de forma PROACTIVA y ESPACIADA solo las cuentas cuyo JWT está
por expirar (o ya expiró), priorizando las de mejor grado, para mantener un pool de
JWT vivos y reutilizables (cache-hit sin captcha en `gentle_login(use_cache=True)`).
En régimen estacionario ~700 cuentas / 168h ≈ 4-5 logins/hora bastan; el catch-up del
backlog se hace con un lote pequeño por ciclo, nunca en ráfaga.

NO es prewarm: prewarm usa `use_cache=True` (en cache-hit NO re-loguea → no extiende
la vida). El keeper fuerza `use_cache=False` para obtener un JWT FRESCO de 7 días.

Se engancha como bg-loop de uvicorn (`app._jwt_keepalive_loop`), mismo patrón que
`_release_watchdog_loop`. Config por env (`JWT_KEEPER_*`).
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("betmexico.dashboard.jwt_keeper")

# ── Config (env, con defaults sanos) ─────────────────────────────────────────
DEFAULT_GRADES: Set[str] = {"A+", "A", "B"}  # C/D quemadas: no vale gastar captcha
_GRADE_RANK = {"A+": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def cfg() -> Dict[str, Any]:
    grades_raw = os.environ.get("JWT_KEEPER_GRADES", "A+,A,B")
    grades = {g.strip() for g in grades_raw.split(",") if g.strip()}
    return {
        "enabled": os.environ.get("JWT_KEEPER_ENABLED", "1") == "1",
        "interval_sec": _env_int("JWT_KEEPER_INTERVAL_SEC", 3600),      # 1h
        "batch_max": _env_int("JWT_KEEPER_BATCH", 20),                  # cuentas/ciclo (12→20: drenar backlog de JWT expirados; seguro con el semáforo GLOBAL de login + gap secuencial; las quemadas caen en cooldown y se auto-apartan el próximo ciclo)
        "refresh_ahead_sec": _env_int("JWT_KEEPER_REFRESH_AHEAD_H", 24) * 3600,
        "gap_min": _env_int("JWT_KEEPER_GAP_MIN_SEC", 20),
        "gap_max": _env_int("JWT_KEEPER_GAP_MAX_SEC", 45),
        "grades": grades or DEFAULT_GRADES,
    }


# ── Lógica pura de selección (testeable sin BD ni deps del bot) ───────────────
def select_refresh_candidates(
    rows: List[Dict[str, Any]],
    now: int,
    *,
    batch_max: int,
    refresh_ahead_sec: int,
    grades: Set[str],
) -> List[Dict[str, Any]]:
    """Filtra + ordena + limita las cuentas a re-loguear este ciclo.

    Regla: viva, útil (grade en `grades`, publicada), NO en cooldown, NO lockeada
    por un operador, y con JWT que ya expiró / expira dentro de `refresh_ahead_sec`
    (las que aún tienen margen se dejan — su JWT sigue sirviendo).

    Orden: mejor grado primero; dentro del grado, la más urgente (menor `exp`, con
    expiradas/nulas —exp=0— al frente). Corta en `batch_max` para no hacer ráfaga.
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
        cd = r.get("cooldown_until")
        if cd not in (None, "") and int(cd) > now:
            continue
        exp = _exp_int(r.get("jwt_expires_at"))
        if exp > now + refresh_ahead_sec:
            continue  # todavía tiene margen → no re-loguear
        out.append(r)

    out.sort(key=lambda r: (
        _GRADE_RANK.get(r.get("grade") or "", 9),
        _exp_int(r.get("jwt_expires_at")),
    ))
    return out[:batch_max]


def _exp_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ── I/O de BD (aislado; usa el context manager de app) ────────────────────────
_SELECT_COLS = ("email", "password", "status", "grade", "jwt_expires_at",
                "cooldown_until", "locked_by", "published_to_pool")


def _load_candidate_rows() -> List[Dict[str, Any]]:
    """Trae de la BD el universo grueso (LIVE + publicadas) para que la lógica pura
    afine. Filtra en SQL lo barato; el resto lo decide `select_refresh_candidates`."""
    import app  # lazy: evita ciclo de import
    with app.db() as conn:
        cur = conn.execute(
            f"SELECT {', '.join(_SELECT_COLS)} FROM accounts "
            "WHERE status='LIVE' AND published_to_pool=1"
        )
        return [dict(row) for row in cur.fetchall()]


def _set_cooldown(email: str) -> None:
    """Reusa la MISMA lógica de cooldown de los flujos de depósito (deposits.py)."""
    try:
        from deposits import _set_account_cooldown
        _set_account_cooldown(email)
    except Exception as e:  # pragma: no cover
        logger.warning(f"[jwt_keeper] no pude setear cooldown a {email}: {e}")


# ── Ciclo (async) ─────────────────────────────────────────────────────────────
async def run_keepalive_cycle(
    *,
    batch_max: int,
    refresh_ahead_sec: int,
    grades: Set[str],
    gap_min: int,
    gap_max: int,
) -> Dict[str, Any]:
    """Un ciclo: selecciona el lote y re-loguea cada cuenta espaciada (JWT fresco).

    Un solo pool de captcha para todo el lote (evita el drenaje de token-por-cuenta
    documentado en ERRORS.md). `use_cache=False` fuerza login real → JWT de 7 días
    nuevo. `allow_proxyless=False` (regla dura Robert: prod NUNCA proxyless).
    """
    now = int(time.time())
    rows = await asyncio.to_thread(_load_candidate_rows)
    cands = select_refresh_candidates(
        rows, now, batch_max=batch_max,
        refresh_ahead_sec=refresh_ahead_sec, grades=grades)
    stats: Dict[str, Any] = {
        "universe": len(rows), "selected": len(cands),
        "live": 0, "rate_limited": 0, "retry": 0, "dead": 0, "error": 0,
    }
    if not cands:
        logger.info(f"[jwt_keeper] nada que refrescar (universo={len(rows)})")
        return stats

    cap_key = os.environ.get("CAPMONSTER_KEY", "")
    try:
        from betmexico_login_service import make_pool
        from login_orchestrator import gentle_login
    except Exception as e:
        logger.error(f"[jwt_keeper] deps del bot no disponibles: {e}")
        stats["error"] = len(cands)
        return stats

    pool = make_pool(cap_key, size=2, workers=1)
    await pool.prefetch(1)
    await pool.start_factory()
    try:
        for i, r in enumerate(cands):
            if i > 0:
                await asyncio.sleep(random.uniform(gap_min, gap_max))
            email, pw = r["email"], r.get("password") or ""
            if not pw:
                stats["error"] += 1
                logger.warning(f"[jwt_keeper] {email} sin password en BD — skip")
                continue
            try:
                res = await gentle_login(
                    email, pw, max_login_retries=3, throttle=True,
                    pool=pool, use_cache=False, allow_proxyless=False)
            except Exception as e:
                stats["error"] += 1
                logger.warning(f"[jwt_keeper] {email} excepción: {str(e)[:120]}")
                continue

            if res.ok:
                stats["live"] += 1
                logger.info(f"[jwt_keeper] {email} JWT fresco ✓ (grade {r.get('grade')})")
            elif res.code == "RATE_LIMITED":
                stats["rate_limited"] += 1
                await asyncio.to_thread(_set_cooldown, email)
                logger.info(f"[jwt_keeper] {email} rate-limited → cooldown 45min")
            elif res.account_dead:
                stats["dead"] += 1
                # Cuarentena (forense 2026-07-11): persistir DEAD, no solo contar.
                # Antes se dejaba LIVE → volvía a caer en el lote cada ciclo,
                # gastando captcha en una cuenta terminal. Reusa el helper de prewarm.
                try:
                    from prewarm import _db_mark_dead
                    await asyncio.to_thread(_db_mark_dead, email, res.code or "LOGIN_DENIED")
                except Exception as e:  # pragma: no cover
                    logger.warning(f"[jwt_keeper] no pude marcar DEAD {email}: {e}")
                logger.info(f"[jwt_keeper] {email} muerta ({res.code}) → cuarentena DEAD")
            else:
                stats["retry"] += 1  # LOGIN_RETRY_LATER → próximo ciclo
    finally:
        try:
            await pool.stop()
        except Exception:
            pass

    logger.info(f"[jwt_keeper] ciclo listo: {stats}")
    return stats


async def run_keepalive_cycle_from_env() -> Dict[str, Any]:
    c = cfg()
    return await run_keepalive_cycle(
        batch_max=c["batch_max"], refresh_ahead_sec=c["refresh_ahead_sec"],
        grades=c["grades"], gap_min=c["gap_min"], gap_max=c["gap_max"])
