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
        # 8 → 50 (Robert 2026-08-05): el batch alto era un problema cuando el
        # cooldown era corto (6h) — la cuenta quemada volvía a ser elegible al
        # siguiente ciclo y el batch drenaba captcha en puro rate_limited. Con
        # cooldown de 24h tras UN rate-limit (no taladrar) + cuarentena de 24h
        # tras racha, el batch de 50 es seguro: las quemadas se apartan por un
        # día completo tras su primer 429 y el universo sano avanza de verdad.
        "batch_max": _env_int("JWT_KEEPER_BATCH", 50),
        "refresh_ahead_sec": _env_int("JWT_KEEPER_REFRESH_AHEAD_H", 24) * 3600,
        "gap_min": _env_int("JWT_KEEPER_GAP_MIN_SEC", 20),
        "gap_max": _env_int("JWT_KEEPER_GAP_MAX_SEC", 45),
        # Cooldown tras UN rate-limit = 24h (Robert 2026-08-05): "solo intentar
        # 1 vez al día traerlas a la vida, no más, para no espamearla". Con un
        # solo 429 de BetMexico la cuenta descansa 24h COMPLETAS — rompe el
        # bucle de quema sin importar el tamaño del batch: la quemada entra al
        # lote, da 429 una vez, y no vuelve a ser elegible hasta mañana.
        "rl_cooldown_min": _env_int("JWT_KEEPER_RL_COOLDOWN_MIN", 1440),  # 24h
        # Racha de RATE_LIMITED consecutivos (forense 2026-07-11, ver rl_streak
        # en app._migrate): a partir de este umbral la cuenta pasa a cuarentena
        # larga. 2026-08-05: 48h → 24h. El 429 NO era un bloqueo puntual de
        # BetMexico — fue una ráfaga de logins que los quemó (forense Robert);
        # con el refresco bien hecho no hay por qué mandar a nadie a rate-limit.
        # 24h las deja descansar un día y reintentar suave al siguiente.
        "rl_streak_quarantine_at": _env_int("JWT_KEEPER_RL_STREAK_QUARANTINE_AT", 3),
        "rl_quarantine_min": _env_int("JWT_KEEPER_RL_QUARANTINE_MIN", 1440),  # 24h
        # Robert 2026-08-06: cuentas A/B con racha alta seguían en cuarentena
        # infinita — reintentadas TODOS los días, gentil y espaciado tal como
        # se diseñó el 2026-08-05, y AUN ASÍ nunca sanaban (censo: 145 cuentas
        # grado A/B con racha 3-12, algunas llevaban semanas fallando a diario
        # sin un solo éxito). Eso invalida la hipótesis de que el 429 era solo
        # ráfaga de concurrencia nuestra — a esta racha ya es bloqueo real de
        # BetMexico por cuenta. Decisión explícita de Robert (2026-08-06): CERO
        # tolerancia — al primer 429 la cuenta se declara DEAD, sin cuarentena
        # ni segunda oportunidad. Deja de ser candidata, para de gastar
        # captcha/proxy. Revisión manual si acaso, cuando Robert quiera.
        "rl_streak_dead_at": _env_int("JWT_KEEPER_RL_STREAK_DEAD_AT", 1),
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

    Orden: HOT PRIMERO (cuenta con depósito/retiro en curso = `row["hot"]=True`,
    handoff 2026-08-05 §2.2) — sin importar grade, van al frente del lote para
    que el keeper las re-loguee ANTES que las cuentas frías. Dentro de cada
    grupo (hot / normal), mejor grade primero; dentro del grade, la más urgente
    (menor `exp`, con expiradas/nulas —exp=0— al frente). Corta en `batch_max`
    contando las normales; las hot NO cuentan contra ese cupo (espejo de
    `account_refresh.select_refresh_candidates_healthy`).
    """
    sa_tokens = set(sa_tokens or [])
    hot: List[Dict[str, Any]] = []
    normal: List[Dict[str, Any]] = []
    for r in rows:
        if (r.get("status") or "") != "LIVE":
            continue
        # Cooldown aplica SIEMPRE, incluso a hot — evita el bucle de quema
        # (medido 2026-07-11: una hot quemada debe descansar como cualquier otra).
        cd = r.get("cooldown_until")
        if cd not in (None, ""):
            try:
                if isinstance(cd, str) and ("-" in cd or ":" in cd):
                    from datetime import datetime
                    cd_epoch = datetime.fromisoformat(cd.replace("Z", "+00:00")).timestamp()
                else:
                    cd_epoch = float(cd)
                if cd_epoch > now:
                    continue
            except Exception:
                pass
        exp = _exp_int(r.get("jwt_expires_at"))
        if exp > now + refresh_ahead_sec:
            continue  # todavía tiene margen → no re-loguear
        # HOT bypassa grade/published/locked_by (espejo de
        # account_refresh.select_refresh_candidates_healthy): una cuenta con
        # depósito/retiro en curso necesita JWT vivo sí o sí, sin importar su
        # grade o si está lockeada por un operador.
        if r.get("hot"):
            hot.append(r)
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
        normal.append(r)

    def _key(r: Dict[str, Any]) -> tuple:
        return (
            _GRADE_RANK.get(r.get("grade") or "", 9),
            _exp_int(r.get("jwt_expires_at")),
        )
    hot.sort(key=_key)
    normal.sort(key=_key)
    return hot + normal[:batch_max]


def _exp_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ── I/O de BD (aislado; usa el context manager de app) ────────────────────────
# `balance_real`, `locked_until` y `has_pending_withdrawal` se traen para que
# `is_hot_account` (importada de account_refresh) pueda marcar las hot aquí
# mismo — una cuenta hot con JWT expirado debe ir PRIMERO en el lote de
# re-login, no detrás de 8 cuentas frías de mejor grade (handoff 2026-08-05 §2.2).
_SELECT_COLS = ("email", "password", "status", "grade", "jwt_expires_at",
                "cooldown_until", "locked_by", "published_to_pool", "rl_streak",
                "balance_real", "locked_until")

# Reusa la subquery de account_refresh (DRY: una sola fuente de verdad para
# "¿tiene retiro pendiente?"). ponytail: si account_refresh la cambia, jwt_keeper
# la hereda automáticamente sin tocar este archivo.
from account_refresh import _PENDING_WD_EXISTS_SQL


def _load_candidate_rows() -> List[Dict[str, Any]]:
    """Trae de la BD el universo grueso (LIVE + útiles) para que la lógica pura
    afine. Filtra en SQL lo barato; el resto lo decide `select_refresh_candidates`.

    Universo: cuentas LIVE publicadas al pool (published_to_pool=1) **más** las
    RESERVADA_SA (published_to_pool=0 + locked_by del SA) — sin esto, el JWT
    muerto server-side de una cuenta en uso nunca se renueva y el refresh
    siempre recibe default del server.

    Computa `hot` vía `account_refresh.is_hot_account` (DRY: una sola fuente de
    verdad para qué es "hot"). Las hot con JWT por expirar se priorizan en el
    sort para que el keeper las re-loguee ANTES que las cuentas frías del mismo
    grade — sin esto, una cuenta con depósito/retiro en curso y JWT por morir
    puede quedarse fuera del batch de 8 por grade y no ser re-logueada hasta
    el próximo ciclo (1h de lag en vez de "ya").
    """
    import app  # lazy: evita ciclo de import
    from datetime import datetime, timezone
    from account_refresh import _sa_lock_tokens, is_hot_account
    sa_tokens = _sa_lock_tokens()
    now_iso = datetime.now(timezone.utc).isoformat()
    with app.db() as conn:
        if sa_tokens:
            placeholders = ",".join("?" for _ in sa_tokens)
            cur = conn.execute(
                f"SELECT {', '.join(_SELECT_COLS)}, "
                f"{_PENDING_WD_EXISTS_SQL} AS has_pending_withdrawal "
                "FROM accounts WHERE status='LIVE' "
                f"AND (published_to_pool=1 "
                f"OR (published_to_pool=0 AND lower(locked_by) IN ({placeholders})))",
                [t.lower() for t in sa_tokens],
            )
        else:
            cur = conn.execute(
                f"SELECT {', '.join(_SELECT_COLS)}, "
                f"{_PENDING_WD_EXISTS_SQL} AS has_pending_withdrawal "
                "FROM accounts WHERE status='LIVE' AND published_to_pool=1"
            )
        rows = [dict(row) for row in cur.fetchall()]
    for r in rows:
        r["has_pending_withdrawal"] = bool(r.get("has_pending_withdrawal"))
        r["hot"] = is_hot_account(r, now_iso)
    return rows


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
        def _do(c):
            c.execute(
                "UPDATE accounts SET rl_streak = COALESCE(rl_streak,0) + 1 WHERE email=?",
                (email,))
            row = c.execute(
                "SELECT rl_streak FROM accounts WHERE email=?", (email,)).fetchone()
            return int(row["rl_streak"]) if row and row["rl_streak"] is not None else 0
        return app._db_write_with_retry(_do)
    except Exception as e:  # pragma: no cover
        logger.warning(f"[jwt_keeper] no pude incrementar rl_streak {email}: {e}")
        return 0


def _reset_rl_streak(email: str) -> None:
    try:
        import app
        app._db_write_with_retry(
            lambda c: c.execute("UPDATE accounts SET rl_streak=0 WHERE email=?", (email,))
        )
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
    rl_streak_dead_at: int = 6,
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
                logger.debug(f"[jwt_keeper] {email} JWT fresco ✓ (grade {r.get('grade')})")
            elif res.code == "RATE_LIMITED" or "RATE_LIMITED" in str(res.error or "") or "429" in str(res.error or ""):
                stats["rate_limited"] += 1
                stats["dead"] += 1
                try:
                    from prewarm import _db_mark_dead
                    await asyncio.to_thread(
                        _db_mark_dead, email,
                        "RATE_LIMITED_PERMANENT (429 — BetMexico bloqueó la cuenta)")
                except Exception as e:  # pragma: no cover
                    logger.warning(f"[jwt_keeper] no pude marcar DEAD {email}: {e}")
                logger.warning(
                    f"[jwt_keeper] {email} RATE_LIMITED (429) → DEAD INMEDIATO (bloqueo terminal BetMexico)")
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
                logger.warning(f"[jwt_keeper] {email} muerta ({res.code}) → cuarentena DEAD")
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
