import os
import sys
from pathlib import Path
from pyrogram import Client
from pytgcalls import PyTgCalls

from bot import config

# ── FFmpeg Path Check (Windows specific) ────────────────────────────────────────
# Helper to ensure ffmpeg is in PATH for PyTgCalls
def _ensure_ffmpeg():
    if sys.platform != "win32":
        return
    
    # Check if already in PATH
    import shutil
    if shutil.which("ffmpeg"):
        return

    # Check common Winget/Gyan path from earlier
    ffmpeg_base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    possible_paths = list(ffmpeg_base.glob("**/ffmpeg-*-full_build/bin"))
    if not possible_paths:
        # Check standard Gyan path
        possible_paths = list(Path("C:/").glob("**/ffmpeg-*-full_build/bin"))

    if possible_paths:
        bin_path = str(possible_paths[0].resolve())
        if bin_path not in os.environ["PATH"]:
            os.environ["PATH"] += os.path.pathsep + bin_path
            print(f"DEBUG: Added FFmpeg to PATH: {bin_path}")

_ensure_ffmpeg()

# ── Bot Client ──────────────────────────────────────────────────────────────────
app = Client(
    name="MusicBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=dict(root="bot/plugins"),
    sleep_threshold=60,
    in_memory=True,
)

# ── Assistant (userbot) Client for joining voice chats ──────────────────────────
# PyTgCalls v2 requires a USER client (not bot) to join group voice calls.
assistant = Client(
    name="MusicAssistant",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.STRING_SESSION,
    in_memory=True,
)

# ── PyTgCalls v2 wrapper around the ASSISTANT (userbot) ─────────────────────────
call = PyTgCalls(assistant)

__all__ = ["app", "assistant", "call"]
