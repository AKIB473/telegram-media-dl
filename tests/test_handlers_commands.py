"""Tests for telegram_media_dl.handlers.commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram_media_dl.handlers import commands as cmd_module


@pytest.fixture
def mock_message():
    """Create a properly mocked Telegram Message."""
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 12345
    msg.chat = MagicMock()
    msg.chat.id = 12345
    msg.text = "/search"
    # answer returns an AsyncMock so .edit_text works downstream
    msg.answer = AsyncMock(return_value=MagicMock(
        edit_text=AsyncMock(),
        delete=AsyncMock(),
    ))
    return msg


class TestCmdSearch:

    @pytest.mark.asyncio
    async def test_search_no_query(self, mock_message):
        """Search with no query string should show usage."""
        mock_message.text = "/search"
        with patch.object(cmd_module, "search_videos", new_callable=lambda: AsyncMock(return_value=[])):
            await cmd_module.cmd_search(mock_message)
        mock_message.answer.assert_called_with("Usage: /search <query>")

    @pytest.mark.asyncio
    async def test_search_empty_query(self, mock_message):
        """Search with spaces-only query should show usage (split yields < 2 parts)."""
        # "/search   ".split(maxsplit=1) => ["/search"]  => len < 2
        mock_message.text = "/search   "
        await cmd_module.cmd_search(mock_message)
        mock_message.answer.assert_called_with("Usage: /search <query>")

    @pytest.mark.asyncio
    async def test_search_with_results(self, mock_message):
        """Search with valid results should display them."""
        mock_message.text = "/search test query"

        mock_results = [
            {"title": "Test Video 1", "url": "https://youtube.com/watch?v=abc1",
             "duration": 120, "view_count": 1000, "thumbnail": "http://thumb.jpg"},
            {"title": "Test Video 2", "url": "https://youtube.com/watch?v=abc2",
             "duration": 300, "view_count": 500},
        ]

        with patch.object(cmd_module, "search_videos", AsyncMock(return_value=mock_results)):
            await cmd_module.cmd_search(mock_message)

        # answer was called to create the "Searching" status
        assert mock_message.answer.called
        # Then the status message was edited with results
        status_msg = mock_message.answer.return_value
        status_msg.edit_text.assert_called_once()
        call_text = status_msg.edit_text.call_args[0][0]
        assert "Test Video 1" in call_text
        assert "Test Video 2" in call_text

    @pytest.mark.asyncio
    async def test_search_no_results(self, mock_message):
        """Search with no results should show error."""
        mock_message.text = "/search impossiblequery12345"

        with patch.object(cmd_module, "search_videos", AsyncMock(return_value=[])):
            await cmd_module.cmd_search(mock_message)

        status_msg = mock_message.answer.return_value
        status_msg.edit_text.assert_called_once()
        call_text = status_msg.edit_text.call_args[0][0]
        assert "No results found" in call_text


class TestCmdHistory:

    @pytest.mark.asyncio
    async def test_history_empty(self, mock_message):
        """History with no downloads should show empty state."""
        with patch("telegram_media_dl.handlers.commands.get_user_history", AsyncMock(return_value=[])):
            await cmd_module.cmd_history(mock_message)
        mock_message.answer.assert_called_with("📜 No downloads yet.")

    @pytest.mark.asyncio
    async def test_history_with_downloads(self, mock_message):
        """History should display recent downloads."""
        mock_history = [
            {"title": "My Video", "url": "https://youtube.com/watch?v=abc",
             "quality": "720p", "status": "done", "file_size": 5_000_000},
        ]
        with patch("telegram_media_dl.handlers.commands.get_user_history", AsyncMock(return_value=mock_history)):
            await cmd_module.cmd_history(mock_message)
        call_text = mock_message.answer.call_args[0][0]
        assert "My Video" in call_text
        assert "720p" in call_text
        assert "done" in call_text


class TestCmdSettings:

    @pytest.mark.asyncio
    async def test_settings_shows_keyboard(self, mock_message):
        """Settings command should show keyboard with preferences."""
        mock_prefs = {
            "default_quality": "best",
            "default_format": "video",
            "notify_complete": 1,
            "target_chat": None,
        }
        with patch("telegram_media_dl.handlers.commands.get_user_prefs", AsyncMock(return_value=mock_prefs)):
            await cmd_module.cmd_settings(mock_message)
        mock_message.answer.assert_called_once()
        call_text = mock_message.answer.call_args[0][0]
        assert "Settings" in call_text


class TestCmdCancel:

    @pytest.mark.asyncio
    async def test_cancel_no_queue(self, mock_message):
        """Cancel with no queue should show error."""
        original_queue = cmd_module._queue
        cmd_module._queue = None
        try:
            await cmd_module.cmd_cancel(mock_message)
            mock_message.answer.assert_called_with("No active downloads.")
        finally:
            cmd_module._queue = original_queue

    @pytest.mark.asyncio
    async def test_cancel_with_active(self, mock_message):
        """Cancel with active jobs should call queue.cancel_user_jobs."""
        mock_queue = MagicMock()
        mock_queue.cancel_user_jobs.return_value = 3
        cmd_module._queue = mock_queue
        try:
            mock_message.from_user.id = 12345
            await cmd_module.cmd_cancel(mock_message)
            mock_queue.cancel_user_jobs.assert_called_with(12345)
            mock_message.answer.assert_called_with("✅ Cancelled 3 download(s).")
        finally:
            cmd_module._queue = None


class TestStartHelp:

    @pytest.mark.asyncio
    async def test_start_command(self, mock_message):
        """Start command should show welcome text."""
        cmd_module._queue = None  # irrelevant for /start
        await cmd_module.cmd_start(mock_message)
        mock_message.answer.assert_called_once()
        call_text = mock_message.answer.call_args[0][0]
        assert "Welcome" in call_text
        assert "Send me any video/audio URL" in call_text

    @pytest.mark.asyncio
    async def test_help_command(self, mock_message):
        """Help command should list all commands."""
        await cmd_module.cmd_help(mock_message)
        mock_message.answer.assert_called_once()
        call_text = mock_message.answer.call_args[0][0]
        assert "/start" in call_text
        assert "/search" in call_text
        assert "/cancel" in call_text