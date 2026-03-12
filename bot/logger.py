import asyncio
import logging
import traceback
from datetime import datetime

from pyrogram import Client

from bot import config

# ── stdlib logger (console) ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("MusicBot")

# Keeps a reference to the bot client after startup
_client: Client | None = None


def set_client(client: Client) -> None:
    """Called once after the Pyrogram client is created."""
    global _client
    _client = client


async def _send_log(text: str) -> None:
    """Internal: attempt to send *text* to the log channel."""
    if not _client or not config.LOG_CHANNEL_ID:
        return
    try:
        await _client.send_message(config.LOG_CHANNEL_ID, text, disable_web_page_preview=True)
    except Exception as exc:
        LOGGER.warning("Failed to send log to channel: %s", exc)


async def log_command(
    command: str,
    user_id: int,
    username: str | None,
    chat_id: int,
    chat_title: str,
) -> None:
    """Log a bot command invocation to the log channel."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        "📋 **Command Log**\n"
        f"├ Command : `{command}`\n"
        f"├ User    : [{username or user_id}](tg://user?id={user_id}) (`{user_id}`)\n"
        f"├ Chat    : {chat_title} (`{chat_id}`)\n"
        f"└ Time    : `{now}`"
    )
    LOGGER.info("CMD %s | user=%s | chat=%s", command, user_id, chat_id)
    await _send_log(text)


async def log_error(
    error: Exception,
    context: str = "Unknown",
    chat_id: int | None = None,
    user_id: int | None = None,
) -> None:
    """Log an exception to the log channel with traceback."""
    tb = traceback.format_exc()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        "❌ **Error Log**\n"
        f"├ Context : `{context}`\n"
        f"├ Chat    : `{chat_id or 'N/A'}`\n"
        f"├ User    : `{user_id or 'N/A'}`\n"
        f"├ Time    : `{now}`\n"
        f"├ Error   : `{type(error).__name__}: {error}`\n"
        f"└ Traceback:\n```\n{tb[-1500:]}\n```"
    )
    LOGGER.error("ERROR [%s] %s: %s\n%s", context, type(error).__name__, error, tb)
    await _send_log(text)


async def log_event(event: str, details: str = "") -> None:
    """Generic event log (bot join/leave, etc.)."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    text = f"ℹ️ **Event**: `{event}`\n{details}\n🕐 `{now}`"
    LOGGER.info("EVENT: %s | %s", event, details)
    await _send_log(text)
