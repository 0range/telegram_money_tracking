import pytest
from aiogram import Dispatcher
from aiogram.client.default import DefaultBotProperties
from bot import dp

@pytest.fixture
def mock_bot():
    return MagicMock()

@pytest.fixture
def dispatcher():
    return dp
