"""Tests para el bot Telegram Mock en telegram_bot_mock/bot.py."""

import pytest
import sqlite3
import sys
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
from login_orchestrator import LoginResult
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
    handle_retry_mission_callback,
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
    # Scope del Superadmin: REEMPLAZA el default, así que debe llevar TODOS los
    # comandos (start/help/cancel) + adduser — sino se borran del menú del SA.
    scoped_cmds, scoped_kwargs = bot.set_my_commands.call_args_list[1]
    scoped_names = {cmd.command for cmd in scoped_cmds[0]}
    assert "adduser" in scoped_names
    assert {"start", "help", "cancel"}.issubset(scoped_names)
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
    args, kwargs = update.message.reply_text.call_args
    assert "CARDING FALLIDO" in args[0] or "NO SE DETECTARON TARJETAS LIVE" in args[0]


@pytest.mark.asyncio
async def test_bet_confirm_splits_live_tol(seed_db, monkeypatch):
    """D1 (RF1/RF3/RF7): /bet separa live/tol, guarda pendientes y espera confirmación."""
    import card_checker

    def fake_bridge(pipe_4parts):
        # 4555... -> live (Approved); 416916... -> Declined, pero BIN tolerado -> tol_bin
        if pipe_4parts.startswith("45552900000000040"):
            return ("Approved", "Card Updated (Last4: 0040)")
        return ("Declined", "declined")

    monkeypatch.setattr(card_checker, "ruthopia_bridge_check", fake_bridge)

    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)
    update.message.text = (
        "45552900000000040|12|28|123\n"
        "41691600000000070|12|28|123"
    )
    context = MagicMock()
    context.user_data = {}

    res = await process_bet_input(update, context)
    assert res == WAIT_BET_CONFIRM

    # Live + tol pasan a pending_bet_pipes; solo la tol queda en pending_tol_pipes
    pending = context.user_data["pending_bet_pipes"]
    assert "45552900000000040|1228|123" in pending
    assert "41691600000000070|1228|123" in pending
    assert "41691600000000070|1228|123" in context.user_data["pending_tol_pipes"]
    assert "45552900000000040|1228|123" not in context.user_data["pending_tol_pipes"]

    # Mensaje de confirmación con conteo + botones confirm/cancel
    args, kwargs = update.message.reply_text.call_args
    assert "Toleradas" in args[0]
    kb = kwargs["reply_markup"]
    flat = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "confirm_bet" in flat
    assert "cancel_bet" in flat


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBA DEDUPLICACIÓN EN BD Y COMBOS
# ─────────────────────────────────────────────────────────────────────────────

def test_db_duplicates_and_deduplication(seed_db, monkeypatch):
    """Inserción de duplicados en la BD y verificación de deduplicación con filter_and_sanitize_check_combos."""
    import card_checker
    # Dedup es el objetivo de este test — el liveness real se mockea
    monkeypatch.setattr(card_checker, "ruthopia_bridge_check", lambda p: ("Approved", "Card Updated (Last4: 1111)"))
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


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBA _run_check_task — RAMA DEAD (regresión: LoginResult no tiene .status)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_check_task_marks_dead_account_without_crashing(seed_db, monkeypatch):
    """Una cuenta DEAD no debe tumbar el batch completo con AttributeError."""
    monkeypatch.delenv("CAPMONSTER_KEY", raising=False)
    monkeypatch.delenv("BMX_CAPMONSTER_KEY", raising=False)

    # betmexico_login_service.py / betmexico_login_api.py solo existen en el VPS
    # (sibling dir al deploy); localmente se stubbean para ejercitar _run_check_task.
    module_type = importlib.import_module("types").ModuleType
    fake_login_service = module_type("betmexico_login_service")
    fake_login_service.make_pool = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "betmexico_login_service", fake_login_service)

    fake_login_api = module_type("betmexico_login_api")
    fake_login_api.BetmexicoApiChecker = MagicMock()
    monkeypatch.setitem(sys.modules, "betmexico_login_api", fake_login_api)

    dead_login = LoginResult(
        ok=False, code="LOGIN_DENIED", account_dead=True, error="credenciales invalidas"
    )
    monkeypatch.setattr(mock_bot, "gentle_login", AsyncMock(return_value=dead_login))

    marked = []
    monkeypatch.setattr(
        mock_bot, "_db_mark_dead", lambda email, reason: marked.append((email, reason))
    )

    bot = MagicMock()
    status_msg = MagicMock()
    status_msg.edit_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=status_msg)

    combos = [{"email": "dead@test.com", "password": "x", "card_pipe": ""}]

    await mock_bot._run_check_task(111, bot, combos, 1)

    assert marked == [("dead@test.com", "Check Login Failed: credenciales invalidas")]
    final_text = bot.send_message.call_args_list[-1].kwargs["text"]
    assert "Cuentas Muertas (DEAD):</b> 1" in final_text
    assert "❌ Error durante el check" not in final_text


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBA RF8 — BOTÓN "SEGUNDO INTENTO" CUANDO LA MISIÓN TERMINA SIN MATCH
# ─────────────────────────────────────────────────────────────────────────────

def _flat_callback_data(kb):
    return [b.callback_data for row in kb.inline_keyboard for b in row]


@pytest.mark.asyncio
async def test_retry_button_offered_on_failed_no_match(seed_db):
    """RF8: misión terminal failed con reason='sin matches' ofrece botón retry_mission_."""
    status_msg = AsyncMock(spec=Message)
    user_info = {"telegram_id": SUPERADMIN_ID, "username": "robertvs"}
    plan = {"accounts": [], "feasible": False, "reason": "sin matches"}

    captured = {}

    async def fake_run(mission_id, plan, user_info, on_progress=None, confirm_gate=None):
        captured["on_progress"] = on_progress

    import telegram_bot_mock.bot as bot_mod
    original = bot_mod.run_auto_mission
    bot_mod.run_auto_mission = fake_run
    try:
        bot_mod._launch_auto_mission_ui(
            MagicMock(), SUPERADMIN_ID, "m_fail", plan, user_info, status_msg
        )
    finally:
        bot_mod.run_auto_mission = original

    # dar tiempo al create_task
    await asyncio.sleep(0.1)
    assert "on_progress" in captured

    captured["on_progress"]("failed", {"reason": "sin matches"})
    await asyncio.sleep(0.1)

    args, kwargs = status_msg.edit_text.call_args
    kb = kwargs.get("reply_markup")
    flat = _flat_callback_data(kb)
    assert "retry_mission_m_fail" in flat


@pytest.mark.asyncio
async def test_retry_button_not_offered_on_other_failure(seed_db):
    """RF8: failed con otra razón NO ofrece botón retry."""
    status_msg = AsyncMock(spec=Message)
    user_info = {"telegram_id": SUPERADMIN_ID, "username": "robertvs"}
    plan = {"accounts": [], "feasible": False, "reason": "otro"}

    captured = {}

    async def fake_run(mission_id, plan, user_info, on_progress=None, confirm_gate=None):
        captured["on_progress"] = on_progress

    import telegram_bot_mock.bot as bot_mod
    original = bot_mod.run_auto_mission
    bot_mod.run_auto_mission = fake_run
    try:
        bot_mod._launch_auto_mission_ui(
            MagicMock(), SUPERADMIN_ID, "m_fail2", plan, user_info, status_msg
        )
    finally:
        bot_mod.run_auto_mission = original

    await asyncio.sleep(0.1)
    captured["on_progress"]("failed", {"reason": "otro"})
    await asyncio.sleep(0.1)

    args, kwargs = status_msg.edit_text.call_args
    kb = kwargs.get("reply_markup")
    flat = _flat_callback_data(kb)
    assert "retry_mission_m_fail2" not in flat


@pytest.mark.asyncio
async def test_retry_mission_callback_launches_new_mission(seed_db, monkeypatch):
    """RF8: el botón retry_mission_ relee la misión fallida y lanza un nuevo intento."""
    import telegram_bot_mock.bot as bot_mod

    with db(write=True) as c:
        c.execute(
            "INSERT OR REPLACE INTO auto_missions (mission_id, operator_id, status, card_pipes, amount, target_count, created_at, updated_at) "
            "VALUES ('m_old', ?, 'failed', '[\"4532015112830366|12|28|123\"]', 150.0, 9, 'now', 'now')",
            (SUPERADMIN_ID,)
        )

    monkeypatch.setattr(bot_mod, "_mission_sem", MagicMock(locked=lambda: False))

    new_id_holder = {}

    def fake_persist(mission_id, operator_id, card_pipes, amount, target_count, plan):
        new_id_holder["new_id"] = mission_id
        assert card_pipes == ["4532015112830366|12|28|123"]
        assert amount == 150.0
        assert target_count == 9

    monkeypatch.setattr(bot_mod, "_persist_auto_mission", fake_persist)

    def fake_plan(db_path, card_pipes, amount, target_count, tol_pipes=None):
        return {
            "feasible": True,
            "reason": "OK",
            "accounts": [{"id": 1, "email": "a@test.com", "card_pipe": card_pipes[0]}],
        }

    monkeypatch.setattr(bot_mod, "plan_auto_mission", fake_plan)
    monkeypatch.setattr(bot_mod, "_launch_auto_mission_ui", MagicMock())

    query = AsyncMock()
    query.data = "retry_mission_m_old"
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.callback_query = query
    context = MagicMock()

    res = await bot_mod.handle_retry_mission_callback(update, context)
    assert res == ConversationHandler.END
    assert "new_id" in new_id_holder
    assert new_id_holder["new_id"] != "m_old"
    assert bot_mod._launch_auto_mission_ui.called


@pytest.mark.asyncio
async def test_retry_mission_callback_not_authorized(seed_db):
    """RF8: un operador que no es dueño de la misión no puede reintentarla."""
    import telegram_bot_mock.bot as bot_mod

    with db(write=True) as c:
        c.execute(
            "INSERT OR REPLACE INTO auto_missions (mission_id, operator_id, status, card_pipes, amount, target_count, created_at, updated_at) "
            "VALUES ('m_own', 999, 'failed', '[\"4532015112830366|12|28|123\"]', 150.0, 9, 'now', 'now')",
        )

    query = AsyncMock()
    query.data = "retry_mission_m_own"
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.callback_query = query
    context = MagicMock()

    res = await bot_mod.handle_retry_mission_callback(update, context)
    assert res is None
    query.edit_message_text.assert_called_once_with(
        "No autorizado para reintentar esta misión.", parse_mode="HTML"
    )
