"""Shared fixtures for handler tests."""
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


@pytest.fixture
def mock_message():
    """Create a mock Telegram Message object."""
    msg = MagicMock()
    msg.chat.id = 12345
    msg.message_id = 100
    msg.text = ""
    msg.from_user = MagicMock()
    msg.from_user.id = 12345
    msg.from_user.username = "testuser"
    msg.from_user.first_name = "Test"
    msg.from_user.is_bot = False
    msg.answer = AsyncMock(return_value=msg)
    msg.edit_text = AsyncMock(return_value=msg)
    msg.edit_reply_markup = AsyncMock(return_value=msg)
    msg.delete = AsyncMock(return_value=True)
    msg.reply = AsyncMock(return_value=msg)
    msg.reply_markup = None
    return msg


@pytest.fixture
def mock_callback_query():
    """Create a mock Telegram CallbackQuery object."""
    cq = MagicMock()
    cq.id = "cb_123"
    cq.data = ""
    cq.message = MagicMock()
    cq.message.chat.id = 12345
    cq.message.message_id = 100
    cq.message.edit_text = AsyncMock(return_value=cq.message)
    cq.message.edit_reply_markup = AsyncMock(return_value=cq.message)
    cq.message.delete = AsyncMock(return_value=True)
    cq.from_user = MagicMock()
    cq.from_user.id = 12345
    cq.from_user.username = "testuser"
    cq.from_user.first_name = "Test"
    cq.from_user.is_bot = False
    cq.answer = AsyncMock()
    return cq


@pytest.fixture
def mock_bot():
    """Create a mock Bot object."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_audio = AsyncMock()
    bot.send_video = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_file = AsyncMock()
    bot.forward_message = AsyncMock()
    return bot