"""Aiogram 3 middleware: rate limiting + user auto-registration."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, User

from .config import settings
from .database import register_user
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Block users who exceed the configured request rate."""

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self.limiter = RateLimiter(
            max_requests=max_requests or settings.RATE_LIMIT_COUNT,
            window_seconds=window_seconds or settings.RATE_LIMIT_WINDOW,
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user and user.id not in settings.ADMIN_IDS:
            allowed, reset_in = self.limiter.is_allowed(user.id)
            if not allowed:
                # Try to answer if the event is a message or callback
                update: Update | None = data.get("update") or (
                    event if isinstance(event, Update) else None
                )
                if update and update.message:
                    await update.message.answer(
                        f"⏳ Rate limit exceeded. Try again in {reset_in}s."
                    )
                elif update and update.callback_query:
                    await update.callback_query.answer(
                        f"⏳ Rate limit exceeded. Try again in {reset_in}s.",
                        show_alert=True,
                    )
                return  # drop the event
        return await handler(event, data)

    @property
    def rate_limiter(self) -> RateLimiter:
        return self.limiter


class UserRegistrationMiddleware(BaseMiddleware):
    """Auto-register (or update) every user who sends a message."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user and not user.is_bot:
            try:
                await register_user(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                )
            except Exception as exc:
                logger.warning("Failed to register user %d: %s", user.id, exc)
        return await handler(event, data)
