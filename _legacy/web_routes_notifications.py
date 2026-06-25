#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Notifications routes.

Tipos: mission_completed | mission_paused_by_restart | server_restart |
       watchdog_run_complete | client_movement | balance_change |
       card_exhausted | bin_inconsistent
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from betmexico_db import db
from web_auth import authenticate

logger = logging.getLogger("betmexico.web.notif")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# operator_id -> list of asyncio.Queue (1 por SSE conectado)
_SUBSCRIBERS: Dict[int, List[asyncio.Queue]] = {}


def push_notification_event(operator_id: Optional[int], payload: Dict) -> None:
    """Publica evento a todos los suscriptores. operator_id=None ⇒ broadcast a todos."""
    targets: List[asyncio.Queue] = []
    if operator_id is None:
        for qs in _SUBSCRIBERS.values():
            targets.extend(qs)
    else:
        targets.extend(_SUBSCRIBERS.get(int(operator_id), []))
    for q in targets:
        try:
            q.put_nowait(payload)
        except Exception:
            pass


@router.get("")
async def list_notifications(
    only_unread: bool = False,
    limit: int = 50,
    user: dict = Depends(authenticate),
):
    operator_id = int(user.get("telegram_id") or 0)
    items = await asyncio.to_thread(
        db.get_notifications, operator_id, bool(only_unread), int(limit)
    )
    return {"notifications": items, "count": len(items)}


@router.get("/count")
async def count_unread(user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    n = await asyncio.to_thread(db.count_unread, operator_id)
    return {"unread": n}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: int, user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    ok = await asyncio.to_thread(db.mark_notification_read, notification_id, operator_id)
    return {"ok": bool(ok)}


@router.post("/mark-all-read")
async def mark_all_read(user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    n = await asyncio.to_thread(db.mark_all_read, operator_id)
    return {"ok": True, "marked": n}


@router.get("/stream")
async def stream(user: dict = Depends(authenticate)):
    """SSE — push live de nuevas notificaciones para este operador."""
    operator_id = int(user.get("telegram_id") or 0)
    queue: asyncio.Queue = asyncio.Queue()
    _SUBSCRIBERS.setdefault(operator_id, []).append(queue)

    async def gen():
        try:
            # Snapshot inicial
            unread = await asyncio.to_thread(db.count_unread, operator_id)
            yield f"data: {json.dumps({'type': 'snapshot', 'unread': unread})}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"ping\"}\n\n"
                    continue
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            try:
                _SUBSCRIBERS.get(operator_id, []).remove(queue)
            except Exception:
                pass

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
