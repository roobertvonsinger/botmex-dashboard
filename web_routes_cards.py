#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Cards routes.

Endpoints:
  POST   /api/cards            crear desde pipe (num|MM/YY|cvv)
  GET    /api/cards            listar visibles al operador
  GET    /api/cards/{id}       detalle (404 si no visible)
  GET    /api/cards/{id}/usage historial de intentos
  PATCH  /api/cards/{id}/notes editar notas (solo creador o SA)
  POST   /api/cards/{id}/ban   marcar tarjeta como banned

Privacidad: cada tarjeta tiene created_by_operator_id; SuperAdmin ve todas.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from betmexico_db import db
from web_auth import authenticate
from web_utils import compute_card_fingerprint, parse_pipe_card

logger = logging.getLogger("betmexico.web.cards")

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _is_visible(card: dict, user: dict) -> bool:
    if not card:
        return False
    if user.get("role") == "superadmin":
        return True
    return int(card.get("created_by_operator_id") or 0) == int(user.get("telegram_id") or 0)


@router.post("")
async def create_card(request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    pipe = (body.get("pipe") or "").strip()
    holder_name = (body.get("holder_name") or None)

    parsed = parse_pipe_card(pipe)
    if not parsed:
        raise HTTPException(status_code=400, detail="Formato de tarjeta inválido. Esperado: num|MM/YY|cvv")

    card_number = parsed["card_number"]
    exp_month = parsed["exp_month"]
    exp_year = parsed["exp_year"]
    cvv = parsed.get("cvv")
    bin_v = card_number[:6]
    last_4 = card_number[-4:]
    fingerprint = compute_card_fingerprint(card_number, exp_month, exp_year)

    operator_id = int(user.get("telegram_id") or 0)
    card_id = await asyncio.to_thread(
        db.create_card,
        fingerprint, card_number, bin_v, last_4,
        exp_month, exp_year, cvv, holder_name, operator_id,
    )
    if not card_id:
        raise HTTPException(status_code=500, detail="No se pudo crear la tarjeta")

    return {"id": card_id, "fingerprint": fingerprint, "last_4": last_4, "bin": bin_v}


@router.get("")
async def list_cards(user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")
    cards = await asyncio.to_thread(db.get_cards, operator_id, role)
    return {"cards": cards, "count": len(cards)}


@router.get("/{card_id}")
async def get_card(card_id: int, user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")
    card = await asyncio.to_thread(db.get_card_by_id, card_id, operator_id, role)
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    return card


@router.get("/{card_id}/usage")
async def get_card_usage(card_id: int, user: dict = Depends(authenticate)):
    operator_id = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")
    card = await asyncio.to_thread(db.get_card_by_id, card_id, operator_id, role)
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    usage = await asyncio.to_thread(db.get_card_usage, card_id)
    return {"card_id": card_id, "usage": usage, "count": len(usage)}


@router.patch("/{card_id}/notes")
async def patch_card_notes(card_id: int, request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    notes = (body.get("notes") or "").strip()
    operator_id = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")

    card = await asyncio.to_thread(db.get_card_by_id, card_id, operator_id, role)
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")

    # Solo creador o SuperAdmin pueden editar
    if role != "superadmin" and int(card.get("created_by_operator_id") or 0) != operator_id:
        raise HTTPException(status_code=403, detail="Solo el creador o SuperAdmin puede editar")

    ok = await asyncio.to_thread(db.update_card_notes, card_id, notes)
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo actualizar")
    return {"ok": True, "card_id": card_id, "notes": notes}


@router.post("/{card_id}/ban")
async def ban_card(card_id: int, request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    reason = (body.get("reason") or "").strip() or "manual_ban"
    operator_id = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")

    card = await asyncio.to_thread(db.get_card_by_id, card_id, operator_id, role)
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    if role != "superadmin" and int(card.get("created_by_operator_id") or 0) != operator_id:
        raise HTTPException(status_code=403, detail="Solo el creador o SuperAdmin puede banear")

    ok = await asyncio.to_thread(db.mark_card_status, card_id, "banned", reason)
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo banear")
    return {"ok": True, "card_id": card_id, "status": "banned", "reason": reason}
