"""Depósitos — endpoint que reusa el core de v1 (_run_deposit) si está disponible.

En el VPS, los módulos del bot viven en /opt/betmexico/bot/ y son visibles porque
el systemd unit declara WorkingDirectory=/opt/betmexico/bot. En dev local estos
imports fallan y el endpoint devuelve 503.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from auth import require_session

logger = logging.getLogger("betmexico.dashboard.deposits")
router = APIRouter(prefix="/api/deposits", tags=["deposits"])

# Caps duros (anti 3DS, anti-baneo)
DEP_MAX_PER_TXN = 499.0   # >$499 dispara 3DS prácticamente garantizado
DEP_MAX_24H = 1499.0      # tope acumulado por cuenta en 24h vía dashboard

# Auto-lock al iniciar depósito (horas)
AUTOLOCK_HOURS_SINGLE = 2
AUTOLOCK_HOURS_MULTI = 2
AUTOLOCK_HOURS_SCHEDULED = 4  # más amplio porque corre N reps cada 1 min


# ── Helpers de captcha pool (scheduled / multi) ─────────────────────────────
# Bug observado 2026-05-23: en /scheduled, después del sleep(60) el token del
# pool estaba expirado (TOKEN_MAX_AGE=55s) y get_token tenía que esperar al
# factory loop a producir uno nuevo — a veces tomaba 70s+. Solución:
# `_drain_stale_tokens` saca los tokens viejos del pool y dispara prefetch
# fresh. Llamarse ~10s antes del próximo intento (en el sleep dinámico) y como
# red de seguridad al iniciar cada iter.

def _drain_stale_tokens(pool, max_age: float = 30.0) -> int:
    """Saca del pool todos los tokens con edad > max_age. Devuelve cuántos drenó.
    Los tokens válidos los reinserta. No-throws."""
    if pool is None or not hasattr(pool, "pool"):
        return 0
    fresh: list = []
    drained = 0
    try:
        while True:
            try:
                item = pool.pool.get_nowait()
            except Exception:
                break
            try:
                _tok, _tid, ts = item
                age = time.time() - ts
                if age <= max_age:
                    fresh.append(item)
                else:
                    drained += 1
            except Exception:
                # Estructura inesperada → descartar
                drained += 1
        for item in fresh:
            try:
                pool.pool.put_nowait(item)
            except Exception:
                pass
        if drained > 0:
            logger.info(f"[Captcha] drained {drained} stale token(s) (edad >{max_age}s)")
    except Exception as e:
        logger.warning(f"[Captcha] _drain_stale_tokens err: {e}")
    return drained


async def _ensure_fresh_captcha(pool, wait_for_solve: float = 8.0) -> None:
    """Garantiza que el pool tenga al menos 1 token <30s de edad.
    Si después del drain queda 0, dispara prefetch y espera hasta `wait_for_solve`
    segundos. No bloquea más de eso — `get_token` después manejará el caso."""
    if pool is None:
        return
    _drain_stale_tokens(pool, max_age=30.0)
    try:
        qsize = pool.pool.qsize() if hasattr(pool, "pool") else 0
    except Exception:
        qsize = 0
    if qsize == 0:
        try:
            asyncio.create_task(pool.prefetch(1))
        except Exception:
            pass
        # Espera corta para dar tiempo al solve (~4-7s típico)
        deadline = time.time() + wait_for_solve
        while time.time() < deadline:
            try:
                if pool.pool.qsize() > 0:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)


# ── Tracking de BINes que lanzan 3DS ────────────────────────────────────────
# Cada vez que detectamos 3DS en un intento → incrementamos total_3ds del BIN
# correspondiente. Endpoint `/api/deposits/bin-check` permite al frontend
# preguntar antes del intento si el BIN tiene historial 3DS y avisar al user.

def _record_bin_3ds(bin6: str) -> None:
    """Incrementa total_3ds + last_3ds_at en bin_stats. UPSERT-safe."""
    if not bin6 or len(bin6) < 6:
        return
    bin6 = bin6[:6]
    from app import db
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db(write=True) as c:
            # Intentar UPDATE primero
            cur = c.execute(
                "UPDATE bin_stats SET "
                "total_3ds = COALESCE(total_3ds, 0) + 1, "
                "last_3ds_at = ?, "
                "updated_at = ? "
                "WHERE bin = ?",
                (now, now, bin6),
            )
            if cur.rowcount == 0:
                # No existía → INSERT
                c.execute(
                    "INSERT INTO bin_stats (bin, total_attempts, total_approved, "
                    "total_rejected, total_3ds, last_3ds_at, updated_at) "
                    "VALUES (?, 0, 0, 0, 1, ?, ?)",
                    (bin6, now, now),
                )
        logger.info(f"[Deposits] BIN {bin6} marcado como 3DS-prone")
    except Exception as e:
        logger.warning(f"[Deposits] _record_bin_3ds error: {e}")


def _bin_3ds_stats(bin6: str) -> dict:
    """Lee historial 3DS de un BIN. Devuelve dict con count, last_seen, total_attempts."""
    if not bin6 or len(bin6) < 6:
        return {"bin": bin6, "total_3ds": 0, "last_3ds_at": None,
                "total_attempts": 0, "total_approved": 0}
    bin6 = bin6[:6]
    from app import db
    try:
        with db() as c:
            r = c.execute(
                "SELECT bin, COALESCE(total_3ds,0) AS total_3ds, last_3ds_at, "
                "COALESCE(total_attempts,0) AS total_attempts, "
                "COALESCE(total_approved,0) AS total_approved "
                "FROM bin_stats WHERE bin = ?",
                (bin6,),
            ).fetchone()
            if not r:
                return {"bin": bin6, "total_3ds": 0, "last_3ds_at": None,
                        "total_attempts": 0, "total_approved": 0}
            return dict(r)
    except Exception:
        return {"bin": bin6, "total_3ds": 0, "last_3ds_at": None,
                "total_attempts": 0, "total_approved": 0}


@router.get("/bin-check/{bin6}")
def bin_check(bin6: str, _user: dict = Depends(require_session)):
    """Devuelve historial 3DS del BIN para que el frontend avise al user.
    `is_3ds_prone = total_3ds >= 1` (cualquier 3DS previo es señal)."""
    stats = _bin_3ds_stats(bin6[:6] if bin6 else "")
    stats["is_3ds_prone"] = stats.get("total_3ds", 0) >= 1
    return stats


def _auto_lock_for_deposit(
    account_id: int,
    operator_id: int,
    user: dict,
    hours: int = AUTOLOCK_HOURS_SINGLE,
) -> None:
    """Lockea la cuenta para el operador que arranca el depósito.

    - Si ya está lockeada por el mismo operador → refresh (idempotente)
    - Si está lockeada por OTRO operador:
        * SA puede override
        * non-SA → 409 Conflict
    - Si no está lockeada → toma el lock
    Broadcasta evento `kind:lock` con flag `auto:True` para distinguir del manual.
    """
    from app import db, _broadcast
    now = datetime.now(timezone.utc)
    locked_at = now.isoformat()
    locked_until = (now + timedelta(hours=hours)).isoformat()
    is_sa = user.get("role") == "superadmin"

    with db(write=True) as c:
        row = c.execute(
            "SELECT locked_by, email FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Cuenta no encontrada")
        cur_lock = row["locked_by"]
        # Normalizar cur_lock para comparar contra operator_id (int)
        try:
            cur_lock_int = int(cur_lock) if cur_lock else None
        except (TypeError, ValueError):
            cur_lock_int = None
        if cur_lock and cur_lock_int != operator_id and not is_sa:
            raise HTTPException(409, f"Cuenta lockeada por otro operador ({cur_lock}). Espera o pide al SA que libere.")
        c.execute(
            "UPDATE accounts SET locked_by=?, locked_at=?, locked_until=? WHERE id=?",
            (str(operator_id), locked_at, locked_until, account_id),
        )
        email = row["email"]
    try:
        from app import _resolve_who
        _broadcast({
            "type": "activity", "kind": "lock",
            "ts": locked_at, **_resolve_who(operator_id), "target": email,
            "id": account_id, "locked_until": locked_until,
            "auto": True,
        })
    except Exception:
        pass


def _window_status(email: str) -> dict:
    """Estado de la ventana de 24h desde el PRIMER depósito aprobado.
    - Si no hay deps aprobados en últimas 24h → window cerrada, disponible $1499
    - Si hay → window abierta, expires_at = first_at + 24h, available = 1499 - used
    """
    from app import db
    import sqlite3
    out = {
        "used": 0.0, "available": DEP_MAX_24H,
        "first_at": None, "expires_at": None, "in_window": False,
    }
    try:
        with db() as c:
            rows = c.execute(
                "SELECT created_at, amount FROM deposit_attempts "
                "WHERE account_email=? AND status='approved' "
                "AND created_at >= datetime('now','-24 hours') "
                "ORDER BY created_at ASC",
                (email,),
            ).fetchall()
    except sqlite3.OperationalError:
        return out
    if not rows:
        return out
    # Parse fechas (sqlite str → datetime UTC naive)
    def _parse(s):
        try:
            return datetime.fromisoformat(s.replace(" ", "T").replace("Z", "+00:00"))
        except Exception:
            return None
    first_at = _parse(rows[0]["created_at"])
    if not first_at:
        return out
    if first_at.tzinfo is None:
        first_at = first_at.replace(tzinfo=timezone.utc)
    expires_at = first_at + timedelta(hours=24)
    used = sum(float(r["amount"] or 0) for r in rows)
    out.update({
        "used": used, "available": max(0.0, DEP_MAX_24H - used),
        "first_at": first_at.isoformat(), "expires_at": expires_at.isoformat(),
        "in_window": True,
    })
    return out


def _check_caps(email: str, amount: float, projected_extra: float = 0.0) -> Optional[str]:
    """Devuelve string de error si viola cap, None si OK.
    `projected_extra` = monto adicional ya proyectado (ej. schedule: amount * reps_extra)."""
    if amount > DEP_MAX_PER_TXN:
        return f"Máximo ${DEP_MAX_PER_TXN:.0f} por intento (>${DEP_MAX_PER_TXN:.0f} dispara 3DS)"
    win = _window_status(email)
    needed = amount + projected_extra
    if needed > win["available"]:
        if win["in_window"]:
            return (f"Excede cap 24h. Ya depositados ${win['used']:.2f}, "
                    f"disponible ${win['available']:.2f}. La window cierra a las "
                    f"{win['expires_at'][:16].replace('T',' ')} UTC")
        return f"Excede cap por txn ${DEP_MAX_PER_TXN:.0f} (intentas ${needed:.2f})"
    return None


def _load_deps():
    """Reusa deps ya cargadas eager en app.py (evita circular imports)."""
    try:
        from app import BOT_RUN_DEPOSIT, BOT_MAKE_POOL, BOT_DEPS_OK
        if BOT_DEPS_OK and BOT_RUN_DEPOSIT and BOT_MAKE_POOL:
            return BOT_RUN_DEPOSIT, BOT_MAKE_POOL
    except Exception as e:
        logger.warning(f"[Deposits] deps no disponibles: {e}")
    return None, None


def _parse_pipe(pipe: str) -> tuple[str, str, str]:
    """Acepta:
      - 4242424242424242|1228|123     (MMYY junto)
      - 4242424242424242|12/28|123    (legacy con diagonal)
      - 4242424242424242|12|28|123    (4 partes)
    Retorna (ccnum, "MM/YY", cvv) — el formato interno con diagonal es
    el que espera el core de v1; el operador NO ve esto.
    """
    parts = [p.strip() for p in (pipe or "").replace(" ", "").split("|") if p.strip()]
    if len(parts) == 3:
        ccnum, exp, cvv = parts
        if "/" in exp:
            return ccnum, exp, cvv
        # MMYY o MMYYYY → MM/YY
        if len(exp) == 4:
            return ccnum, f"{exp[:2]}/{exp[2:]}", cvv
        if len(exp) == 6:
            return ccnum, f"{exp[:2]}/{exp[4:]}", cvv
        raise ValueError("Vencimiento inválido (usa MMYY)")
    if len(parts) == 4:
        return parts[0], f"{parts[1]}/{parts[2][-2:]}", parts[3]
    raise ValueError("Formato pipe inválido. Usa: numero|MMYY|CVV")


# ── Velocity check: misma tarjeta en cuentas distintas → bloqueo de pasarela ──
# Regla operativa (Robert 2026-05-15):
#   - Las primeras 2 cuentas distintas con la misma tarjeta APROBADAS NO tienen
#     cooldown (el matchmaker hace pares rápidos a propósito).
#   - A partir del 3er APROBADO, cooldown mínimo de 1 minuto desde el último
#     APROBADO en cuenta distinta. Esto evita el patrón "1 tarjeta en muchas
#     cuentas en segundos" que la pasarela detecta como fraude.
#   - SOLO cuentan los aprobados (status='approved'). Los rechazos no
#     ensucian la tarjeta para la pasarela en cuanto a velocity; ya están
#     cubiertos por otras señales del propio gateway.
#   - La ventana de "memoria" es de 30 min — pasado ese tiempo, la tarjeta
#     vuelve a ser "fresca" y se reinicia el contador.
CARD_VELOCITY_MEMORY_MIN = 30      # ventana donde contamos aprobados distintos
CARD_VELOCITY_FREE_PAIR = 2        # primeros N aprobados en cuentas distintas sin cooldown
CARD_VELOCITY_COOLDOWN_SEC = 60    # cooldown a partir del N+1 aprobado


def _check_card_velocity(card_pipe: str, account_email: str) -> Optional[dict]:
    """None = OK proceder. dict = bloquear.
    Cuenta APROBADOS con esta card_pipe en cuentas distintas en últimos 30min.
    Si ya hay 2+ aprobados distintos y el último fue hace <60s → bloquea."""
    if not card_pipe or not account_email:
        return None
    from app import db
    try:
        with db() as c:
            rows = c.execute(
                "SELECT account_email, created_at, "
                "(strftime('%s','now') - strftime('%s', created_at)) AS age_sec "
                "FROM deposit_attempts "
                "WHERE card_pipe=? AND account_email != ? "
                "AND status='approved' "
                "AND created_at > datetime('now', ?) "
                "ORDER BY created_at DESC LIMIT 20",
                (card_pipe, account_email, f"-{CARD_VELOCITY_MEMORY_MIN} minutes"),
            ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    others = sorted({r["account_email"] for r in rows})
    distinct_count = len(others)
    last_age_sec = int(rows[0]["age_sec"] or 0)
    # Primeras N cuentas libres (esta cuenta sería la #distinct_count+1)
    if distinct_count < CARD_VELOCITY_FREE_PAIR:
        return None
    # Ya hay 2+ cuentas distintas → exigir cooldown
    if last_age_sec >= CARD_VELOCITY_COOLDOWN_SEC:
        return None
    wait_sec = CARD_VELOCITY_COOLDOWN_SEC - last_age_sec
    return {
        "blocked": True,
        "reason": "CARD_VELOCITY",
        "message": (f"Tarjeta ya usada en {distinct_count} cuenta(s) distinta(s). "
                    f"Espera {wait_sec}s para enfriar antes de probar otra "
                    f"(política: primeras {CARD_VELOCITY_FREE_PAIR} libres, después "
                    f"{CARD_VELOCITY_COOLDOWN_SEC}s entre cuentas)."),
        "other_accounts": others,
        "distinct_count": distinct_count,
        "last_seen": rows[0]["created_at"],
        "last_age_sec": last_age_sec,
        "wait_sec": wait_sec,
        "free_pair": CARD_VELOCITY_FREE_PAIR,
        "cooldown_sec": CARD_VELOCITY_COOLDOWN_SEC,
    }


def _record_attempt(
    attempt_id: str,
    email: str,
    amount: float,
    status: str,
    rejection_reason: Optional[str],
    duration_ms: int,
    operator_id: int,
    card_pipe: Optional[str] = None,
    result_raw: Optional[dict] = None,
    balance_before: Optional[float] = None,
    balance_after: Optional[float] = None,
) -> None:
    """Persiste el intento en deposit_attempts + recalc grade + broadcast SSE.

    Histórico (2026-05-11 → 2026-05-22): este helper SOLO hacía broadcast
    porque `_run_deposit._persist_final` ya escribía en BD. Pero el endpoint
    `/execute-stream` usa `_run_deposit_with_phases` que NO escribe — y este
    helper era el único llamado, dejando los attempts sin persistir.
    Fix 2026-05-23: re-habilitada escritura. Idempotente por attempt_id
    (INSERT OR IGNORE) para evitar duplicación si `_persist_final` ya escribió.
    """
    from app import _broadcast
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    # ── 1. Persistir en BD ──────────────────────────────────────
    try:
        from betmexico_db import db as _bot_db
        # log_attempt internamente hace INSERT OR IGNORE por attempt_id
        _bot_db.log_attempt(
            attempt_id=attempt_id,
            batch_id=None,
            account_email=email,
            card_id=None,  # /execute-stream no resuelve card_id (no es crítico)
            amount=float(amount or 0.0),
            source="manual_single",
            operator_id=int(operator_id) if operator_id else None,
            status=status,
            gateway_response_raw=(json.dumps(result_raw, ensure_ascii=False, default=str)[:4000]
                                   if result_raw else None),
            gateway_txn_id=(result_raw or {}).get("txn_id"),
            balance_before=balance_before,
            balance_after=balance_after,
            duration_ms=int(duration_ms) if duration_ms is not None else None,
            rejection_reason=rejection_reason,
            mission_id=None,
            card_pipe=card_pipe,
        )
    except Exception as e:
        logger.error(f"[Deposits] _record_attempt log_attempt error: {e}")

    # ── 2. Persistir tarjeta en account_cards si APPROVED ──────
    # Histórico: el wrapper `_run_deposit_with_phases` (usado por single/execute-stream,
    # multi/stream y scheduled/create) NO llama a `register_card_to_account` — solo el
    # legacy `_run_deposit` del bot lo hacía. Resultado: tras un APPROVED por estos
    # endpoints, la tarjeta no quedaba ligada a la cuenta y el operador tenía que
    # volverla a pegar manualmente. Fix 2026-05-25: persistimos aquí (idempotente
    # por UNIQUE card_number — INSERT OR IGNORE).
    # Regla operativa (Robert): solo APPROVED real cuenta. 3DS_REQUIRED no guarda
    # porque la tarjeta no se acreditó.
    if status == "approved" and card_pipe:
        try:
            cc_num, cc_exp, cc_cvv = _parse_pipe(card_pipe)
            from betmexico_db import db as _bot_db
            # Buscar password de la cuenta (la firma de register_card_to_account
            # requiere el marriage completo email+password).
            from app import db as _dash_db
            with _dash_db() as c:
                acc_row = c.execute(
                    "SELECT password FROM accounts WHERE email=?", (email,)
                ).fetchone()
            password = acc_row["password"] if acc_row else ""
            # registered_by_name: resolver del roster por telegram_id (con casing original)
            from web_auth import WEB_USERS_RAW as _USERS_RAW
            op_name = ""
            for uname, u in _USERS_RAW.items():
                if u.get("telegram_id") == operator_id:
                    op_name = uname
                    break
            _bot_db.register_card_to_account(
                cc_num, cc_exp, cc_cvv,
                email, password,
                int(operator_id) if operator_id else 0,
                op_name,
            )
        except Exception as e:
            logger.warning(f"[Deposits] _record_attempt register_card_to_account error: {e}")

    # ── 3. Recalcular grade (BD viva) ──────────────────────────
    try:
        from web_grading import recalc_grade_from_db
        recalc_grade_from_db(email)
    except Exception as e:
        logger.debug(f"[Deposits] _record_attempt recalc_grade: {e}")

    # ── 4. Broadcast SSE para feed de actividad ────────────────
    try:
        from app import _resolve_who
        _broadcast({
            "type": "activity",
            "kind": "deposit",
            "ts": now_str,
            **_resolve_who(operator_id),
            "target": email,
            "amount": amount,
            "status": status,
            "reason": rejection_reason,
            "duration_ms": duration_ms,
            "card_pipe": card_pipe,
        })
    except Exception:
        pass


# ── Wrapper con visibilidad de fases ─────────────────────────────────────────
# Orquesta el depósito llamando funciones bajas del bot (get_jwt, begin_deposit,
# submit_card, check_transaction) directamente y emite eventos entre cada paso.
# NO escribe en BD, NO quema tarjetas — eso lo hace _run_deposit del bot. Este
# wrapper es solo para visibilidad live (stepper UI). El caller persiste el
# resultado vía _record_attempt + db.log_attempt.

async def _safe_phase(cb, name: str, payload: dict) -> None:
    """Llama phase_cb tragándose excepciones. Si cb es None, no-op."""
    if cb is None:
        return
    try:
        await cb(name, payload)
    except Exception as e:
        logger.warning(f"[Deposits] phase_cb error en '{name}': {e}")


def _build_admin_proxy_url() -> Optional[str]:
    """Construye URL de proxy admin (http://user:pass@server) para httpx.
    Wrapper sobre proxy_pool (combina bot + extras locales del dashboard)."""
    from proxy_pool import build_admin_proxy_url
    return build_admin_proxy_url()


async def _run_deposit_with_phases(
    email: str,
    password: str,
    cc_num: str,
    cc_exp: str,
    cc_cvv: str,
    amount: float,
    user: dict,
    pool,
    phase_cb,  # Callable[[str, dict], Awaitable[None]] | None
    proxy: Optional[str] = None,
    persist_login_data: bool = True,
    session_jwt: Optional[str] = None,
    session_proxy: Optional[str] = None,
) -> dict:
    """Orquesta deposit emitiendo fases. Mismo shape que _run_deposit.

    NO escribe en BD. NO quema tarjetas. NO maneja marriage.
    Solo visibilidad — caller persiste resultado.

    Returns:
      {"success": bool, "result_code": str, "error": str|None, "duration_ms": int}
    """
    try:
        from betmexico_login_service import get_jwt as _get_jwt
        from betmexico_deposit import (
            begin_deposit as _begin_deposit,
            submit_card as _submit_card,
            check_transaction as _check_transaction,
        )
    except ImportError as e:
        # Bot deps no cargados — devolver error sin crashear
        await _safe_phase(phase_cb, "done", {
            "success": False, "result_code": "DEPS_MISSING", "error": str(e)
        })
        return {"success": False, "result_code": "DEPS_MISSING",
                "error": f"Bot deps no disponibles: {e}", "duration_ms": 0}

    t_total = time.time()
    # used_proxy se setea adentro del failover. Caller puede pasar proxy explícito
    # para forzar uno; si None, el failover rota por el pool.
    used_proxy: Optional[str] = None

    # ── PASO 1: Login (o reuso de sesión) ─────────────────────────────────
    jwt = None
    login_result: dict = {}
    from_cache = False

    if session_jwt:
        # Reuso de sesión (scheduled iter>0): el JWT de BetMexico vive ~7 días
        # (medido en prod) y se obtuvo hace ~1 min en la iter 0 de este run —
        # saltamos login + captcha por completo. used_proxy se hereda para
        # mantener afinidad de IP durante todo el run (misma IP = más natural
        # para el antifraude). Esto NO es el JWT-cache de BD de hace días (que
        # da 401 silencioso); es el token recién validado de ESTE run.
        jwt = session_jwt
        used_proxy = session_proxy
        await _safe_phase(phase_cb, "login_reused", {
            "ok": True, "duration_ms": 0, "reused": True,
        })
    else:
        await _safe_phase(phase_cb, "login_start", {})
        t0 = time.time()
        try:
            # use_cache=False: mirrors prewarm.py — un JWT cacheado puede devolver 401
            # silencioso y balance=0 falso. Para depósitos eso es inaceptable.
            # Failover real: si el primer proxy timeout, rota al siguiente.
            from proxy_pool import call_with_proxy_failover
            # max_retries=1: get_jwt hace 1 intento de captcha por IP (no quema 3 en
            # la misma IP quemada). El retry-con-rotación-de-IP lo maneja
            # call_with_proxy_failover, que es donde está el token de captcha bueno.
            (jwt, login_result), used_proxy = await call_with_proxy_failover(
                _get_jwt, email, password, pool, proxy=proxy, use_cache=False,
                max_retries=1,
            )
        except Exception as e:
            logger.error(f"[Deposits/phases] get_jwt {email}: {e}")
            login_result = {"status": "ERROR", "error": str(e)}
        login_ms = int((time.time() - t0) * 1000)
        from_cache = bool(
            isinstance(login_result, dict) and login_result.get("from_cache")
        )

        if not jwt:
            await _safe_phase(phase_cb, "login_done", {
                "ok": False, "duration_ms": login_ms, "from_cache": from_cache,
            })
            err = None
            if isinstance(login_result, dict):
                err = login_result.get("error") or login_result.get("status")
            err = err or "Login falló"
            await _safe_phase(phase_cb, "done", {
                "success": False, "result_code": "LOGIN_FAILED", "error": err,
            })
            return {
                "success": False, "result_code": "LOGIN_FAILED",
                "error": err, "duration_ms": int((time.time() - t_total) * 1000),
            }

        await _safe_phase(phase_cb, "login_done", {
            "ok": True, "duration_ms": login_ms, "from_cache": from_cache,
        })

    # ── Persistir detalles del login en BD ───────────────────────────────
    # persist_login_data=False (scheduled iter>0): skip — _record_attempt
    # ya recalcula grade; upsert/txns solo aportan en la primera iteración
    # de una secuencia sobre la misma cuenta.
    if persist_login_data:
        try:
            from betmexico_db import db as _bot_db
            from web_grading import recalc_grade_from_db
            if login_result and not from_cache:
                await asyncio.to_thread(
                    _bot_db.upsert_account, login_result, user.get("telegram_id", 0)
                )
                txns_data = (login_result.get("account_details") or {}).get("transactions", {}) or {}
                txn_items = txns_data.get("items") or []
                if txn_items:
                    await asyncio.to_thread(
                        _bot_db.save_account_transactions,
                        email, txn_items, user.get("telegram_id", 0),
                    )
                await asyncio.to_thread(recalc_grade_from_db, email)
        except Exception as e:
            logger.warning(f"[Deposits/phases] persist login details failed: {e}")

    # ── HTTPX client compartido para pasos 2/3/4 ──────────────────────────
    # Reusa el proxy que validó el login (afinidad — evita rotar a un proxy
    # potencialmente caído a mitad del flujo).
    client_kwargs = {"timeout": 30.0, "verify": False}
    if used_proxy:
        client_kwargs["proxy"] = used_proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        # ── PASO 2: begin_deposit ────────────────────────────────────────
        await _safe_phase(phase_cb, "gateway_begin", {})
        t0 = time.time()
        try:
            step1 = await _begin_deposit(client, jwt, amount)
        except Exception as e:
            logger.error(f"[Deposits/phases] begin_deposit {email}: {e}")
            step1 = {"error": str(e)}
        begin_ms = int((time.time() - t0) * 1000)

        if "error" in step1:
            await _safe_phase(phase_cb, "gateway_begin_done", {
                "order_id": None, "ok": False, "duration_ms": begin_ms,
            })
            err = step1.get("error") or "begin_deposit falló"
            await _safe_phase(phase_cb, "done", {
                "success": False, "result_code": "BEGIN_ERROR", "error": err,
            })
            return {
                "success": False, "result_code": "BEGIN_ERROR",
                "error": err, "duration_ms": int((time.time() - t_total) * 1000),
            }

        order_id = step1.get("orderId", "")
        txn_id = step1.get("transactionId", "")
        await _safe_phase(phase_cb, "gateway_begin_done", {
            "order_id": order_id, "ok": True, "duration_ms": begin_ms,
        })

        # ── PASO 3: submit_card ──────────────────────────────────────────
        await _safe_phase(phase_cb, "gateway_submit", {"order_id": order_id})
        t0 = time.time()
        try:
            step2 = await _submit_card(client, cc_num, cc_exp, cc_cvv, order_id)
        except Exception as e:
            logger.error(f"[Deposits/phases] submit_card {email}: {e}")
            step2 = {"error": str(e)}
        submit_ms = int((time.time() - t0) * 1000)

        if "error" in step2:
            await _safe_phase(phase_cb, "gateway_submit_done", {
                "result_code": "ERROR", "is_3ds": False, "duration_ms": submit_ms,
            })
            err = step2.get("error") or "submit_card falló"
            await _safe_phase(phase_cb, "done", {
                "success": False, "result_code": "SUBMIT_ERROR", "error": err,
            })
            return {
                "success": False, "result_code": "SUBMIT_ERROR",
                "error": err, "duration_ms": int((time.time() - t_total) * 1000),
            }

        result_code = step2.get("resultCode", "UNKNOWN")
        payload = step2.get("payload", {}) or {}
        # Detección 3DS robusta (3 niveles):
        #
        # NIVEL 1 — flags explícitos del payload:
        is_3ds_explicit = bool(
            payload.get("threeDs")
            or payload.get("threeDS")
            or payload.get("three_ds")
            or payload.get("threeDsRequired")
            or payload.get("requires3DS")
            or payload.get("is3DS")
            or payload.get("redirectUrl")    # 3DS challenge URL
            or payload.get("acsUrl")          # Access Control Server (3DS)
            or step2.get("threeDs")
            or step2.get("redirectUrl")
        )
        # NIVEL 2 — 3DS implícito por JWT cardinal:
        # Cardinal Commerce 3DS 2.0 devuelve `payload={"jwt": "..."}` sin flags
        # explícitos. Bug visto 2026-05-23 con marckovzz40: el dashboard reportó
        # APPROVED pero la transacción quedó en "Created" (no acreditada) — era
        # 3DS pendiente. Detectamos: payload contiene SOLO jwt (sin otros campos
        # de éxito) → es 3DS challenge.
        is_3ds_via_jwt = bool(
            payload.get("jwt")
            and "transactionId" not in payload
            and "redirectStatus" not in payload
        )
        is_3ds = is_3ds_explicit or is_3ds_via_jwt
        # Log raw para diagnóstico (truncado a 1500 chars para no inundar)
        try:
            import json as _json
            logger.info(f"[Deposits/phases] {email} submit raw resultCode={result_code} "
                        f"is_3ds={is_3ds} payload_keys={list(payload.keys())[:15]} "
                        f"step2={_json.dumps(step2, default=str)[:1500]}")
        except Exception:
            pass

        await _safe_phase(phase_cb, "gateway_submit_done", {
            "result_code": result_code, "is_3ds": is_3ds,
            "duration_ms": submit_ms,
        })

        # ── 3DS detectado: NO llamar check_transaction ───────────────────
        if is_3ds:
            await _safe_phase(phase_cb, "done", {
                "success": False, "result_code": "3DS_REQUIRED",
                "error": "3DS_REQUIRED — Tarjeta requiere autenticación",
            })
            return {
                "success": False, "result_code": "3DS_REQUIRED",
                "error": "3DS_REQUIRED — Tarjeta requiere autenticación",
                "duration_ms": int((time.time() - t_total) * 1000),
                "raw_submit": step2,
            }

        # ── PASO 4: check_transaction ────────────────────────────────────
        await _safe_phase(phase_cb, "gateway_check", {})
        t0 = time.time()
        check_exc: Optional[str] = None
        try:
            step3 = await _check_transaction(client, jwt, txn_id)
        except Exception as e:
            logger.error(f"[Deposits/phases] check_transaction {email}: {e}")
            step3 = {"error": str(e)}
            check_exc = str(e)[:200]
        check_ms = int((time.time() - t0) * 1000)
        txn_status = (step3.get("transactionStatus", 0)
                      if "error" not in step3 else 0)

        # Log raw del check para diagnóstico
        try:
            import json as _json
            logger.info(f"[Deposits/phases] {email} check raw txnStatus={txn_status} "
                        f"step3={_json.dumps(step3, default=str)[:1500]}")
        except Exception:
            pass

        check_done_payload: dict = {
            "txn_status": txn_status, "duration_ms": check_ms,
        }
        # Surface el error si check_transaction explotó — submit_card pudo haber
        # devuelto BANK_APPROVED pero el check falló (network, timeout, etc.).
        # El caller decide si tratar esto como ambiguo (success=True pero sin
        # confirmación del banco).
        if check_exc is not None:
            check_done_payload["check_error"] = check_exc

        await _safe_phase(phase_cb, "gateway_check_done", check_done_payload)

    # ── Resultado final ──────────────────────────────────────────────────
    # Para considerar APPROVED REAL requerimos:
    #   1) resultCode == BANK_APPROVED del processorpay (lo que ya teníamos)
    #   2) transactionStatus == SUCCESS (6) en BetMexico — confirma que el
    #      depósito SE APLICÓ al balance. Si está pendiente (0) o failed (-4),
    #      el banco quizá aprobó pero BetMexico todavía no acreditó → no es real.
    # Si check_transaction falló por excepción (check_exc), aceptamos resultCode
    # solo para no perder approvals legítimos por network blips. Caveat: en ese
    # caso quedará marcado AMBIGUOUS para que el operador verifique manualmente.
    TXN_STATUS_SUCCESS = 6
    TXN_STATUS_PENDING = 0
    TXN_STATUS_FAILED = -4

    rc_ok = (result_code == "BANK_APPROVED")
    # NIVEL 3 — 3DS implícito post-check: la transacción se creó en BetMexico
    # pero quedó en status "Created"/"Pending" sin acreditar. Robert (2026-05-23):
    # "el 3d a veces no se nota, solo se queda ahí abierto... si se cierra el modal
    # sin darle cancelar, no nota el procesador que se intentó un pago".
    # Síntoma exacto: txnStatus=0 + transactionStatusDescription en (Created,Pending,Processing).
    status_desc = str((step3 or {}).get("transactionStatusDescription", "")).strip().lower()
    is_3ds_implicit = (
        rc_ok
        and txn_status == TXN_STATUS_PENDING
        and status_desc in ("created", "pending", "processing", "")
    )
    if is_3ds_implicit and not is_3ds:
        is_3ds = True
        # Re-emit done phase como 3DS para que UI lo muestre así
        await _safe_phase(phase_cb, "implicit_3ds_detected", {
            "txn_status_desc": status_desc, "txn_id": txn_id,
        })

    if is_3ds:
        # Cualquier 3DS (explícito o implícito) → no approved
        approved = False
        result_code = "3DS_REQUIRED"
        # Registrar BIN en bin_stats (total_3ds, last_3ds_at)
        try:
            _record_bin_3ds(cc_num[:6])
        except Exception as _e:
            logger.debug(f"[Deposits/phases] _record_bin_3ds: {_e}")
    elif rc_ok and check_exc is None:
        # Check válido y no 3DS → confiar en transactionStatus
        approved = (txn_status == TXN_STATUS_SUCCESS)
        if not approved:
            if txn_status == TXN_STATUS_PENDING:
                result_code = "PENDING_NOT_APPLIED"
            elif txn_status == TXN_STATUS_FAILED:
                result_code = "BANK_REJECTED_AFTER_APPROVE"
            else:
                result_code = f"UNKNOWN_TXN_STATUS_{txn_status}"
    elif rc_ok and check_exc is not None:
        # Check falló por network — aceptamos como ambiguo
        approved = True
        result_code = "BANK_APPROVED_UNVERIFIED"
    else:
        approved = False

    error_msg = None
    if not approved:
        if result_code == "3DS_REQUIRED":
            error_msg = "3DS_REQUIRED — BIN lanza 3DS (transacción no acreditada)"
        else:
            decline = (payload.get("message")
                       or payload.get("statusDescription")
                       or "decline genérico")
            error_msg = f"{result_code} — {decline}"

    await _safe_phase(phase_cb, "done", {
        "success": approved, "result_code": result_code, "error": error_msg,
    })

    return {
        "success": approved,
        "result_code": result_code,
        "error": error_msg,
        "duration_ms": int((time.time() - t_total) * 1000),
        "txn_id": txn_id,
        "order_id": order_id,
        "txn_status": txn_status,
        "raw_submit": step2,
        "raw_check": step3,
        "jwt": jwt,
        "used_proxy": used_proxy,
    }


@router.post("/execute")
async def deposit_execute(request: Request, user: dict = Depends(require_session)):
    _run_deposit, make_pool = _load_deps()
    if _run_deposit is None or make_pool is None:
        raise HTTPException(503, "Módulo de depósitos no disponible en este entorno")

    body = await request.json()
    try:
        account_id = int(body.get("account_id") or 0)
        amount = float(body.get("amount") or 0)
        card_pipe = (body.get("card_pipe") or "").strip()
    except (TypeError, ValueError):
        raise HTTPException(400, "Campos inválidos")

    if not account_id or not card_pipe or amount <= 0:
        raise HTTPException(400, "Faltan campos: account_id, card_pipe, amount")

    if amount < 1 or amount > DEP_MAX_PER_TXN:
        raise HTTPException(400, f"Monto fuera de rango (1-{DEP_MAX_PER_TXN:.0f})")

    try:
        cc_num, cc_exp, cc_cvv = _parse_pipe(card_pipe)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Lookup cuenta
    from app import db
    with db() as c:
        row = c.execute(
            "SELECT id, email, password FROM accounts WHERE id=? LIMIT 1",
            (account_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Cuenta no encontrada")

    email = row["email"]
    password = row["password"]
    operator_id = int(user.get("telegram_id") or 0)
    attempt_id = uuid.uuid4().hex

    # Cap check
    cap_err = _check_caps(email, amount)
    if cap_err:
        raise HTTPException(400, cap_err)

    # Velocity check (saltarse con force=true, solo SA)
    force = bool(body.get("force"))
    is_sa = (user.get("role") == "superadmin")
    if not (force and is_sa):
        vel = _check_card_velocity(card_pipe, email)
        if vel:
            raise HTTPException(409, {"detail": vel["message"], "velocity": vel})

    # Auto-lock: la cuenta queda lockeada para el operador. Otros operadores
    # NO la verán hasta que se libere (manual o expiración). Falla 409 si está
    # lockeada por otro y el caller no es superadmin.
    _auto_lock_for_deposit(account_id, operator_id, user, hours=AUTOLOCK_HOURS_SINGLE)

    # Pool de captcha — factory ON: el retry-con-rotación-de-IP puede pedir
    # varios tokens (1 por IP hasta acertar una limpia), y sin factory el pool
    # quedaría vacío tras el primer token → get_token() timeout en el reintento.
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")
    pool = None
    prefetch_task = None
    t0 = time.time()
    result = None
    _exc = None
    try:
        pool = make_pool(cap_key, size=1, workers=1)
        await pool.start_factory()
        prefetch_task = asyncio.create_task(pool.prefetch(1))

        result = await _run_deposit(
            email=email,
            password=password,
            cc_num=cc_num,
            cc_exp=cc_exp,
            cc_cvv=cc_cvv,
            amount=amount,
            user={"telegram_id": operator_id, "username": user.get("username", "")},
            pool=pool,
            save_card=True,
            check_marriage=False,
        )
    except BaseException as e:
        # BaseException = atrapa CancelledError también (Py 3.8+). Sin esto, el
        # client-disconnect mid-deposit dejaba `_record_attempt` sin correr → BD
        # sin row → tarjeta "quemada invisible".
        _exc = e
        logger.error(f"[Deposits] {email} ${amount}: {type(e).__name__}: {e}")
        # Re-raise abajo en el finally para que el _record_attempt corra primero
    finally:
        if prefetch_task is not None and not prefetch_task.done():
            prefetch_task.cancel()
            try:
                await prefetch_task
            except (asyncio.CancelledError, Exception):
                pass
        if pool is not None:
            try:
                await pool.stop()
            except Exception:
                pass
        # _record_attempt SIEMPRE — el finally garantiza row en BD aunque
        # CancelledError propague (cliente desconectó mid-deposit).
        duration_ms = int((time.time() - t0) * 1000)
        if _exc is not None:
            _record_attempt(
                attempt_id, email, amount, "error",
                f"{type(_exc).__name__}: {str(_exc)[:280]}",
                duration_ms, operator_id, card_pipe=card_pipe,
            )
        elif result is not None:
            success = bool(result.get("success"))
            _record_attempt(
                attempt_id, email, amount,
                "approved" if success else "rejected",
                result.get("error") or result.get("result_code"),
                duration_ms, operator_id, card_pipe=card_pipe,
            )

    if _exc is not None:
        # CancelledError → propagar bare (no la envolvemos en HTTPException;
        # debe seguir como cancelación). Exception normal → HTTPException 500
        # para que el frontend reciba mensaje útil en el toast.
        if isinstance(_exc, Exception):
            raise HTTPException(500, f"Error: {str(_exc)[:200]}")
        raise _exc

    duration_ms = int((time.time() - t0) * 1000)
    success = bool(result.get("success"))

    return {
        "success": success,
        "result_code": result.get("result_code"),
        "error": result.get("error"),
        "duration_ms": duration_ms,
        "attempt_id": attempt_id,
    }


@router.post("/execute-stream")
async def deposit_execute_stream(request: Request, user: dict = Depends(require_session)):
    """SSE variant de /execute — emite fases en vivo (login/begin/submit/check).

    Mismas validaciones que /execute (parse, cap, velocity, auto-lock).
    Body idéntico: `{account_id, card_pipe, amount, force?}`.

    Eventos SSE emitidos:
      - `{type:'start', attempt_id, email, amount}`
      - `{type:'phase', name, data}` — uno por fase (ver _run_deposit_with_phases)
      - `{type:'done', attempt_id, success, result_code, error, duration_ms}`
      - `{type:'fatal', attempt_id, error}` — solo si el generator explota
    """
    _run_deposit, make_pool = _load_deps()
    if _run_deposit is None or make_pool is None:
        raise HTTPException(503, "Módulo de depósitos no disponible en este entorno")

    body = await request.json()
    try:
        account_id = int(body.get("account_id") or 0)
        amount = float(body.get("amount") or 0)
        card_pipe = (body.get("card_pipe") or "").strip()
    except (TypeError, ValueError):
        raise HTTPException(400, "Campos inválidos")

    if not account_id or not card_pipe or amount <= 0:
        raise HTTPException(400, "Faltan campos: account_id, card_pipe, amount")

    if amount < 1 or amount > DEP_MAX_PER_TXN:
        raise HTTPException(400, f"Monto fuera de rango (1-{DEP_MAX_PER_TXN:.0f})")

    try:
        cc_num, cc_exp, cc_cvv = _parse_pipe(card_pipe)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Lookup cuenta
    from app import db
    with db() as c:
        row = c.execute(
            "SELECT id, email, password FROM accounts WHERE id=? LIMIT 1",
            (account_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Cuenta no encontrada")

    email = row["email"]
    password = row["password"]
    operator_id = int(user.get("telegram_id") or 0)

    # Cap check
    cap_err = _check_caps(email, amount)
    if cap_err:
        raise HTTPException(400, cap_err)

    # Velocity check (saltarse con force=true, solo SA) — mismo orden que /execute
    force = bool(body.get("force"))
    is_sa = (user.get("role") == "superadmin")
    if not (force and is_sa):
        vel = _check_card_velocity(card_pipe, email)
        if vel:
            raise HTTPException(409, {"detail": vel["message"], "velocity": vel})

    # Auto-lock antes de empezar a streamear
    _auto_lock_for_deposit(account_id, operator_id, user, hours=AUTOLOCK_HOURS_SINGLE)

    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")
    attempt_id = uuid.uuid4().hex

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()

        async def phase_cb(name: str, payload: dict) -> None:
            await queue.put({"type": "phase", "name": name, "data": payload})

        pool = None
        prefetch_task = None
        deposit_task = None
        t_start = time.time()
        result: dict = {}

        try:
            # Start event con attempt_id para que el frontend correlacione
            yield f"data: {json.dumps({'type':'start','attempt_id':attempt_id,'email':email,'amount':amount})}\n\n"

            pool = make_pool(cap_key, size=1, workers=1)
            await pool.start_factory()  # necesario: retry-con-rotación pide varios tokens
            prefetch_task = asyncio.create_task(pool.prefetch(1))

            # Lanza deposit en background — emite fases vía phase_cb → queue
            deposit_task = asyncio.create_task(
                _run_deposit_with_phases(
                    email=email, password=password,
                    cc_num=cc_num, cc_exp=cc_exp, cc_cvv=cc_cvv,
                    amount=amount,
                    user={"telegram_id": operator_id, "username": user.get("username", "")},
                    pool=pool,
                    phase_cb=phase_cb,
                )
            )

            # Drena la queue mientras el deposit corre. Heartbeat cada 2s si idle.
            while True:
                ev = None
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat — mantiene la conexión viva tras proxies/buffering
                    yield f": ping\n\n"
                    # Si la task terminó Y no hay más eventos pendientes → salir
                    if deposit_task.done() and queue.empty():
                        break
                # Si recibimos 'done' phase, también salimos (la task ya emitió todo)
                if ev is not None and ev.get("name") == "done":
                    break

            # Espera el resultado real (el wrapper ya terminó si vimos 'done')
            try:
                result = await deposit_task
            except Exception as e:
                logger.error(f"[execute-stream] deposit task error: {e}")
                result = {"success": False, "result_code": "ERROR", "error": str(e)[:300]}

            duration_ms = int((time.time() - t_start) * 1000)
            success = bool(result.get("success"))

            # Evento final del stream (cierre lógico para el cliente SSE)
            # _record_attempt vive en finally para garantizar persistencia incluso si el cliente
            # se desconecta antes de recibir el 'done' (FastAPI cierra el async gen mid-stream).
            yield "data: " + json.dumps({
                "type": "done",
                "attempt_id": attempt_id,
                "success": success,
                "result_code": result.get("result_code"),
                "error": result.get("error"),
                "duration_ms": duration_ms,
            }) + "\n\n"

        except Exception as e:
            logger.error(f"[execute-stream] generator error: {e}")
            yield f"data: {json.dumps({'type':'fatal','attempt_id':attempt_id,'error':str(e)[:300]})}\n\n"
        finally:
            # Cancelar deposit_task primero si sigue corriendo — log de warning para
            # rastrear casos donde submit_card pudo haber aprobado pero perdimos visibilidad.
            if deposit_task is not None and not deposit_task.done():
                logger.warning(
                    f"[execute-stream] {email} deposit_task cancelled mid-flight — outcome may be unknown"
                )
                deposit_task.cancel()
                try:
                    await deposit_task
                except (asyncio.CancelledError, Exception):
                    pass
            # Si no capturamos result en el try (early disconnect antes del await), intenta
            # rescatarlo de la task ya terminada para no perder la entrada del activity feed.
            # NOTA: asyncio.CancelledError es BaseException (no Exception) en Python 3.8+,
            # por eso capturamos BaseException aquí — un except Exception dejaría escapar
            # CancelledError y se perdería _record_attempt en disconnects.
            if not result and deposit_task is not None and deposit_task.done():
                try:
                    result = deposit_task.result() or {}
                except BaseException:
                    result = {}
            # Persistir en feed/BD (broadcast SSE al bus global). Se ejecuta SIEMPRE que tengamos
            # data — incluso si el cliente se desconectó antes del 'done'. Envuelto en try/except
            # para que un fallo de broadcast no rompa la limpieza del pool.
            if result:
                try:
                    duration_ms_final = int((time.time() - t_start) * 1000)
                    success_final = bool(result.get("success"))
                    # Mapping de status alineado con _persist_final
                    rc = result.get("result_code") or ""
                    if success_final:
                        status_final = "approved"
                    elif rc in ("LOGIN_FAILED", "CAPTCHA_POOL_EMPTY"):
                        status_final = "login_lost"
                    elif rc in ("BEGIN_ERROR", "PAYMENT_ERROR"):
                        status_final = "gateway_error"
                    elif rc == "TIMEOUT":
                        status_final = "timeout"
                    else:
                        status_final = "rejected"
                    reason_final = result.get("error") or rc or None
                    _record_attempt(
                        attempt_id, email, amount, status_final, reason_final,
                        duration_ms_final, operator_id,
                        card_pipe=card_pipe,
                        result_raw=result,
                        balance_after=result.get("balance_real"),
                    )
                except Exception as e:
                    logger.error(f"[execute-stream] _record_attempt error: {e}")
            if prefetch_task is not None and not prefetch_task.done():
                prefetch_task.cancel()
                try:
                    await prefetch_task
                except (asyncio.CancelledError, Exception):
                    pass
            if pool is not None:
                try:
                    await pool.stop()
                except Exception:
                    pass

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/cap-status/{account_id}")
def cap_status(account_id: int, _user: dict = Depends(require_session)):
    """Estado del cap de 24h para una cuenta — para mostrar en el modal."""
    from app import db
    with db() as c:
        row = c.execute("SELECT email FROM accounts WHERE id=?", (account_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Cuenta no encontrada")
    win = _window_status(row["email"])
    return {
        "max_per_txn": DEP_MAX_PER_TXN,
        "max_24h": DEP_MAX_24H,
        **win,
    }


# ── Multicuenta (Matchmaker) ─────────────────────────────────────────────────
# Pool de tarjetas vs N cuentas (max 5). Algoritmo:
#  - 5s cooldown por tarjeta y por cuenta
#  - 2 fails por tarjeta → retirada; 2 fails por cuenta → retirada
#  - 3DS_REQUIRED solo strike a tarjeta, NO a cuenta
#  - LOGIN_FAILED/AUTOEXCLUSION/KYC_PENDING/3DS_UNDETECTED → cuenta DEAD
#  - Tarjeta éxitosa NO se retira (sigue probando otras cuentas)
#  - Par (card, account) sólo se intenta una vez

MM_COOLDOWN = 5
MM_MAX_FAILS = 2

# Runs activos del matchmaker — para soporte de cancelación
_active_mm_runs: dict[str, asyncio.Event] = {}


@router.post("/multi/stream")
async def multi_stream(request: Request, user: dict = Depends(require_session)):
    _run_deposit, make_pool = _load_deps()
    if _run_deposit is None or make_pool is None:
        raise HTTPException(503, "Módulo de depósitos no disponible")

    body = await request.json()
    account_ids = list(body.get("account_ids") or [])[:5]
    cards_raw = list(body.get("cards") or [])[:10]
    amount = float(body.get("amount") or 50)

    if not account_ids:
        raise HTTPException(400, "account_ids requerido")
    if not cards_raw:
        raise HTTPException(400, "cards requerido")
    if amount <= 0 or amount > DEP_MAX_PER_TXN:
        raise HTTPException(400, f"Monto debe ser entre $1 y ${DEP_MAX_PER_TXN:.0f}")

    # Parsea tarjetas
    cards: list[dict] = []
    for cp in cards_raw:
        try:
            num, exp, cvv = _parse_pipe(cp)
            cards.append({
                "num": num, "exp": exp, "cvv": cvv,
                "tail": f"···{num[-4:]}", "pipe": cp,
                "fail_count": 0, "last_used": 0.0, "retired": False,
            })
        except ValueError:
            pass

    if not cards:
        raise HTTPException(400, "Ninguna tarjeta válida")

    from app import db, _broadcast
    placeholders = ",".join("?" * len(account_ids))
    with db() as c:
        rows = c.execute(
            f"SELECT id, email, password FROM accounts WHERE id IN ({placeholders})",
            account_ids,
        ).fetchall()
    accounts = [{
        "id": r["id"], "email": r["email"], "password": r["password"],
        "fail_count": 0, "last_used": 0.0, "done": False,
    } for r in rows]

    if not accounts:
        raise HTTPException(404, "Ninguna cuenta encontrada")

    # Cap check por cuenta — si alguna está full, abortar antes de empezar
    cap_errors = []
    for a in accounts:
        err = _check_caps(a["email"], amount)
        if err:
            cap_errors.append(f"{a['email']}: {err}")
    if cap_errors:
        raise HTTPException(400, "Caps violados:\n" + "\n".join(cap_errors))

    operator_id = int(user.get("telegram_id") or 0)
    user_ctx = {"telegram_id": operator_id, "username": user.get("username", "")}

    # Auto-lock TODAS las cuentas del batch para este operador. Si alguna está
    # lockeada por otro y el caller no es SA → 409. Si SA, override.
    for a in accounts:
        _auto_lock_for_deposit(a["id"], operator_id, user, hours=AUTOLOCK_HOURS_MULTI)
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")

    run_id = uuid.uuid4().hex[:10]
    cancel_event = asyncio.Event()
    _active_mm_runs[run_id] = cancel_event

    async def gen():
        pool = None
        prefetch = None

        tried: set[tuple[str, int]] = set()  # (card_num, account_id)
        matches: list[dict] = []
        attempts = 0
        # Tracking de attempt() tasks vivas — para cancelarlas en finally si
        # el generator explota a mitad del run (evita orphan tasks queriendo
        # captcha tokens de un pool ya detenido).
        _inflight_tasks: list[asyncio.Task] = []

        # Queue compartida para emisión live de fases desde attempt() → outer gen().
        # Cada attempt() escribe eventos {type:"phase", email, tail, name, data}
        # mientras corre; el outer loop los drena concurrentemente con el gather.
        phase_queue: asyncio.Queue = asyncio.Queue()

        def make_attempt_phase_cb(email_p: str, tail_p: str):
            async def cb(name: str, payload: dict) -> None:
                await phase_queue.put({
                    "type": "phase",
                    "email": email_p,
                    "tail": tail_p,
                    "name": name,
                    "data": payload,
                })
            return cb

        yield f"data: {json.dumps({'type':'start','run_id':run_id,'accounts':len(accounts),'cards':len(cards),'amount':amount})}\n\n"

        async def attempt(acc, card, n):
            nonlocal attempts
            email = acc["email"]
            t0 = time.time()
            # Velocity check pre-gateway — primeras 2 cuentas libres, después
            # cooldown 60s. NO penaliza fail_count: solo skip y sigue.
            vel = _check_card_velocity(card.get("pipe"), email)
            if vel:
                logger.info(f"[Matchmaker] velocity skip {email}/{card['tail']}: "
                            f"wait {vel['wait_sec']}s ({vel['distinct_count']} cuentas previas)")
                # Throttle velocity-blocked pairs so matchmaker doesn't tight-loop
                await asyncio.sleep(min(vel.get("wait_sec") or 60, 30))
                return {"success": False, "result_code": "VELOCITY_SKIP",
                        "skip": True, "velocity": vel}, int((time.time() - t0) * 1000)
            # Wrapper con fases — empuja eventos a phase_queue mientras corre,
            # mismo shape de retorno que _run_deposit. NO escribe en BD, NO
            # marca DEAD, NO maneja marriage — eso lo hace el caller (este
            # bloque) con _record_attempt + la lógica de estado del matchmaker.
            phase_cb = make_attempt_phase_cb(email, card["tail"])
            try:
                r = await _run_deposit_with_phases(
                    email=email, password=acc["password"],
                    cc_num=card["num"], cc_exp=card["exp"], cc_cvv=card["cvv"],
                    amount=amount, user=user_ctx, pool=pool,
                    phase_cb=phase_cb,
                )
            except Exception as e:
                logger.error(f"[Matchmaker] {email}/{card['tail']}: {e}")
                r = {"success": False, "result_code": "ERROR", "error": str(e)[:200]}
            duration = int((time.time() - t0) * 1000)
            ok = bool(r.get("success"))
            _record_attempt(
                uuid.uuid4().hex, email, amount,
                "approved" if ok else "rejected",
                r.get("error") or r.get("result_code"),
                duration, operator_id,
                card_pipe=card.get("pipe"),
            )
            return r, duration

        try:
            # Init pool INSIDE try so auto_lock is released in finally if start_factory fails
            pool = make_pool(cap_key, size=max(2, len(cards)), workers=1)
            await pool.start_factory()
            prefetch = asyncio.create_task(pool.prefetch(min(len(accounts), len(cards))))

            while True:
                if cancel_event.is_set():
                    yield f"data: {json.dumps({'type':'cancelled','run_id':run_id})}\n\n"
                    break
                # Retira tarjetas con max fails
                for c in cards:
                    if not c["retired"] and c["fail_count"] >= MM_MAX_FAILS:
                        c["retired"] = True
                        yield f"data: {json.dumps({'type':'card_retired','tail':c['tail'],'fails':c['fail_count']})}\n\n"

                live_cards = [c for c in cards if not c["retired"]]
                live_accs  = [a for a in accounts if not a["done"] and a["fail_count"] < MM_MAX_FAILS]
                if not live_cards or not live_accs:
                    break

                # Construye batch greedy: 1 card + 1 account, no busy, no cooldown, no tried
                now = asyncio.get_event_loop().time()
                batch: list[tuple[dict, dict, int]] = []
                used_cards = set()
                used_accs = set()
                # Prioriza cuentas no atendidas aún
                live_accs.sort(key=lambda a: (a["fail_count"], a["last_used"]))
                for acc in live_accs:
                    if acc["email"] in used_accs:
                        continue
                    if now - acc["last_used"] < MM_COOLDOWN and acc["last_used"] > 0:
                        continue
                    for card in live_cards:
                        if card["num"] in used_cards:
                            continue
                        if (card["num"], acc["id"]) in tried:
                            continue
                        if now - card["last_used"] < MM_COOLDOWN and card["last_used"] > 0:
                            continue
                        attempts += 1
                        batch.append((acc, card, attempts))
                        used_cards.add(card["num"])
                        used_accs.add(acc["email"])
                        break

                if not batch:
                    # Verifica si hay pares posibles aún
                    pairs_left = any(
                        (c["num"], a["id"]) not in tried
                        for c in live_cards for a in live_accs
                    )
                    if not pairs_left:
                        break
                    # Espera el cooldown mínimo
                    waits = []
                    for c in live_cards:
                        if c["last_used"] > 0:
                            waits.append(MM_COOLDOWN - (now - c["last_used"]))
                    for a in live_accs:
                        if a["last_used"] > 0:
                            waits.append(MM_COOLDOWN - (now - a["last_used"]))
                    waits = [w for w in waits if w > 0]
                    if not waits:
                        break
                    wait = min(waits)
                    yield f"data: {json.dumps({'type':'cooldown','wait':round(wait,1)})}\n\n"
                    await asyncio.sleep(min(wait, 2.0))
                    continue

                # Emite trying y lanza paralelo
                for acc, card, n in batch:
                    yield f"data: {json.dumps({'type':'trying','email':acc['email'],'tail':card['tail'],'attempt':n})}\n\n"

                # Lanza tasks en paralelo y drena phase_queue mientras corren —
                # los eventos `phase` salen en tiempo real, no acumulados al final.
                tasks = [asyncio.create_task(attempt(acc, card, n)) for acc, card, n in batch]
                _inflight_tasks.extend(tasks)
                # asyncio.gather() ya devuelve un _GatheringFuture awaitable —
                # envolverlo con create_task() crashea con "a coroutine was
                # expected" en Py 3.11+. El Future tiene .done() y se awaitea
                # igual; no necesita wrap.
                gather_task = asyncio.gather(*tasks, return_exceptions=True)

                while not gather_task.done():
                    try:
                        ev = await asyncio.wait_for(phase_queue.get(), timeout=0.5)
                        yield f"data: {json.dumps(ev)}\n\n"
                    except asyncio.TimeoutError:
                        # SSE comment heartbeat — keeps proxy connections alive
                        # durante captcha solves largos (30s+). nginx/traefik
                        # cierran conexiones sin tráfico ~60s.
                        yield ": ping\n\n"

                # Drena el remanente que pudo entrar entre la última lectura y
                # gather_task.done() (events de la fase 'done' final, etc.)
                while not phase_queue.empty():
                    try:
                        ev = phase_queue.get_nowait()
                        yield f"data: {json.dumps(ev)}\n\n"
                    except asyncio.QueueEmpty:
                        break

                results = await gather_task

                for (acc, card, n), res in zip(batch, results):
                    if isinstance(res, Exception):
                        yield f"data: {json.dumps({'type':'error','email':acc['email'],'tail':card['tail'],'message':str(res)[:200]})}\n\n"
                        continue
                    r, duration = res
                    code = r.get("result_code", "UNKNOWN")
                    # Velocity skip — NO marca tried, NO incrementa fail_count,
                    # NO actualiza last_used (la tarjeta no se "consumió"). El
                    # siguiente loop la considera con cooldown 60s aplicado por
                    # _check_card_velocity automáticamente.
                    if code == "VELOCITY_SKIP":
                        vel = r.get("velocity", {})
                        yield f"data: {json.dumps({'type':'velocity_skip','email':acc['email'],'tail':card['tail'],'wait_sec':vel.get('wait_sec'),'distinct_count':vel.get('distinct_count'),'message':vel.get('message','')})}\n\n"
                        continue
                    # Sí se hizo intento real → marca tried + last_used
                    tried.add((card["num"], acc["id"]))
                    now2 = asyncio.get_event_loop().time()
                    card["last_used"] = now2
                    acc["last_used"] = now2
                    ok = bool(r.get("success"))

                    if ok:
                        acc["done"] = True
                        card["retired"] = True  # tarjeta se casa con la cuenta — nunca más se prueba en otras
                        matches.append({"email": acc["email"], "tail": card["tail"], "pipe": card["pipe"]})
                        yield f"data: {json.dumps({'type':'match','email':acc['email'],'tail':card['tail'],'pipe':card['pipe'],'amount':amount,'duration_ms':duration,'attempt':n})}\n\n"
                    elif code in ("LOGIN_FAILED", "AUTOEXCLUSION", "KYC_PENDING", "3DS_UNDETECTED", "SHADOW_BAN?"):
                        # Cuenta fuera del run + persistir DEAD en BD para no volver a intentarla
                        acc["fail_count"] = MM_MAX_FAILS
                        try:
                            from app import db as _appdb
                            with _appdb(write=True) as cdb:
                                cdb.execute(
                                    "UPDATE accounts SET status='DEAD', dead_reason=?, dead_at=? "
                                    "WHERE email=? AND status != 'DEAD'",
                                    (code, datetime.now(timezone.utc).isoformat(), acc["email"])
                                )
                        except Exception as ex:
                            logger.error(f"[Matchmaker] no pude marcar DEAD {acc['email']}: {ex}")
                        yield f"data: {json.dumps({'type':'account_dead','email':acc['email'],'code':code,'tail':card['tail'],'attempt':n,'persisted':True})}\n\n"
                    elif code in ("3DS_REQUIRED", "BANK_REJECTED"):
                        # Solo strike a tarjeta — la cuenta está fina (BANK_REJECTED viene del banco
                        # emisor de la tarjeta, no de BetMexico)
                        card["fail_count"] += 1
                        yield f"data: {json.dumps({'type':'rejected','email':acc['email'],'tail':card['tail'],'code':code,'card_fails':card['fail_count'],'attempt':n,'card_only':True})}\n\n"
                    else:
                        card["fail_count"] += 1
                        acc["fail_count"] += 1
                        yield f"data: {json.dumps({'type':'rejected','email':acc['email'],'tail':card['tail'],'code':code,'card_fails':card['fail_count'],'acct_fails':acc['fail_count'],'attempt':n})}\n\n"

                # Notifica al SSE global del activity feed
                for m in matches[-len(batch):]:
                    try:
                        from app import _resolve_who
                        _broadcast({
                            "type": "activity", "kind": "deposit",
                            "ts": datetime.now(timezone.utc).isoformat(),
                            **_resolve_who(operator_id), "target": m["email"],
                            "amount": amount, "status": "approved",
                        })
                    except Exception:
                        pass

            # done MUST emit aquí dentro del try — si quedaba fuera del try/finally,
            # una excepción en el while haría que finally limpie pero el frontend
            # nunca recibe 'done' y las pair rows quedan stuck en busy.
            yield f"data: {json.dumps({'type':'done','matches':len(matches),'attempts':attempts,'pending':sum(1 for a in accounts if not a['done'] and a['fail_count']<MM_MAX_FAILS)})}\n\n"
        except Exception as e:
            logger.error(f"[Matchmaker {run_id}] generator error: {e}")
            try:
                yield f"data: {json.dumps({'type':'fatal','run_id':run_id,'error':str(e)[:300]})}\n\n"
            except Exception:
                pass
        finally:
            # Cancelar attempt tasks vivas antes de matar el pool — sin esto,
            # las que seguían corriendo se quedan haciendo get_token() contra
            # un pool ya detenido y producen "Pool vacío" 90s después.
            try:
                for t in list(_inflight_tasks):
                    if not t.done():
                        t.cancel()
            except Exception:
                pass
            if prefetch is not None and not prefetch.done():
                prefetch.cancel()
            if pool is not None:
                try:
                    await pool.stop()
                except Exception:
                    pass
            _active_mm_runs.pop(run_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/multi/{run_id}/cancel")
def multi_cancel(run_id: str, _user: dict = Depends(require_session)):
    ev = _active_mm_runs.get(run_id)
    if not ev:
        raise HTTPException(404, "Run no encontrado o ya terminado")
    ev.set()
    return {"cancelled": run_id}


# ── Programado ──────────────────────────────────────────────────────────────
# 1 tarjeta → 1 cuenta, N repeticiones (max 20) cada 60s.
# Cancela auto en LOGIN_FAILED / AUTOEXCLUSION / KYC_PENDING.

_active_schedules: dict = {}


@router.post("/scheduled/create")
async def scheduled_create(request: Request, user: dict = Depends(require_session)):
    _run_deposit, make_pool = _load_deps()
    if _run_deposit is None or make_pool is None:
        raise HTTPException(503, "Módulo de depósitos no disponible")

    body = await request.json()
    account_id = int(body.get("account_id") or 0)
    card_pipe = (body.get("card_pipe") or "").strip()
    amount = float(body.get("amount") or 50)
    repetitions = max(1, min(20, int(body.get("repetitions") or 5)))
    interval = 60

    if not account_id or not card_pipe:
        raise HTTPException(400, "account_id y card_pipe requeridos")
    if amount <= 0 or amount > DEP_MAX_PER_TXN:
        raise HTTPException(400, f"Monto debe ser entre $1 y ${DEP_MAX_PER_TXN:.0f}")
    try:
        cc_num, cc_exp, cc_cvv = _parse_pipe(card_pipe)
    except ValueError as e:
        raise HTTPException(400, str(e))

    from app import db, _broadcast, _resolve_who
    with db() as c:
        row = c.execute(
            "SELECT id, email, password FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Cuenta no encontrada")

    sched_id = uuid.uuid4().hex[:10]
    operator_id = int(user.get("telegram_id") or 0)
    email = row["email"]
    password = row["password"]
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")

    # Velocity check al crear el schedule (no en cada iter — misma cuenta+tarjeta
    # no dispara velocity, solo si la tarjeta se usó en OTRA cuenta hace <60s).
    force = bool(body.get("force"))
    is_sa = (user.get("role") == "superadmin")
    if not (force and is_sa):
        vel = _check_card_velocity(card_pipe, email)
        if vel:
            raise HTTPException(409, {"detail": vel["message"], "velocity": vel})

    # Auto-lock: durante todo el schedule (N reps × 1min + buffer) la cuenta es
    # del operador. Si está lockeada por otro y NO soy SA, 409.
    _auto_lock_for_deposit(account_id, operator_id, user, hours=AUTOLOCK_HOURS_SCHEDULED)

    async def loop():
        pool = None
        try:
            logger.info(f"[Scheduled {sched_id}] loop arrancó — email={email} reps={repetitions} amount={amount}")
            # Heartbeat inicial: confirma al frontend que la misión arrancó
            # ANTES del pool warm-up (5-15s). Sin esto, el modal quedaba en
            # "Preparando intento 1…" estático durante ese gap y el operador
            # no sabía si el backend estaba vivo. Si _broadcast falla aquí,
            # el frontend lo nota por su watchdog de 30s.
            try:
                _broadcast({
                    "type": "activity", "kind": "scheduled_started",
                    "sched_id": sched_id, "total": repetitions,
                    "email": email,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    **_resolve_who(operator_id),
                })
                logger.info(f"[Scheduled {sched_id}] heartbeat scheduled_started broadcasted")
            except Exception as e:
                logger.warning(f"[Scheduled {sched_id}] started broadcast failed: {e}")
            # Init pool INSIDE try so _active_schedules cleanup runs in finally
            # even if start_factory fails (prevents orphaned scheduled entry).
            logger.info(f"[Scheduled {sched_id}] llamando make_pool…")
            pool = make_pool(cap_key, size=1, workers=1)
            logger.info(f"[Scheduled {sched_id}] make_pool OK, start_factory…")
            await pool.start_factory()
            logger.info(f"[Scheduled {sched_id}] start_factory OK, prefetch + entrando al for")
            asyncio.create_task(pool.prefetch(1))
            # Sesión reutilizada entre iteraciones: la iter 0 hace login real
            # (1 captcha) y captura el JWT + proxy; las iters 1..N lo reusan sin
            # volver a loguear. El JWT vive ~7 días, el run dura <20 min → seguro.
            session_jwt = None
            session_proxy = None
            for i in range(repetitions):
                iter_num = i + 1
                # Track del iter actual en _active_schedules para que GET /scheduled/list
                # pueda devolverlo y el frontend rehidrate la barra de progreso tras
                # un refresh sin esperar al próximo evento SSE.
                if sched_id in _active_schedules:
                    _active_schedules[sched_id]["current_iter"] = iter_num

                # phase_cb por iter: emite scheduled_phase a SSE para visibilidad
                # live. _it captura iter_num por default-arg para evitar late-bind.
                async def phase_cb(name, payload, _it=iter_num):
                    try:
                        _broadcast({
                            "type": "activity", "kind": "scheduled_phase",
                            "sched_id": sched_id,
                            "iter": _it, "total": repetitions,
                            "name": name, "data": payload or {},
                            "email": email,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            **_resolve_who(operator_id),
                        })
                    except Exception as e:
                        logger.warning(f"[Scheduled {sched_id}] phase broadcast failed: {e}")

                # Solo la iter 0 necesita captcha (para el login real). Las iters
                # 1..N reusan la sesión → sin captcha, sin refresh de tokens.
                t0 = time.time()
                r = None
                try:
                    r = await _run_deposit_with_phases(
                        email=email, password=password,
                        cc_num=cc_num, cc_exp=cc_exp, cc_cvv=cc_cvv,
                        amount=amount,
                        user={"telegram_id": operator_id, "username": user.get("username", "")},
                        pool=pool,
                        phase_cb=phase_cb,
                        persist_login_data=(i == 0),
                        session_jwt=session_jwt,
                        session_proxy=session_proxy,
                    )
                except asyncio.CancelledError:
                    # Cancel mid-iter: registrar el intento antes de propagar para
                    # que la tarjeta no quede "quemada invisible" en BD. El outer
                    # except hace broadcast scheduled_cancelled.
                    duration = int((time.time() - t0) * 1000)
                    _record_attempt(
                        uuid.uuid4().hex, email, amount, "error",
                        "CancelledError", duration, operator_id,
                        card_pipe=card_pipe,
                    )
                    raise
                except Exception as e:
                    # Excepción real: armar dict de error para que el flujo normal
                    # de abajo broadcastee scheduled + scheduled_aborted y rompa
                    # el loop. NO re-raise: el frontend debe ver el aborted.
                    logger.error(f"[Scheduled {sched_id}] {email}: {e}")
                    r = {"success": False, "result_code": "ERROR", "error": str(e)[:200]}
                duration = int((time.time() - t0) * 1000)
                ok = bool(r.get("success"))
                code = r.get("result_code", "UNKNOWN")
                # Captura la sesión de la iter 0 (login exitoso) para reusarla en
                # las siguientes. Solo se setea una vez; iters posteriores ya
                # vienen con session_jwt y no re-loguean.
                if ok and session_jwt is None and r.get("jwt"):
                    session_jwt = r.get("jwt")
                    session_proxy = r.get("used_proxy")
                    logger.info(f"[Scheduled {sched_id}] sesión capturada en iter {i+1} — reuso activado para las siguientes")
                _record_attempt(
                    uuid.uuid4().hex, email, amount,
                    "approved" if ok else "rejected",
                    r.get("error") or code, duration, operator_id,
                    card_pipe=card_pipe,
                )
                _broadcast({
                    "type": "activity", "kind": "scheduled",
                    "sched_id": sched_id, "iter": i + 1, "total": repetitions,
                    "email": email, "amount": amount,
                    "success": ok, "code": code,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    **_resolve_who(operator_id),
                })
                # Cualquier falla aborta el loop completo: no tiene sentido
                # reintentar el mismo monto que ya rechazó (quema cuentas).
                if not ok:
                    _broadcast({
                        "type": "activity", "kind": "scheduled_aborted",
                        "sched_id": sched_id, "email": email, "code": code,
                        "iter": i + 1, "total": repetitions,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        **_resolve_who(operator_id),
                    })
                    break
                if i < repetitions - 1:
                    # Cadencia: `interval` segundos completos DESPUÉS de lograr el
                    # depósito (Robert 2026-05-28). Como las iters siguientes reusan
                    # la sesión (sin login ni captcha), ya no hay que pre-refrescar
                    # tokens ni descontar el tiempo del intento — es un sleep limpio.
                    await asyncio.sleep(interval)
        except asyncio.CancelledError:
            _broadcast({
                "type": "activity", "kind": "scheduled_cancelled",
                "sched_id": sched_id, "email": email,
                "ts": datetime.now(timezone.utc).isoformat(),
                **_resolve_who(operator_id),
            })
            raise
        except Exception as e:
            # Histórico: este except era SOLO para CancelledError → cualquier
            # otra excepción (start_factory fail, make_pool error, _run_deposit
            # crash) moría silenciosa en la asyncio task sin loguear nada y el
            # frontend solo veía "Preparando…" eterno sin watchdog.
            # Fix 2026-05-25: capturar todo, loguear stacktrace, broadcastear
            # scheduled_aborted para que el frontend salga del estado "vivo".
            import traceback
            logger.error(
                f"[Scheduled {sched_id}] ERROR INESPERADO en loop(): {e}\n"
                f"{traceback.format_exc()}"
            )
            try:
                _broadcast({
                    "type": "activity", "kind": "scheduled_aborted",
                    "sched_id": sched_id, "email": email,
                    "code": f"LOOP_ERROR: {type(e).__name__}",
                    "iter": 0, "total": repetitions,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    **_resolve_who(operator_id),
                })
            except Exception:
                pass
        finally:
            if pool is not None:
                try:
                    await pool.stop()
                except Exception:
                    pass
            _active_schedules.pop(sched_id, None)
            logger.info(f"[Scheduled {sched_id}] loop terminó — entry removido de _active_schedules")

    task = asyncio.create_task(loop())
    _active_schedules[sched_id] = {
        "task": task, "email": email,
        "amount": amount, "repetitions": repetitions,
        "operator_id": operator_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "card_pipe": card_pipe,
        "current_iter": 0,        # se actualiza en el loop, se expone vía /scheduled/list
    }
    return {"sched_id": sched_id, "email": email, "repetitions": repetitions}


@router.get("/scheduled/list")
def scheduled_list(user: dict = Depends(require_session)):
    """Lista misiones programadas activas del user (SA ve todas).
    Frontend la consulta al cargar para rehidratar el drawer si el operador
    recargó la página en medio de una misión — TDAH-friendly: nunca perder
    de vista lo que está corriendo."""
    tg = int(user.get("telegram_id") or 0)
    is_sa = user.get("role") == "superadmin"
    out = []
    for sid, info in list(_active_schedules.items()):
        if info["task"].done():
            _active_schedules.pop(sid, None)
            continue
        if not is_sa and info["operator_id"] != tg:
            continue
        out.append({
            "sched_id": sid, "email": info["email"],
            "amount": info["amount"], "repetitions": info["repetitions"],
            "started_at": info["started_at"],
            "card_pipe": info.get("card_pipe", ""),
            "current_iter": info.get("current_iter", 0),
            "operator_id": info["operator_id"],
        })
    return out


@router.post("/scheduled/{sched_id}/cancel")
def scheduled_cancel(sched_id: str, user: dict = Depends(require_session)):
    info = _active_schedules.get(sched_id)
    if not info:
        raise HTTPException(404, "Misión no encontrada")
    tg = int(user.get("telegram_id") or 0)
    if user.get("role") != "superadmin" and info["operator_id"] != tg:
        raise HTTPException(403, "No es tuya")
    info["task"].cancel()
    return {"cancelled": sched_id}
