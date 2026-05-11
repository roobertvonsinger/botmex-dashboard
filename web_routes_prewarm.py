#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Pre-warm endpoint con salvaguardas.

Reglas (Robert):
  1. Cap por sesión: max 30 pre-warms por operador en últimos 10 min.
  2. Cap CapMonster: si saldo < $5, abortar.
  3. Skip si JWT vigente Y last_check < 5 min (cached).
  4. Cancel-on-deselect: /cancel mata las tasks activas.
  5. Heartbeat lo administra el front; aquí solo se sirven endpoints.
  6. Cada task usa fetch_mode='balance_only' + JWT cache.
  7. Logs en process_log con process_type='prewarm'.
  8. Timeout 25s por task.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from betmexico_db import db
from web_auth import authenticate
from betmexico_login_service import get_jwt, make_pool

logger = logging.getLogger("betmexico.web.prewarm")

router = APIRouter(prefix="/api/prewarm", tags=["prewarm"])

# (operator_id:str, email:str) -> asyncio.Task
_PREWARM_TASKS: Dict[str, asyncio.Task] = {}

_PREWARM_CAP_PER_OPERATOR_PER_10MIN = 30
_PREWARM_CAPMONSTER_MIN = 5.0
_PREWARM_FRESH_BALANCE_SEC = 5 * 60
_PREWARM_TASK_TIMEOUT_SEC = 25

CAPMONSTER_API_KEY = os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad")
CAPMONSTER_ENDPOINT = "https://api.capmonster.cloud"


async def _capmonster_balance() -> Optional[float]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{CAPMONSTER_ENDPOINT}/getBalance",
                json={"clientKey": CAPMONSTER_API_KEY},
            )
            data = r.json()
            if data.get("errorId") == 0:
                return float(data.get("balance", 0))
    except Exception as e:
        logger.warning(f"[Prewarm] CapMonster balance error: {e}")
    return None


def _is_balance_fresh(account: Dict) -> bool:
    """Heurística: last_checked_at + JWT vigente => 'fresco' < 5 min."""
    try:
        last = account.get("last_checked_at")
        if not last:
            return False
        from datetime import datetime
        try:
            ts = datetime.fromisoformat(last.replace(" ", "T"))
        except Exception:
            return False
        age = time.time() - ts.timestamp()
        return age < _PREWARM_FRESH_BALANCE_SEC
    except Exception:
        return False


async def _run_prewarm(operator_id: int, email: str, password: str) -> None:
    """Corutina interna: JWT cache + balance_only. Idempotente, tolera fallo."""
    process_id = uuid.uuid4().hex
    db.log_process_phase(
        process_id, "prewarm", "init",
        payload_json=json.dumps({"email": email, "operator_id": int(operator_id)}),
    )
    t0 = time.time()
    pool = None
    try:
        pool = make_pool(CAPMONSTER_API_KEY, size=1, workers=1)
        await pool.prefetch(1)
        await pool.start_factory()

        # JWT cache es la primera defensa
        jwt, login_result = await asyncio.wait_for(
            get_jwt(email, password, pool, use_cache=True),
            timeout=float(_PREWARM_TASK_TIMEOUT_SEC),
        )
        if not jwt:
            db.log_process_phase(
                process_id, "prewarm", "no_jwt",
                payload_json=json.dumps({
                    "email": email, "operator_id": int(operator_id),
                    "status": login_result.get("status") if isinstance(login_result, dict) else None,
                }),
                duration_ms=int((time.time() - t0) * 1000),
            )
            return

        from betmexico_login_api import BetmexicoApiChecker
        async with BetmexicoApiChecker(proxy=None) as checker:
            details = await asyncio.wait_for(
                checker.fetch_account_details_parallel(jwt, fetch_mode="balance_only"),
                timeout=15.0,
            )
        if details:
            await asyncio.to_thread(db.upsert_account_balance, email, details)

        db.log_process_phase(
            process_id, "prewarm", "complete",
            payload_json=json.dumps({"email": email, "operator_id": int(operator_id),
                                     "balance_real": details.get("balance_real") if details else None}),
            duration_ms=int((time.time() - t0) * 1000),
        )
    except asyncio.CancelledError:
        db.log_process_phase(
            process_id, "prewarm", "cancelled",
            payload_json=json.dumps({"email": email, "operator_id": int(operator_id)}),
            duration_ms=int((time.time() - t0) * 1000),
        )
        raise
    except asyncio.TimeoutError:
        db.log_process_phase(
            process_id, "prewarm", "timeout",
            payload_json=json.dumps({"email": email, "operator_id": int(operator_id)}),
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception as e:
        logger.error(f"[Prewarm] {email} error: {e}")
        db.log_process_phase(
            process_id, "prewarm", "error",
            payload_json=json.dumps({"email": email, "operator_id": int(operator_id), "error": str(e)[:300]}),
            duration_ms=int((time.time() - t0) * 1000),
        )
    finally:
        _PREWARM_TASKS.pop(f"{int(operator_id)}:{email}", None)
        if pool is not None:
            try:
                await pool.stop()
            except Exception:
                pass


@router.post("/select")
async def prewarm_select(request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    emails: List[str] = list(body.get("account_emails") or [])
    if not isinstance(emails, list) or not emails:
        raise HTTPException(status_code=400, detail="account_emails requerido")

    operator_id = int(user.get("telegram_id") or 0)

    # Cap CapMonster
    bal = await _capmonster_balance()
    if bal is not None and bal < _PREWARM_CAPMONSTER_MIN:
        return {"status": "capmonster_low", "started": 0, "capmonster_balance": bal}

    # Cap por sesión
    used = await asyncio.to_thread(
        db.count_recent_process_log, "prewarm", operator_id, 10
    )
    remaining = max(0, _PREWARM_CAP_PER_OPERATOR_PER_10MIN - used)

    started = 0
    cached = 0
    skipped = 0
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

        acc = await asyncio.to_thread(db.get_account_by_email, email)
        if not acc:
            skipped += 1
            skipped_reasons["no_account"] = skipped_reasons.get("no_account", 0) + 1
            continue

        # JWT vigente + balance fresco => cached
        jwt_cache = await asyncio.to_thread(db.get_jwt_cache, email)
        if jwt_cache and _is_balance_fresh(acc):
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
        "cap_used": used + started,
        "cap_max": _PREWARM_CAP_PER_OPERATOR_PER_10MIN,
    }


@router.post("/cancel")
async def prewarm_cancel(request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    emails: List[str] = list(body.get("account_emails") or [])
    operator_id = int(user.get("telegram_id") or 0)
    cancelled = 0
    for email in emails:
        key = f"{operator_id}:{email}"
        task = _PREWARM_TASKS.get(key)
        if task and not task.done():
            task.cancel()
            cancelled += 1
    return {"cancelled": cancelled}


@router.get("/status")
async def prewarm_status(user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    active = sum(
        1 for k, t in _PREWARM_TASKS.items()
        if k.startswith(f"{operator_id}:") and not t.done()
    )
    used = await asyncio.to_thread(
        db.count_recent_process_log, "prewarm", operator_id, 10
    )
    bal = await _capmonster_balance()
    recent = await asyncio.to_thread(
        db.get_recent_process_log, "prewarm", operator_id, 10
    )
    return {
        "active": active,
        "cap_used": used,
        "cap_max": _PREWARM_CAP_PER_OPERATOR_PER_10MIN,
        "capmonster_balance": bal,
        "recent_runs": recent,
    }
