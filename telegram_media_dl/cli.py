"""tmdl — Telegram Media Downloader CLI."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    _rich = True
except ImportError:
    console = None  # type: ignore[assignment]
    _rich = False


def _print(msg: str) -> None:
    if _rich:
        console.print(msg)
    else:
        print(msg)


# ──────────────────────────────────────────────────────────────
# CLI group
# ──────────────────────────────────────────────────────────────


@click.group()
def main() -> None:
    """tmdl — Telegram Media Downloader."""


@main.command()
def run() -> None:
    """Start the Telegram bot."""
    _print("[bold green]Starting bot…[/bold green]" if _rich else "Starting bot…")
    from telegram_media_dl.bot import main as bot_main

    asyncio.run(bot_main())


@main.command("init")
def cmd_init() -> None:
    """Create a .env file from .env.example."""
    example = Path(".env.example")
    dest = Path(".env")
    if dest.exists():
        _print("[yellow].env already exists.[/yellow]" if _rich else ".env already exists.")
        return
    if example.exists():
        dest.write_text(example.read_text())
        _print("[green].env created from .env.example[/green]" if _rich else ".env created.")
    else:
        dest.write_text("BOT_TOKEN=your_bot_token_here\n")
        _print("[green].env created with default template[/green]" if _rich else ".env created.")


@main.command("check")
def cmd_check() -> None:
    """Verify dependencies and configuration."""
    ok = True
    deps = [
        "aiogram",
        "yt_dlp",
        "aiosqlite",
        "pydantic_settings",
        "cachetools",
        "click",
        "rich",
    ]
    _print("\n[bold]Checking dependencies…[/bold]" if _rich else "Checking dependencies…")
    for dep in deps:
        found = importlib.util.find_spec(dep) is not None
        status = "✅" if found else "❌"
        _print(f"  {status} {dep}")
        if not found:
            ok = False

    _print("\n[bold]Checking config…[/bold]" if _rich else "\nChecking config…")
    try:
        from telegram_media_dl.config import settings

        token_ok = settings.BOT_TOKEN not in ("", "placeholder", "your_bot_token_here")
        _print(f"  {'✅' if token_ok else '⚠️'} BOT_TOKEN {'set' if token_ok else 'not set'}")
        _print(f"  ✅ Download dir: {settings.DOWNLOAD_DIR}")
        _print(f"  ✅ DB path: {settings.DB_PATH}")
    except Exception as exc:
        _print(f"  ❌ Config error: {exc}")
        ok = False

    if ok:
        _print("\n[bold green]All checks passed![/bold green]" if _rich else "\nAll checks passed!")
    else:
        _print("\n[bold red]Some checks failed.[/bold red]" if _rich else "\nSome checks failed.")
        sys.exit(1)


@main.command("info")
@click.argument("url")
def cmd_info(url: str) -> None:
    """Fetch and display video info for a URL."""
    _print(f"Fetching info for: {url}")
    try:
        from telegram_media_dl.downloader import get_video_info
        from telegram_media_dl.utils import format_duration, format_size

        info = get_video_info(url)
        title = info.get("title", "Unknown")
        uploader = info.get("uploader") or info.get("channel", "Unknown")
        duration = format_duration(info.get("duration"))
        size = info.get("filesize") or info.get("filesize_approx")
        size_str = format_size(size) if size else "Unknown"

        if _rich:
            table = Table(title=f"📹 {title}")
            table.add_column("Field")
            table.add_column("Value")
            table.add_row("Title", title)
            table.add_row("Uploader", uploader)
            table.add_row("Duration", duration)
            table.add_row("Size", size_str)
            table.add_row("URL", url)
            console.print(table)
        else:
            print(f"Title:    {title}")
            print(f"Uploader: {uploader}")
            print(f"Duration: {duration}")
            print(f"Size:     {size_str}")
    except Exception as exc:
        _print(f"❌ Error: {exc}")
        sys.exit(1)


@main.command("download")
@click.argument("url")
@click.option("--quality", default="best", help="Video quality (best/1080p/720p/…)")
@click.option("--format", "fmt", default="video", help="Format: video or audio")
@click.option("--output", "-o", default="downloads", help="Output directory")
def cmd_download(url: str, quality: str, fmt: str, output: str) -> None:
    """Download a video/audio directly from a URL."""

    async def _run() -> None:
        from telegram_media_dl.downloader import Downloader

        def on_progress(msg: str) -> None:
            print(f"\r{msg}", end="", flush=True)

        def on_status(msg: str) -> None:
            print(f"\n{msg}")

        downloader = Downloader(
            download_dir=Path(output),
            on_progress=on_progress,
            on_status=on_status,
        )
        filepath, info = await downloader.download(url, fmt, quality, "cli")
        print(f"\n✅ Saved: {filepath}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        _print(f"❌ Download failed: {exc}")
        sys.exit(1)


@main.group("db")
def cmd_db() -> None:
    """Database operations."""


@cmd_db.command("stats")
def db_stats() -> None:
    """Show database statistics."""

    async def _run() -> None:
        from telegram_media_dl.database import get_stats, init_db

        await init_db()
        stats = await get_stats()
        if _rich:
            table = Table(title="📊 Database Stats")
            table.add_column("Metric")
            table.add_column("Value")
            for k, v in stats.items():
                table.add_row(k.replace("_", " ").title(), str(v))
            console.print(table)
        else:
            for k, v in stats.items():
                print(f"{k}: {v}")

    asyncio.run(_run())


@cmd_db.command("reset")
@click.confirmation_option(prompt="This will delete ALL data. Are you sure?")
def db_reset() -> None:
    """Clear the entire database."""
    from telegram_media_dl.config import settings

    db_path = Path(str(settings.DB_PATH))
    if db_path.exists():
        db_path.unlink()
        _print("[red]Database deleted.[/red]" if _rich else "Database deleted.")
    else:
        _print("No database file found.")


if __name__ == "__main__":
    main()
