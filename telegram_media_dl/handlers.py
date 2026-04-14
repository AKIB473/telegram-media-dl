"""Telegram event handlers for telegram-media-dl."""
import asyncio
import logging
import os
from typing import Optional

from telethon import Button, TelegramClient, events

from .config import config
from .downloader import Downloader, DownloadError, FileTooLargeError, get_video_info
from .queue_manager import DownloadQueue, DownloadJob, DownloadStatus
from .rate_limiter import RateLimiter
from .utils import (
    build_info_message,
    cleanup_file,
    format_size,
    get_site_name,
    is_generic_url,
    is_valid_url,
)

logger = logging.getLogger(__name__)

# ── Quality selection menus ──────────────────────────────────────────────────
VIDEO_QUALITY_BUTTONS = [
    [Button.inline("🎬 Best Quality", b"q:video:best")],
    [Button.inline("📺 1080p", b"q:video:1080p"), Button.inline("🎥 720p", b"q:video:720p")],
    [Button.inline("📱 480p", b"q:video:480p"), Button.inline("📉 360p", b"q:video:360p")],
    [Button.inline("🎵 Audio Only (MP3)", b"q:audio:192")],
    [Button.inline("❌ Cancel", b"cancel")],
]

AUDIO_QUALITY_BUTTONS = [
    [Button.inline("🎵 320 kbps (Best)", b"q:audio:320")],
    [Button.inline("🎵 192 kbps", b"q:audio:192")],
    [Button.inline("🎵 128 kbps", b"q:audio:128")],
    [Button.inline("🎵 96 kbps", b"q:audio:96")],
    [Button.inline("❌ Cancel", b"cancel")],
]


class BotHandlers:
    """Registers and handles all Telegram bot events."""

    def __init__(self, client: TelegramClient):
        self.client = client
        self.queue = DownloadQueue(max_concurrent=config.MAX_CONCURRENT_DOWNLOADS)
        self.rate_limiter = RateLimiter(
            max_requests=config.RATE_LIMIT_COUNT,
            window_seconds=config.RATE_LIMIT_WINDOW,
        )
        # user_id -> {url, format_choice, info_msg_id}
        self._pending: dict = {}
        self._register()

        # Periodic cleanup task
        asyncio.create_task(self._cleanup_loop())

    def _register(self) -> None:
        self.client.on(events.NewMessage(pattern="/start"))(self._cmd_start)
        self.client.on(events.NewMessage(pattern="/help"))(self._cmd_help)
        self.client.on(events.NewMessage(pattern="/status"))(self._cmd_status)
        self.client.on(events.NewMessage(pattern="/queue"))(self._cmd_queue)
        self.client.on(events.NewMessage(pattern="/cancel"))(self._cmd_cancel)
        self.client.on(events.NewMessage(pattern="/stats"))(self._cmd_stats)
        self.client.on(events.NewMessage(pattern="/reset"))(self._cmd_reset)
        self.client.on(events.NewMessage(pattern="/broadcast"))(self._cmd_broadcast)
        self.client.on(events.NewMessage)(self._handle_message)
        self.client.on(events.CallbackQuery)(self._handle_callback)

    # ── Commands ─────────────────────────────────────────────────────────────

    async def _cmd_start(self, event: events.NewMessage.Event) -> None:
        name = event.sender.first_name or "there"
        await event.reply(
            f"👋 Hello, **{name}**!\n\n"
            "I can download videos and audio from **50+ sites** including:\n"
            "YouTube • Instagram • TikTok • Twitter • Facebook • Reddit • Vimeo • and more!\n\n"
            "📎 Just **send me a link** to get started.\n\n"
            "Type /help for all commands."
        )

    async def _cmd_help(self, event: events.NewMessage.Event) -> None:
        await event.reply(
            "**📖 How to use:**\n"
            "1. Send any supported video/audio link\n"
            "2. I'll show you video info and quality options\n"
            "3. Choose your preferred quality\n"
            "4. Receive your file!\n\n"
            "**📋 Commands:**\n"
            "/start — Welcome message\n"
            "/help — Show this help\n"
            "/status — Your active downloads\n"
            "/cancel — Cancel your active downloads\n"
            "/queue — Show global queue\n\n"
            "**⚡ Limits:**\n"
            f"• Max file size: **{config.MAX_FILE_SIZE_MB} MB**\n"
            f"• Rate limit: **{config.RATE_LIMIT_COUNT}** downloads per hour\n"
            f"• Max concurrent: **{config.MAX_CONCURRENT_DOWNLOADS}** at a time\n\n"
            "**🌐 Supported Sites:**\n"
            "YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit, "
            "Twitch, Vimeo, Dailymotion, SoundCloud, and 40+ more!"
        )

    async def _cmd_status(self, event: events.NewMessage.Event) -> None:
        uid = event.sender_id
        jobs = self.queue.get_user_jobs(uid)
        active = [j for j in jobs if j.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)]
        if not active:
            await event.reply("✅ No active downloads.")
            return
        lines = ["**📥 Your active downloads:**\n"]
        for j in active:
            lines.append(f"• `{j.url[:50]}...` — **{j.status.value}** {j.progress}")
        await event.reply("\n".join(lines))

    async def _cmd_queue(self, event: events.NewMessage.Event) -> None:
        if not self._is_admin(event.sender_id):
            await event.reply("❌ Admin only command.")
            return
        active = self.queue.get_active_jobs()
        if not active:
            await event.reply("✅ Queue is empty.")
            return
        lines = [f"**📋 Active Queue ({len(active)} jobs):**\n"]
        for j in active:
            lines.append(f"• User `{j.user_id}` | `{j.url[:40]}` | **{j.status.value}**")
        await event.reply("\n".join(lines))

    async def _cmd_cancel(self, event: events.NewMessage.Event) -> None:
        uid = event.sender_id
        count = self.queue.cancel_user_jobs(uid)
        if count:
            await event.reply(f"🚫 Cancelled {count} download(s).")
        else:
            await event.reply("✅ No active downloads to cancel.")

    async def _cmd_stats(self, event: events.NewMessage.Event) -> None:
        if not self._is_admin(event.sender_id):
            await event.reply("❌ Admin only command.")
            return
        s = self.queue.stats()
        rate_usage = self.rate_limiter.get_all_usage()
        await event.reply(
            f"**📊 Bot Statistics:**\n\n"
            f"**Queue:**\n"
            f"• Queued: {s['queued']}\n"
            f"• Active: {s['active']}\n"
            f"• Done: {s['done']}\n"
            f"• Failed: {s['failed']}\n"
            f"• Cancelled: {s['cancelled']}\n"
            f"• Total: {s['total']}\n"
            f"• Unique users: {s['unique_users']}\n\n"
            f"**Rate Limits:** {len(rate_usage)} users with active usage"
        )

    async def _cmd_reset(self, event: events.NewMessage.Event) -> None:
        """Admin: reset rate limit for a user. Usage: /reset <user_id>"""
        if not self._is_admin(event.sender_id):
            await event.reply("❌ Admin only command.")
            return
        parts = event.message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await event.reply("Usage: /reset <user_id>")
            return
        uid = int(parts[1])
        self.rate_limiter.reset(uid)
        await event.reply(f"✅ Rate limit reset for user `{uid}`.")

    async def _cmd_broadcast(self, event: events.NewMessage.Event) -> None:
        """Admin: broadcast a message to all known users."""
        if not self._is_admin(event.sender_id):
            await event.reply("❌ Admin only command.")
            return
        text = event.message.text.replace("/broadcast", "", 1).strip()
        if not text:
            await event.reply("Usage: /broadcast <message>")
            return
        users = set(self.queue._user_jobs.keys())
        sent = 0
        for uid in users:
            try:
                await self.client.send_message(uid, f"📢 **Broadcast:**\n\n{text}")
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await event.reply(f"✅ Broadcast sent to {sent} users.")

    # ── Message handler ───────────────────────────────────────────────────────

    async def _handle_message(self, event: events.NewMessage.Event) -> None:
        if event.message.text.startswith("/"):
            return

        url = event.message.text.strip()
        if not is_generic_url(url):
            return

        uid = event.sender_id

        # Rate limit check
        allowed, reset_in = self.rate_limiter.is_allowed(uid)
        if not allowed:
            mins = reset_in // 60
            secs = reset_in % 60
            await event.reply(
                f"⏳ **Rate limit reached.**\n"
                f"You can download {config.RATE_LIMIT_COUNT} files per hour.\n"
                f"Reset in: `{mins}m {secs}s`"
            )
            return

        if not is_valid_url(url):
            await event.reply(
                "⚠️ This site may not be supported.\n"
                "I'll try anyway — send me the quality choice below.",
            )

        site = get_site_name(url)
        info_msg = await event.reply(f"🔍 Fetching info from **{site}**...")

        # Fetch video info
        try:
            loop = asyncio.get_event_loop()
            info = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: get_video_info(url)),
                timeout=30,
            )

            # Store pending context
            self._pending[uid] = {"url": url, "info": info}

            caption = build_info_message(info) if config.SHOW_VIDEO_INFO else f"🔗 Ready to download from **{site}**"

            # Send thumbnail if available and enabled
            thumbnail = info.get("thumbnail")
            if config.SEND_THUMBNAIL and thumbnail:
                try:
                    await self.client.send_file(
                        event.chat_id,
                        thumbnail,
                        caption=caption,
                        buttons=VIDEO_QUALITY_BUTTONS,
                        parse_mode="markdown",
                    )
                    await info_msg.delete()
                    return
                except Exception:
                    pass

            await info_msg.edit(caption, buttons=VIDEO_QUALITY_BUTTONS, parse_mode="markdown")

        except asyncio.TimeoutError:
            self._pending[uid] = {"url": url, "info": {}}
            await info_msg.edit(
                f"⚠️ Could not fetch info (timeout). Select format anyway:",
                buttons=VIDEO_QUALITY_BUTTONS,
            )
        except Exception as e:
            self._pending[uid] = {"url": url, "info": {}}
            await info_msg.edit(
                f"⚠️ Info fetch failed: `{str(e)[:100]}`\nSelect format to try anyway:",
                buttons=VIDEO_QUALITY_BUTTONS,
            )

    # ── Callback handler ──────────────────────────────────────────────────────

    async def _handle_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8", errors="ignore")
        uid = event.sender_id

        if data == "cancel":
            self._pending.pop(uid, None)
            await event.edit("❌ Cancelled.")
            return

        if not data.startswith("q:"):
            return

        # Format: q:<format_choice>:<quality>
        parts = data.split(":")
        if len(parts) != 3:
            return

        _, format_choice, quality = parts

        if uid not in self._pending:
            await event.edit("⚠️ Session expired. Please send the link again.")
            return

        pending = self._pending.pop(uid)
        url = pending["url"]

        status_msg = await event.edit(
            f"⏳ Added to queue...\n`{url[:60]}`"
        )

        async def _do_download(job: DownloadJob) -> None:
            async def _update_progress(text: str) -> None:
                try:
                    await status_msg.edit(text)
                except Exception:
                    pass

            async def _update_status(text: str) -> None:
                try:
                    await status_msg.edit(text)
                except Exception:
                    pass

            downloader = Downloader(
                on_progress=lambda t: asyncio.create_task(_update_progress(t)),
                on_status=lambda t: asyncio.create_task(_update_status(t)),
            )

            try:
                filepath, info = await downloader.download(
                    url=url,
                    format_choice=format_choice,
                    quality=quality,
                    job_id=job.job_id,
                )

                job.status = DownloadStatus.UPLOADING
                await _update_status("📤 Uploading to Telegram...")

                title = info.get("title", "Download")
                caption = f"✅ **{title[:200]}**"
                if format_choice == "audio":
                    await self.client.send_file(
                        uid,
                        filepath,
                        caption=caption,
                        voice=False,
                        attributes=[],
                        parse_mode="markdown",
                    )
                else:
                    await self.client.send_file(
                        uid,
                        filepath,
                        caption=caption,
                        parse_mode="markdown",
                        supports_streaming=True,
                    )

                await _update_status(f"✅ Done! Enjoy your {'audio' if format_choice == 'audio' else 'video'}.")
                cleanup_file(filepath)

            except FileTooLargeError as e:
                await _update_status(f"❌ {e}")
            except DownloadError as e:
                await _update_status(f"❌ Download failed:\n`{str(e)[:200]}`")
            except Exception as e:
                logger.error("Unexpected error in job %s: %s", job.job_id, e, exc_info=True)
                await _update_status(f"❌ Unexpected error: `{str(e)[:150]}`")

        self.queue.enqueue(
            user_id=uid,
            url=url,
            format_choice=format_choice,
            quality=quality,
            coro_factory=_do_download,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_admin(self, user_id: int) -> bool:
        return user_id in config.ADMIN_IDS

    async def _cleanup_loop(self) -> None:
        """Periodically clean up old jobs and temp files."""
        while True:
            await asyncio.sleep(1800)
            removed = self.queue.cleanup_old_jobs(max_age_seconds=3600)
            if removed:
                logger.info("Cleaned up %d old jobs", removed)
