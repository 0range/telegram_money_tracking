import pytest
from aiogram import types
from unittest.mock import AsyncMock, MagicMock, patch
from bot import dp, get_main_menu, get_categories_keyboard
import datetime

@pytest.mark.asyncio
async def test_start_command():
    message = types.Message(
        message_id=123,
        date=datetime.datetime.now(),
        chat=types.Chat(id=123, type="private"),
        from_user=types.User(id=123, is_bot=False, first_name="Test"),
        text="/start"
    )
    
    # Используем fake_update для корректного создания объекта Update
    fake_update = types.Update(update_id=123, message=message)
    
    mock_bot = MagicMock()
    await dp.feed_update(mock_bot, fake_update)
    
    mock_bot.send_message.assert_called_with(
        chat_id=123,
        text="Добро пожаловать! 🤑\nВыберите действие:",
        reply_markup=get_main_menu()
    )
