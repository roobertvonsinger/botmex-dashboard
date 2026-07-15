"""Pre-warm router — pre-carga tokens de captcha + balance para cuentas seleccionadas.

Mismo diseño que web_routes_prewarm.py del v1 (mismas reglas de Robert):
  1. Cap por sesión: max 30 pre-warms por operador en últimos 10 min.
  2. Cap CapMonster: si saldo < $5, abortar.
  3. Skip si JWT vigente Y last_check < 5 min.
  4. Cancel-on-deselect: /cancel mata tasks activas.
  5. Timeout 25s por task.
  6. fetch_mode='balance_only' + JWT cache.
  7. Logs en process_log con process_type='prewarm'.

Dependencias del bot (betmexico_login_service, betmexico_login_api) se importan
en tiempo de ejecución — disponibles en VPS vía WorkingDirectory=/opt/betmexico/bot,
no disponibles en dev local (fallan con _HAS_BOT_DEPS=False).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from auth import require_session

try:
    from betmexico_login_service import get_jwt, make_pool
    from betmexico_login_api import BetmexicoApiChecker
    score_payment_readiness = None  # se setea desde app.BOT_SCORE_PAYMENT al usar
    _HAS_BOT_DEPS = True
except ImportError:
    _HAS_BOT_DEPS = False
    score_payment_readiness = None  # type: ignore

# Pool de proxies local del dashboard — combina bot + extras (NodeMaven, etc.)
from proxy_pool import build_admin_proxy_url as _build_proxy_url

logger = logging.getLogger("betmexico.dashboard.prewarm")

router = APIRouter(prefix="/api/prewarm", tags=["prewarm"])

_PREWARM_TASKS: Dict[str, asyncio.Task] = {}

CAP_PER_OPERATOR_10MIN = 9999  # sin tope práctico — el operador decide
ACCOUNT_FRESH_MINUTES = 30      # < 30min desde last check → skip con warning
ACCOUNT_DAILY_LIMIT = 3          # >= 3 prewarms en el día → skip con warning
REFRESH_PARALLEL = 2            # max logins concurrentes — 15→8→2 (forense 2026-07-11: la TASA agregada de logins es la causa #1 del rate-limit; ≥45/min ≈65% denial). El cuello REAL ahora es el semáforo GLOBAL de login_orchestrator (LOGIN_MAX_CONCURRENCY); esto es 2ª barrera del bulk.
CAPMONSTER_MIN_BALANCE = 5.0
BALANCE_FRESH_SEC = 5 * 60
TASK_TIMEOUT_SEC = 25


# ── DB helpers (SQL directo, sin betmexico_db) ─────────────────────────────────

def _db_get_account(email: str) -> Optional[dict]:
    from app import db, DB_PATH
    import sqlite3
    try:
        with db() as c:
            row = c.execute(
                "SELECT id, email, password, balance_real, balance_total, "
                "last_checked_at, jwt_token, jwt_expires_at, status, cooldown_until "
                "FROM accounts WHERE email=? LIMIT 1",
                (email,),
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.OperationalError:
        return None


def _db_get_jwt_cache(email: str) -> Optional[str]:
    acc = _db_get_account(email)
    if not acc:
        return None
    token = acc.get("jwt_token")
    expires = acc.get("jwt_expires_at")
    if not token or not expires:
        return None
    if int(expires) < int(time.time()):
        return None
    return token


def _db_log_phase(
    process_id: str, phase: str, payload: dict, duration_ms: int = 0
) -> None:
    from app import db
    import sqlite3
    try:
        now = datetime.now(timezone.utc)
        with db(write=True) as c:
            c.execute(
                "INSERT OR IGNORE INTO process_log "
                "(process_id, process_type, phase, payload_json, duration_ms, "
                " timestamp_ms, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    process_id, "prewarm", phase,
                    json.dumps(payload), duration_ms,
                    int(time.time() * 1000), now.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
    except Exception as e:
        logger.debug(f"[Prewarm] log_phase error: {e}")


def _db_count_recent(operator_id: int, minutes: int) -> int:
    from app import db
    import sqlite3
    try:
        cutoff = datetime.now(timezone.utc)
        cutoff_ms = int((time.time() - minutes * 60) * 1000)
        with db() as c:
            row = c.execute(
                "SELECT COUNT(*) FROM process_log "
                "WHERE process_type='prewarm' AND timestamp_ms >= ? "
                "AND payload_json LIKE ?",
                (cutoff_ms, f'%"operator_id": {operator_id}%'),
            ).fetchone()
            return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _db_account_prewarms_today(email: str) -> int:
    """Cuenta cuántos prewarms 'complete' tuvo esta cuenta hoy (cualquier operador)."""
    from app import db
    import sqlite3
    try:
        with db() as c:
            row = c.execute(
                "SELECT COUNT(*) FROM process_log "
                "WHERE process_type='prewarm' AND phase='complete' "
                "AND payload_json LIKE ? "
                "AND date(created_at) = date('now')",
                (f'%"email": "{email}"%',),
            ).fetchone()
            return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _account_minutes_since_check(acc: dict) -> Optional[float]:
    """Minutos desde el último check de la cuenta. None si no se sabe."""
    last = acc.get("last_checked_at")
    if not last:
        return None
    try:
        ts = datetime.fromisoformat(last.replace(" ", "T"))
        return (time.time() - ts.timestamp()) / 60
    except Exception:
        return None


def _db_get_recent_log(operator_id: int, minutes: int) -> list:
    from app import db
    import sqlite3
    try:
        cutoff_ms = int((time.time() - minutes * 60) * 1000)
        with db() as c:
            rows = c.execute(
                "SELECT process_id, phase, payload_json, duration_ms, created_at "
                "FROM process_log WHERE process_type='prewarm' "
                "AND timestamp_ms >= ? AND payload_json LIKE ? "
                "ORDER BY timestamp_ms DESC LIMIT 20",
                (cutoff_ms, f'%"operator_id": {operator_id}%'),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def _db_upsert_balance(email: str, details: dict) -> None:
    """Persiste balance + último depósito.
    - balance_total = balance_real + balance_bonos (el dict de details NO trae
      balance_total — había que calcularlo; antes se escribía NULL).
    - Guard "preserve old balance" SOLO si el fetch fue claramente vacío
      (sin last_deposit, sin fullname, sin txns) — eso indica JWT muerto/401
      silencioso. Si el fetch trae cualquier señal de éxito, confiamos en
      balance_real aunque sea 0 (usuario realmente puede tener $0).
    - last_deposit_* solo se sobreescribe si el fetch trajo datos válidos."""
    from app import db
    import sqlite3
    bal_real = float(details.get("balance_real", 0.0) or 0.0)
    bal_bonos = float(details.get("balance_bonos", 0.0) or 0.0)
    bal_total = bal_real + bal_bonos
    new_amt = details.get("last_deposit_amount")
    new_date = details.get("last_deposit_date")
    has_dep = (new_amt is not None and float(new_amt or 0) > 0
               and new_date and str(new_date).strip() not in ("", "N/A"))
    # Señales de que la API respondió de verdad (no es 401 silencioso):
    api_succeeded = (
        has_dep
        or bool(details.get("fullname"))
        or bool((details.get("transactions") or {}).get("items"))
        or bal_bonos > 0
    )
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db(write=True) as c:
            # Solo preservar saldo viejo si la API respondió VACÍO (= falla)
            if bal_real == 0.0 and not api_succeeded:
                row = c.execute(
                    "SELECT balance_real, balance_bonos, balance_total "
                    "FROM accounts WHERE email=?", (email,),
                ).fetchone()
                if row and (row["balance_real"] or 0) > 0:
                    bal_real = float(row["balance_real"] or 0.0)
                    bal_bonos = float(row["balance_bonos"] or 0.0)
                    bal_total = float(row["balance_total"] or (bal_real + bal_bonos))
            if has_dep:
                c.execute(
                    "UPDATE accounts SET balance_real=?, balance_bonos=?, "
                    "balance_total=?, last_deposit_amount=?, last_deposit_date=?, "
                    "last_checked_at=? WHERE email=?",
                    (bal_real, bal_bonos, bal_total,
                     float(new_amt), str(new_date), now_utc, email),
                )
            else:
                c.execute(
                    "UPDATE accounts SET balance_real=?, balance_bonos=?, "
                    "balance_total=?, last_checked_at=? WHERE email=?",
                    (bal_real, bal_bonos, bal_total, now_utc, email),
                )
    except sqlite3.OperationalError:
        pass


def _db_save_txns_and_recalc(email: str, details: dict, operator_id: int) -> None:
    """Guarda transacciones nuevas + recalcula grade desde BD completa.
    Cambio 2026-05-23: el recalc ahora usa `web_grading.recalc_grade_from_db`
    que lee TODAS las txns persistidas en BD, no solo las 10 del fetch actual.
    Eso da grade correcto incluso cuando fetch_mode='balance_only' trae solo
    una página."""
    txn_data = (details or {}).get("transactions") or {}
    items = txn_data.get("items") or []
    # Persiste txns nuevas (reusa el helper del bot)
    if items:
        try:
            from betmexico_db import db as _bot_db
            saver = getattr(_bot_db, "save_account_transactions", None)
            if saver:
                _bot_db.save_account_transactions(email, items, checked_by=operator_id)
        except Exception as e:
            logger.debug(f"[Prewarm] save_account_transactions: {e}")
    # Recalc grade usando TODAS las txns en BD (no solo las del fetch).
    try:
        from web_grading import recalc_grade_from_db
        recalc_grade_from_db(email)
    except Exception as e:
        logger.debug(f"[Prewarm] recalc_grade_from_db: {e}")


def _db_update_last_checked(email: str) -> None:
    """Solo actualiza last_checked_at — cuando el fetch falló pero el login fue OK."""
    from app import db
    import sqlite3
    try:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with db(write=True) as c:
            c.execute(
                "UPDATE accounts SET last_checked_at=? WHERE email=?",
                (now_utc, email),
            )
    except sqlite3.OperationalError:
        pass


def _db_invalidate_jwt(email: str) -> None:
    """Borra JWT de cache — cuando el JWT de cache fue rechazado por BetMexico."""
    from app import db
    import sqlite3
    try:
        with db(write=True) as c:
            c.execute(
                "UPDATE accounts SET jwt_token=NULL, jwt_expires_at=NULL WHERE email=?",
                (email,),
            )
    except sqlite3.OperationalError:
        pass


def _db_mark_dead(email: str, reason: str) -> None:
    """Cuarentena de cuenta quemada (fix forense 2026-07-11). Marca DEAD +
    dead_reason SOLO cuando el orquestador devolvió account_dead=True (login
    terminal: LOGIN_DENIED / KYC_PENDING / AUTOEXCLUSION — regla Robert). Antes
    el prewarm NUNCA persistía esto → la cuenta seguía LIVE y se re-logueaba en
    cada ciclo, quemando captcha y alimentando la ráfaga de logins (causa #2 del
    rate-limit). Ahora sale de la vista LIVE, del pool y de toda selección de
    login; revive solo por acción manual (ej. reset de contraseña). NO pisa un
    dead_reason previo (una AUTOEXCLUSION real no se re-etiqueta). Best-effort."""
    from app import db
    import sqlite3
    try:
        dead_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with db(write=True) as c:
            c.execute(
                "UPDATE accounts SET status='DEAD', "
                "dead_reason=COALESCE(NULLIF(dead_reason,''), ?), "
                "dead_at=COALESCE(dead_at, ?) "
                "WHERE email=? AND status!='DEAD'",
                (reason, dead_at, email),
            )
        logger.warning(f"[Prewarm] {email} CUARENTENA → DEAD ({reason})")
    except sqlite3.OperationalError:
        pass


def _is_balance_fresh(acc: dict) -> bool:
    last = acc.get("last_checked_at")
    if not last:
        return False
    try:
        ts = datetime.fromisoformat(last.replace(" ", "T"))
        return (time.time() - ts.timestamp()) < BALANCE_FRESH_SEC
    except Exception:
        return False


# ── CapMonster balance ─────────────────────────────────────────────────────────

async def _capmonster_balance() -> Optional[float]:
    import os
    key = os.environ.get("CAPMONSTER_KEY", "")
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                "https://api.capmonster.cloud/getBalance",
                json={"clientKey": key},
            )
            data = r.json()
            if data.get("errorId") == 0:
                return float(data.get("balance", 0))
    except Exception as e:
        logger.warning(f"[Prewarm] CapMonster balance error: {e}")
    return None


# ── Pre-warm task ──────────────────────────────────────────────────────────────

async def _run_prewarm(operator_id: int, email: str, password: str) -> dict:
    """Retorna {ok: bool, status: str, error: str?}."""
    process_id = uuid.uuid4().hex
    _db_log_phase(process_id, "init", {"email": email, "operator_id": operator_id})
    t0 = time.time()
    pool = None
    import os
    cap_key = os.environ.get("CAPMONSTER_KEY", "")
    # proxy_url se decide adentro del failover. used_proxy se conserva para reusar
    # el mismo proxy en el ApiChecker post-login (afinidad de proxy validado).
    used_proxy: Optional[str] = None
    try:
        # gentle_login (rework 2026-05-28): reemplaza call_with_proxy_failover
        # (cuya rotación interna era ráfaga sin jitter → quemaba IPs). Añade
        # jitter anti-ráfaga + reintentos espaciados + timeout POR INTENTO (no
        # global de 25s que mataba a media-rotación). use_cache=True aprovecha
        # JWT cacheado vigente (sin captcha) en el intento 0 — updates baratos.
        # max_login_retries=5: el update solo trae balance, vale reintentar.
        #
        # C2 (fix 2026-07-02): NO gastar captcha si el login será cache-hit.
        # Pre-chequeamos el JWT cache ANTES de precalentar el pool. Con JWT vigente,
        # gentle_login reusa (0 captcha) → el prefetch(1)+factory resolvía 1 token
        # que se tiraba a la basura en CADA cuenta cacheada (regresión de ERRORS.md
        # "Capsolver gastado en vano"). Creamos el pool igual (defensivo: si por una
        # carrera el cache expira justo aquí, gentle_login tiene de dónde pedir un
        # token on-demand), pero solo lo precalentamos en cache-miss real.
        jwt_from_cache = False
        cached_jwt = await asyncio.to_thread(_db_get_jwt_cache, email)
        pool = make_pool(cap_key, size=2, workers=1)
        if not cached_jwt:
            await pool.prefetch(1)
            await pool.start_factory()

        from login_orchestrator import gentle_login
        login_res = await gentle_login(
            email, password, max_login_retries=5, throttle=True,
            pool=pool, use_cache=True,
        )
        jwt = login_res.jwt
        jwt_from_cache = login_res.from_cache  # señal real del orquestador
        used_proxy = login_res.used_proxy
        if not jwt:
            # LOGIN_RETRY_LATER / LOGIN_DENIED / KYC_PENDING / AUTOEXCLUSION / RATE_LIMITED.
            # CUARENTENA (fix forense 2026-07-11): antes NO persistíamos nada aquí
            # → 174 cuentas quemadas seguían LIVE y se re-logueaban en cada ciclo,
            # alimentando la ráfaga (causa #2). Ahora persistimos SOLO las señales
            # inequívocas del orquestador (no transitorios):
            #   • account_dead=True (login terminal por regla Robert) → DEAD+reason.
            #   • RATE_LIMITED (403/429 recuperable) → cooldown_until: la selección
            #     la salta hasta enfriar, sin martillarla (martillar la hunde más).
            # LOGIN_RETRY_LATER/TIMEOUT/ERROR (transitorios) → solo last_checked, como antes.
            quarantined = None
            if login_res.account_dead:
                await asyncio.to_thread(_db_mark_dead, email, login_res.code or "LOGIN_DENIED")
                quarantined = "dead"
            elif login_res.code == "RATE_LIMITED":
                from deposits import _set_account_cooldown
                await asyncio.to_thread(_set_account_cooldown, email)
                quarantined = "cooldown"
            _db_log_phase(
                process_id, "no_jwt",
                {"email": email, "operator_id": operator_id,
                 "status": login_res.code, "attempts": login_res.attempts,
                 "account_dead": login_res.account_dead, "quarantined": quarantined},
                int((time.time() - t0) * 1000),
            )
            await asyncio.to_thread(_db_update_last_checked, email)
            return {"ok": False, "status": login_res.code or "no_jwt",
                    "error": login_res.error or login_res.code or "Login falló"}

        # ── C1 (fix 2026-07-02): NUNCA proxyless contra BetMexico (ley Robert) ──
        # En cache-hit gentle_login NO trae proxy (used_proxy=None) → tanto
        # check_autoexclusion como el fetch de balance saldrían con la IP REAL del
        # server. Tomamos un proxy del pool (mismo patrón que
        # deposits._acquire_session_and_begin). Pool vacío → abortar el update:
        # jamás exponer la IP real, mejor no actualizar esta vuelta.
        if not used_proxy:
            try:
                from proxy_pool import shuffled_proxy_urls
                _urls = shuffled_proxy_urls()
            except Exception:
                _urls = []
            if _urls:
                import random
                used_proxy = random.choice(_urls)
            else:
                await asyncio.to_thread(_db_update_last_checked, email)
                _db_log_phase(
                    process_id, "no_proxy",
                    {"email": email, "operator_id": operator_id,
                     "reason": "pool vacio — no se actualiza proxyless"},
                    int((time.time() - t0) * 1000),
                )
                return {"ok": False, "status": "no_proxy",
                        "error": "Sin proxy disponible — update omitido (no exponer IP)"}

        # ── Gate de autoexclusión (update) ────────────────────────────────
        # BetMexico entrega JWT válido a cuentas autoexcluidas, pero son basura
        # para operar (begin_deposit las rechaza). Las detectamos al ACTUALIZAR
        # y las mandamos a DEAD para que no aparezcan en la vista de operadores
        # (list_accounts filtra status='LIVE' por default). Robert 2026-05-29.
        try:
            from autoexclusion import check_autoexclusion, mark_account_autoexcluded
            ax_info = await check_autoexclusion(jwt, proxy=used_proxy)
        except Exception as _axe:
            logger.warning(f"[Prewarm] check_autoexclusion err {email}: {_axe}")
            ax_info = None
        if ax_info:
            reason = await asyncio.to_thread(
                mark_account_autoexcluded, email, ax_info, operator_id)
            _db_log_phase(
                process_id, "autoexclusion",
                {"email": email, "operator_id": operator_id, "reason": reason},
                int((time.time() - t0) * 1000),
            )
            logger.warning(f"[Prewarm] {email} AUTOEXCLUSION → DEAD ({reason})")
            return {"ok": False, "status": "autoexclusion", "error": reason}

        # Mantener afinidad: ApiChecker usa el mismo proxy que validó el login.
        # fetch_mode="balance_only" (cambio 2026-05-23): trae balance +
        # last_deposit + KYC. NO trae txns (~3-5s ahorro). Robert: "el balance
        # y fechas de depósito y cantidades sí actualizar, pero los datos
        # estáticos repararse desde BD". Las txns nuevas las trae el watchdog
        # o el flujo de depósito (que sí usa "full").
        async with BetmexicoApiChecker(proxy=used_proxy) as checker:
            details = await asyncio.wait_for(
                checker.fetch_account_details_parallel(jwt, fetch_mode="balance_only"),
                timeout=12.0,
            )
        if details:
            await asyncio.to_thread(_db_upsert_balance, email, details)
            # Guarda txns frescas + recalcula grade (oportunidad gratuita)
            await asyncio.to_thread(_db_save_txns_and_recalc, email, details, operator_id)
        else:
            # Login/fetch OK pero sin datos — actualizar timestamp para evitar retry inmediato
            await asyncio.to_thread(_db_update_last_checked, email)
            # JWT silenció datos (401 silencioso) — invalidar siempre para forzar login real la próxima vez
            await asyncio.to_thread(_db_invalidate_jwt, email)

        phase = "complete" if details else "no_details"
        _db_log_phase(
            process_id, phase,
            {"email": email, "operator_id": operator_id,
             "balance_real": details.get("balance_real") if details else None,
             "grade": details.get("payment_score", {}).get("grade") if details else None,
             "jwt_from_cache": jwt_from_cache},
            int((time.time() - t0) * 1000),
        )
        return {"ok": bool(details), "status": phase,
                "error": None if details else "fetch sin datos"}
    except asyncio.CancelledError:
        _db_log_phase(
            process_id, "cancelled",
            {"email": email, "operator_id": operator_id},
            int((time.time() - t0) * 1000),
        )
        raise
    except asyncio.TimeoutError:
        _db_log_phase(
            process_id, "timeout",
            {"email": email, "operator_id": operator_id},
            int((time.time() - t0) * 1000),
        )
        # Actualizar last_checked_at para que el anti-spam detecte el intento fallido
        await asyncio.to_thread(_db_update_last_checked, email)
        return {"ok": False, "status": "timeout", "error": "Timeout 12s"}
    except Exception as e:
        logger.error(f"[Prewarm] {email}: {e}")
        _db_log_phase(
            process_id, "error",
            {"email": email, "operator_id": operator_id, "error": str(e)[:300]},
            int((time.time() - t0) * 1000),
        )
        return {"ok": False, "status": "error", "error": str(e)[:200]}
    finally:
        _PREWARM_TASKS.pop(f"{operator_id}:{email}", None)
        if pool is not None:
            try:
                await pool.stop()
            except Exception:
                pass


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/select")
async def prewarm_select(request: Request, user: dict = Depends(require_session)):
    if not _HAS_BOT_DEPS:
        raise HTTPException(status_code=503, detail="Bot deps no disponibles en este entorno")

    body = await request.json()
    emails: List[str] = list(body.get("account_emails") or [])
    force = bool(body.get("force"))  # True = ignora cache, fuerza re-fetch live
    if not emails:
        raise HTTPException(status_code=400, detail="account_emails requerido")

    operator_id = int(user.get("telegram_id") or 0)
    if not operator_id:
        # Fallback: usar hash del username como ID si no hay telegram_id
        operator_id = abs(hash(user.get("username", "unknown"))) % 10_000_000

    bal = await _capmonster_balance()
    # Solo avisa, no bloquea — el operador decide
    cap_warning = (bal is not None and bal < CAPMONSTER_MIN_BALANCE)

    used = await asyncio.to_thread(_db_count_recent, operator_id, 10)
    remaining = max(0, CAP_PER_OPERATOR_10MIN - used)

    started = cached = skipped = 0
    skipped_reasons: Dict[str, int] = {}

    for email in emails:
        if started >= remaining:
            skipped += 1
            skipped_reasons["cap_session"] = skipped_reasons.get("cap_session", 0) + 1
            continue

        key = f"{operator_id}:{email}"
        if key in _PREWARM_TASKS and not _PREWARM_TASKS[key].done():
            skipped += 1
            skipped_reasons["already_running"] = skipped_reasons.get("already_running", 0) + 1
            continue

        acc = await asyncio.to_thread(_db_get_account, email)
        if not acc:
            skipped += 1
            skipped_reasons["no_account"] = skipped_reasons.get("no_account", 0) + 1
            continue

        # Cuarentena (forense 2026-07-11): saltar quemadas (DEAD) y en cooldown.
        if acc.get("status") == "DEAD":
            skipped += 1
            skipped_reasons["dead"] = skipped_reasons.get("dead", 0) + 1
            continue
        from deposits import _cooldown_active
        if _cooldown_active(acc.get("cooldown_until")):
            skipped += 1
            skipped_reasons["cooldown"] = skipped_reasons.get("cooldown", 0) + 1
            continue

        jwt_cache = await asyncio.to_thread(_db_get_jwt_cache, email)
        # En modo force ignoramos el cache de balance fresh — el operador pidió
        # explícitamente actualizar live (ej. picó 'Actualizar visibles').
        if not force and jwt_cache and _is_balance_fresh(acc):
            cached += 1
            continue

        password = acc.get("password", "")
        if not password:
            skipped += 1
            skipped_reasons["no_password"] = skipped_reasons.get("no_password", 0) + 1
            continue

        task = asyncio.create_task(_run_prewarm(operator_id, email, password))
        _PREWARM_TASKS[key] = task
        started += 1

    return {
        "status": "ok",
        "started": started,
        "cached": cached,
        "skipped": skipped,
        "skipped_reasons": skipped_reasons,
        "capmonster_balance": bal,
        "capmonster_warning": cap_warning,
        "cap_used": used + started,
        "cap_max": CAP_PER_OPERATOR_10MIN,
    }


@router.post("/cancel")
async def prewarm_cancel(request: Request, user: dict = Depends(require_session)):
    body = await request.json()
    emails: List[str] = list(body.get("account_emails") or [])
    operator_id = int(user.get("telegram_id") or 0) or abs(hash(user.get("username", ""))) % 10_000_000
    cancelled = 0
    for email in emails:
        task = _PREWARM_TASKS.get(f"{operator_id}:{email}")
        if task and not task.done():
            task.cancel()
            cancelled += 1
    return {"cancelled": cancelled}


@router.get("/status")
async def prewarm_status(user: dict = Depends(require_session)):
    operator_id = int(user.get("telegram_id") or 0) or abs(hash(user.get("username", ""))) % 10_000_000
    active = sum(
        1 for k, t in _PREWARM_TASKS.items()
        if k.startswith(f"{operator_id}:") and not t.done()
    )
    used = await asyncio.to_thread(_db_count_recent, operator_id, 10)
    bal = await _capmonster_balance()
    recent = await asyncio.to_thread(_db_get_recent_log, operator_id, 10)
    return {
        "active": active,
        "cap_used": used,
        "cap_max": CAP_PER_OPERATOR_10MIN,
        "capmonster_balance": bal,
        "recent_runs": recent,
    }


# ── Refresh con stream — login live + emite cada cuenta cuando está lista ─────

@router.post("/refresh-stream")
async def prewarm_refresh_stream(request: Request, user: dict = Depends(require_session)):
    """SSE: corre prewarm en paralelo y emite cada cuenta cuando termina su fetch.
    Permite al frontend repintar fila por fila con microanimación."""
    if not _HAS_BOT_DEPS:
        raise HTTPException(status_code=503, detail="Bot deps no disponibles")
    body = await request.json()
    ids = list(body.get("account_ids") or [])
    if not ids:
        raise HTTPException(status_code=400, detail="account_ids requerido")

    # P3 (tanda 5): solo SA refresca en bulk. Los operadores actualizan UNA cuenta
    # a la vez (botón ↻ por fila). El refresh masivo dispara logins en lote
    # (captcha + proxies + riesgo de rate-limit) que la capa de operador no debe
    # orquestar. Ver feedback_capas_operador_vs_backend / project_visibilidad_roles.
    if user.get("role") != "superadmin" and len(ids) > 1:
        raise HTTPException(
            status_code=403,
            detail="Solo puedes actualizar una cuenta a la vez.",
        )

    operator_id = int(user.get("telegram_id") or 0)
    if not operator_id:
        operator_id = abs(hash(user.get("username", "unknown"))) % 10_000_000

    # Lookup cuentas
    from app import db as _app_db
    placeholders = ",".join("?" * len(ids))
    with _app_db() as c:
        rows = c.execute(
            f"SELECT id, email, password, last_checked_at, status, cooldown_until, jwt_expires_at "
            f"FROM accounts WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    accs = [dict(r) for r in rows]
    logger.info(f"[refresh-stream] op={operator_id} ids={len(ids)} accs={len(accs)} valid")

    # force=true: SA puede saltarse las reglas anti-spam (fresh < 30min, > 3 hoy)
    force = bool(body.get("force"))
    is_sa = (user.get("role") == "superadmin")

    bal = await _capmonster_balance()
    # Solo emite warning, NO aborta — el operador sabe que su saldo está bajo
    cap_warning = (bal is not None and bal < CAPMONSTER_MIN_BALANCE)

    used = await asyncio.to_thread(_db_count_recent, operator_id, 10)
    remaining = max(0, CAP_PER_OPERATOR_10MIN - used)
    logger.info(f"[refresh-stream] cap_used={used} remaining={remaining} cm=${bal} force={force} sa={is_sa}")

    async def gen():
        yield f"data: {json.dumps({'type':'start','total':len(accs),'cap_remaining':remaining,'cap_used':used,'capmonster_balance':bal,'capmonster_warning':cap_warning})}\n\n"

        q: asyncio.Queue = asyncio.Queue()
        sem = asyncio.Semaphore(REFRESH_PARALLEL)  # anti rate-limit BetMexico

        async def _process(acc, slot_idx):
            email = acc["email"]
            try:
                if slot_idx >= remaining:
                    await q.put({"type": "skip", "id": acc["id"], "email": email, "reason": "cap"})
                    return
                if not acc.get("password"):
                    await q.put({"type": "skip", "id": acc["id"], "email": email, "reason": "no_password"})
                    return
                # Cuarentena (forense 2026-07-11): NO re-loguear cuentas quemadas.
                # DEAD = terminal; cooldown activo = enfriando tras rate-limit.
                # Re-martillarlas quema captcha y alimenta la ráfaga (causa #1+#2).
                if acc.get("status") == "DEAD":
                    await q.put({"type": "skip", "id": acc["id"], "email": email, "reason": "dead"})
                    return
                from deposits import _cooldown_active, _cooldown_remaining_min
                if _cooldown_active(acc.get("cooldown_until")):
                    await q.put({"type": "skip", "id": acc["id"], "email": email,
                                 "reason": "cooldown",
                                 "cooldown_min": _cooldown_remaining_min(acc.get("cooldown_until"))})
                    return
                # Anti-abuso CapMonster: operadores NO pueden refrescar cuentas sin JWT vivo.
                # Hacerlo forzaría un login fresco (= captcha = gasto). Solo el jwt_keeper
                # automatizado (SA) debe renovar sesiones muertas. SA puede siempre.
                if not is_sa:
                    _jexp = acc.get("jwt_expires_at")
                    _jwt_alive = (
                        _jexp not in (None, "")
                        and int(_jexp) > time.time() + 60
                    )
                    if not _jwt_alive:
                        await q.put({"type": "skip", "id": acc["id"], "email": email,
                                     "reason": "no_jwt",
                                     "error": "Cuenta en descanso — espera a que el sistema la recupere"})
                        return
                # Throttle: max N logins concurrentes para no triggear rate-limit
                async with sem:
                    result = await _run_prewarm(operator_id, email, acc["password"])
                # Si el login falló, emitir fail con razón clara
                if not result or not result.get("ok"):
                    err = (result or {}).get("error") or (result or {}).get("status") or "login falló"
                    await q.put({"type": "fail", "id": acc["id"], "email": email, "error": err})
                    return
                # Lee la fila ya actualizada
                with _app_db() as cc:
                    r = cc.execute(
                        "SELECT a.id, a.email, a.password, a.balance_total, a.balance_real, "
                        "a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, "
                        "a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, a.check_count, "
                        "a.jwt_expires_at, a.dead_reason, a.cooldown_until, "
                        "COALESCE(a.published_to_pool,1) AS published_to_pool, "
                        "(SELECT COUNT(*) FROM account_cards ac WHERE ac.account_email=a.email) AS cards_count, "
                        "(SELECT COUNT(*) FROM account_notes an WHERE an.account_email=a.email "
                        " AND COALESCE(an.note_text,'') != '') AS notes_count "
                        "FROM accounts a WHERE a.id=?",
                        (acc["id"],),
                    ).fetchone()
                if r:
                    row = dict(r)
                    # Resolver locked_by a display name (igual que list_accounts)
                    if row.get("locked_by"):
                        from app import _resolve_operator
                        from auth import USER_COLORS
                        raw = row["locked_by"]
                        row["locked_by"] = _resolve_operator(raw)
                        try:
                            row["locked_color"] = USER_COLORS.get(int(raw))
                        except (ValueError, TypeError):
                            row["locked_color"] = None

                    _exp = row.pop("jwt_expires_at", None)
                    _dr = row.pop("dead_reason", None)
                    _cd = row.pop("cooldown_until", None)
                    if is_sa:
                        row["jwt_alive"] = bool(
                            _exp not in (None, "")
                            and int(_exp) > datetime.now(timezone.utc).timestamp() + 60)
                        row["needs_reset"] = bool(
                            row.get("status") == "DEAD"
                            and str(_dr or "") in ("LOGIN_DENIED", "ATTEMPT_LIMIT"))
                        _now = datetime.now(timezone.utc).timestamp()
                        try:
                            row["cooldown_min"] = max(0, round((int(_cd) - _now) / 60)) if _cd not in (None, "") and int(_cd) > _now else 0
                        except (TypeError, ValueError):
                            row["cooldown_min"] = 0

                    await q.put({"type": "account", "data": row})
                else:
                    await q.put({"type": "fail", "id": acc["id"], "email": email, "error": "row not found"})
            except Exception as e:
                logger.warning(f"[refresh-stream] {email}: {e}")
                await q.put({"type": "fail", "id": acc["id"], "email": email, "error": str(e)[:120]})

        # Lanza todo en paralelo (asyncio gather con producción a la queue)
        tasks = [asyncio.create_task(_process(acc, i)) for i, acc in enumerate(accs)]

        done_count = 0
        last_keepalive = asyncio.get_event_loop().time()
        while done_count < len(accs):
            if await request.is_disconnected():
                # Cliente cerró la conexión — cancelar tasks en vuelo para no quemar captchas
                for t in tasks:
                    if not t.done():
                        t.cancel()
                break
            try:
                ev = await asyncio.wait_for(q.get(), timeout=2.0)
                yield f"data: {json.dumps(ev)}\n\n"
                done_count += 1
                last_keepalive = asyncio.get_event_loop().time()
            except asyncio.TimeoutError:
                # Heartbeat para mantener la conexión viva
                yield f": ping\n\n"
                # Si todas las tasks terminaron pero la queue se vació, salir
                if all(t.done() for t in tasks) and q.empty():
                    break

        yield f"data: {json.dumps({'type':'done','total':len(accs),'completed':done_count})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
