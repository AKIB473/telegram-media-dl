# Telegram Media Downloader

A production-grade Telegram bot that downloads videos and audio from YouTube, Instagram, TikTok, Twitter/X, and dozens of other sites via **yt-dlp**.

## Features

- ✅ **Aiogram 3** — pure bot token only, no API_ID/HASH
- ✅ **Quality selection** — Best / 1080p / 720p / 480p / 360p / Audio (320/192/128 kbps)
- ✅ **YouTube search** — `/search <query>` with inline result buttons
- ✅ **Download history** — per-user, stored in SQLite
- ✅ **User preferences** — default quality, format, notifications, target chat
- ✅ **Target chat forwarding** — auto-forward every download to a channel
- ✅ **Rate limiting** — sliding-window, configurable
- ✅ **Admin commands** — `/stats`, `/broadcast`, `/queue`, `/reset`
- ✅ **Subtitles** — auto-download and embed English subtitles
- ✅ **Metadata + thumbnail** — embed via mutagen / ffmpeg
- ✅ **Cookie support** — for age-restricted content
- ✅ **Docker** — single `docker-compose up` deployment
- ✅ **CLI (`tmdl`)** — run / init / check / info / download / db

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/AKIB473/telegram-media-dl
cd telegram-media-dl

# 2. Configure
cp .env.example .env
# Edit .env and set BOT_TOKEN

# 3. Install and run
pip install -e ".[dev]"
tmdl run
```

### Docker

```bash
docker-compose up -d
```

## Configuration

All settings are read from environment variables or a `.env` file.
Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | **Required** Telegram bot token |
| `ADMIN_IDS` | `[]` | Comma-separated admin user IDs |
| `TARGET_CHAT` | `None` | Auto-forward downloads here |
| `DOWNLOAD_DIR` | `downloads` | Local download directory |
| `MAX_FILE_SIZE_MB` | `1900` | File size limit |
| `MAX_CONCURRENT` | `3` | Parallel downloads |
| `RATE_LIMIT_COUNT` | `5` | Requests per window |
| `RATE_LIMIT_WINDOW` | `3600` | Rate limit window (seconds) |
| `ALLOW_PLAYLISTS` | `false` | Allow playlist downloads |
| `DOWNLOAD_TIMEOUT` | `300` | Per-download timeout (seconds) |
| `COOKIE_FILE` | `None` | Path to cookies.txt |

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome screen |
| `/help` | Feature list |
| `/search <query>` | Search YouTube |
| `/history` | Last 10 downloads |
| `/settings` | Preferences |
| `/cancel` | Cancel active downloads |
| `/quality <q>` | Set default quality |
| `/setchat <id>` | Set target chat |
| `/mychat` | Show target chat |

### Admin Commands

| Command | Description |
|---|---|
| `/stats` | Bot statistics |
| `/broadcast <msg>` | Message all users |
| `/queue` | Active queue |
| `/reset <user_id>` | Reset rate limit |

## CLI

```bash
tmdl run                    # Start the bot
tmdl init                   # Create .env
tmdl check                  # Verify deps + config
tmdl info <url>             # Video info
tmdl download <url>         # Direct download
tmdl db stats               # DB statistics
tmdl db reset               # Clear DB
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
