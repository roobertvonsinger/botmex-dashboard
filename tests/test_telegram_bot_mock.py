"""Tests para el bot Telegram Mock en telegram_bot_mock/bot.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, User, Chat, Document
from telegram.ext import ConversationHandler

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
    WAIT_CHECK_CONFIRM,
    WAIT_BET_CONFIRM,
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
    update.message.reply_text.assert_called_once_with("❌ No estás autorizado para usar este bot.")


@pytest.mark.asyncio
async def test_start_cmd_authorized():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    await start_cmd(update, None)
    assert update.message.reply_text.called
    args, kwargs = update.message.reply_text.call_args
    assert "ʙ.ᴏᴛᴍᴇxɪᴄᴏ" in args[0]
    assert "⊢ ʙ.ᴏᴛᴍᴇx" in args[0]
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_help_cmd():
    update = MagicMock(spec=Update)
    update.message = AsyncMock(spec=Message)

    await help_cmd(update, None)
    args, kwargs = update.message.reply_text.call_args
    assert "GUÍA RÁPIDA DE COMANDOS" in args[0]


@pytest.mark.asyncio
async def test_botmex_cmd():
    update = MagicMock(spec=Update)
    update.message = AsyncMock(spec=Message)

    await botmex_cmd(update, None)
    args, kwargs = update.message.reply_text.call_args
    assert "Acceso al Dashboard Web" in args[0]


@pytest.mark.asyncio
async def test_cancel_cmd():
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


@pytest.mark.asyncio
async def test_check_input_limits(seed_db):
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    # Exceder límite de 100 combos en chat
    text_combos = "\n".join([f"user{i}@test.com:pass" for i in range(101)])
    update.message.text = text_combos
    update.message.document = None

    context = MagicMock()
    context.user_data = {}

    res = await process_check_input(update, context)
    assert res == WAIT_CHECK_CONFIRM
    update.message.reply_text.assert_called_with("❌ Máximo 100 combos en chat. Para más, adjunta un archivo .txt (hasta 5,000).")


@pytest.mark.asyncio
async def test_check_input_non_txt_document():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    doc = MagicMock(spec=Document)
    doc.file_name = "data.csv"
    update.message.document = doc

    context = MagicMock()
    context.user_data = {}

    res = await process_check_input(update, context)
    assert res == WAIT_CHECK_CONFIRM
    update.message.reply_text.assert_called_with("❌ Solo se admiten archivos con extensión .txt")


@pytest.mark.asyncio
async def test_check_input_empty():
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
async def test_bet_cmd_unauthorized():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 9999999999
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    res = await bet_cmd(update, None)
    assert res == ConversationHandler.END


@pytest.mark.asyncio
async def test_bet_input_validation(seed_db):
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = SUPERADMIN_ID
    update.effective_user = user
    update.message = AsyncMock(spec=Message)

    # Exceder límite de 4 tarjetas
    pipes = "4111111111111111|12|28|123\n" * 5
    update.message.text = pipes

    context = MagicMock()
    context.user_data = {}

    res = await process_bet_input(update, context)
    assert res == WAIT_BET_CONFIRM
    update.message.reply_text.assert_called_with("❌ Debes enviar entre 1 y 4 tarjetas por intento.")
