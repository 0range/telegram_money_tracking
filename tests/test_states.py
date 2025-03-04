import pytest
from aiogram import Dispatcher
from bot import dp, BudgetStates
from aiogram.fsm.storage.memory import MemoryStorage

@pytest.mark.asyncio
async def test_budget_flow():
    dispatcher = Dispatcher(storage=MemoryStorage())
    message = MagicMock()
    message.text = "Управление бюджетами"
    message.from_user = MagicMock(id=789)
    message.answer = AsyncMock()

    # Начало процесса установки бюджета
    await dispatcher.feed_update(bot=MagicMock(), update=types.Update(message=message))
    message.answer.assert_called_with("Управление бюджетами:", reply_markup=...)

    # Выбор категории
    callback = MagicMock()
    callback.data = "🍔 Еда вне дома"
    callback.from_user = MagicMock(id=789)
    await dispatcher.feed_update(bot=MagicMock(), update=types.Update(callback_query=callback))
    
    # Проверка состояния
    state = dispatcher.fsm.get_context(bot=MagicMock(), user_id=789, chat_id=789)
    assert await state.get_state() == BudgetStates.ENTER_AMOUNT
