"""Tests para el bot Telegram Mock en telegram_bot_mock/bot.py."""

import pytest
import sqlite3
import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat, Document, BotCommandScopeChat
from telegram.ext import ConversationHandler

import app as app_mod
from app import db, filter_and_sanitize_check_combos
import telegram_bot_mock.config as mock_config
import telegram_bot_mock.bot as mock_bot
from telegram_bot_mock.config import is_authorized, SUPERADMIN_ID
from telegram_bot_mock.bot import (
    start_cmd,
    help_cmd,
    botmex_cmd,
    cancel_cmd,
    check_cmd,
    bet_cmd,
    process_check_input,
    process_bet_input,
    handle_check_callback,
    handle_bet_callback,
    start_buttons_callback,
    setup_bot_commands,
    _run_check_task,
    WAIT_CHECK_CONFIRM,
    WAIT_BET_CONFIRM,
)


@pytest.fixture(autouse=True)
def _patch_bot_db_path(seed_db, monkeypatch):
    """Asegura que app.DB_PATH y mock_bot.DB_PATH apunten a la BD temporal de seed_db."""
    db_str = str(seed_db)
    monkeypatch.setattr(app_mod, "DB_PATH", seed_db)
    monkeypatch.setattr(mock_config, "DB_PATH", seed_db)
    monkeypatch.setattr(mock_bot, "DB_PATH", seed_db)
    _ensure_tables()


def _ensure_tables():
    """Crea tablas adicionales requeridas por el bot si no están en la fixture seed_db."""
    with db(write=True) as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS operator_penalties ("
            "telegram_id INTEGER PRIMARY KEY, "
            "strikes_count INTEGER NOT NULL DEFAULT 0, "
            "penalty_until TEXT, "
            "last_strike_at TEXT)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS auto_missions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "mission_id TEXT UNIQUE NOT NULL, "
            "operator_id INTEGER NOT NULL, "
            "operator_name TEXT, "
            "status TEXT NOT NULL, "
            "phase TEXT, "
            "phase_detail TEXT, "
            "card_pipes TEXT NOT NULL, "
            "amount REAL NOT NULL, "
            "target_count INTEGER NOT NULL, "
            "accounts_selected TEXT, "
            "matches TEXT, "
            "scheduled_batch_id TEXT, "
            "created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL, "
            "completed_at TEXT)"
        )


def test_authorization_check():
    assert is_authorized(SUPERADMIN_ID) is True
    assert is_authorized(7599631505) is True
    assert is_authorized(9999999999) is False


@pytest.mark.asyncio
async def test_start_cmd_unauthorized():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 9999999999
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    await start_cmd(update, None)
    args, kwargs = update.message.reply_text.call_args
    assert "Acceso denegado" in args[0]


@pytest.mark.asyncio
async def test_start_cmd_authorized():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    await start_cmd(update, None)
    assert update.message.reply_photo.called
    args, kwargs = update.message.reply_photo.call_args
    assert "ʙ ᴏ ᴛ · ᴍ ᴇ x ɪ ᴄ ᴏ" in kwargs.get("caption", "")
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_help_cmd():
    update = MagicMock(spec=Update)
    update.message = AsyncMock(spec=Message)

    await help_cmd(update, None)
    args, kwargs = update.message.reply_text.call_args
    assert "Manual Operativo BoTMexico" in args[0]
    # /adduser es operativo exclusivo del Superadmin: NO debe pregonarse en /help
    assert "adduser" not in args[0]
    # El help siempre trae salida de vuelta al inicio
    kb = kwargs.get("reply_markup")
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "🏠 Volver al inicio" in labels


@pytest.mark.asyncio
async def test_help_btn_start_help_keeps_home_button():
    """El help abierto desde el botón del /start también debe tener 'Volver al inicio'."""
    query = AsyncMock()
    query.data = "btn_start_help"
    query.message = MagicMock()
    query.message.photo = [MagicMock()]

    update = MagicMock(spec=Update)
    update.callback_query = query

    res = await start_buttons_callback(update, None)
    args, kwargs = query.edit_message_caption.call_args
    assert "Manual Operativo BoTMexico" in kwargs["caption"]
    kb = kwargs.get("reply_markup")
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "🏠 Volver al inicio" in labels


@pytest.mark.asyncio
async def test_btn_start_cancel_returns_to_start_menu(seed_db):
    """'Volver al inicio' cancela misiones activas y re-renderiza el menú principal."""
    query = AsyncMock()
    query.data = "btn_start_cancel"
    query.message = MagicMock()
    query.message.photo = [MagicMock()]

    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.callback_query = query

    context = MagicMock()
    context.user_data = {"some_key": "some_val"}

    res = await start_buttons_callback(update, context)
    assert res == ConversationHandler.END
    args, kwargs = query.edit_message_caption.call_args
    assert "ʙ ᴏ ᴛ · ᴍ ᴇ x ɪ ᴄ ᴏ" in kwargs["caption"]
    assert kwargs.get("parse_mode") == "HTML"
    kb = kwargs.get("reply_markup")
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "💳 CC Auto-Match" in labels


@pytest.mark.asyncio
async def test_setup_bot_commands_scopes_adduser_to_superadmin():
    """El menú nativo NO publica /adduser: va solo en el scope del chat del Superadmin."""
    bot = AsyncMock()
    application = MagicMock()
    application.bot = bot

    await setup_bot_commands(application)

    # Default scope: sin adduser
    default_cmds, default_kwargs = bot.set_my_commands.call_args_list[0]
    assert all(cmd.command != "adduser" for cmd in default_cmds[0])
    assert "scope" not in default_kwargs or default_kwargs["scope"] is None
    # Scope del Superadmin: adduser presente
    scoped_cmds, scoped_kwargs = bot.set_my_commands.call_args_list[1]
    assert any(cmd.command == "adduser" for cmd in scoped_cmds[0])
    scope = scoped_kwargs["scope"]
    assert isinstance(scope, BotCommandScopeChat)
    assert scope.chat_id == SUPERADMIN_ID


@pytest.mark.asyncio
async def test_botmex_cmd():
    update = MagicMock(spec=Update)
    update.message = AsyncMock(spec=Message)

    await botmex_cmd(update, None)
    args, kwargs = update.message.reply_text.call_args
    assert "Acceso directo al portal web" in args[0]


@pytest.mark.asyncio
async def test_cancel_cmd(seed_db):
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    context = MagicMock()
    context.bot_data = {}
    context.user_data = {"some_key": "some_val"}

    res = await cancel_cmd(update, context)
    assert res == ConversationHandler.END
    assert len(context.user_data) == 0
    assert update.message.reply_text.called


@pytest.mark.asyncio
async def test_check_cmd_unauthorized():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 9999999999
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    res = await check_cmd(update, None)
    assert res == ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBAS /CHECK: COMBOS MALFORMADOS, LÍMITES Y ENCODINGS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_input_limits_102_combos(seed_db):
    """Prueba envío de 102 combos en texto chat (excede límite de 100)."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    text_combos = "\n".join([f"user{i}@test.com:pass{i}" for i in range(102)])
    update.message.text = text_combos
    update.message.document = None

    context = MagicMock()
    context.user_data = {}

    res = await process_check_input(update, context)
    assert res == WAIT_CHECK_CONFIRM
    update.message.reply_text.assert_called_with("❌ Máximo 100 combos en chat. Para más, adjunta un archivo .txt (hasta 5,000).")


@pytest.mark.asyncio
async def test_check_input_empty_text():
    """Prueba envío de texto vacío o con puros espacios."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)
    update.message.document = None
    update.message.text = "   \n  \n "

    context = MagicMock()
    context.user_data = {}

    res = await process_check_input(update, context)
    assert res == WAIT_CHECK_CONFIRM
    update.message.reply_text.assert_called_with("❌ No se encontraron combos en la entrada.")


@pytest.mark.asyncio
async def test_check_input_malformed_text(seed_db):
    """Envío de combos con tarjetas que fallan la validación Luhn / liveness."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)
    update.message.document = None
    # Tarjeta que falla la prueba Luhn (4000000000000002)
    update.message.text = "user_invalid_card@test.com:pass123:4000000000000002|12|28|123\n"

    context = MagicMock()
    context.user_data = {}

    res = await process_check_input(update, context)
    assert res == ConversationHandler.END
    args, kwargs = update.message.reply_text.call_args
    assert "NINGÚN COMBO SUPERÓ LAS VALIDACIONES" in args[0]


@pytest.mark.asyncio
async def test_check_input_non_txt_document():
    """Envío de documento con extensión distinta a .txt (ej. .csv)."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    doc = MagicMock(spec=Document)
    doc.file_name = "combos.csv"
    update.message.document = doc

    context = MagicMock()
    context.user_data = {}

    res = await process_check_input(update, context)
    assert res == WAIT_CHECK_CONFIRM
    update.message.reply_text.assert_called_with("❌ Solo se admiten archivos con extensión .txt")


@pytest.mark.asyncio
async def test_check_input_document_encodings_latin1_and_utf16(seed_db):
    """Envío de archivo .txt con codificación latin-1 y utf-16."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    # 1. Probar Latin-1 con caracteres especiales (ej. ñ)
    doc_latin1 = MagicMock(spec=Document)
    doc_latin1.file_name = "combos_latin1.txt"
    doc_latin1.file_id = "fid_latin1"
    update.message.document = doc_latin1

    context = MagicMock()
    context.user_data = {}

    latin1_content = bytearray("latin_user@test.com:pass123\n".encode("latin-1"))
    tg_file1 = MagicMock()
    tg_file1.download_as_bytearray = AsyncMock(return_value=latin1_content)
    context.bot.get_file = AsyncMock(return_value=tg_file1)

    res1 = await process_check_input(update, context)
    assert res1 == WAIT_CHECK_CONFIRM
    assert len(context.user_data["pending_check"]) == 1
    assert context.user_data["pending_check"][0]["email"] == "latin_user@test.com"

    # 2. Probar UTF-16
    doc_utf16 = MagicMock(spec=Document)
    doc_utf16.file_name = "combos_utf16.txt"
    doc_utf16.file_id = "fid_utf16"
    update.message.document = doc_utf16
    context.user_data = {}

    utf16_content = bytearray("utf16_user@test.com:pass123\n".encode("utf-16"))
    tg_file2 = MagicMock()
    tg_file2.download_as_bytearray = AsyncMock(return_value=utf16_content)
    context.bot.get_file = AsyncMock(return_value=tg_file2)

    res2 = await process_check_input(update, context)
    assert res2 == WAIT_CHECK_CONFIRM


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBAS DE CANCELACIÓN (/CANCEL)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_during_conversation_and_task(seed_db):
    """Simulación de /cancel durante un ConversationHandler y cancelación en BD."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    # Insertar una misión activa en BD
    with db(write=True) as c:
        c.execute(
            "INSERT INTO auto_missions (mission_id, operator_id, status, card_pipes, amount, target_count, created_at, updated_at) "
            "VALUES ('m_test_cancel', ?, 'running', 'pipe', 150.0, 9, 'now', 'now')",
            (SUPERADMIN_ID,)
        )

    context = MagicMock()
    context.user_data = {"pending_check": [{"email": "test@test.com"}]}

    res = await cancel_cmd(update, context)
    assert res == ConversationHandler.END
    assert len(context.user_data) == 0

    with db(write=True) as c:
        row = c.execute("SELECT status FROM auto_missions WHERE mission_id='m_test_cancel'").fetchone()
        assert row["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_callbacks(seed_db):
    """Prueba de cancelación usando botones Inline (cancel_check y cancel_bet)."""
    # Callback check
    query_c = AsyncMock()
    query_c.data = "cancel_check"
    update_c = MagicMock(spec=Update)
    update_c.callback_query = query_c
    context_c = MagicMock()
    context_c.user_data = {"pending_check": [{"email": "a@b.com"}]}

    res_c = await handle_check_callback(update_c, context_c)
    assert res_c == ConversationHandler.END
    assert "pending_check" not in context_c.user_data
    query_c.edit_message_text.assert_called_with("❌ Verificación /check cancelada.")

    # Callback bet
    query_b = AsyncMock()
    query_b.data = "cancel_bet"
    update_b = MagicMock(spec=Update)
    update_b.callback_query = query_b
    context_b = MagicMock()
    context_b.user_data = {"pending_bet_pipes": ["4532015112830366|12|28|123"]}

    res_b = await handle_bet_callback(update_b, context_b)
    assert res_b == ConversationHandler.END
    assert "pending_bet_pipes" not in context_b.user_data
    query_b.edit_message_text.assert_called_with("❌ Proceso /bet cancelado.")


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBAS /BET: 0 Y 5 TARJETAS, SIN CUENTAS, COOLDOWN
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bet_input_zero_cards(seed_db):
    """Envío de 0 tarjetas en /bet."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)
    update.message.text = "   "

    context = MagicMock()
    context.user_data = {}

    res = await process_bet_input(update, context)
    assert res == WAIT_BET_CONFIRM
    update.message.reply_text.assert_called_with("❌ Debes enviar entre 1 y 4 tarjetas por intento.")


@pytest.mark.asyncio
async def test_bet_input_five_cards(seed_db):
    """Envío de 5 tarjetas en /bet."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)
    pipes = "\n".join(["4532015112830366|12|28|123"] * 5)
    update.message.text = pipes

    context = MagicMock()
    context.user_data = {}

    res = await process_bet_input(update, context)
    assert res == WAIT_BET_CONFIRM
    update.message.reply_text.assert_called_with("❌ Debes enviar entre 1 y 4 tarjetas por intento.")


@pytest.mark.asyncio
async def test_bet_no_accounts_available(seed_db):
    """Intento de /bet cuando la BD no tiene cuentas aptas (o plan_auto_mission no es feasible)."""
    query = AsyncMock()
    query.data = "confirm_bet"

    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.callback_query = query

    context = MagicMock()
    context.user_data = {"pending_bet_pipes": ["4532015112830366|12|28|123"]}

    # Cuentas en BD sin JWT ni elegibilidad
    with db(write=True) as c:
        c.execute("UPDATE accounts SET status='DEAD'")

    res = await handle_bet_callback(update, context)
    assert res == ConversationHandler.END
    args, kwargs = query.edit_message_text.call_args
    assert "No fue posible armar el plan" in args[0]


@pytest.mark.asyncio
async def test_bet_card_invalid_or_cooldown(seed_db):
    """Intento de /bet cuando la tarjeta falla liveness (Luhn o cooldown)."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)
    # Tarjeta que falla Luhn
    update.message.text = "4000000000000002|12|28|123"

    context = MagicMock()
    context.user_data = {}

    res = await process_bet_input(update, context)
    assert res == ConversationHandler.END
    status_msg = update.message.reply_text.return_value
    args, kwargs = status_msg.edit_text.call_args
    assert "CARDING FALLIDO" in args[0] or "NO SE DETECTARON TARJETAS LIVE" in args[0]


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBA DEDUPLICACIÓN EN BD Y COMBOS
# ─────────────────────────────────────────────────────────────────────────────

def test_db_duplicates_and_deduplication(seed_db):
    """Inserción de duplicados en la BD y verificación de deduplicación con filter_and_sanitize_check_combos."""
    with db(write=True) as c:
        c.execute(
            "INSERT OR IGNORE INTO accounts (email, password, status, first_checked_at, last_checked_at) "
            "VALUES ('dup_email@test.com', 'pass123', 'LIVE', '2026-01-01', '2026-01-01')"
        )
        c.execute(
            "INSERT OR IGNORE INTO account_cards (account_email, card_number) "
            "VALUES ('existing_card_user@test.com', '4532015112830366')"
        )

    combos = [
        "dup_email@test.com:pass123", # Ya en BD (email)
        "new1@test.com:pass123:4532015112830366|12|28|123", # Ya en BD (tarjeta)
        "new2@test.com:pass123:5579070133314628|12|28|123", # Válido 1
        "new2@test.com:pass123:5579070133314628|12|28|123", # Duplicado exacto en la misma lista
    ]

    res = filter_and_sanitize_check_combos(combos)
    assert res["total_received"] == 4
    assert res["dupes_count"] == 1
    assert "dup_email@test.com" in res["in_db_emails"]
    assert "4532015112830366" in res["in_db_cards"]
    assert len(res["valid_combos"]) == 1
    assert res["valid_combos"][0]["email"] == "new2@test.com"
