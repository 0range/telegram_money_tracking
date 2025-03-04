import pytest
from aiogram import Dispatcher
from bot import dp

@pytest.fixture
def mock_bot():
    return MagicMock()

@pytest.fixture
def dispatcher():
    return dp
