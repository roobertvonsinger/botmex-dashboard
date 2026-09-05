#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clabe_fetch — obtiene las clabes de depósito SPEI (NVIO + STP) de una cuenta
BetMexico vía `POST /api/stp/BeginDeposit` con JWT cacheado + proxy del pool.

Las clabes son FIJAS por usuario → se persisten en BD (tabla
`account_deposit_clabes`) una sola vez. NO se llama BeginDeposit en cada
refresh (alimentaría el rate-limit de BetMexico por tráfico innecesario;
ver docs/ERRORS.md §rate-limit). Solo se re-obtiene vía acción manual
del operador (botón "Refrescar clabes" en La Pantalla).

Patrón de fetch replicado de _legacy/web_routes_deposits.py + tools/bmx_call.py:
  httpx.AsyncClient(proxy=<url>, verify=False)
  header Authorization: Bearer {jwt}
  host paymentsapi.betmexico.mx
NUNCA proxyless en prod (filtra IP real del server — feedback_nunca_proxyless).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("betmexico.dashboard.clabe_fetch")

BETMEXICO_PAYMENTS_API = "https://paymentsapi.betmexico.mx"
BEGIN_DEPOSIT_PATH = "/api/stp/BeginDeposit"
BEGIN_DEPOSIT_URL = f"{BETMEXICO_PAYMENTS_API}{BEGIN_DEPOSIT_PATH}"


def _load_jwt_for_account(db_path: str, account_id: int) -> tuple[Optional[str], Optional[str], str]:
    """Lee (jwt_token, email, status_info) de la BD para una cuenta por id.

    Devuelve (jwt, email, info). jwt=None si no hay cuenta o no hay JWT vigente.
    """
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        r = con.execute(
            "SELECT email, jwt_token, jwt_expires_at, status "
            "FROM accounts WHERE id=? LIMIT 1",
            (account_id,),
        ).fetchone()
    finally:
        con.close()
    if not r:
        return None, None, f"no existe cuenta id={account_id}"
    jwt = r["jwt_token"]
    email = r["email"]
    exp = r["jwt_expires_at"]
    status = r["status"]
    if not jwt:
        return None, email, f"sin jwt_token (status={status})"
    if exp and int(exp) < int(time.time()):
        return None, email, f"jwt EXPIRADO (status={status})"
    return jwt, email, f"ok status={status}"


def _get_admin_proxy_url() -> Optional[str]:
    """Proxy del pool (nunca proxyless en prod). Helper canónico de proxy_pool."""
    try:
        import proxy_pool as pp
        return pp.build_admin_proxy_url()
    except Exception as e:
        logger.warning(f"[clabe_fetch] proxy_pool no disponible: {e}")
        return None


async def fetch_clabes_from_betmexico(jwt: str, proxy_url: Optional[str]) -> dict:
    """Pega POST /api/stp/BeginDeposit (sin body) con JWT + proxy.

    Devuelve el dict de respuesta de BetMexico:
      {reference, userId, fullName, accounts:[{account, blocked, order, integration}]}
    Lanza RuntimeError si la API responde != 200 o sin accounts.
    """
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://betmexico.mx",
        "Referer": "https://betmexico.mx/",
    }
    async with httpx.AsyncClient(timeout=30.0, verify=False, proxy=proxy_url) as client:
        r = await client.post(BEGIN_DEPOSIT_URL, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"BeginDeposit HTTP {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"BeginDeposit respuesta no-JSON: {e}")
    if not isinstance(data, dict) or "accounts" not in data:
        raise RuntimeError(f"BeginDeposit sin 'accounts': {json.dumps(data, ensure_ascii=False)[:300]}")
    return data


def _persist_clabes(db_path: str, account_id: int, email: str, data: dict) -> int:
    """Persiste las clabes en account_deposit_clabes (idempotente: UNIQUE(account_id, clabe)).

    Reemplaza las clabes previas de la cuenta (delete + insert) para reflejar
    cambios de blocked/order. Devuelve el nº de clabes guardadas.
    """
    accounts = data.get("accounts") or []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(db_path, timeout=30.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout = 30000")
        con.execute("PRAGMA synchronous = NORMAL")
        con.execute("DELETE FROM account_deposit_clabes WHERE account_id=?", (account_id,))
        for a in accounts:
            clabe = a.get("account")
            if not clabe:
                continue
            con.execute(
                "INSERT OR REPLACE INTO account_deposit_clabes "
                "(account_id, account_email, reference, user_id, full_name, "
                " clabe, integration, clabe_order, blocked, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    account_id,
                    email,
                    data.get("reference"),
                    data.get("userId"),
                    data.get("fullName"),
                    str(clabe),
                    a.get("integration"),
                    a.get("order"),
                    1 if a.get("blocked") else 0,
                    now,
                ),
            )
        con.commit()
        return len(accounts)
    finally:
        con.close()


def get_saved_clabes(db_path: str, account_id: int) -> list[dict]:
    """Lee las clabes persistidas de una cuenta. [] si no hay."""
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, account_id, account_email, reference, user_id, full_name, "
            "clabe, integration, clabe_order, blocked, fetched_at "
            "FROM account_deposit_clabes WHERE account_id=? "
            "ORDER BY clabe_order ASC",
            (account_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


async def refresh_clabes_for_account(db_path: str, account_id: int) -> dict:
    """Orquesta: lee JWT de BD → obtiene proxy → fetch BeginDeposit → persiste.

    Devuelve {ok, clabes:[...], info, error?}. Idempotente: siempre reemplaza.
    Es la función que llama el endpoint POST /api/accounts/{id}/clabes/refresh.
    """
    jwt, email, info = _load_jwt_for_account(db_path, account_id)
    if not jwt:
        return {"ok": False, "clabes": [], "info": info,
                "error": "Sin JWT vigente para esta cuenta"}
    proxy_url = _get_admin_proxy_url()
    if not proxy_url:
        logger.warning(f"[clabe_fetch] proxy pool seco para cuenta {account_id}; "
                       f"intentando SIN proxy (SOLO acceptable si no hay pool)")
    try:
        data = await fetch_clabes_from_betmexico(jwt, proxy_url)
    except Exception as e:
        logger.error(f"[clabe_fetch] BeginDeposit falló para cuenta {account_id}: {e}")
        return {"ok": False, "clabes": [], "info": info, "error": str(e)}
    try:
        n = _persist_clabes(db_path, account_id, email or "", data)
    except Exception as e:
        logger.error(f"[clabe_fetch] persist falló para cuenta {account_id}: {e}")
        return {"ok": False, "clabes": [], "info": info, "error": f"persist: {e}"}
    saved = get_saved_clabes(db_path, account_id)
    logger.info(f"[clabe_fetch] cuenta {account_id} ({email}): {n} clabes guardadas")
    return {"ok": True, "clabes": saved, "info": info}
