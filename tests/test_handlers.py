import pytest
from aiogram import types
from unittest.mock import AsyncMock, MagicMock, patch
from bot import dp, get_main_menu, get_categories_keyboard

@pytest.mark.asyncio
async def test_start_command():
    message = MagicMock()
    message.text = "/start"
    message.from_user = MagicMock(id=123)
    message.answer = AsyncMock()
    
    await dp.feed_update(bot=MagicMock(), update=types.Update(message=message))
    
    message.answer.assert_called_with(
        "Добро пожаловать! 🤑\nВыберите действие:",
        reply_markup=get_main_menu()
    )

@pytest.mark.asyncio
async def test_create_family_flow():
    message = MagicMock()
    message.text = "Создать семью"
    message.from_user = MagicMock(id=456)
    message.answer = AsyncMock()

    with patch('bot.generate_family_id', return_value='family-ABC123'):
        await dp.feed_update(bot=MagicMock(), update=types.Update(message=message))
        
    assert "Семья успешно создана" in message.answer.call_args[0][0]
    assert 'family-ABC123' in message.answer.call_args[0][0]
