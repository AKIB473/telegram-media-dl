"""Settings command handlers: /quality /setchat /mychat and callbacks."""
from __future__ import annotations

import logging

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..database import get_user_prefs, set_user_pref
from ..keyboards import quality_keyboard, settings_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("quality"))
async def cmd_quality(message: Message) -> None:
    assert message.from_user is not None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Usage: /quality <best|1080p|720p|480p|360p>\n\n"
            "Or use /settings to adjust preferences interactively."
        )
        return

    quality = parts[1].strip().lower()
    valid = {"best", "1080p", "720p", "480p", "360p"}
    if quality not in valid:
        await message.answer(f"❌ Invalid quality. Choose from: {', '.join(sorted(valid))}")
        return

    await set_user_pref(message.from_user.id, "default_quality", quality)
    await message.answer(f"✅ Default quality set to <b>{quality}</b>.", parse_mode="HTML")


@router.message(Command("setchat"))
async def cmd_setchat(message: Message) -> None:
    assert message.from_user is not None and message.text is not None
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /setchat <chat_id>")
        return

    chat_id = parts[1].strip()
    await set_user_pref(message.from_user.id, "target_chat", chat_id)
    await message.answer(
        f"✅ Target chat set to <code>{chat_id}</code>.\n"
        "Future downloads will be forwarded there.",
        parse_mode="HTML",
    )


@router.message(Command("mychat"))
async def cmd_mychat(message: Message) -> None:
    assert message.from_user is not None
    prefs = await get_user_prefs(message.from_user.id)
    chat = prefs.get("target_chat")
    if chat:
        await message.answer(f"🎯 Current target chat: <code>{chat}</code>", parse_mode="HTML")
    else:
        await message.answer("No target chat configured. Use /setchat <chat_id> to set one.")


# ──────────────────────────────────────────────────────────────
# Settings callback handlers
# ──────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("cfg:"))
async def handle_settings_callback(callback: CallbackQuery) -> None:
    assert callback.from_user is not None and callback.message is not None
    user_id = callback.from_user.id
    action = (callback.data or "").split(":")[1]
    await callback.answer()

    if action == "done":
        await callback.message.edit_text("✅ Settings saved.")
        return

    if action == "notify":
        prefs = await get_user_prefs(user_id)
        current = prefs.get("notify_complete", 1)
        new_val = 0 if current else 1
        await set_user_pref(user_id, "notify_complete", new_val)
        prefs["notify_complete"] = new_val
        await callback.message.edit_reply_markup(reply_markup=settings_keyboard(prefs))
        return

    if action == "quality":
        await callback.message.edit_text(
            "🎛 <b>Select default quality:</b>",
            reply_markup=quality_keyboard(),
            parse_mode="HTML",
        )
        return

    if action == "format":
        prefs = await get_user_prefs(user_id)
        current_fmt = prefs.get("default_format", "video")
        new_fmt = "audio" if current_fmt == "video" else "video"
        await set_user_pref(user_id, "default_format", new_fmt)
        prefs["default_format"] = new_fmt
        await callback.message.edit_reply_markup(reply_markup=settings_keyboard(prefs))
        return

    if action == "setchat":
        await callback.message.edit_text(
            "Send /setchat <chat_id> to set a target chat for auto-forwarding."
        )
        return


def register(dp: Dispatcher) -> None:
    dp.include_router(router)
