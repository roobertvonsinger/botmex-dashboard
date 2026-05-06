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
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import require_session

logger = logging.getLogger("betmexico.dashboard.deposits")
router = APIRouter(prefix="/api/deposits", tags=["deposits"])


def _load_deps():
    """Lazy import — evita circular imports al startup."""
    try:
        from web_routes_deposits import _run_deposit
        from betmexico_login_service import make_pool
        return _run_deposit, make_pool
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


def _record_attempt(
    attempt_id: str,
    email: str,
    amount: float,
    status: str,
    rejection_reason: Optional[str],
    duration_ms: int,
    operator_id: int,
) -> None:
    from app import db, _broadcast
    import sqlite3
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db(write=True) as c:
            c.execute(
                "INSERT INTO deposit_attempts "
                "(attempt_id, account_email, amount, source, operator_id, status, "
                " rejection_reason, duration_ms, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    attempt_id, email, amount, "dashboard_v2", operator_id, status,
                    rejection_reason, duration_ms, now_str,
                ),
            )
    except sqlite3.OperationalError as e:
        logger.warning(f"[Deposits] no se pudo grabar attempt: {e}")

    # Broadcast SSE para feed de Actividad
    try:
        _broadcast({
            "type": "activity",
            "kind": "deposit",
            "ts": now_str,
            "who": operator_id,
            "target": email,
            "amount": amount,
            "status": status,
            "reason": rejection_reason,
            "duration_ms": duration_ms,
        })
    except Exception:
        pass


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

    if amount < 1 or amount > 5000:
        raise HTTPException(400, "Monto fuera de rango (1-5000)")

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

    # Pool de captcha — start_factory arranca workers (rápido, no bloquea).
    # NO awaiteamos prefetch: si get_jwt usa caché, ni token necesita; si no,
    # factory está produciendo en background y get_token() espera al primero.
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")
    pool = None
    prefetch_task = None
    t0 = time.time()
    try:
        pool = make_pool(cap_key, size=1, workers=1)
        await pool.start_factory()
        # Prefetch en background — útil si no hay JWT cacheado, gratis si sí lo hay
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
            save_card=False,
            check_marriage=False,
        )
    except Exception as e:
        logger.error(f"[Deposits] {email} ${amount}: {e}")
        duration_ms = int((time.time() - t0) * 1000)
        _record_attempt(attempt_id, email, amount, "error", str(e)[:300], duration_ms, operator_id)
        raise HTTPException(500, f"Error: {str(e)[:200]}")
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

    duration_ms = int((time.time() - t0) * 1000)
    success = bool(result.get("success"))
    status = "approved" if success else "rejected"
    reason = result.get("error") or result.get("result_code")

    _record_attempt(attempt_id, email, amount, status, reason, duration_ms, operator_id)

    return {
        "success": success,
        "result_code": result.get("result_code"),
        "error": result.get("error"),
        "duration_ms": duration_ms,
        "attempt_id": attempt_id,
    }
