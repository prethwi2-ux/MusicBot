"""
bot/database/channel_db.py
Uses a private Telegram channel as the audio storage database.
Audio files are uploaded once and their message IDs cached for reuse.
Metadata is stored in the message caption as JSON.
"""
import json
import asyncio
from typing import Optional

from pyrogram import Client
from pyrogram.types import Message

from bot import config
from bot.database.settings_db import db
from bot.logger import LOGGER, log_error


async def save_audio(
    client: Client,
    file_path: str,
    title: str,
    duration: int,
    thumb_path: Optional[str] = None,
    video_id: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Optional[dict]:
    """
    Upload an audio file to the database channel and store metadata in caption.
    Returns a dict with keys: message_id, file_id, title, duration, video_id.
    """
    metadata = {
        "title": title,
        "duration": duration,
        "video_id": video_id or "",
        "source_url": source_url or "",
    }
    # Compact JSON for metadata caption
    caption = f"🎵 MusicBot DB\n```json\n{json.dumps(metadata, separators=(',',':'), ensure_ascii=False)}\n```"

    try:
        msg: Message = await client.send_audio(
            chat_id=config.DATABASE_CHANNEL_ID,
            audio=file_path,
            caption=caption,
            thumb=thumb_path,
            title=title,
            duration=duration,
        )
        result = {
            "message_id": msg.id,
            "file_id": msg.audio.file_id,
            "title": title,
            "duration": duration,
            "video_id": video_id or "",
        }
        # Cache it immediately in persistent DB
        if video_id:
            db.set_audio(video_id, result)
        LOGGER.info("Saved audio '%s' to DB channel, msg_id=%s", title, msg.id)
        return result
    except Exception as e:
        await log_error(e, context="save_audio", chat_id=config.DATABASE_CHANNEL_ID)
        return None


async def get_audio_by_message_id(
    client: Client, message_id: int
) -> Optional[dict]:
    """
    Fetch an audio record from the database channel by message ID.
    Returns metadata dict or None if not found.
    """
    try:
        msg: Message = await client.get_messages(config.DATABASE_CHANNEL_ID, message_id)
        if not msg or not msg.audio:
            return None
        # Parse metadata from caption
        metadata = _parse_caption(msg.caption or "")
        return {
            "message_id": msg.id,
            "file_id": msg.audio.file_id,
            "title": metadata.get("title", msg.audio.title or "Unknown"),
            "duration": metadata.get("duration", msg.audio.duration or 0),
            "video_id": metadata.get("video_id", ""),
            "source_url": metadata.get("source_url", ""),
        }
    except Exception as e:
        await log_error(e, context="get_audio_by_message_id")
        return None


async def get_audio_by_video_id(
    client: Client, video_id: str
) -> Optional[dict]:
    """
    Lookup by YouTube video ID – checks persistent DB.
    """
    return db.get_audio(video_id)


async def forward_audio(client: Client, message_id: int, target_chat_id: int) -> Optional[Message]:
    """Forward a cached audio from the DB channel to a target chat."""
    try:
        return await client.forward_messages(
            chat_id=target_chat_id,
            from_chat_id=config.DATABASE_CHANNEL_ID,
            message_ids=message_id,
        )
    except Exception as e:
        await log_error(e, context="forward_audio")
        return None


def _parse_caption(caption: str) -> dict:
    """Extract JSON metadata block from a message caption."""
    try:
        start = caption.find("{")
        end = caption.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(caption[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {}
