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
    try:
        from betmexico_config import get_admin_proxy
    except ImportError:
        get_admin_proxy = None  # type: ignore
except ImportError:
    _HAS_BOT_DEPS = False
    score_payment_readiness = None  # type: ignore
    get_admin_proxy = None  # type: ignore


def _build_proxy_url() -> Optional[str]:
    """Construye URL de proxy admin para http.client."""
    if not get_admin_proxy:
        return None
    try:
        p = get_admin_proxy()
        if not p:
            return None
        srv = p.get("server", "")
        u = p.get("username", "")
        pw = p.get("password", "")
        if u and pw:
            return f"http://{u}:{pw}@{srv}"
        return f"http://{srv}"
    except Exception:
        return None

logger = logging.getLogger("betmexico.dashboard.prewarm")

router = APIRouter(prefix="/api/prewarm", tags=["prewarm"])

_PREWARM_TASKS: Dict[str, asyncio.Task] = {}

CAP_PER_OPERATOR_10MIN = 9999  # sin tope práctico — el operador decide
ACCOUNT_FRESH_MINUTES = 30      # < 30min desde last check → skip con warning
ACCOUNT_DAILY_LIMIT = 3          # >= 3 prewarms en el día → skip con warning
REFRESH_PARALLEL = 15           # max logins concurrentes (anti rate-limit BetMexico)
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
                "last_checked_at, jwt_token, jwt_expires_at, status "
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
    - Si la API regresó balance_real=0 pero la BD ya tenía saldo >0, conserva
      el saldo (BetMéxico es intermitente, mismo guard que usa el bot).
    - last_deposit_* solo se sobreescribe si el fetch trajo datos válidos —
      no pisa con 0/N/A si el fetch vino vacío (ej. fetch_mode='balance_only')."""
    from app import db
    import sqlite3
    bal_real = float(details.get("balance_real", 0.0) or 0.0)
    bal_bonos = float(details.get("balance_bonos", 0.0) or 0.0)
    bal_total = bal_real + bal_bonos
    new_amt = details.get("last_deposit_amount")
    new_date = details.get("last_deposit_date")
    has_dep = (new_amt is not None and float(new_amt or 0) > 0
               and new_date and str(new_date).strip() not in ("", "N/A"))
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db(write=True) as c:
            if bal_real == 0.0:
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
    """Guarda transacciones nuevas + recalcula grade. No-op si no llegaron txns."""
    try:
        from app import BOT_SCORE_PAYMENT as _score
    except Exception:
        _score = None
    if _score is None:
        return
    txn_data = (details or {}).get("transactions") or {}
    items = txn_data.get("items") or []
    # Persiste txns (reusa el helper del bot si está disponible)
    if items:
        try:
            from betmexico_db import db as _bot_db
            await_safe = getattr(_bot_db, "save_account_transactions", None)
            if await_safe:
                # save_account_transactions(email, items, checked_by) — sync en bot
                _bot_db.save_account_transactions(email, items, checked_by=operator_id)
        except Exception as e:
            logger.debug(f"[Prewarm] save_account_transactions: {e}")
    # Recalcula grade
    try:
        scoring = _score(details)
    except Exception as e:
        logger.debug(f"[Prewarm] score_payment_readiness: {e}")
        scoring = None
    if not scoring:
        return
    from app import db
    import sqlite3
    try:
        with db(write=True) as c:
            c.execute(
                "UPDATE accounts SET grade=?, grade_score=? WHERE email=?",
                (scoring.get("grade"), scoring.get("score"), email),
            )
    except sqlite3.OperationalError:
        pass


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
    proxy_url = _build_proxy_url()  # ¡CRÍTICO! sale por proxy MX, no por IP del VPS
    try:
        # Verificar JWT cache ANTES de crear pool — evita gastar Capsolver en vano.
        # Si el JWT sigue vigente, ir directo al fetch sin login ni captcha.
        jwt = await asyncio.to_thread(_db_get_jwt_cache, email)
        jwt_from_cache = jwt is not None

        if not jwt:
            # JWT vencido o ausente — necesita login real (consume 1 captcha)
            pool = make_pool(cap_key, size=1, workers=1)
            await pool.prefetch(1)
            await pool.start_factory()

            jwt, login_result = await asyncio.wait_for(
                get_jwt(email, password, pool, proxy=proxy_url, use_cache=True),
                timeout=float(TASK_TIMEOUT_SEC),
            )
            if not jwt:
                status = login_result.get("status") if isinstance(login_result, dict) else None
                _db_log_phase(
                    process_id, "no_jwt",
                    {"email": email, "operator_id": operator_id, "status": status},
                    int((time.time() - t0) * 1000),
                )
                return {"ok": False, "status": status or "no_jwt",
                        "error": (login_result.get("error") if isinstance(login_result, dict) else None) or status or "Login falló"}

        async with BetmexicoApiChecker(proxy=proxy_url) as checker:
            details = await asyncio.wait_for(
                checker.fetch_account_details_parallel(jwt, fetch_mode="full"),
                timeout=18.0,
            )
        if details:
            await asyncio.to_thread(_db_upsert_balance, email, details)
            # Guarda txns frescas + recalcula grade (oportunidad gratuita)
            await asyncio.to_thread(_db_save_txns_and_recalc, email, details, operator_id)
        else:
            # Login/fetch OK pero sin datos — actualizar timestamp para evitar retry inmediato
            await asyncio.to_thread(_db_update_last_checked, email)
            if jwt_from_cache:
                # JWT de cache rechazado — invalidar para que el próximo refresh haga login real
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
        return {"ok": False, "status": "timeout", "error": "Timeout 25s"}
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

    operator_id = int(user.get("telegram_id") or 0)
    if not operator_id:
        operator_id = abs(hash(user.get("username", "unknown"))) % 10_000_000

    # Lookup cuentas
    from app import db as _app_db
    placeholders = ",".join("?" * len(ids))
    with _app_db() as c:
        rows = c.execute(
            f"SELECT id, email, password, last_checked_at FROM accounts WHERE id IN ({placeholders})",
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
                # Reglas anti-spam (a menos que SA fuerce):
                if not force:
                    mins = _account_minutes_since_check(acc)
                    if mins is not None and mins < ACCOUNT_FRESH_MINUTES:
                        await q.put({"type": "skip", "id": acc["id"], "email": email,
                                     "reason": "fresh", "minutes": round(mins, 1),
                                     "can_force": is_sa})
                        return
                    today = await asyncio.to_thread(_db_account_prewarms_today, email)
                    if today >= ACCOUNT_DAILY_LIMIT:
                        await q.put({"type": "skip", "id": acc["id"], "email": email,
                                     "reason": "daily_limit", "today_count": today,
                                     "can_force": is_sa})
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
                        "COALESCE(a.published_to_pool,1) AS published_to_pool, "
                        "(SELECT COUNT(*) FROM account_cards ac WHERE ac.account_email=a.email) AS cards_count, "
                        "(SELECT COUNT(*) FROM account_notes an WHERE an.account_email=a.email "
                        " AND COALESCE(an.note_text,'') != '') AS notes_count "
                        "FROM accounts a WHERE a.id=?",
                        (acc["id"],),
                    ).fetchone()
                if r:
                    await q.put({"type": "account", "data": dict(r)})
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
