#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Watchdog automático.

Loop en background que cada N min recorre cuentas LIVE candidatas y refresca
balance vía JWT cache + fetch_mode='balance_only'. Genera notificación al
terminar cada corrida y expone endpoints SA para monitoreo.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from betmexico_db import db
from web_auth import authenticate, require_superadmin
from betmexico_login_service import get_jwt, make_pool

logger = logging.getLogger("betmexico.web.watchdog")

router = APIRouter(prefix="/api/watchdog", tags=["watchdog"])

CAPMONSTER_API_KEY = os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad")
CAPMONSTER_ENDPOINT = "https://api.capmonster.cloud"

_INTERVAL_MIN = int(os.getenv("BMX_WATCHDOG_INTERVAL_MIN", "90"))
_BATCH_SIZE = 50
_MAX_CANDIDATES = 100
_PARALLEL_CAP = 5
_CAPMONSTER_MIN = 5.0

_WATCHDOG_PAUSED = False
_WATCHDOG_FORCE_RUN = asyncio.Event()
_WATCHDOG_STATS: Dict[str, Any] = {
    "last_run": None,
    "next_run": None,
    "duration_ms": 0,
    "checked": 0,
    "errors": 0,
    "captcha_cost": 0.0,
    "stats_24h": {"checked": 0, "errors": 0, "captcha_cost": 0.0, "runs": 0},
}


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
        logger.warning(f"[Watchdog] CapMonster balance error: {e}")
    return None


async def _check_one(account: Dict, sem: asyncio.Semaphore, pool) -> Dict[str, Any]:
    """Procesa 1 cuenta. Retorna {ok, error, captcha_cost_estimate}."""
    email = account.get("email", "")
    password = account.get("password", "")
    process_id = uuid.uuid4().hex
    t0 = time.time()
    out = {"ok": False, "error": None, "captcha_cost": 0.0, "from_cache": False}

    async with sem:
        try:
            db.log_process_phase(
                process_id, "watchdog", "init",
                payload_json=json.dumps({"email": email}),
            )
            jwt, login_result = await asyncio.wait_for(
                get_jwt(email, password, pool, use_cache=True),
                timeout=25.0,
            )
            if isinstance(login_result, dict) and login_result.get("from_cache"):
                out["from_cache"] = True
            else:
                # Estimación: 1 captcha resuelto ~ $0.0008 en CapMonster
                out["captcha_cost"] = 0.0008

            if not jwt:
                out["error"] = "no_jwt"
                db.log_process_phase(
                    process_id, "watchdog", "no_jwt",
                    payload_json=json.dumps({"email": email}),
                    duration_ms=int((time.time() - t0) * 1000),
                )
                return out

            from betmexico_login_api import BetmexicoApiChecker
            async with BetmexicoApiChecker(proxy=None) as checker:
                details = await asyncio.wait_for(
                    checker.fetch_account_details_parallel(jwt, fetch_mode="balance_only"),
                    timeout=15.0,
                )
            if details:
                await asyncio.to_thread(db.upsert_account_balance, email, details)
            out["ok"] = True
            db.log_process_phase(
                process_id, "watchdog", "complete",
                payload_json=json.dumps({"email": email,
                                          "balance_real": (details or {}).get("balance_real")}),
                duration_ms=int((time.time() - t0) * 1000),
            )
        except asyncio.TimeoutError:
            out["error"] = "timeout"
            db.log_process_phase(
                process_id, "watchdog", "timeout",
                payload_json=json.dumps({"email": email}),
                duration_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            out["error"] = str(e)[:200]
            logger.error(f"[Watchdog] {email}: {e}")
            db.log_process_phase(
                process_id, "watchdog", "error",
                payload_json=json.dumps({"email": email, "error": str(e)[:300]}),
                duration_ms=int((time.time() - t0) * 1000),
            )
    return out


async def _run_one_pass() -> Dict[str, Any]:
    """Una corrida completa del watchdog. No-op si pausado o saldo bajo."""
    t_start = time.time()
    stats = {"checked": 0, "errors": 0, "captcha_cost": 0.0, "skipped_reason": None}

    if _WATCHDOG_PAUSED:
        stats["skipped_reason"] = "paused"
        return stats

    bal = await _capmonster_balance()
    if bal is not None and bal < _CAPMONSTER_MIN:
        logger.warning(f"[Watchdog] CapMonster balance {bal} < {_CAPMONSTER_MIN}, skip run")
        stats["skipped_reason"] = "capmonster_low"
        stats["capmonster_balance"] = bal
        return stats

    candidates = await asyncio.to_thread(db.get_watchdog_candidates, _MAX_CANDIDATES)
    if not candidates:
        stats["skipped_reason"] = "no_candidates"
        return stats

    pool = None
    try:
        pool = make_pool(CAPMONSTER_API_KEY, size=4, workers=2)
        await pool.prefetch(2)
        await pool.start_factory()
        sem = asyncio.Semaphore(_PARALLEL_CAP)

        # Tandas de _BATCH_SIZE
        for i in range(0, len(candidates), _BATCH_SIZE):
            if _WATCHDOG_PAUSED:
                break
            batch = candidates[i:i + _BATCH_SIZE]
            results = await asyncio.gather(
                *[_check_one(acc, sem, pool) for acc in batch],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    stats["errors"] += 1
                    continue
                stats["checked"] += 1
                if r.get("error"):
                    stats["errors"] += 1
                stats["captcha_cost"] += float(r.get("captcha_cost") or 0.0)
    finally:
        if pool is not None:
            try:
                await pool.stop()
            except Exception:
                pass

    stats["duration_ms"] = int((time.time() - t_start) * 1000)
    return stats


async def _watchdog_loop() -> None:
    """Loop principal. Robust a excepciones, sleep 90 min entre corridas."""
    global _WATCHDOG_STATS
    logger.info(f"[Watchdog] Started. Interval={_INTERVAL_MIN}min, paused={_WATCHDOG_PAUSED}")
    while True:
        try:
            stats = await _run_one_pass()
            now_ts = time.time()
            _WATCHDOG_STATS["last_run"] = now_ts
            _WATCHDOG_STATS["duration_ms"] = stats.get("duration_ms", 0)
            _WATCHDOG_STATS["checked"] = stats.get("checked", 0)
            _WATCHDOG_STATS["errors"] = stats.get("errors", 0)
            _WATCHDOG_STATS["captcha_cost"] = stats.get("captcha_cost", 0.0)
            _WATCHDOG_STATS["next_run"] = now_ts + _INTERVAL_MIN * 60
            # Stats acumuladas 24h (aproximación: solo conteo de corridas + sumas en memoria; reset lazy)
            agg = _WATCHDOG_STATS.setdefault("stats_24h", {"checked": 0, "errors": 0, "captcha_cost": 0.0, "runs": 0})
            agg["runs"] += 1
            agg["checked"] += stats.get("checked", 0)
            agg["errors"] += stats.get("errors", 0)
            agg["captcha_cost"] += stats.get("captcha_cost", 0.0)

            if not stats.get("skipped_reason"):
                # Notificación global (todos los SA la ven)
                await asyncio.to_thread(
                    db.create_notification,
                    "watchdog_run_complete",
                    "Watchdog corrida completada",
                    f"Checadas {stats.get('checked', 0)} cuentas, {stats.get('errors', 0)} errores",
                    json.dumps(stats, default=str),
                    None,
                    "info",
                )
            else:
                logger.info(f"[Watchdog] Skipped: {stats.get('skipped_reason')}")

        except Exception as e:
            logger.error(f"[Watchdog] Loop error: {e}")

        # Espera con posibilidad de force-run
        try:
            await asyncio.wait_for(_WATCHDOG_FORCE_RUN.wait(), timeout=_INTERVAL_MIN * 60)
            _WATCHDOG_FORCE_RUN.clear()
        except asyncio.TimeoutError:
            pass


async def start_watchdog() -> None:
    """Wrapper para asyncio.create_task en startup."""
    await _watchdog_loop()


# ── Endpoints SA ──────────────────────────────────────────────────

@router.get("/status")
async def watchdog_status(user: dict = Depends(require_superadmin)):
    return {
        "paused": _WATCHDOG_PAUSED,
        "interval_min": _INTERVAL_MIN,
        "last_run": _WATCHDOG_STATS.get("last_run"),
        "next_run": _WATCHDOG_STATS.get("next_run"),
        "last_results": {
            "checked": _WATCHDOG_STATS.get("checked", 0),
            "errors": _WATCHDOG_STATS.get("errors", 0),
            "captcha_cost": round(_WATCHDOG_STATS.get("captcha_cost", 0.0), 4),
            "duration_ms": _WATCHDOG_STATS.get("duration_ms", 0),
        },
        "stats_24h": _WATCHDOG_STATS.get("stats_24h", {}),
    }


@router.post("/run-now")
async def watchdog_run_now(user: dict = Depends(require_superadmin)):
    _WATCHDOG_FORCE_RUN.set()
    return {"ok": True, "msg": "Forzando corrida en el próximo ciclo del loop"}


@router.post("/pause")
async def watchdog_pause(user: dict = Depends(require_superadmin)):
    global _WATCHDOG_PAUSED
    _WATCHDOG_PAUSED = True
    return {"ok": True, "paused": True}


@router.post("/resume")
async def watchdog_resume(user: dict = Depends(require_superadmin)):
    global _WATCHDOG_PAUSED
    _WATCHDOG_PAUSED = False
    return {"ok": True, "paused": False}
