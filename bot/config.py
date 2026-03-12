import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from the project root (directory containing this file's parent)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH, override=True)



def _get_int(key: str, default: int = 0) -> int:
    val = os.environ.get(key, str(default))
    try:
        return int(val)
    except ValueError:
        return default


def _get_list(key: str, default: list = None) -> list:
    val = os.environ.get(key, "")
    if not val.strip():
        return default or []
    return [int(x.strip()) for x in val.split(",") if x.strip().isdigit()]


# ── Telegram API ────────────────────────────────────────────────────────────────
API_ID: int = _get_int("API_ID")
API_HASH: str = os.environ.get("API_HASH", "")
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
STRING_SESSION: str = os.environ.get("STRING_SESSION", "")
YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "")

# ── Channels ────────────────────────────────────────────────────────────────────
DATABASE_CHANNEL_ID: int = _get_int("DATABASE_CHANNEL_ID")
LOG_CHANNEL_ID: int = _get_int("LOG_CHANNEL_ID")

# ── Access Control ──────────────────────────────────────────────────────────────
OWNER_ID: int = _get_int("OWNER_ID")
SUDO_USERS: list = _get_list("SUDO_USERS", [OWNER_ID])

# ── Music Settings ──────────────────────────────────────────────────────────────
MAX_DURATION: int = _get_int("MAX_DURATION", 3600)
STREAM_QUALITY: str = os.environ.get("STREAM_QUALITY", "high")
AUTO_LEAVE_DELAY: int = _get_int("AUTO_LEAVE_DELAY", 300)
MAX_QUEUE_SIZE: int = _get_int("MAX_QUEUE_SIZE", 100)
DOWNLOAD_DIR: str = os.environ.get("DOWNLOAD_DIR", "./downloads")

# ── Quality Mapping ─────────────────────────────────────────────────────────────
QUALITY_MAP = {
    "low": "64k",
    "medium": "128k",
    "high": "192k",
    "ultra": "320k",
}
AUDIO_BITRATE: str = QUALITY_MAP.get(STREAM_QUALITY, "192k")

# ── Anti-Spam ───────────────────────────────────────────────────────────────────
SPAM_LIMIT: int = 5       # commands per window
SPAM_WINDOW: int = 10     # seconds

# ── Ensure downloads directory exists ───────────────────────────────────────────
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ── Validate critical config ─────────────────────────────────────────────────────
_REQUIRED = {"API_ID": API_ID, "API_HASH": API_HASH, "BOT_TOKEN": BOT_TOKEN}
for _name, _val in _REQUIRED.items():
    if not _val:
        raise EnvironmentError(f"[Config] Missing required environment variable: {_name}")
