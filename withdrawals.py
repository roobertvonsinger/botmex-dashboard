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

import json
import logging
import time
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
            f"{a.get('institutionName','?')} ···{str(a.get('account',''))[-4:]}"
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
        raise RuntimeError(f"BeginWithdrawal sin transactionId en 200: {json.dumps(data)[:300]}")

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

    return {
        "transactionId": result["transactionId"],
        "reference": result.get("reference"),
        "accountId": account_id_bmx,
        "accountDigits": account_digits,
        "institutionName": institution_name,
        "amount": float(amount),
        "account_email": email or "",
        "warnings": warnings,
    }
