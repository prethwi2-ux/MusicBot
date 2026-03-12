# 🎵 MusicBot — Telegram Voice Chat Music Bot

A **production-ready**, fully async Telegram Music Bot built with **Pyrogram + PyTgCalls + yt-dlp**.  
Uses a **private Telegram channel** as the audio database (no MongoDB or paid services required).

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎵 YouTube playback | URL or search query |
| 📁 Telegram audio | Reply to an audio file with `/play` |
| 📋 Queue system | Add, skip, remove, shuffle |
| 🔁 Loop modes | Off → Song → Queue cycling |
| ⏸ Pause / Resume | Admin-only controls |
| 🔊 Volume control | `/volume 0–200` |
| ⏩ Seek | Jump to any position |
| 🔍 Inline search | `@YourBot lofi music` |
| 💾 DB Channel | Reuses uploaded audio via file_id |
| 📝 Log Channel | All commands & errors logged |
| 👮 Admin gate | Commands restricted to group admins |
| ⚡ Anti-spam | Per-user rate limiting |
| 🏃 Auto-leave | Leaves idle voice chats automatically |
| 📊 Stats | `/ping`, `/stats`, `/np` |

---

## 🗂️ Project Structure

```
musicBot/
├── main.py                    # Entry point
├── generate_session.py        # Assistant session string generator
├── requirements.txt
├── .env.example               # Template — copy to .env
└── bot/
    ├── __init__.py            # Pyrogram + PyTgCalls clients
    ├── config.py              # Env var loader
    ├── logger.py              # Telegram + console logging
    ├── database/
    │   ├── channel_db.py      # Telegram channel as audio DB
    │   └── cache.py           # LRU+TTL in-memory cache
    ├── music/
    │   ├── downloader.py      # yt-dlp downloader + search
    │   ├── player.py          # PyTgCalls stream manager
    │   ├── queue.py           # Per-group queue + loop modes
    │   └── helpers.py         # UI formatters, progress bar
    ├── plugins/
    │   ├── play.py            # /play
    │   ├── controls.py        # /pause /resume /stop /skip
    │   ├── queue_cmds.py      # /queue /shuffle
    │   ├── loop.py            # /loop
    │   ├── volume.py          # /volume
    │   ├── seek.py            # /seek
    │   ├── info.py            # /ping /stats /np
    │   ├── callbacks.py       # Inline button callbacks
    │   ├── inline.py          # Inline search mode
    │   └── admin.py           # /start /help /broadcast
    └── utils/
        ├── admin_check.py     # Admin permission checks
        ├── decorators.py      # @admin_only @anti_spam @log_cmd
        └── formatters.py      # Human-readable size/time
```

---

## ⚙️ Setup & Deployment

### 1. Prerequisites

- Python 3.11+
- A VPS or computer that stays online (e.g. Ubuntu VPS, Railway, etc.)
- **ffmpeg** installed on the system

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg python3-pip git

# Windows (via Chocolatey)
choco install ffmpeg
```

### 2. Clone the project

```bash
git clone <your-repo-url>
cd musicBot
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Telegram API credentials

1. Go to [my.telegram.org/apps](https://my.telegram.org/apps)
2. Create an app → note **API_ID** and **API_HASH**
3. Create a bot via [@BotFather](https://t.me/BotFather) → get **BOT_TOKEN**
4. Enable **Inline Mode** in BotFather for inline search

### 5. Create Telegram channels

| Channel | Purpose |
|---|---|
| **Database Channel** | Private channel — bot stores audio files here |
| **Log Channel** | Bot sends command logs and error traces here |

- Make the bot an **admin** of both channels.
- Get their IDs (start with `-100...`). Use [@userinfobot](https://t.me/userinfobot) or forward a message to [@getidsbot](https://t.me/getidsbot).

### 6. Generate assistant session string

The bot uses a **userbot (assistant account)** to join voice chats.

```bash
python generate_session.py
```

Follow the prompts (phone number → OTP → 2FA if enabled).  
Copy the printed `STRING_SESSION` value.

### 7. Configure environment

```bash
cp .env.example .env
nano .env   # or use any text editor
```

Fill in all values:

```env
API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
STRING_SESSION=your_session_string
DATABASE_CHANNEL_ID=-100xxxxxxxxxx
LOG_CHANNEL_ID=-100xxxxxxxxxx
OWNER_ID=123456789
SUDO_USERS=123456789
MAX_DURATION=3600
STREAM_QUALITY=high
AUTO_LEAVE_DELAY=300
```

### 8. Run the bot

```bash
python main.py
```

To run persistently in the background on Linux:

```bash
# Using screen
screen -S musicbot
python main.py
# Ctrl+A then D to detach

# Or using systemd (recommended for VPS)
```

---

## 🤖 Bot Permissions Required

In the group:
- ✅ Send messages
- ✅ Manage voice chats (for assistant)

The **assistant account** must be able to join the group voice chat.  
Add the assistant as a member or admin of the group.

---

## 📋 Commands Reference

| Command | Description | Admin? |
|---|---|---|
| `/play <query/url>` | Play a song or add to queue | ❌ |
| `/pause` | Pause playback | ✅ |
| `/resume` | Resume playback | ✅ |
| `/skip` | Skip current song | ✅ |
| `/stop` | Stop and clear queue | ✅ |
| `/seek <sec>` | Seek to position | ✅ |
| `/queue [page]` | Show queue | ❌ |
| `/shuffle` | Shuffle queue | ✅ |
| `/loop` | Cycle loop mode | ✅ |
| `/volume <0-200>` | Set volume | ✅ |
| `/np` | Now playing card | ❌ |
| `/ping` | Bot latency | ❌ |
| `/stats` | Bot statistics | ❌ |
| `/help` | Command list | ❌ |

**Inline:** `@YourBot <song name>` — search and share

---

## 🔧 Troubleshooting

| Issue | Fix |
|---|---|
| `GroupCallNotFound` | Start a voice chat in the group first |
| `ffmpeg not found` | Install ffmpeg on your system |
| Bot doesn't join VC | Ensure assistant is a member of the group |
| No audio playing | Check STREAM_QUALITY, ensure file downloaded |
| Database channel errors | Bot must be admin of DATABASE_CHANNEL |

---

## 📦 Key Libraries

- [Pyrogram](https://docs.pyrogram.org) — Telegram MTProto client
- [PyTgCalls](https://pytgcalls.github.io) — Voice chat streaming
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube audio downloader
- [TgCrypto](https://github.com/pyrogram/tgcrypto) — Fast Pyrogram crypto
