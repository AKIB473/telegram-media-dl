"""Tests for telegram_media_dl.handlers.settings."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram_media_dl.handlers.settings import (
    cmd_quality,
    cmd_setchat,
    cmd_mychat,
    handle_settings_callback,
)


@pytest.fixture
def mock_message():
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 12345
    msg.text = ""
    msg.answer = AsyncMock(return_value=msg)
    msg.edit_text = AsyncMock(return_value=msg)
    msg.edit_reply_markup = AsyncMock(return_value=msg)
    return msg


@pytest.fixture
def mock_callback_query():
    cb = MagicMock()
    cb.data = ""
    cb.from_user = MagicMock()
    cb.from_user.id = 12345
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.answer = AsyncMock()
    return cb


class TestCmdQuality:

    @pytest.mark.asyncio
    async def test_valid_quality(self, mock_message):
        """Setting a valid quality should succeed."""
        mock_message.text = "/quality 1080p"

        with patch("telegram_media_dl.handlers.settings.set_user_pref", new_callable=AsyncMock) as mock_set:
            await cmd_quality(mock_message)
            mock_set.assert_called_once_with(12345, "default_quality", "1080p")

        mock_message.answer.assert_called_once()
        assert "1080p" in mock_message.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_invalid_quality(self, mock_message):
        """Setting an invalid quality should show error with valid options."""
        mock_message.text = "/quality ultra"

        await cmd_quality(mock_message)

        call_text = mock_message.answer.call_args[0][0]
        assert "Invalid quality" in call_text
        for q in ["best", "1080p", "720p", "480p", "360p"]:
            assert q in call_text

    @pytest.mark.asyncio
    async def test_no_args(self, mock_message):
        """Quality command without args should show usage."""
        mock_message.text = "/quality"

        await cmd_quality(mock_message)

        call_text = mock_message.answer.call_args[0][0]
        assert "Usage:" in call_text


class TestCmdSetchat:

    @pytest.mark.asyncio
    async def test_valid_chat_id(self, mock_message):
        """Setting a target chat should succeed."""
        mock_message.text = "/setchat -1001234567890"

        with patch("telegram_media_dl.handlers.settings.set_user_pref", new_callable=AsyncMock) as mock_set:
            await cmd_setchat(mock_message)
            mock_set.assert_called_once_with(12345, "target_chat", "-1001234567890")

        call_text = mock_message.answer.call_args[0][0]
        assert "-1001234567890" in call_text

    @pytest.mark.asyncio
    async def test_no_args(self, mock_message):
        """Setchat without args should show usage."""
        mock_message.text = "/setchat"

        await cmd_setchat(mock_message)

        call_text = mock_message.answer.call_args[0][0]
        assert "Usage:" in call_text


class TestCmdMychat:

    @pytest.mark.asyncio
    async def test_with_target(self, mock_message):
        """Mychat should show configured target chat."""
        mock_prefs = {
            "default_quality": "best",
            "default_format": "video",
            "notify_complete": 1,
            "target_chat": "-1001234567890",
        }

        with patch("telegram_media_dl.handlers.settings.get_user_prefs", AsyncMock(return_value=mock_prefs)):
            await cmd_mychat(mock_message)

        call_text = mock_message.answer.call_args[0][0]
        assert "-1001234567890" in call_text

    @pytest.mark.asyncio
    async def test_no_target(self, mock_message):
        """Mychat without target should indicate no config."""
        mock_prefs = {
            "default_quality": "best",
            "default_format": "video",
            "target_chat": None,
            "notify_complete": 1,
        }

        with patch("telegram_media_dl.handlers.settings.get_user_prefs", AsyncMock(return_value=mock_prefs)):
            await cmd_mychat(mock_message)

        call_text = mock_message.answer.call_args[0][0]
        assert "No target chat" in call_text


class TestSettingsCallbacks:

    @pytest.mark.asyncio
    async def test_notify_toggles_off(self):
        """Toggling notify should flip value from 1 to 0."""
        cb = MagicMock()
        cb.data = "cfg:notify"
        cb.from_user = MagicMock()
        cb.from_user.id = 12345
        cb.message = MagicMock()
        cb.message.edit_reply_markup = AsyncMock()
        cb.answer = AsyncMock()

        with patch("telegram_media_dl.handlers.settings.get_user_prefs", return_value={
            "default_quality": "best",
            "default_format": "video",
            "notify_complete": 1,
            "target_chat": None,
        }):
            with patch("telegram_media_dl.handlers.settings.set_user_pref", new_callable=AsyncMock) as mock_set:
                await handle_settings_callback(cb)
                mock_set.assert_awaited_once_with(12345, "notify_complete", 0)

    @pytest.mark.asyncio
    async def test_format_toggles_to_audio(self):
        """Format toggle should flip from video to audio."""
        cb = MagicMock()
        cb.data = "cfg:format"
        cb.from_user = MagicMock()
        cb.from_user.id = 12345
        cb.message = MagicMock()
        cb.message.edit_reply_markup = AsyncMock()
        cb.answer = AsyncMock()

        with patch("telegram_media_dl.handlers.settings.get_user_prefs", return_value={
            "default_quality": "best",
            "default_format": "video",
            "notify_complete": 1,
            "target_chat": None,
        }):
            with patch("telegram_media_dl.handlers.settings.set_user_pref", new_callable=AsyncMock) as mock_set:
                await handle_settings_callback(cb)
                mock_set.assert_awaited_once_with(12345, "default_format", "audio")

    @pytest.mark.asyncio
    async def test_done_shows_saved(self):
        """Done callback should show saved message."""
        cb = MagicMock()
        cb.data = "cfg:done"
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        cb.answer = AsyncMock()

        await handle_settings_callback(cb)

        cb.message.edit_text.assert_called_with("✅ Settings saved.")

    @pytest.mark.asyncio
    async def test_quality_shows_keyboard(self):
        """Quality action should show quality selection keyboard."""
        cb = MagicMock()
        cb.data = "cfg:quality"
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        cb.answer = AsyncMock()

        await handle_settings_callback(cb)

        cb.message.edit_text.assert_called_once()
        call_text = cb.message.edit_text.call_args[0][0]
        assert "Select default quality" in call_text

    @pytest.mark.asyncio
    async def test_setchat_action(self):
        """Setchat action should show instructions."""
        cb = MagicMock()
        cb.data = "cfg:setchat"
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        cb.answer = AsyncMock()

        await handle_settings_callback(cb)

        cb.message.edit_text.assert_called_with(
            "Send /setchat <chat_id> to set a target chat for auto-forwarding."
        )