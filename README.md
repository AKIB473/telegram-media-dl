# ⚡ telegram-media-dl

> Production-grade Telegram bot for downloading media from **50+ sites**

[![PyPI](https://img.shields.io/pypi/v/telegram-media-dl)](https://pypi.org/project/telegram-media-dl/)
[![Python](https://img.shields.io/pypi/pyversions/telegram-media-dl)](https://pypi.org/project/telegram-media-dl/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features

- 🎬 Download from **YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit, Vimeo, Twitch** and 40+ more
- 🎵 **Audio extraction** with quality selection (96/128/192/320 kbps)
- 📺 **Video quality** selection (360p / 480p / 720p / 1080p / Best)
- ⚡ **Async download queue** — handles multiple users simultaneously
- 🔄 **Auto-retry** on failure (configurable)
- 🛡️ **Rate limiting** per user (configurable)
- 📦 **File size check** before download (respects Telegram's 2GB limit)
- 👑 **Admin commands** — stats, queue view, broadcast, rate limit reset
- 🖼️ **Video thumbnail** preview before download
- 📊 **Live progress** updates during download
- 🐳 Docker-ready
- 📦 **Pip installable**

## 🚀 Quick Start

### Install

```bash
pip install telegram-media-dl
```

### Configure

```bash
tmdl init        # Creates .env template
nano .env        # Fill in your credentials
```

### Run

```bash
tmdl run
```

---

## 📋 Setup Guide

### 1. Get Telegram API credentials

1. Go to https://my.telegram.org/apps
2. Create a new application
3. Copy `API_ID` and `API_HASH`

### 2. Create a bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the `BOT_TOKEN`

### 3. Configure `.env`

```env
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=1234567890:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=your_telegram_user_id
```

---

## 🖥️ CLI Commands

```bash
tmdl run                          # Start the bot
tmdl init                         # Create .env template
tmdl check                        # Check config & dependencies
tmdl info <url>                   # Show video info without downloading
tmdl download <url>               # Download directly (no bot)
tmdl download <url> --format audio --quality 320
tmdl download <url> --quality 720p --output ./videos
```

---

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Full help |
| `/status` | Your active downloads |
| `/cancel` | Cancel your downloads |

**Admin only:**

| Command | Description |
|---|---|
| `/queue` | View global download queue |
| `/stats` | Bot statistics |
| `/reset <user_id>` | Reset rate limit for a user |
| `/broadcast <msg>` | Send message to all users |

---

## ⚙️ Configuration

All settings via `.env` file:

| Variable | Default | Description |
|---|---|---|
| `API_ID` | — | Telegram API ID (required) |
| `API_HASH` | — | Telegram API Hash (required) |
| `BOT_TOKEN` | — | Bot token (required) |
| `ADMIN_IDS` | — | Comma-separated admin user IDs |
| `DOWNLOAD_DIR` | `downloads` | Download directory |
| `MAX_FILE_SIZE_MB` | `1900` | Max file size in MB |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Max parallel downloads |
| `DEFAULT_VIDEO_QUALITY` | `best` | Default video quality |
| `DEFAULT_AUDIO_QUALITY` | `192` | Default audio quality (kbps) |
| `DOWNLOAD_TIMEOUT` | `300` | Download timeout in seconds |
| `RATE_LIMIT_COUNT` | `5` | Downloads per user per window |
| `RATE_LIMIT_WINDOW` | `3600` | Rate limit window in seconds |
| `ALLOW_PLAYLISTS` | `false` | Allow playlist downloads |
| `SEND_THUMBNAIL` | `true` | Send thumbnail preview |
| `SHOW_VIDEO_INFO` | `true` | Show video metadata |
| `MAX_RETRIES` | `3` | Download retry count |

---

## 🐳 Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["tmdl", "run"]
```

```bash
docker build -t tmdl .
docker run -d --env-file .env tmdl
```

---

## 🌐 Supported Sites

YouTube • Instagram • TikTok • Twitter/X • Facebook • Reddit • Twitch • Vimeo • Dailymotion • SoundCloud • Spotify • Pinterest • LinkedIn • Bilibili • NicoVideo • Streamable • Medal.tv • Rumble • Odysee • Mixcloud • Bandcamp • and **40+ more** via yt-dlp

---

## 📄 License

MIT © [Akibuzzaman Akib](https://github.com/AKIB473)
