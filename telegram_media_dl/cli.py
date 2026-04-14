"""CLI for telegram-media-dl — tmdl command."""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def _check_env() -> bool:
    """Check if .env file exists and has required keys."""
    env_path = Path(".env")
    if not env_path.exists():
        return False
    content = env_path.read_text()
    required = ["API_ID", "API_HASH", "BOT_TOKEN"]
    return all(key in content for key in required)


@click.group()
@click.version_option(package_name="telegram-media-dl")
def cli():
    """⚡ tmdl — Telegram Media Downloader Bot CLI"""
    pass


@cli.command()
@click.option("--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARNING)")
def run(log_level: str):
    """Start the Telegram bot."""
    if not _check_env():
        console.print(
            Panel(
                "❌ [bold red].env file not found or missing required keys.[/]\n\n"
                "Run [bold cyan]tmdl init[/] to create a template, then fill in your credentials.",
                title="Configuration Error",
            )
        )
        sys.exit(1)

    from .bot import MediaDownloaderBot, setup_logging
    setup_logging(log_level)

    console.print(Panel(
        "[bold green]⚡ Starting telegram-media-dl bot...[/]\n"
        "Press Ctrl+C to stop.",
        title="telegram-media-dl",
    ))

    bot = MediaDownloaderBot()
    bot.run()


@cli.command()
@click.option("--force", is_flag=True, help="Overwrite existing .env file")
def init(force: bool):
    """Create a .env configuration file."""
    env_path = Path(".env")
    if env_path.exists() and not force:
        console.print("[yellow]⚠️  .env already exists. Use --force to overwrite.[/]")
        sys.exit(1)

    example = Path(__file__).parent.parent / ".env.example"
    if example.exists():
        env_path.write_text(example.read_text())
    else:
        env_path.write_text(
            "# Telegram API credentials\n"
            "# Get from https://my.telegram.org/apps\n"
            "API_ID=your_api_id_here\n"
            "API_HASH=your_api_hash_here\n\n"
            "# Bot token from @BotFather\n"
            "BOT_TOKEN=your_bot_token_here\n\n"
            "# Admin user IDs (comma-separated)\n"
            "ADMIN_IDS=\n\n"
            "# Download settings\n"
            "DOWNLOAD_DIR=downloads\n"
            "MAX_FILE_SIZE_MB=1900\n"
            "MAX_CONCURRENT_DOWNLOADS=3\n"
            "DEFAULT_VIDEO_QUALITY=best\n"
            "DEFAULT_AUDIO_QUALITY=192\n"
            "DOWNLOAD_TIMEOUT=300\n\n"
            "# Rate limiting\n"
            "RATE_LIMIT_COUNT=5\n"
            "RATE_LIMIT_WINDOW=3600\n\n"
            "# Features\n"
            "ALLOW_PLAYLISTS=false\n"
            "SEND_THUMBNAIL=true\n"
            "SHOW_VIDEO_INFO=true\n"
            "MAX_RETRIES=3\n"
            "SESSION_NAME=tmdl_bot\n"
        )

    console.print(f"[green]✅ Created .env at {env_path.absolute()}[/]")
    console.print("[yellow]Edit the file and fill in your API credentials, then run:[/]")
    console.print("  [bold cyan]tmdl run[/]")


@cli.command()
@click.argument("url")
@click.option("--format", "fmt", default="video", type=click.Choice(["video", "audio"]),
              help="Download format")
@click.option("--quality", default="best",
              type=click.Choice(["best", "1080p", "720p", "480p", "360p"]),
              help="Video quality")
@click.option("--output", "-o", default=".", help="Output directory")
def download(url: str, fmt: str, quality: str, output: str):
    """Download a video/audio URL directly (no bot needed)."""

    async def _do():
        from .downloader import Downloader, DownloadError
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)

        progress_msgs = []

        def on_progress(msg):
            progress_msgs.append(msg)

        def on_status(msg):
            console.print(f"[cyan]{msg}[/]")

        dl = Downloader(download_dir=out_dir, on_progress=on_progress, on_status=on_status)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as prog:
            task = prog.add_task(f"Downloading {url[:60]}...", total=None)
            try:
                filepath, info = await dl.download(url, fmt, quality, "cli_download")
                prog.update(task, description="✅ Done!")
                console.print(f"\n[green]✅ Saved to:[/] {filepath}")
                console.print(f"[dim]Title: {info.get('title', 'Unknown')}[/]")
            except DownloadError as e:
                prog.update(task, description="❌ Failed")
                console.print(f"[red]❌ {e}[/]")
                sys.exit(1)

    asyncio.run(_do())


@cli.command()
@click.argument("url")
def info(url: str):
    """Show info about a video URL without downloading."""

    async def _do():
        from .downloader import get_video_info
        from .utils import build_info_message, format_duration, format_size

        with Progress(
            SpinnerColumn(),
            TextColumn("Fetching info..."),
            console=console,
        ) as prog:
            task = prog.add_task("", total=None)
            loop = asyncio.get_event_loop()
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: get_video_info(url)),
                    timeout=30,
                )
                prog.update(task, description="✅ Done")
            except Exception as e:
                prog.update(task, description="❌ Failed")
                console.print(f"[red]Error: {e}[/]")
                sys.exit(1)

        table = Table(title="Video Info", show_header=False, box=None)
        table.add_column("Key", style="bold cyan", width=15)
        table.add_column("Value")

        fields = [
            ("Title", data.get("title", "N/A")),
            ("Uploader", data.get("uploader") or data.get("channel", "N/A")),
            ("Duration", format_duration(data.get("duration"))),
            ("Views", f"{data.get('view_count', 0):,}" if data.get("view_count") else "N/A"),
            ("Likes", f"{data.get('like_count', 0):,}" if data.get("like_count") else "N/A"),
            ("Upload Date", data.get("upload_date", "N/A")),
            ("Ext", data.get("ext", "N/A")),
        ]
        size = data.get("filesize") or data.get("filesize_approx")
        if size:
            fields.append(("Size (approx)", format_size(size)))

        for k, v in fields:
            table.add_row(k, str(v))

        console.print(table)

    asyncio.run(_do())


@cli.command()
def check():
    """Check configuration and dependencies."""
    console.print("[bold]Checking telegram-media-dl setup...[/]\n")

    # Check config
    env_ok = _check_env()
    console.print(f"{'✅' if env_ok else '❌'} .env file: {'found' if env_ok else 'missing — run tmdl init'}")

    # Check dependencies
    deps = {
        "telethon": "Telegram client",
        "yt_dlp": "Download engine",
        "dotenv": "Config loader",
        "rich": "CLI output",
    }
    for mod, desc in deps.items():
        try:
            __import__(mod)
            console.print(f"✅ {desc} ({mod})")
        except ImportError:
            console.print(f"❌ {desc} ({mod}) — [red]not installed[/]")

    # Check ffmpeg
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    console.print(
        f"{'✅' if ffmpeg else '⚠️ '} ffmpeg: {'found at ' + ffmpeg if ffmpeg else 'not found (audio conversion may fail)'}"
    )

    console.print("\n[bold]Done.[/]")


def main():
    cli()


if __name__ == "__main__":
    main()
