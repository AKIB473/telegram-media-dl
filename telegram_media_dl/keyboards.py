"""All InlineKeyboardMarkup builders for telegram-media-dl."""
from __future__ import annotations

from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def quality_keyboard() -> InlineKeyboardMarkup:
    """Quality selection keyboard shown after URL is detected."""
    builder = InlineKeyboardBuilder()
    # Video quality
    for label, data in [
        ("🎬 Best", "q:best"),
        ("1080p", "q:1080p"),
        ("720p", "q:720p"),
        ("480p", "q:480p"),
        ("360p", "q:360p"),
    ]:
        builder.button(text=label, callback_data=data)
    builder.adjust(3, 2)

    # Audio quality
    audio_row = InlineKeyboardBuilder()
    for label, data in [
        ("🎵 320kbps", "q:audio:320"),
        ("192kbps", "q:audio:192"),
        ("128kbps", "q:audio:128"),
    ]:
        audio_row.button(text=label, callback_data=data)
    audio_row.adjust(3)

    # Cancel
    cancel_row = InlineKeyboardBuilder()
    cancel_row.button(text="❌ Cancel", callback_data="q:cancel")

    builder.attach(audio_row)
    builder.attach(cancel_row)
    return builder.as_markup()


def search_results_keyboard(results: List[dict]) -> InlineKeyboardMarkup:
    """One button per search result, plus a cancel button."""
    builder = InlineKeyboardBuilder()
    for i, result in enumerate(results[:5], start=1):
        title = result.get("title", f"Result {i}")
        # Truncate long titles
        if len(title) > 55:
            title = title[:52] + "…"
        builder.button(text=f"{i}. {title}", callback_data=f"sr:{i-1}")
    builder.button(text="❌ Cancel", callback_data="sr:cancel")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    """Interactive settings keyboard."""
    notify = prefs.get("notify_complete", 1)
    notify_icon = "🔔 On" if notify else "🔕 Off"
    quality = prefs.get("default_quality", "best")
    fmt = prefs.get("default_format", "video")

    builder = InlineKeyboardBuilder()
    builder.button(text=f"Notifications: {notify_icon}", callback_data="cfg:notify")
    builder.button(text=f"Quality: {quality}", callback_data="cfg:quality")
    builder.button(text=f"Format: {fmt}", callback_data="cfg:format")
    builder.button(text="🎯 Set Target Chat", callback_data="cfg:setchat")
    builder.button(text="✅ Done", callback_data="cfg:done")
    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Generic yes/no confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes", callback_data=f"confirm:yes:{action}")
    builder.button(text="❌ No", callback_data=f"confirm:no:{action}")
    builder.adjust(2)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Welcome screen keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬇️ Download", callback_data="menu:download")
    builder.button(text="🔍 Search", callback_data="menu:search")
    builder.button(text="⚙️ Settings", callback_data="menu:settings")
    builder.button(text="📜 History", callback_data="menu:history")
    builder.adjust(2)
    return builder.as_markup()
