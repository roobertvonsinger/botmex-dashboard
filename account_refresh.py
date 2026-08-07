"""account_refresh.py — refresca balance/movimientos de cuentas con JWT VIGENTE.

PROBLEMA: fuera de login manual, post-depósito y jwt_keeper (que solo toca
cuentas por expirar), el balance en BD puede quedar horas desactualizado sin
que nadie lo note — La Pantalla muestra lo último que quedó en BD.

SOLUCIÓN: ciclo periódico que toma las cuentas cuyo JWT SIGUE vigente ahora
(lo opuesto a jwt_keeper, que ataca las por expirar) y les hace un fetch de
detalles REUSANDO ese JWT — sin login, sin captcha, sin tocar el semáforo
`_LOGIN_SEM` de login_orchestrator. Mismo patrón ya probado en prod por
`deposits._refresh_account_after_deposit`.

Medido en prod 2026-07-19 (KVM4, betmexico-web): 935 cuentas / 821 LIVE / 55
publicadas al pool / solo 18 con JWT vigente en ese momento — universo chico,
cabe entero en un batch por ciclo. Default 1 refresh/cuenta/hora (confirmado
con Robert).

Se engancha como bg-loop de uvicorn (`app._account_refresh_loop`), mismo
patrón que `jwt_keeper`. Config por env (`ACCOUNT_REFRESH_*`).
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("betmexico.dashboard.account_refresh")

DEFAULT_GRADES: Set[str] = {"A+", "A", "B"}

# Bug 1 fix (handoff 2026-08-07): ciclo propio de resolución de retiros
# pendientes. El ciclo genérico de 20min es 10-20x más lento que la cadencia
# normal de resolución (1-2 min, medido por Robert en vivo). Este piso de 60s
# viene documentado en withdrawals.py PASO4 ("el polling es 60s mínimo — no
# taladrar"). Solo itera cuentas con retiro en curso (universo chico) — no
# taladra la API en general.
WITHDRAWAL_POLL_INTERVAL_SEC = 60


def _sa_lock_tokens() -> List[str]:
    """Tokens que identifican un lock del super-admin en `accounts.locked_by`.

    El campo guarda formatos mixtos: `lock_account` (vía UI) persiste el
    `username` del SA ('RobertVS'), `_auto_lock_for_deposit` persiste su
    `telegram_id` numérico ('1341812706'). Para identificar RESERVADA_SA
    correctamente hay que aceptar ambos. Se resuelve dinámicamente desde
    `auth.USERS` por rol 'superadmin' — si auth no está disponible, fallback
    al token histórico (solo numérico) para no romper el ciclo.
    """
    try:
        import auth

        tokens: List[str] = []
        for uname, info in auth.USERS.items():
            if info.get("role") == "superadmin":
                tokens.append(uname.lower())  # formato username
                tg = info.get("telegram_id")
                if tg is not None:
                    tokens.append(str(tg))  # formato telegram_id
        return tokens or ["1341812706"]
    except Exception as e:
        logger.warning(
            f"[account_refresh] auth.USERS no disponible, fallback SA token: {e}"
        )
        return ["1341812706"]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def cfg() -> Dict[str, Any]:
    grades_raw = os.environ.get("ACCOUNT_REFRESH_GRADES", "A+,A,B")
    grades = {g.strip() for g in grades_raw.split(",") if g.strip()}
    return {
        "enabled": os.environ.get("ACCOUNT_REFRESH_ENABLED", "1") == "1",
        # 300 → 1200 (Robert 2026-08-05): el autofetch ahora es el DETECTOR de
        # sesiones muertas server-side + refresco de balance. Corre cada 20 min
        # (no cada 5): el fetch no renueva el JWT (7 días fijos, solo login emite
        # uno fresco), así que refrescar balance cada 5 min no mantiene nada vivo
        # — solo actualiza datos. 20 min es suficiente para datos variables.
        "interval_sec": _env_int("ACCOUNT_REFRESH_INTERVAL_SEC", 1200),  # 20 min
        "batch_max": _env_int("ACCOUNT_REFRESH_BATCH", 60),
        "gap_min": _env_int("ACCOUNT_REFRESH_GAP_MIN_SEC", 2),
        "gap_max": _env_int("ACCOUNT_REFRESH_GAP_MAX_SEC", 5),
        "grades": grades or DEFAULT_GRADES,
    }


# ── Lógica pura de selección (testeable sin BD ni deps del bot) ───────────────
def select_refresh_candidates_healthy(
    rows: List[Dict[str, Any]],
    now: int,
    *,
    batch_max: int,
    grades: Set[str],
    sa_tokens: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Filtra + ordena + limita las cuentas a refrescar este ciclo.

    Regla normal: viva, útil (grade en `grades`, publicada), NO lockeada por
    un operador, y con JWT que SIGUE vigente ahora. Orden: `last_checked_at`
    ascendente (la más desactualizada primero).

    Excepción RESERVADA_SA: pool=0 + locked_by del SA sí es candidata.

    Regla "hot" (Robert, 2026-08-04): una fila con `row["hot"]=True` (ver
    `is_hot_account`) SIEMPRE es candidata — bypassea lock/grade/pool y NO
    cuenta contra `batch_max` — solo requiere estar LIVE y tener JWT vigente
    (sin eso no hay forma de refrescarla). Van primero en el resultado.
    """
    sa_tokens = set(sa_tokens or [])
    hot: List[Dict[str, Any]] = []
    normal: List[Dict[str, Any]] = []
    for r in rows:
        if (r.get("status") or "") != "LIVE":
            continue
        exp = _exp_int(r.get("jwt_expires_at"))
        if exp <= now:
            continue  # sin JWT vigente → no es candidata (la toca jwt_keeper)

        if r.get("hot"):
            hot.append(r)
            continue

        grade = r.get("grade") or ""
        if grade not in grades:
            continue
        locked_by = r.get("locked_by")
        is_sa_reserved = (
            not r.get("published_to_pool") and str(locked_by).lower() in sa_tokens
        )
        if not is_sa_reserved:
            if not r.get("published_to_pool"):
                continue
            if locked_by is not None:
                continue
        normal.append(r)

    hot.sort(key=lambda r: r.get("last_checked_at") or "")
    normal.sort(key=lambda r: r.get("last_checked_at") or "")
    return hot + normal[:batch_max]


def _exp_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def is_hot_account(row: Dict[str, Any], now_iso: str) -> bool:
    """Cuenta que DEBE refrescarse siempre, sin importar lock/grade/pool/
    batch_max (Robert, 2026-08-04): balance_real>$50, ventana de autolock
    post-depósito activa (locked_until en el futuro — dinero de un depósito
    del mismo proceso aún sin asentar), o retiro en curso sin liberar
    (has_pending_withdrawal — hasta que status_api==6 lo saca de aquí).
    `locked_until` compara lexicográficamente contra `now_iso`: ambos son
    ISO8601 en UTC, mismo formato, el orden lexicográfico coincide con el
    cronológico."""
    balance = float(row.get("balance_real") or 0)
    if balance > 50:
        return True
    locked_until = row.get("locked_until")
    if locked_until and str(locked_until) > now_iso:
        return True
    if row.get("has_pending_withdrawal"):
        return True
    return False


# ── I/O de BD (aislado; usa el context manager de app) ────────────────────────
_SELECT_COLS = (
    "id",
    "email",
    "status",
    "grade",
    "jwt_expires_at",
    "locked_by",
    "published_to_pool",
    "last_checked_at",
    "balance_real",
    "locked_until",
)

_PENDING_WD_EXISTS_SQL = (
    "EXISTS(SELECT 1 FROM account_withdrawals w WHERE w.account_id = accounts.id "
    "AND (w.status_api IS NULL OR (w.status_api >= 0 AND w.status_api != 6)))"
)


def _load_candidate_rows() -> List[Dict[str, Any]]:
    """Trae TODAS las cuentas LIVE y computa `hot` en Python vía
    `is_hot_account` — el filtro grade/pool/lock para cuentas NO-hot sigue
    viviendo únicamente en `select_refresh_candidates_healthy` (una sola
    fuente de verdad, antes estaba parcialmente duplicado en el WHERE de
    este SELECT).

    Antes el WHERE excluía cuentas no publicadas/lockeadas a nivel SQL —
    eso escondía por completo las cuentas hot que están lockeadas por un
    operador no-SA (el caso normal durante depósito/retiro en curso).
    """
    import app  # lazy: evita ciclo de import

    now_iso = datetime.now(timezone.utc).isoformat()
    with app.db() as conn:
        cur = conn.execute(
            f"SELECT {', '.join(_SELECT_COLS)}, "
            f"{_PENDING_WD_EXISTS_SQL} AS has_pending_withdrawal "
            "FROM accounts WHERE status='LIVE'"
        )
        rows = [dict(row) for row in cur.fetchall()]
    for r in rows:
        r["has_pending_withdrawal"] = bool(r.get("has_pending_withdrawal"))
        r["hot"] = is_hot_account(r, now_iso)
    return rows


def _db_get_withdrawal_ready(email: str) -> int:
    import app

    with app.db() as c:
        row = c.execute(
            "SELECT withdrawal_ready FROM accounts WHERE email=?", (email,)
        ).fetchone()
    return int(row["withdrawal_ready"] or 0) if row else 0


def _db_set_withdrawal_ready(
    email: str, ready: bool, institution: Optional[str]
) -> None:
    import app

    with app.db(write=True) as c:
        c.execute(
            "UPDATE accounts SET withdrawal_ready=?, withdrawal_institution=? WHERE email=?",
            (1 if ready else 0, institution, email),
        )


# ── Ciclo (async) ─────────────────────────────────────────────────────────────
async def run_refresh_cycle(
    *,
    batch_max: int,
    grades: Set[str],
    gap_min: int,
    gap_max: int,
) -> Dict[str, Any]:
    """Un ciclo: selecciona el lote y refresca cada cuenta espaciada, REUSANDO
    su JWT vigente (sin captcha, sin login, sin tocar _LOGIN_SEM)."""
    now = int(time.time())
    rows = await asyncio.to_thread(_load_candidate_rows)
    sa_tokens = _sa_lock_tokens()
    cands = select_refresh_candidates_healthy(
        rows, now, batch_max=batch_max, grades=grades, sa_tokens=sa_tokens
    )
    stats: Dict[str, Any] = {
        "universe": len(rows),
        "selected": len(cands),
        "refreshed": 0,
        "skipped_no_jwt": 0,
        "skipped_no_proxy": 0,
        "failed": 0,
    }
    if not cands:
        logger.info(f"[account_refresh] nada que refrescar (universo={len(rows)})")
        return stats

    try:
        from betmexico_login_api import BetmexicoApiChecker
        from betmexico_db import db as _db
        from prewarm import _db_upsert_balance, _db_save_txns_and_recalc
        from proxy_pool import build_admin_proxy_url
    except Exception as e:
        logger.error(f"[account_refresh] deps del bot no disponibles: {e}")
        stats["failed"] = len(cands)
        return stats

    for i, r in enumerate(cands):
        if i > 0:
            await asyncio.sleep(random.uniform(gap_min, gap_max))
        email = r["email"]

        try:
            cached = await asyncio.to_thread(_db.get_jwt_cache, email)
        except Exception as e:
            logger.warning(f"[account_refresh] {email} cache lookup err: {e}")
            cached = None
        if (
            not cached
            or not cached.get("token")
            or cached.get("expires_at", 0) <= time.time() + 60
        ):
            stats["skipped_no_jwt"] += 1
            continue
        jwt = cached["token"]

        proxy_url = build_admin_proxy_url()
        if not proxy_url:
            # REGLA DURA (Robert): NUNCA proxyless en prod.
            stats["skipped_no_proxy"] += 1
            logger.warning(f"[account_refresh] {email} sin proxy disponible — skip")
            continue

        try:
            async with BetmexicoApiChecker(proxy=proxy_url) as checker:
                details = await asyncio.wait_for(
                    checker.fetch_account_details_parallel(
                        jwt, fetch_mode="balance_only"
                    ),
                    timeout=15.0,
                )
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"[account_refresh] {email} fetch falló: {str(e)[:160]}")
            continue

        if not details:
            # Posible 401/JWT muerto server-side pese a exp local vigente.
            # NO marcar dead, NO tocar jwt_expires_at — lo captura jwt_keeper
            # cuando expire localmente. Solo se cuenta como fallo del ciclo.
            stats["failed"] += 1
            logger.debug(
                f"[account_refresh] {email} fetch vacío (posible JWT muerto server-side)"
            )
            continue

        # `fetch_account_details_parallel` SIEMPRE devuelve un dict truthy
        # (defaults N/A/0.00). Si TODO quedó en default, el JWT está muerto
        # server-side (401 redirectLogin) — invalidar cache para que el
        # próximo ciclo haga login REAL en vez de reusar el JWT muerto, y
        # despertar al jwt_keeper YA (no esperar su tick horario — FUGA #1).
        from prewarm import _fetch_looks_empty, _db_invalidate_jwt

        if _fetch_looks_empty(details):
            stats["failed"] += 1
            logger.debug(
                f"[account_refresh] {email} fetch vacío (JWT muerto server-side) — invalidando cache"
            )
            try:
                await asyncio.to_thread(_db_invalidate_jwt, email)
            except Exception:
                pass
            try:
                from app import _wake_jwt_keeper

                _wake_jwt_keeper()
            except Exception:
                pass
            continue

        try:
            await asyncio.to_thread(_db_upsert_balance, email, details)
            await asyncio.to_thread(_db_save_txns_and_recalc, email, details, None)
            stats["refreshed"] += 1
            logger.debug(
                f"[account_refresh] {email} balance fresco "
                f"(balance_real={details.get('balance_real')})"
            )
            try:
                from app import _broadcast, _resolve_who

                _broadcast(
                    {
                        "type": "activity",
                        "kind": "account_refreshed",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "email": email,
                        "target": email,
                        "balance_real": details.get("balance_real"),
                        "balance_total": (
                            float(details.get("balance_real", 0) or 0)
                            + float(details.get("balance_bonos", 0) or 0)
                        ),
                        **_resolve_who(None),
                    }
                )
            except Exception:
                pass

            # withdrawal_ready: PASO1 de withdrawals.py es la única fuente de
            # verdad de "¿aterrizó el SPEI?" — se verifica en el mismo ciclo
            # que ya refresca balance con el mismo JWT/proxy, sin llamada extra
            # de login/captcha. Robert, 2026-08-04: gatea el botón de retiro
            # del portal sin exponer un round-trip vivo a BetMexico en cada render.
            try:
                from withdrawals import (
                    get_bank_accounts,
                    NoApprovedWithdrawalAccount,
                    MultipleApprovedAccounts,
                )

                ready: Optional[bool] = None
                institution: Optional[str] = None
                try:
                    approved = await get_bank_accounts(jwt, proxy_url)
                    ready, institution = True, approved[0].get("institutionName")
                except NoApprovedWithdrawalAccount:
                    ready, institution = False, None
                except MultipleApprovedAccounts:
                    # SPEI SÍ aterrizó (hay >1 cuenta aprobada) — el operador puede
                    # intentar retirar; execute_withdrawal decide con más detalle
                    # en el momento del click. No se puede elegir "la" institución.
                    ready, institution = True, "Múltiples cuentas — revisar"
                except Exception as e:
                    logger.debug(
                        f"[account_refresh] {email} check withdrawal_ready falló: {str(e)[:120]}"
                    )

                if ready is not None:
                    prev = _db_get_withdrawal_ready(email)
                    if prev != (1 if ready else 0):
                        _db_set_withdrawal_ready(email, ready, institution)
                        try:
                            from app import _broadcast

                            _broadcast(
                                {
                                    "type": "activity",
                                    "kind": "withdrawal_ready_changed",
                                    "ts": datetime.now(timezone.utc).isoformat(),
                                    "email": email,
                                    "withdrawal_ready": ready,
                                    "withdrawal_institution": institution,
                                }
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(
                    f"[account_refresh] {email} withdrawal_ready check error: {str(e)[:120]}"
                )
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"[account_refresh] {email} persist falló: {str(e)[:160]}")

    logger.info(f"[account_refresh] ciclo listo: {stats}")
    return stats


async def run_refresh_cycle_from_env() -> Dict[str, Any]:
    c = cfg()
    return await run_refresh_cycle(
        batch_max=c["batch_max"],
        grades=c["grades"],
        gap_min=c["gap_min"],
        gap_max=c["gap_max"],
    )


# ── Resolución server-side de retiros pendientes (Bug 1 fix, handoff 2026-08-07) ─

_WD_PENDING_SQL = (
    "SELECT w.transaction_id, w.account_id, w.account_email, "
    "w.account_digits, w.status_api, w.gateway, w.last_modified_utc, w.amount, "
    "a.jwt_token "
    "FROM account_withdrawals w "
    "JOIN accounts a ON a.id = w.account_id "
    "WHERE w.status_api IS NULL OR (w.status_api >= 0 AND w.status_api != 6)"
)


def _load_pending_withdrawals() -> List[Dict[str, Any]]:
    """Trae todas las filas de account_withdrawals que siguen pendientes
    (status_api IS NULL OR (status_api >= 0 AND status_api != 6)) — el mismo
    predicado que _PENDING_WD_EXISTS_SQL, pero trayendo las columnas que
    resolve_withdrawal_status necesita + el jwt_token de la cuenta."""
    import app

    with app.db() as c:
        cur = c.execute(_WD_PENDING_SQL)
        return [dict(row) for row in cur.fetchall()]


async def _resolve_pending_withdrawals() -> Dict[str, Any]:
    """Un ciclo de resolución: para cada cuenta con retiro pendiente, llama
    resolve_withdrawal_status (PASO4+PASO5 de withdrawals.py) y persiste el
    resultado. Emite broadcast SSE withdrawal_status si el estado pasa a
    terminal — sin depender de ningún tab del navegador abierto (Bug 1 fix).

    Usa el jwt_token persistido en accounts (mismo que withdraw_status
    endpoint usa). Si el JWT expiró, resolve_withdrawal_status caerá en
    "idle" sin avanzar — jwt_keeper lo refrescará y el próximo ciclo lo
    resolverá. El universo es chico (solo cuentas con retiro en curso ahora
    mismo), así que 60s no taladra la API en general."""
    import app
    from withdrawals import resolve_withdrawal_status
    from proxy_pool import build_admin_proxy_url

    rows = await asyncio.to_thread(_load_pending_withdrawals)
    stats: Dict[str, Any] = {"pending": len(rows), "resolved": 0, "terminal": 0}
    if not rows:
        return stats

    proxy_url = build_admin_proxy_url()
    _WD_TERMINAL: Set[int] = {6}

    for row in rows:
        jwt = row.get("jwt_token")
        if not jwt:
            continue
        try:
            out = await resolve_withdrawal_status(
                jwt=jwt,
                proxy_url=proxy_url,
                tx_id=row["transaction_id"],
                expected_digits=row["account_digits"],
                prev_status_api=row["status_api"],
                prev_gateway=row["gateway"],
                prev_last_modified=row["last_modified_utc"],
            )
        except Exception as e:
            logger.warning(
                f"[account_refresh] resolve withdrawal {row['transaction_id']} "
                f"({row.get('account_email')}): {str(e)[:160]}"
            )
            continue

        stats["resolved"] += 1
        new_status_api = out.get("transactionStatus")
        new_terminal = new_status_api in _WD_TERMINAL or out.get("status") in (
            "successful",
            "completed",
            "failed",
        )
        was_terminal = row["status_api"] in _WD_TERMINAL
        if new_terminal and not was_terminal:
            stats["terminal"] += 1
            try:
                from app import _broadcast

                _broadcast(
                    {
                        "type": "activity",
                        "kind": "withdrawal_status",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "target": row["account_email"],
                        "id": row["account_id"],
                        "transactionId": row["transaction_id"],
                        "status": out["status"],
                        "amount": row["amount"],
                    }
                )
            except Exception:
                pass

    logger.info(f"[account_refresh] withdrawal resolution: {stats}")
    return stats


async def _withdrawal_resolution_loop():
    """Bg-loop independiente del ciclo genérico de 20min: resuelve retiros
    pendientes cada WITHDRAWAL_POLL_INTERVAL_SEC (60s, piso documentado en
    withdrawals.py PASO4) sin depender de ningún tab del navegador abierto.
    Solo itera cuentas con retiro en curso (universo chico) — no taladra la
    API en general. Es el fix del Bug 1: antes, el status de un retiro
    pendiente solo avanzaba a terminal si un operador tenía el panel de esa
    cuenta abierto (el poll JS vive en memoria del tab)."""
    await asyncio.sleep(180)  # arrancar después del ciclo principal (120s)
    while True:
        try:
            await _resolve_pending_withdrawals()
        except Exception as e:
            logger.warning(
                f"[account_refresh] withdrawal_resolution_loop: {str(e)[:160]}"
            )
        await asyncio.sleep(WITHDRAWAL_POLL_INTERVAL_SEC)
