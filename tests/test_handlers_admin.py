"""Tests for telegram_media_dl.handlers.admin."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram_media_dl.handlers import admin as admin_module


@pytest.fixture
def mock_message():
    """Create a mock Telegram Message."""
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 111  # Default: admin
    msg.chat = MagicMock()
    msg.chat.id = 12345
    msg.text = ""
    msg.answer = AsyncMock()
    msg.bot = MagicMock()
    msg.bot.send_message = AsyncMock()
    return msg


@pytest.fixture(autouse=True)
def setup_admin():
    """Patch settings.ADMIN_IDS to include our test admin."""
    with patch("telegram_media_dl.handlers.admin.settings") as mock_settings:
        mock_settings.ADMIN_IDS = [111, 222]
        yield mock_settings


class TestCmdStats:

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, mock_message):
        """Stats command should reject non-admin users."""
        mock_message.from_user.id = 9999  # Not in ADMIN_IDS
        mock_message.text = "/stats"

        await admin_module.cmd_stats(mock_message)

        mock_message.answer.assert_called_with("⛔ Admin only.")

    @pytest.mark.asyncio
    async def test_admin_shows_stats(self, mock_message):
        """Admin should see bot statistics."""
        mock_message.from_user.id = 111
        mock_message.text = "/stats"

        with patch("telegram_media_dl.handlers.admin.get_stats", AsyncMock(return_value={
            "total_users": 42,
            "total_downloads": 1234,
            "today_downloads": 56,
        })):
            with patch.object(admin_module, "_queue") as mock_queue_obj:
                mock_queue_obj.stats.return_value = {
                    "queued": 1,
                    "active": 2,
                    "done": 100,
                    "failed": 3,
                    "cancelled": 0,
                    "total": 106,
                    "unique_users": 42,
                }
                await admin_module.cmd_stats(mock_message)

        call_text = mock_message.answer.call_args[0][0]
        assert "📊" in call_text
        assert "42" in call_text
        assert "1234" in call_text

    @pytest.mark.asyncio
    async def test_stats_without_queue(self, mock_message):
        """Stats should work even without queue object."""
        mock_message.from_user.id = 111
        mock_message.text = "/stats"

        with patch("telegram_media_dl.handlers.admin.get_stats", AsyncMock(return_value={
            "total_users": 0,
            "total_downloads": 0,
            "today_downloads": 0,
        })):
            admin_module._queue = None
            try:
                await admin_module.cmd_stats(mock_message)
            finally:
                pass

        call_text = mock_message.answer.call_args[0][0]
        assert "Total users" in call_text or "👥" in call_text


class TestCmdBroadcast:

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, mock_message):
        """Broadcast should reject non-admin users."""
        mock_message.from_user.id = 9999
        mock_message.text = "/broadcast hello"

        await admin_module.cmd_broadcast(mock_message)

        mock_message.answer.assert_called_with("⛔ Admin only.")

    @pytest.mark.asyncio
    async def test_broadcast_no_args(self, mock_message):
        """Broadcast without message should show usage."""
        mock_message.from_user.id = 111
        mock_message.text = "/broadcast"

        await admin_module.cmd_broadcast(mock_message)

        mock_message.answer.assert_called_with("Usage: /broadcast <message>")

    @pytest.mark.asyncio
    async def test_broadcast_success(self, mock_message):
        """Broadcast should send message to all known users."""
        mock_message.from_user.id = 111
        mock_message.text = "/broadcast Maintenance at 3am"
        mock_message.answer = AsyncMock()
        mock_message.bot = MagicMock()
        mock_message.bot.send_message = AsyncMock()

        with patch("telegram_media_dl.handlers.admin.get_all_user_ids", AsyncMock(return_value=[100, 200])):
            await admin_module.cmd_broadcast(mock_message)

            # Should have sent to 2 users + 1 status update = multiple calls
            assert mock_message.bot.send_message.call_count == 2

        call_text = mock_message.answer.call_args[0][0]
        assert "broadcasting" in call_text.lower()

    @pytest.mark.asyncio
    async def test_broadcast_no_users(self, mock_message):
        """Broadcast with no users should show appropriate message."""
        mock_message.from_user.id = 111
        mock_message.text = "/broadcast test"

        with patch("telegram_media_dl.handlers.admin.get_all_user_ids", AsyncMock(return_value=[])):
            await admin_module.cmd_broadcast(mock_message)

        mock_message.answer.assert_called_with("No users found.")


class TestCmdQueue:

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, mock_message):
        """Queue command should reject non-admin users."""
        mock_message.from_user.id = 9999
        mock_message.text = "/queue"

        await admin_module.cmd_queue(mock_message)

        mock_message.answer.assert_called_with("⛔ Admin only.")

    @pytest.mark.asyncio
    async def test_empty_queue(self, mock_message):
        """Queue command should show empty state."""
        mock_message.from_user.id = 111
        mock_message.text = "/queue"

        mock_queue = MagicMock()
        mock_queue.get_active_jobs.return_value = []

        admin_module._queue = mock_queue
        try:
            await admin_module.cmd_queue(mock_message)
        finally:
            admin_module._queue = None

        mock_message.answer.assert_called_with("📭 Queue is empty.")

    @pytest.mark.asyncio
    async def test_queue_with_active_jobs(self, mock_message):
        """Queue should display active jobs."""
        mock_message.from_user.id = 111
        mock_message.text = "/queue"

        job1 = MagicMock()
        job1.job_id = "job_1"
        job1.user_id = 123
        job1.status = "downloading"
        job1.quality = "720p"
        job1.format_choice = "video"

        mock_queue = MagicMock()
        mock_queue.get_active_jobs.return_value = [job1]

        admin_module._queue = mock_queue
        try:
            await admin_module.cmd_queue(mock_message)
        finally:
            admin_module._queue = None

        call_text = mock_message.answer.call_args[0][0]
        assert "Active Queue" in call_text


class TestCmdReset:

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, mock_message):
        """Reset command should reject non-admin users."""
        mock_message.from_user.id = 9999
        mock_message.text = "/reset 12345"

        admin_module._rate_limiter = MagicMock()
        try:
            await admin_module.cmd_reset(mock_message)
        finally:
            admin_module._rate_limiter = None

        mock_message.answer.assert_called_with("⛔ Admin only.")

    @pytest.mark.asyncio
    async def test_reset_invalid_user_id(self, mock_message):
        """Reset with non-numeric user ID should show error."""
        mock_message.from_user.id = 111
        mock_message.text = "/reset abc"

        admin_module._rate_limiter = MagicMock()
        try:
            await admin_module.cmd_reset(mock_message)
        finally:
            admin_module._rate_limiter = None

        mock_message.answer.assert_called_with("❌ Invalid user ID.")

    @pytest.mark.asyncio
    async def test_reset_success(self, mock_message):
        """Reset should succeed for valid user ID."""
        mock_message.from_user.id = 111
        mock_message.text = "/reset 12345"

        mock_rl = MagicMock()
        admin_module._rate_limiter = mock_rl
        try:
            await admin_module.cmd_reset(mock_message)

            mock_rl.reset.assert_called_once_with(12345)
            mock_message.answer.assert_called_with("✅ Rate limit reset for user 12345.")
        finally:
            admin_module._rate_limiter = None