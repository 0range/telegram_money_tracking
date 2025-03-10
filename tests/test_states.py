import pytest
from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from unittest.mock import MagicMock, AsyncMock, patch
from bot import BudgetStates
import datetime

@pytest.mark.asyncio
async def test_budget_flow():
    dispatcher = Dispatcher(storage=MemoryStorage())
    message = types.Message(
        message_id=456,
        date=datetime.datetime.now(),
        chat=types.Chat(id=789, type="private"),
        from_user=types.User(id=789, is_bot=False, first_name="Test"),
        text="Управление бюджетами"
    )
    
    fake_update = types.Update(update_id=456, message=message)
    
    mock_bot = MagicMock()
    await dispatcher.feed_update(mock_bot, fake_update)
    
    # Проверяем отправку клавиатуры
    mock_bot.send_message.assert_called_with(
        chat_id=789,
        text="Управление бюджетами:",
        reply_markup=...
    )
