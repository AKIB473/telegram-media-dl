<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:229ED9,100:0d5fa3&height=180&section=header&text=Telegram+Media+Downloader&fontSize=36&fontColor=ffffff&fontAlignY=40&desc=Production-grade+Telegram+bot+%E2%80%94+50%2B+platforms%2C+async%2C+Docker-ready&descAlignY=62&descSize=15" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-229ED9?style=for-the-badge&logo=telegram&logoColor=white)](https://aiogram.dev)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![CI](https://github.com/AKIB473/telegram-media-dl/actions/workflows/ci.yml/badge.svg)](https://github.com/AKIB473/telegram-media-dl/actions)

<br/>

**Send any YouTube, Instagram, TikTok, Twitter/X, Facebook link to the bot — get the video in seconds.**

[**✨ Features**](#-features) · [**⚡ Quick Start**](#-quick-start) · [**🐳 Docker**](#-docker-deployment) · [**⚙️ Config**](#%EF%B8%8F-configuration) · [**🏗️ Architecture**](#%EF%B8%8F-architecture)

</div>

---

## 📋 Table of Contents

- [What it does](#-what-it-does)
- [Features](#-features)
- [Supported platforms](#-supported-platforms-50)
- [Quick Start](#-quick-start)
- [Docker Deployment](#-docker-deployment)
- [Configuration](#%EF%B8%8F-configuration)
- [Bot Commands](#-bot-commands)
- [CLI Tool](#-cli-tool-tmdl)
- [Architecture](#%EF%B8%8F-architecture)
- [Tech Stack](#-tech-stack)
- [Development](#-development)
- [Project Structure](#-project-structure)

---

## 🎯 What it does

A user sends a video URL to the bot on Telegram. The bot:

1. Detects the platform (YouTube, Instagram, TikTok, etc.)
2. Shows available quality options (1080p, 720p, 480p, 360p, Audio-only)
3. Downloads the video asynchronously using **yt-dlp**
4. Embeds metadata + thumbnail + subtitles
5. Sends the file back via Telegram
6. Optionally auto-forwards to a channel

All of this happens without the user leaving Telegram. No browser, no third-party website, no ads.

---

## ✨ Features

### Core Features
- 🎥 **50+ platform support** — YouTube, Instagram, TikTok, Twitter/X, Facebook, SoundCloud, Twitch, Dailymotion, and [more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- 📊 **Quality selection** — Best / 1080p / 720p / 480p / 360p / Audio-only (MP3 320/192/128 kbps)
- ⚡ **Async downloads** — Multiple downloads happen in parallel, non-blocking
- 🔍 **YouTube search** — `/search query` with inline result buttons, no URL needed
- 📝 **Metadata embedding** — title, artist, thumbnail embedded via mutagen + ffmpeg
- 🔤 **Subtitles** — auto-download and embed English subtitles when available
- 🍪 **Cookie support** — download age-restricted and login-required content via cookies.txt

### User Features
- 📜 **Download history** — per-user SQLite history, last 10 downloads
- ⚙️ **Preferences** — save default quality, format, notification settings
- 📤 **Target chat** — auto-forward every download to a specific channel
- ❌ **Cancel** — cancel active downloads at any time

### Admin Features
- 📊 **Statistics** — active users, total downloads, storage used, queue depth
- 📢 **Broadcast** — send a message to all bot users
- 🔧 **Queue monitor** — see all active and pending downloads
- 🔄 **Rate limit reset** — manually reset rate limit for a user

### Infrastructure
- 🔒 **Rate limiting** — sliding-window rate limiter per user (configurable)
- 📦 **File size guard** — configurable max file size (default 1.9 GB, Telegram's limit)
- 🐳 **Docker** — single `docker-compose up` deployment
- 🔁 **CI/CD** — GitHub Actions with pytest, linting, automatic testing on every push
- 🛠️ **CLI tool** (`tmdl`) — manage the bot from the terminal

---

## 🌐 Supported Platforms (50+)

| Platform | Video | Audio | Playlist |
|---|---|---|---|
| YouTube | ✅ up to 4K | ✅ MP3 | ✅ |
| Instagram | ✅ Reels, Posts | ✅ | ❌ |
| TikTok | ✅ | ❌ | ❌ |
| Twitter / X | ✅ | ❌ | ❌ |
| Facebook | ✅ | ❌ | ❌ |
| SoundCloud | ❌ | ✅ | ✅ |
| Twitch (clips) | ✅ | ❌ | ❌ |
| Dailymotion | ✅ | ❌ | ❌ |
| Reddit | ✅ | ❌ | ❌ |
| Vimeo | ✅ | ❌ | ❌ |
| 40+ more | varies | varies | varies |

*Full list: [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)*

---

## ⚡ Quick Start

### Prerequisites

- Python 3.10+
- ffmpeg installed on your system
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/AKIB473/telegram-media-dl
cd telegram-media-dl

# 2. Create and configure .env
cp .env.example .env
```

Open `.env` and set your bot token:

```env
BOT_TOKEN=1234567890:your_bot_token_here
ADMIN_IDS=your_telegram_user_id
```

```bash
# 3. Install dependencies
pip install -e ".[dev]"

# 4. Start the bot
tmdl run
```

The bot is now live. Send it a YouTube link to test.

---

## 🐳 Docker Deployment

The recommended way to run in production.

```bash
# 1. Clone
git clone https://github.com/AKIB473/telegram-media-dl
cd telegram-media-dl

# 2. Configure
cp .env.example .env
# Edit .env — set BOT_TOKEN at minimum

# 3. Start
docker-compose up -d

# 4. View logs
docker-compose logs -f

# 5. Stop
docker-compose down
```

### What docker-compose includes

- **bot** container — the Python bot
- **Persistent volume** for downloads and SQLite database
- **Auto-restart** on failure
- Health check built in

---

## ⚙️ Configuration

All settings via environment variables or `.env` file.

### Required

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Telegram bot token from @BotFather |

### Optional — Users & Access

| Variable | Default | Description |
|---|---|---|
| `ADMIN_IDS` | `[]` | Comma-separated Telegram user IDs with admin access |
| `ALLOWED_USER_IDS` | `[]` | Leave empty to allow all users |
| `TARGET_CHAT` | `None` | Channel/group ID to auto-forward every download |

### Optional — Downloads

| Variable | Default | Description |
|---|---|---|
| `DOWNLOAD_DIR` | `downloads/` | Directory to store temporary downloads |
| `MAX_FILE_SIZE_MB` | `1900` | Maximum file size to send (Telegram limit: 2 GB) |
| `MAX_CONCURRENT` | `3` | Parallel downloads allowed at once |
| `DOWNLOAD_TIMEOUT` | `300` | Seconds before a download is killed |
| `ALLOW_PLAYLISTS` | `false` | Whether to allow playlist downloads |
| `COOKIE_FILE` | `None` | Path to `cookies.txt` for restricted content |
| `DEFAULT_QUALITY` | `best` | Default quality: `best`, `1080`, `720`, `480`, `360`, `audio` |

### Optional — Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_COUNT` | `5` | Maximum downloads per window per user |
| `RATE_LIMIT_WINDOW` | `3600` | Window size in seconds (3600 = 1 hour) |

---

## 📱 Bot Commands

### User Commands

| Command | Description |
|---|---|
| `/start` | Welcome message and quick guide |
| `/help` | Full feature list |
| `<any URL>` | Send a URL directly — bot auto-detects the platform |
| `/search <query>` | Search YouTube, pick from inline buttons |
| `/history` | Your last 10 downloads |
| `/settings` | View and change your preferences |
| `/quality <q>` | Set default quality (`best`, `720`, `audio`, etc.) |
| `/setchat <id>` | Set a target channel to auto-forward downloads |
| `/mychat` | Show your current target chat |
| `/cancel` | Cancel all active downloads |

### Admin Commands

| Command | Description |
|---|---|
| `/stats` | Bot statistics: users, downloads, storage, queue |
| `/broadcast <message>` | Send a message to all users |
| `/queue` | View active download queue |
| `/reset <user_id>` | Reset rate limit for a user |

---

## 🛠️ CLI Tool (`tmdl`)

Manage the bot from the terminal:

```bash
# Start the bot
tmdl run

# Create a fresh .env with guided prompts
tmdl init

# Check configuration and dependencies
tmdl check

# Get info about a URL (without downloading)
tmdl info https://youtube.com/watch?v=dQw4w9WgXcQ

# Download directly (bypasses Telegram)
tmdl download https://youtube.com/watch?v=dQw4w9WgXcQ --quality 720

# Database management
tmdl db stats     # Show database statistics
tmdl db reset     # Clear all data (use with caution)
```

---

## 🏗️ Architecture

```
User sends URL via Telegram
        │
        ▼
┌────────────────────┐
│   aiogram 3 bot    │  ← Async event loop, webhook or polling
│   (handlers.py)    │
└────────────────────┘
        │
        ▼
┌────────────────────┐
│   Rate Limiter     │  ← Sliding window, per-user, SQLite-backed
└────────────────────┘
        │
        ▼
┌────────────────────┐
│   Download Queue   │  ← asyncio.Queue, MAX_CONCURRENT workers
│   (queue.py)       │
└────────────────────┘
        │
        ▼
┌────────────────────┐
│   yt-dlp wrapper   │  ← Platform detection + download
│   (downloader.py)  │
└────────────────────┘
        │
        ▼
┌────────────────────┐
│   ffmpeg / mutagen │  ← Metadata + thumbnail + subtitle embed
└────────────────────┘
        │
        ▼
┌────────────────────┐
│   Telegram API     │  ← Send file back (chunked upload)
└────────────────────┘
        │
        ▼
┌────────────────────┐
│   Target chat fwd  │  ← Optional auto-forward
└────────────────────┘
```

### Why async?

yt-dlp downloads can take 30–300 seconds. If the bot used synchronous code, every user would be blocked waiting for the previous download to finish. The async queue allows:
- Up to `MAX_CONCURRENT` simultaneous downloads
- Non-blocking: other users can interact while downloads run
- Clean cancellation without killing the whole process

---

## 🧰 Tech Stack

| Component | Technology | Why |
|---|---|---|
| Bot framework | **aiogram 3** | Modern async, no API_ID/HASH needed (bot token only) |
| Video downloader | **yt-dlp** | Actively maintained fork of youtube-dl, 50+ platforms |
| Media processing | **ffmpeg + mutagen** | Reliable metadata embedding and format conversion |
| Database | **aiosqlite (SQLite)** | Lightweight, zero configuration, async-compatible |
| Containerization | **Docker + docker-compose** | Reproducible deployment anywhere |
| CI/CD | **GitHub Actions** | Runs pytest + linting on every push |
| Packaging | **pyproject.toml** | Modern Python packaging, installable as `tmdl` CLI |

---

## 💻 Development

```bash
# Clone
git clone https://github.com/AKIB473/telegram-media-dl
cd telegram-media-dl

# Install in development mode with all extras
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=tgdl --cov-report=html

# Lint
flake8 tgdl/
```

### Running tests

The test suite uses `pytest-asyncio` for async tests and `pytest-mock` for Telegram API mocking.

```bash
pytest tests/ -v
# ✓ test_rate_limiter.py (12 tests)
# ✓ test_downloader.py (8 tests)
# ✓ test_handlers.py (15 tests)
# ✓ test_db.py (11 tests)
# ✓ test_cli.py (8 tests)
```

---

## 📁 Project Structure

```
telegram-media-dl/
│
├── tgdl/
│   ├── __init__.py
│   ├── bot.py              ← Bot initialization and startup
│   ├── handlers/
│   │   ├── download.py     ← URL handler, quality selection
│   │   ├── search.py       ← YouTube search
│   │   ├── settings.py     ← User preferences
│   │   └── admin.py        ← Admin commands
│   ├── core/
│   │   ├── downloader.py   ← yt-dlp wrapper
│   │   ├── queue.py        ← Async download queue
│   │   ├── rate_limiter.py ← Sliding window rate limiter
│   │   └── metadata.py     ← ffmpeg / mutagen embedding
│   ├── db/
│   │   ├── models.py       ← SQLite schema
│   │   └── repository.py   ← Async DB access layer
│   └── cli/
│       └── main.py         ← tmdl CLI entry point
│
├── tests/                  ← pytest test suite (48 tests)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml          ← Project config + tmdl CLI entry point
├── .env.example
└── README.md
```

---

## 🚀 Deployment Options

| Method | Best for | Complexity |
|---|---|---|
| **Docker** (recommended) | VPS, cloud servers | Low |
| **Systemd service** | Linux VPS without Docker | Medium |
| **Railway / Render** | Managed cloud hosting | Low |
| **Local** (`tmdl run`) | Development and testing | Minimal |

---

## ⚠️ Legal Notes

- This bot is for **personal use** and **educational purposes**
- Respect the **terms of service** of each platform
- Do **not** use to download copyrighted content without permission
- The bot does **not** store downloaded files permanently — they are deleted after delivery

---

## 🤝 Contributing

Contributions welcome!

```bash
# Fork → branch → change → PR
git checkout -b feat/your-feature
# make changes
git commit -m "feat: add platform X support"
git push origin feat/your-feature
# open Pull Request
```

**Ideas for contributions:**
- Add more platform-specific handlers
- Improve subtitle embedding
- Add Redis-backed queue for distributed deployment
- Progress bar in Telegram (using yt-dlp progress hooks)

---

## 📄 License

MIT — free to use, modify, and distribute.

---

<div align="center">

Built by [AKIBUZZAMAN AKIB](https://github.com/AKIB473)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:229ED9,100:0d5fa3&height=80&section=footer" width="100%"/>

</div>
