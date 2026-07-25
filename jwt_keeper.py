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
        "batch_max": _env_int("JWT_KEEPER_BATCH", 8),                   # cuentas/ciclo. 12→20→8 (2026-07-11): subirlo a 20 para "drenar backlog" fue error — el backlog resultó ~90% QUEMADO (medido: selected:20/rate_limited:18), así que batch alto solo gasta más captcha en cuentas que dan rate_limited. Con el cooldown de 6h apartando las quemadas, un batch chico toca suave, aparta las quemadas y refresca las pocas sanas sin desperdicio. Sube de nuevo cuando el universo enfríe.
        "refresh_ahead_sec": _env_int("JWT_KEEPER_REFRESH_AHEAD_H", 24) * 3600,
        "gap_min": _env_int("JWT_KEEPER_GAP_MIN_SEC", 20),
        "gap_max": _env_int("JWT_KEEPER_GAP_MAX_SEC", 45),
        # Cooldown que el keeper aplica a una cuenta que le da RATE_LIMITED. DEBE
        # ser >> interval (1h): si fuera 45min (< 1h) la cuenta quemada volvería a
        # ser elegible justo cuando el keeper corre de nuevo → BUCLE DE QUEMA
        # (medido 2026-07-11: 12 selected / 12 rate_limited cada ciclo). El keeper
        # NO tiene urgencia (el JWT ya expiró, no hay sesión que salvar), así que
        # una cuenta quemada descansa VARIOS ciclos. Efecto: el keeper se auto-regula
        # — aparta las quemadas y deja de tocarlas hasta que enfríen de verdad. 6h = 6 ciclos.
        "rl_cooldown_min": _env_int("JWT_KEEPER_RL_COOLDOWN_MIN", 360),
        # Racha de RATE_LIMITED consecutivos (forense 2026-07-11 tarde, ver rl_streak
        # en app._migrate): a partir de este umbral, la cuenta deja de ser "enfriando"
        # (transitorio) y pasa a "quemada permanente" (cuarentena larga). Medido en
        # prod: cuentas con 429 en TODOS sus intentos durante 22h+ pese al cooldown de
        # 6h — no es cuestión de esperar más, es que BetMexico las tiene bloqueadas.
        "rl_streak_quarantine_at": _env_int("JWT_KEEPER_RL_STREAK_QUARANTINE_AT", 3),
        "rl_quarantine_min": _env_int("JWT_KEEPER_RL_QUARANTINE_MIN", 2880),  # 48h
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
    sa_tokens: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Filtra + ordena + limita las cuentas a re-loguear este ciclo.

    Regla: viva, útil (grade en `grades`, publicada), NO en cooldown, NO lockeada
    por un operador, y con JWT que ya expiró / expira dentro de `refresh_ahead_sec`
    (las que aún tienen margen se dejan — su JWT sigue sirviendo).

    Excepción: las RESERVADA_SA (`published_to_pool=0 + locked_by` del SA) SÍ son
    candidatas — el SA las usa y necesita su JWT vivo para que el refresh reciba
    datos reales y no default. `sa_tokens` lista los valores que identifican al
    SA en `locked_by` (ver `account_refresh._sa_lock_tokens`).

    Orden: mejor grado primero; dentro del grado, la más urgente (menor `exp`, con
    expiradas/nulas —exp=0— al frente). Corta en `batch_max` para no hacer ráfaga.
    """
    sa_tokens = set(sa_tokens or [])
    out: List[Dict[str, Any]] = []
    for r in rows:
        if (r.get("status") or "") != "LIVE":
            continue
        grade = r.get("grade") or ""
        if grade not in grades:
            continue
        locked_by = r.get("locked_by")
        # RESERVADA_SA (pool=0 + locked_by del SA) → candidata.
        is_sa_reserved = (
            not r.get("published_to_pool")
            and str(locked_by).lower() in sa_tokens
        )
        if not is_sa_reserved:
            if not r.get("published_to_pool"):
                continue
            if locked_by is not None:
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
                "cooldown_until", "locked_by", "published_to_pool", "rl_streak")


def _load_candidate_rows() -> List[Dict[str, Any]]:
    """Trae de la BD el universo grueso (LIVE + útiles) para que la lógica pura
    afine. Filtra en SQL lo barato; el resto lo decide `select_refresh_candidates`.

    Universo: cuentas LIVE publicadas al pool (published_to_pool=1) **más** las
    RESERVADA_SA (published_to_pool=0 + locked_by del SA) — sin esto, el JWT
    muerto server-side de una cuenta en uso nunca se renueva y el refresh
    siempre recibe default del server.
    """
    import app  # lazy: evita ciclo de import
    from account_refresh import _sa_lock_tokens
    sa_tokens = _sa_lock_tokens()
    with app.db() as conn:
        if sa_tokens:
            placeholders = ",".join("?" for _ in sa_tokens)
            cur = conn.execute(
                f"SELECT {', '.join(_SELECT_COLS)} FROM accounts "
                "WHERE status='LIVE' "
                f"AND (published_to_pool=1 "
                f"OR (published_to_pool=0 AND lower(locked_by) IN ({placeholders})))",
                [t.lower() for t in sa_tokens],
            )
        else:
            cur = conn.execute(
                f"SELECT {', '.join(_SELECT_COLS)} FROM accounts "
                "WHERE status='LIVE' AND published_to_pool=1"
            )
        return [dict(row) for row in cur.fetchall()]


def _set_cooldown(email: str, minutes: int) -> None:
    """Reusa el helper de cooldown de depósitos (deposits.py) pero con un cooldown
    LARGO propio del keeper (ver `rl_cooldown_min` en cfg): rompe el bucle de quema."""
    try:
        from deposits import _set_account_cooldown
        _set_account_cooldown(email, minutes=minutes)
    except Exception as e:  # pragma: no cover
        logger.warning(f"[jwt_keeper] no pude setear cooldown a {email}: {e}")


def _bump_rl_streak(email: str) -> int:
    """Incrementa rl_streak y devuelve el nuevo valor (best-effort, 0 si falla)."""
    try:
        import app
        with app.db(write=True) as c:
            c.execute(
                "UPDATE accounts SET rl_streak = COALESCE(rl_streak,0) + 1 WHERE email=?",
                (email,))
            row = c.execute(
                "SELECT rl_streak FROM accounts WHERE email=?", (email,)).fetchone()
            return int(row["rl_streak"]) if row and row["rl_streak"] is not None else 0
    except Exception as e:  # pragma: no cover
        logger.warning(f"[jwt_keeper] no pude incrementar rl_streak {email}: {e}")
        return 0


def _reset_rl_streak(email: str) -> None:
    try:
        import app
        with app.db(write=True) as c:
            c.execute("UPDATE accounts SET rl_streak=0 WHERE email=?", (email,))
    except Exception as e:  # pragma: no cover
        logger.warning(f"[jwt_keeper] no pude resetear rl_streak {email}: {e}")


# ── Ciclo (async) ─────────────────────────────────────────────────────────────
async def run_keepalive_cycle(
    *,
    batch_max: int,
    refresh_ahead_sec: int,
    grades: Set[str],
    gap_min: int,
    gap_max: int,
    rl_cooldown_min: int = 360,
    rl_streak_quarantine_at: int = 3,
    rl_quarantine_min: int = 2880,
) -> Dict[str, Any]:
    """Un ciclo: selecciona el lote y re-loguea cada cuenta espaciada (JWT fresco).

    Un solo pool de captcha para todo el lote (evita el drenaje de token-por-cuenta
    documentado en ERRORS.md). `use_cache=False` fuerza login real → JWT de 7 días
    nuevo. `allow_proxyless=False` (regla dura Robert: prod NUNCA proxyless).
    """
    now = int(time.time())
    rows = await asyncio.to_thread(_load_candidate_rows)
    from account_refresh import _sa_lock_tokens
    sa_tokens = _sa_lock_tokens()
    cands = select_refresh_candidates(
        rows, now, batch_max=batch_max,
        refresh_ahead_sec=refresh_ahead_sec, grades=grades,
        sa_tokens=sa_tokens)
    stats: Dict[str, Any] = {
        "universe": len(rows), "selected": len(cands),
        "live": 0, "rate_limited": 0, "retry": 0, "dead": 0, "error": 0,
        "quarantined": 0,
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
                if (r.get("rl_streak") or 0) > 0:
                    await asyncio.to_thread(_reset_rl_streak, email)
                logger.info(f"[jwt_keeper] {email} JWT fresco ✓ (grade {r.get('grade')})")
            elif res.code == "RATE_LIMITED":
                stats["rate_limited"] += 1
                streak = await asyncio.to_thread(_bump_rl_streak, email)
                if streak >= rl_streak_quarantine_at:
                    stats["quarantined"] += 1
                    await asyncio.to_thread(_set_cooldown, email, rl_quarantine_min)
                    logger.warning(
                        f"[jwt_keeper] {email} racha={streak} rate-limited SIN éxito → "
                        f"CUARENTENA {rl_quarantine_min}min (quemada permanente, no transitoria)")
                else:
                    await asyncio.to_thread(_set_cooldown, email, rl_cooldown_min)
                    logger.info(f"[jwt_keeper] {email} rate-limited (racha={streak}) → cooldown {rl_cooldown_min}min")
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
        grades=c["grades"], gap_min=c["gap_min"], gap_max=c["gap_max"],
        rl_cooldown_min=c["rl_cooldown_min"],
        rl_streak_quarantine_at=c["rl_streak_quarantine_at"],
        rl_quarantine_min=c["rl_quarantine_min"])
