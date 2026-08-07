#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""withdrawals — retiro automático vía API BetMexico (5 pasos).

Patrón: replica clabe_fetch.py. Importable, testeable con httpx.MockTransport.
Host: TODO va a paymentsapi.betmexico.mx. NUNCA proxyless en prod.

PASO1: GET /api/User/BankAccounts        → cuenta de retiro aprobada
PASO2: GET /api/Wallet/Total/Amount/ByAccountType → saldo Real
PASO3: POST /api/stp/BeginWithdrawal     → dispara retiro (SINGLE-SHOT, no retry)
PASO4: GET /api/User/PendingWithdrawal   → estado del retiro en curso
PASO5: GET /api/wallet/bankTransaction/{tx_id} → auditoría/rail externo
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional, Any

import httpx

from clabe_fetch import _load_jwt_for_account, _get_admin_proxy_url

logger = logging.getLogger("betmexico.dashboard.withdrawals")

PAYMENTS_API = "https://paymentsapi.betmexico.mx"
BANK_ACCOUNTS_URL = f"{PAYMENTS_API}/api/User/BankAccounts"
BALANCE_URL = f"{PAYMENTS_API}/api/Wallet/Total/Amount/ByAccountType"
BEGIN_WITHDRAWAL_URL = f"{PAYMENTS_API}/api/stp/BeginWithdrawal"
PENDING_WITHDRAWAL_URL = f"{PAYMENTS_API}/api/User/PendingWithdrawal"
BANK_TRANSACTION_URL = f"{PAYMENTS_API}/api/wallet/bankTransaction"

CANONICAL_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://betmexico.mx",
    "Referer": "https://betmexico.mx/",
}


# ── Excepciones ──────────────────────────────────────────────────────────────


class WithdrawalError(Exception):
    """Base para errores de retiro controlados."""


class JwtExpired(WithdrawalError):
    """JWT de la cuenta expirado o ausente."""


class NoApprovedWithdrawalAccount(WithdrawalError):
    """La cuenta no tiene cuenta de retiro con accountStatus==2 (Approved)."""


class MultipleApprovedAccounts(WithdrawalError):
    """Más de una cuenta de retiro aprobada — el operador debe elegir."""


class InsufficientBalance(WithdrawalError):
    """Saldo Real insuficiente para el monto solicitado."""


class ConcurrentWithdrawalPending(WithdrawalError):
    """Ya hay un retiro pendiente: BetMexico devolvió THE_TRANSACTION_DOES_NOT_COMPLY."""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _auth_headers(jwt: str) -> dict:
    return {**CANONICAL_HEADERS, "Authorization": f"Bearer {jwt}"}


def _client_kwargs(proxy_url: Optional[str], transport=None) -> dict:
    """Devuelve los kwargs para httpx.AsyncClient según si tenemos transport mock o no."""
    if transport is not None:
        return {"transport": transport}
    return {"proxy": proxy_url, "verify": False}


# ── PASO 1: leer cuenta de retiro (SIEMPRE fresca — bug#1) ───────────────────


async def get_bank_accounts(
    jwt: str,
    proxy_url: Optional[str],
    transport=None,
) -> list[dict]:
    """PASO1: GET /api/User/BankAccounts.

    Devuelve lista de cuentas con accountStatus==2 (Approved).
    Lanza NoApprovedWithdrawalAccount si ninguna. Lanza MultipleApprovedAccounts si >1.
    NUNCA cachear el resultado — un depósito SPEI puede cambiar la cuenta destino (bug#1).
    """
    kw = _client_kwargs(proxy_url, transport)
    try:
        async with httpx.AsyncClient(timeout=30.0, **kw) as client:
            r = await client.get(BANK_ACCOUNTS_URL, headers=_auth_headers(jwt))
    except Exception as e:
        raise RuntimeError(f"BankAccounts error de red: {e}") from e

    if r.status_code != 200:
        raise RuntimeError(f"BankAccounts HTTP {r.status_code}: {r.text[:300]}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"BankAccounts respuesta no-JSON: {e}") from e

    all_accounts = data.get("accounts") or []
    approved = [a for a in all_accounts if a.get("accountStatus") == 2]

    if not approved:
        raise NoApprovedWithdrawalAccount(
            "Sin cuenta de retiro aprobada (accountStatus==2). "
            "Un depósito SPEI registra la cuenta de retiro automáticamente."
        )
    if len(approved) > 1:
        options = ", ".join(
            f"{a.get('institutionName', '?')} ···{str(a.get('account', ''))[-4:]}"
            for a in approved
        )
        raise MultipleApprovedAccounts(
            f"Hay {len(approved)} cuentas de retiro aprobadas ({options}). "
            "Confirma cuál usar."
        )
    return approved


# ── PASO 2: verificar saldo disponible ───────────────────────────────────────


async def get_real_balance(
    jwt: str,
    proxy_url: Optional[str],
    transport=None,
) -> dict:
    """PASO2: GET /api/Wallet/Total/Amount/ByAccountType → {Real, Bonos}.

    Solo `Real` es retirable. Lanza RuntimeError si la respuesta no trae `Real`.
    """
    kw = _client_kwargs(proxy_url, transport)
    try:
        async with httpx.AsyncClient(timeout=30.0, **kw) as client:
            r = await client.get(BALANCE_URL, headers=_auth_headers(jwt))
    except Exception as e:
        raise RuntimeError(f"Balance error de red: {e}") from e

    if r.status_code != 200:
        raise RuntimeError(f"Balance HTTP {r.status_code}: {r.text[:300]}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Balance respuesta no-JSON: {e}") from e

    if "Real" not in data:
        raise RuntimeError(f"Balance sin clave 'Real': {json.dumps(data)[:300]}")

    return data


# ── PASO 3: disparar el retiro (SINGLE-SHOT — no retry) ──────────────────────


async def begin_withdrawal(
    jwt: str,
    proxy_url: Optional[str],
    account_id_bmx: str,
    amount: float,
    email: str,
    transport=None,
) -> dict:
    """PASO3: POST /api/stp/BeginWithdrawal → {transactionId}.

    Body MÍNIMO exacto (verificado con 5 retiros reales):
      {accountId, amount (float), email}
    Bodies más chicos → 500; más grandes son innecesarios.

    SINGLE-SHOT: NO reintentar en ningún error de red/proxy.
    Un retry podría duplicar el retiro (a diferencia de BeginDeposit que es idempotente).
    Lanza ConcurrentWithdrawalPending si hay retiro pendiente activo.
    """
    body = {
        "accountId": account_id_bmx,
        "amount": float(amount),  # float, no string
        "email": email,
    }
    kw = _client_kwargs(proxy_url, transport)
    # SINGLE-SHOT: sin try/except de red para que excepciones de conexión suban directo
    # (el caller decide si loggear — NO reintentar)
    async with httpx.AsyncClient(timeout=30.0, **kw) as client:
        r = await client.post(
            BEGIN_WITHDRAWAL_URL,
            headers=_auth_headers(jwt),
            content=json.dumps(body).encode(),
        )

    if r.status_code == 400:
        try:
            msg = r.json().get("message", "")
        except Exception:
            msg = r.text
        if "THE_TRANSACTION_DOES_NOT_COMPLY" in msg:
            raise ConcurrentWithdrawalPending(
                "Ya hay un retiro pendiente activo en esta cuenta."
            )
        raise RuntimeError(f"BeginWithdrawal 400: {msg[:300]}")

    if r.status_code == 401:
        raise RuntimeError("BeginWithdrawal JWT inválido/expirado (401)")

    if r.status_code != 200:
        raise RuntimeError(f"BeginWithdrawal HTTP {r.status_code}: {r.text[:300]}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"BeginWithdrawal respuesta no-JSON: {e}") from e

    if not data.get("transactionId"):
        raise RuntimeError(
            f"BeginWithdrawal sin transactionId en 200: {json.dumps(data)[:300]}"
        )

    return data


# ── PASO 4: monitorear estado del retiro ─────────────────────────────────────


async def get_pending_withdrawal(
    jwt: str,
    proxy_url: Optional[str],
    transport=None,
) -> Optional[dict]:
    """PASO4: GET /api/User/PendingWithdrawal.

    Devuelve dict con estado del retiro en curso, o None si no hay pendiente (id==null).
    El polling es 60s mínimo — no taladrar (rate-limit).
    """
    kw = _client_kwargs(proxy_url, transport)
    try:
        async with httpx.AsyncClient(timeout=30.0, **kw) as client:
            r = await client.get(PENDING_WITHDRAWAL_URL, headers=_auth_headers(jwt))
    except Exception as e:
        raise RuntimeError(f"PendingWithdrawal error de red: {e}") from e

    if r.status_code != 200:
        raise RuntimeError(f"PendingWithdrawal HTTP {r.status_code}: {r.text[:300]}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"PendingWithdrawal respuesta no-JSON: {e}") from e

    # Si id es null → no hay retiro pendiente
    if data.get("id") is None:
        return None

    return data


# ── PASO 5: auditar el rail externo ──────────────────────────────────────────


async def get_bank_transaction(
    jwt: str,
    proxy_url: Optional[str],
    tx_id: str,
    expected_digits: Optional[str] = None,
    transport=None,
) -> dict:
    """PASO5: GET /api/wallet/bankTransaction/{tx_id}.

    Devuelve dict normalizado con flags de guardarrail:
      gateway_spei: bool        — True si gateway==2 (SPEI)
      gateway_mismatch: bool    — True si gateway==1 (tarjeta, bug#3)
      digits_mismatch: bool     — True si lastAccountDigits != expected_digits (bug#1)
      expected_digits: str|None
      actual_digits: str|None
    """
    kw = _client_kwargs(proxy_url, transport)
    try:
        async with httpx.AsyncClient(timeout=30.0, **kw) as client:
            r = await client.get(
                f"{BANK_TRANSACTION_URL}/{tx_id}",
                headers=_auth_headers(jwt),
            )
    except Exception as e:
        raise RuntimeError(f"BankTransaction error de red: {e}") from e

    if r.status_code != 200:
        raise RuntimeError(f"BankTransaction HTTP {r.status_code}: {r.text[:300]}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"BankTransaction respuesta no-JSON: {e}") from e

    gateway = data.get("gateway") or data.get("gatewayType")
    actual_digits = data.get("lastAccountDigits") or data.get("account")

    gateway_spei = gateway == 2
    gateway_mismatch = gateway == 1  # bug#3: retiro a tarjeta cuando esperabas SPEI
    digits_mismatch = (
        bool(expected_digits)
        and bool(actual_digits)
        and str(actual_digits)[-4:] != str(expected_digits)[-4:]
    )

    return {
        **data,
        "gateway_spei": gateway_spei,
        "gateway_mismatch": gateway_mismatch,
        "digits_mismatch": digits_mismatch,
        "expected_digits": expected_digits,
        "actual_digits": actual_digits,
    }


# ── Resolución compartida (PASO4 + PASO5 + persistencia) ──────────────────────


def _persist_wd_status(
    tx_id: str,
    status_api: int,
    gateway: Any = None,
    last_modified_utc: Any = None,
    *,
    full: bool = False,
) -> None:
    """Persiste status_api (y opcionalmente gateway/last_modified_utc) en
    account_withdrawals. Lazy import de app.db para no crear dependencia
    circular (withdrawals → app → withdrawals). `full=True` cuando hay
    resultado de PASO5 (gateway + last_modified_utc frescos)."""
    import app

    with app.db(write=True) as c:
        if full:
            c.execute(
                "UPDATE account_withdrawals SET status_api=?, gateway=?, "
                "last_modified_utc=? WHERE transaction_id=?",
                (status_api, gateway, last_modified_utc, tx_id),
            )
        else:
            c.execute(
                "UPDATE account_withdrawals SET status_api=? WHERE transaction_id=?",
                (status_api, tx_id),
            )


async def resolve_withdrawal_status(
    jwt: Optional[str],
    proxy_url: Optional[str],
    tx_id: str,
    expected_digits: Optional[str],
    prev_status_api: Optional[int],
    prev_gateway: Any = None,
    prev_last_modified: Any = None,
    transport=None,
    *,
    _get_pending=None,
    _get_bank_tx=None,
) -> dict:
    """Resuelve el estado de un retiro: llama PASO4 (PendingWithdrawal) y,
    si retorna status==6 o ya no está pendiente, PASO5 (BankTransaction) para
    confirmar. Persiste el resultado en account_withdrawals (status_api,
    gateway, last_modified_utc) y devuelve el dict `out` que antes construía
    app.py::withdraw_status inline. Lógica compartida para que el endpoint
    HTTP y el bg-loop server-side (account_refresh._withdrawal_resolution_loop)
    llamen la MISMA función — no duplicar.

    `_get_pending`/`_get_bank_tx` son inyectables para que app.py pueda pasar
    SUS referencias (que los tests monkeypatchean vía `monkeypatch.setattr(app,
    "get_pending_withdrawal", ...)`). Si no se pasan, usa las del módulo
    withdrawals (caso del bg-loop)."""
    fn_pending = _get_pending or get_pending_withdrawal
    fn_bank_tx = _get_bank_tx or get_bank_transaction

    pending = None
    if jwt:
        try:
            pending = await fn_pending(jwt, proxy_url, transport=transport)
        except Exception:
            pending = None

    out: dict = {
        "transactionId": tx_id,
        "accountDigits": expected_digits,
        "alerts": {"gatewayMismatch": False, "digitsMismatch": False},
    }

    if pending is not None:
        status_api = pending.get("transactionStatus")
        out["transactionStatus"] = status_api
        if status_api == 6:
            # bug#2: status:6 = BetMexico lo ejecutó, NO que aterrizó en el banco.
            # Confirmar rail externo vía PASO5 antes de reportar "delivered".
            bank_tx = None
            if jwt:
                try:
                    bank_tx = await fn_bank_tx(
                        jwt,
                        proxy_url,
                        tx_id,
                        expected_digits=expected_digits,
                        transport=transport,
                    )
                except Exception:
                    bank_tx = None
            out["status"] = "successful"
            out["phase"] = "executed"
            out["description"] = "Ejecutado por BetMexico — confirma en tu banco"
            if bank_tx is not None:
                out["lastModifiedUtc"] = bank_tx.get("lastModifiedUtc")
                out["gateway"] = bank_tx.get("gateway")
                out["alerts"]["gatewayMismatch"] = bool(bank_tx.get("gateway_mismatch"))
                out["alerts"]["digitsMismatch"] = bool(bank_tx.get("digits_mismatch"))
                _persist_wd_status(
                    tx_id,
                    status_api,
                    bank_tx.get("gateway"),
                    bank_tx.get("lastModifiedUtc"),
                    full=True,
                )
            else:
                _persist_wd_status(tx_id, status_api)
        else:
            out["status"] = "pending"
            out["phase"] = "pending"
            out["description"] = (
                pending.get("transactionStatusDescription") or "Pendiente"
            )
            _persist_wd_status(tx_id, status_api)
    elif prev_status_api == 6:
        out["status"] = "completed"
        out["phase"] = "completed"
        out["transactionStatus"] = prev_status_api
        out["lastModifiedUtc"] = prev_last_modified
        out["gateway"] = prev_gateway
    elif prev_status_api is not None and prev_status_api < 0:
        out["status"] = "failed"
        out["phase"] = "failed"
        out["transactionStatus"] = prev_status_api
        out["lastModifiedUtc"] = prev_last_modified
        out["gateway"] = prev_gateway
    else:
        # Root cause (2026-07-26, medido con tx real 232b8814...): BetMexico saca
        # el retiro de PendingWithdrawal (PASO4→None) en cuanto se resuelve — MUCHO
        # antes de que este endpoint vuelva a mirar el rail externo. status_api en
        # BD quedaba pegado al último valor intermedio que reportó PASO4 mientras
        # aún aparecía ahí (ej. 2), y sin este PASO5 el status caía en "idle" para
        # siempre: el frontend nunca ve un estado terminal → "Retiro en proceso"
        # colgado eternamente aunque BetMexico ya lo haya ejecutado. PASO5 es la
        # única fuente que sigue teniendo el desenlace real una vez que cae de la
        # lista de pendientes.
        bank_tx = None
        if jwt:
            try:
                bank_tx = await fn_bank_tx(
                    jwt,
                    proxy_url,
                    tx_id,
                    expected_digits=expected_digits,
                    transport=transport,
                )
            except Exception:
                bank_tx = None
        if bank_tx is not None and bank_tx.get("transactionStatus") == 6:
            out["status"] = "successful"
            out["phase"] = "executed"
            out["description"] = "Ejecutado por BetMexico — confirma en tu banco"
            out["transactionStatus"] = 6
            out["lastModifiedUtc"] = bank_tx.get("lastModifiedUtc")
            out["gateway"] = bank_tx.get("gateway")
            out["alerts"]["gatewayMismatch"] = bool(bank_tx.get("gateway_mismatch"))
            out["alerts"]["digitsMismatch"] = bool(bank_tx.get("digits_mismatch"))
            _persist_wd_status(
                tx_id,
                6,
                bank_tx.get("gateway"),
                bank_tx.get("lastModifiedUtc"),
                full=True,
            )
        elif bank_tx is not None:
            # El rail respondió pero sin status 6 — reporta lo que dice, no lo
            # pisamos con un valor inventado.
            out["status"] = "pending"
            out["phase"] = "pending"
            out["transactionStatus"] = bank_tx.get("transactionStatus")
            out["lastModifiedUtc"] = bank_tx.get("lastModifiedUtc")
            out["gateway"] = bank_tx.get("gateway")
        else:
            # Ni PASO4 ni PASO5 confirman nada ahora mismo — de verdad desconocido,
            # NO se disfraza de completado ni de fallido sin evidencia. El próximo
            # poll lo vuelve a intentar.
            out["status"] = "idle"
            out["phase"] = "idle"
            out["transactionStatus"] = prev_status_api
            out["lastModifiedUtc"] = prev_last_modified
            out["gateway"] = prev_gateway

    return out


# ── Orquestador PASO0-3 ───────────────────────────────────────────────────────


async def execute_withdrawal(
    db_path: str,
    account_id: int,
    amount: float,
) -> dict:
    """Orquesta PASO0 (JWT) → PASO1 (cuenta) → PASO2 (saldo) → PASO3 (disparo).

    Devuelve:
      {transactionId, reference?, accountId, accountDigits, institutionName,
       amount, account_email, warnings:[]}

    Lanza:
      JwtExpired          — JWT ausente o expirado
      NoApprovedWithdrawalAccount / MultipleApprovedAccounts — sin cuenta de retiro
      InsufficientBalance — saldo Real < amount
      ConcurrentWithdrawalPending — ya hay retiro pendiente
      RuntimeError        — error de red / API inesperado
    """
    warnings: list[str] = []

    # PASO 0 — validar JWT
    jwt, email, info = _load_jwt_for_account(db_path, account_id)
    if not jwt:
        raise JwtExpired(f"JWT expirado o ausente para cuenta {account_id}: {info}")

    proxy_url = _get_admin_proxy_url()
    if not proxy_url:
        logger.warning(
            f"[withdrawals] proxy pool seco para cuenta {account_id}; "
            "retiro sin proxy — posible fuga de IP real"
        )
        warnings.append("proxy_pool_vacio")

    # PASO 1 — leer cuenta de retiro FRESCA (no cachear — bug#1)
    approved = await get_bank_accounts(jwt, proxy_url)
    account = approved[0]
    account_id_bmx = account["accountId"]
    account_digits = str(account.get("account", ""))[-4:]
    institution_name = account.get("institutionName", "")

    # PASO 2 — verificar saldo Real
    balance = await get_real_balance(jwt, proxy_url)
    real = float(balance.get("Real", 0))
    if real < amount:
        raise InsufficientBalance(
            f"Saldo insuficiente: Real=${real:.2f}, solicitado=${amount:.2f}"
        )

    # PASO 3 — disparar retiro (SINGLE-SHOT)
    result = await begin_withdrawal(
        jwt=jwt,
        proxy_url=proxy_url,
        account_id_bmx=account_id_bmx,
        amount=float(amount),
        email=email or "",
    )

    logger.info(
        f"[withdrawals] cuenta {account_id} ({email}): retiro ${amount:.2f} disparado, "
        f"transactionId={result.get('transactionId')}, destino={institution_name} ···{account_digits}"
    )

    # Bug 2 (handoff 2026-08-07): persistir withdrawal_institution con la
    # institución REALMENTE usada en ESTA transacción (resultado de SU PROPIA
    # llamada a get_bank_accounts arriba, PASO1). Antes, el único que escribía
    # withdrawal_institution era account_refresh.py (hasta 20 min después) con
    # su PROPIA llamada independiente a get_bank_accounts — dos fuentes podían
    # divergir en la misma ventana de tiempo (medido en vivo: cuenta 1632,
    # badge "BANAMEX" vs retiro real a "INBURSA" en el mismo segundo). No-throw:
    # el retiro YA se disparó, un fallo de persistencia aquí no lo afecta.
    try:
        con = sqlite3.connect(db_path, timeout=10)
        con.execute(
            "UPDATE accounts SET withdrawal_ready=?, withdrawal_institution=? WHERE email=?",
            (1, institution_name, email or ""),
        )
        con.commit()
        con.close()
    except Exception as e:
        logger.debug(
            f"[withdrawals] persist withdrawal_institution {email}: {str(e)[:120]}"
        )

    return {
        "transactionId": result["transactionId"],
        "reference": result.get("reference"),
        "accountId": account_id_bmx,
        "accountDigits": account_digits,
        "institutionName": institution_name,
        "amount": float(amount),
        "account_email": email or "",
        "warnings": warnings,
        # Internos (underscore) para que app.py pueda pasarlos al refresh
        # post-retiro sin recargarlos de BD (el JWT y proxy que YA tenemos en
        # mano, sin gastar captcha de nuevo). No son parte del contrato público.
        "_jwt": jwt,
        "_proxy_url": proxy_url,
    }


async def _refresh_account_after_withdrawal(
    email: str,
    jwt: Optional[str],
    used_proxy: Optional[str],
    operator_id: int,
) -> None:
    """Tras un retiro, refresca balance + movimientos de la cuenta REUSANDO el
    JWT del login que ya se hizo (sin gastar captcha) y los persiste en BD.
    Espejo de `deposits._refresh_account_after_deposit` (Robert 2026-08-05,
    handoff §2.3): antes el dashboard solo actualizaba balance en el próximo
    ciclo de `account_refresh.py` (5 min de lag), o cuando el operador picaba
    "Actualizar" manual. Tras un retiro, el saldo DEBE verse reflejado de
    inmediato — el retiro ya se ejecutó en BetMexico, este refresh solo trae
    el estado post-retiro a BD.

    No-throws: un fallo aquí NO debe afectar el resultado del retiro ya emitido
    (igual que el patrón de deposits). Emite `account_refreshed` por SSE para
    que el frontend repinte la fila.

    ponytail: es 95% idéntico a deposits._refresh_account_after_deposit. El
    upgrade path es extraer un `refresh_account_after_action(email, jwt, proxy,
    operator_id, log_tag)` en prewarm.py y hacer ambos wrappers thin — fuera
    de scope de este handoff que pide explícitamente el espejo.
    """
    if not jwt:
        return
    try:
        from betmexico_login_api import BetmexicoApiChecker

        async with BetmexicoApiChecker(proxy=used_proxy) as checker:
            details = await asyncio.wait_for(
                checker.fetch_account_details_parallel(jwt, fetch_mode="full"),
                timeout=15.0,
            )
        if not details:
            return
        from prewarm import (
            _db_upsert_balance,
            _db_save_txns_and_recalc,
            _fetch_looks_empty,
            _db_invalidate_jwt,
        )

        # `fetch_account_details_parallel` siempre devuelve dict truthy con
        # defaults; si quedó todo vacío el JWT murió server-side (401). No
        # persistir (pisaría saldo) — invalidar JWT y salir. El próximo
        # depósito/refresh/jwt_keeper hará login real.
        if _fetch_looks_empty(details):
            logger.info(
                f"[withdrawals] refresh post-retiro {email} vacío (JWT muerto) — cache invalidado"
            )
            try:
                await asyncio.to_thread(_db_invalidate_jwt, email)
            except Exception:
                pass
            return
        await asyncio.to_thread(_db_upsert_balance, email, details)
        await asyncio.to_thread(_db_save_txns_and_recalc, email, details, operator_id)
        logger.info(
            f"[withdrawals] refresh post-retiro OK {email} "
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
                    **_resolve_who(operator_id),
                }
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[withdrawals] refresh post-retiro {email}: {str(e)[:160]}")
