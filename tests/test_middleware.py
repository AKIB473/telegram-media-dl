"""Tests for telegram_media_dl.middleware."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram_media_dl.middleware import RateLimitMiddleware, UserRegistrationMiddleware
from telegram_media_dl.config import settings


@pytest.fixture
def mock_event():
    event = MagicMock()
    event.__class__ = MagicMock
    return event


@pytest.fixture
def mock_update_with_message():
    update = MagicMock()
    update.message = MagicMock()
    update.message.answer = AsyncMock()
    update.message.chat = MagicMock()
    update.message.chat.id = 12345
    update.callback_query = None
    return update


class TestRateLimitMiddleware:
    """Tests for the sliding-window rate limit middleware."""

    @pytest.mark.asyncio
    async def test_allowed_user_passes_through(self, mock_event, mock_update_with_message):
        """Users within rate limit should reach the handler."""
        mock_data = {
            "event_from_user": MagicMock(id=999),
            "update": mock_update_with_message,
        }

        handler_called = False

        async def next_handler(event, data):
            nonlocal handler_called
            handler_called = True

        with patch("telegram_media_dl.middleware.settings") as mock_settings:
            mock_settings.ADMIN_IDS = []
            mock_settings.ALLOWED_USER_IDS = []
            mock_settings.RATE_LIMIT_COUNT = 5
            mock_settings.RATE_LIMIT_WINDOW = 3600

            mw = RateLimitMiddleware()
            await mw(next_handler, mock_event, mock_data)

        assert handler_called is True

    @pytest.mark.asyncio
    async def test_rate_limited_user_blocked(self, mock_event, mock_update_with_message):
        """Users exceeding rate limit should be blocked."""
        user_id = 12345
        mock_data = {
            "event_from_user": MagicMock(id=user_id),
            "update": mock_update_with_message,
        }

        async def next_handler(event, data):
            pass

        with patch("telegram_media_dl.middleware.settings") as mock_settings:
            mock_settings.ADMIN_IDS = []
            mock_settings.ALLOWED_USER_IDS = []
            mock_settings.RATE_LIMIT_COUNT = 1
            mock_settings.RATE_LIMIT_WINDOW = 3600

            mw = RateLimitMiddleware()

            # First request should pass
            await mw(next_handler, mock_event, mock_data)

            # Second request should be blocked
            await mw(next_handler, mock_event, mock_data)

        # Should have sent a rate limit message
        response_text = mock_update_with_message.message.answer.call_args[0][0]
        assert "Rate limit exceeded" in response_text

    @pytest.mark.asyncio
    async def test_admin_bypasses_rate_limit(self, mock_event, mock_update_with_message):
        """Admin users should never be rate-limited."""
        admin_id = 111
        mock_data = {
            "event_from_user": MagicMock(id=admin_id),
            "update": mock_update_with_message,
        }

        call_count = 0

        async def next_handler(event, data):
            nonlocal call_count
            call_count += 1

        with patch("telegram_media_dl.middleware.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [111]
            mock_settings.ALLOWED_USER_IDS = []
            mock_settings.RATE_LIMIT_COUNT = 1
            mock_settings.RATE_LIMIT_WINDOW = 3600

            mw = RateLimitMiddleware()

            # Make many requests — admin should never be blocked
            for _ in range(10):
                await mw(next_handler, mock_event, mock_data)

        assert call_count == 10

    @pytest.mark.asyncio
    async def test_callback_query_rate_limit_message(self, mock_event):
        """Rate-limited callback query should show alert."""
        user_id = 5555
        mock_callback = MagicMock()
        mock_callback.answer = AsyncMock()
        mock_event = MagicMock()

        mock_data = {
            "event_from_user": MagicMock(id=user_id),
            "update": MagicMock(message=None, callback_query=mock_callback),
        }

        async def next_handler(event, data):
            pass

        with patch("telegram_media_dl.middleware.settings") as mock_settings:
            mock_settings.ADMIN_IDS = []
            mock_settings.ALLOWED_USER_IDS = []
            mock_settings.RATE_LIMIT_COUNT = 1
            mock_settings.RATE_LIMIT_WINDOW = 3600

            mw = RateLimitMiddleware()

            # First request
            await mw(next_handler, mock_event, mock_data)
            # Second request — blocked, should answer callback
            await mw(next_handler, mock_event, mock_data)

        mock_callback.answer.assert_called()
        call_text = mock_callback.answer.call_args[0][0]
        assert "Rate limit exceeded" in call_text
        assert "show_alert" in str(mock_callback.answer.call_args[1])

    @pytest.mark.asyncio
    async def test_allowed_user_ids_filters(self, mock_event, mock_update_with_message):
        """Non-allowed users should be blocked when ALLOWED_USER_IDS is set."""
        user_id = 9999
        mock_data = {
            "event_from_user": MagicMock(id=user_id),
            "update": mock_update_with_message,
        }

        handler_called = False

        async def next_handler(event, data):
            nonlocal handler_called
            handler_called = True

        with patch("telegram_media_dl.middleware.settings") as mock_settings:
            mock_settings.ALLOWED_USER_IDS = [111, 222]  # user_id 9999 not in list
            mock_settings.ADMIN_IDS = []
            mock_settings.RATE_LIMIT_COUNT = 5
            mock_settings.RATE_LIMIT_WINDOW = 3600

            mw = RateLimitMiddleware()
            await mw(next_handler, mock_event, mock_data)

        assert handler_called is False
        response_text = mock_update_with_message.message.answer.call_args[0][0]
        assert "not authorized" in response_text.lower()

    @pytest.mark.asyncio
    async def test_allowed_user_ids_empty_allows_all(self, mock_event, mock_update_with_message):
        """When ALLOWED_USER_IDS is empty, all users should pass."""
        user_id = 9999
        mock_data = {
            "event_from_user": MagicMock(id=user_id),
            "update": mock_update_with_message,
        }

        handler_called = False

        async def next_handler(event, data):
            nonlocal handler_called
            handler_called = True

        with patch("telegram_media_dl.middleware.settings") as mock_settings:
            mock_settings.ALLOWED_USER_IDS = []
            mock_settings.ADMIN_IDS = []
            mock_settings.RATE_LIMIT_COUNT = 5
            mock_settings.RATE_LIMIT_WINDOW = 3600

            mw = RateLimitMiddleware()
            await mw(next_handler, mock_event, mock_data)

        assert handler_called is True


class TestUserRegistrationMiddleware:

    @pytest.mark.asyncio
    async def test_registers_new_user(self, mock_event, mock_update_with_message):
        """Non-bot users should be auto-registered."""
        user = MagicMock()
        user.id = 12345
        user.username = "testuser"
        user.first_name = "Test"
        user.is_bot = False
        mock_data = {
            "event_from_user": user,
        }

        async def next_handler(event, data):
            pass

        with patch("telegram_media_dl.middleware.register_user") as mock_register:
            mock_register.return_value = None
            mw = UserRegistrationMiddleware()
            await mw(next_handler, mock_event, mock_data)

            mock_register.assert_awaited_once_with(
                user_id=12345,
                username="testuser",
                first_name="Test",
            )

    @pytest.mark.asyncio
    async def test_skips_bots(self, mock_event):
        """Bot users should not be registered."""
        user = MagicMock()
        user.is_bot = True
        mock_data = {
            "event_from_user": user,
        }

        async def next_handler(event, data):
            pass

        with patch("telegram_media_dl.middleware.register_user") as mock_register:
            mw = UserRegistrationMiddleware()
            await mw(next_handler, mock_event, mock_data)

            mock_register.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_registers_user_without_username(self, mock_event):
        """User without username should still be registered (username=None)."""
        user = MagicMock()
        user.id = 12345
        user.username = None
        user.first_name = "Anonymous"
        user.is_bot = False
        mock_data = {
            "event_from_user": user,
        }

        async def next_handler(event, data):
            pass

        with patch("telegram_media_dl.middleware.register_user") as mock_register:
            mw = UserRegistrationMiddleware()
            await mw(next_handler, mock_event, mock_data)

            mock_register.assert_awaited_once_with(
                user_id=12345,
                username=None,
                first_name="Anonymous",
            )