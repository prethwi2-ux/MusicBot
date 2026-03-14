"""
bot/music/player.py
Manages PyTgCalls v2 streams per group: start, pause, resume, stop, seek, volume.
Handles stream-end callbacks and auto-plays the next track.

PyTgCalls v2 key changes vs v0.9:
  - Import: from pytgcalls import PyTgCalls
  - Stream types: pytgcalls.types.MediaStream (replaces AudioPiped)
  - Audio quality: pytgcalls.types.AudioQuality
  - Events: @call.on_update(filters.stream_end)
  - join_group_call(chat_id, stream)
  - leave_group_call(chat_id)
  - pause_stream(chat_id) / resume_stream(chat_id)
  - change_volume_call(chat_id, volume)
  - play(chat_id, stream) — starts or replaces current stream
"""
import asyncio
import time
import os
from typing import Optional

from pytgcalls import PyTgCalls, filters as tgfilters
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, Update
from pytgcalls.exceptions import (
    CallBusy,
    CallDeclined,
    CallDiscarded,
    ClientNotStarted,
)

from bot.music.queue import get_queue, delete_queue, MusicQueue
from bot.music.downloader import AudioInfo
from bot import config
from bot.logger import LOGGER, log_error, log_event


def _make_stream(audio: AudioInfo, seek_secs: int = 0) -> MediaStream:
    """Build a PyTgCalls v2 MediaStream from an AudioInfo (Remote or Local)."""
    # Prioritize remote stream URL for "No-Download" mode
    stream_path = audio.stream_url or audio.file_path
    if not stream_path:
        raise ValueError(f"No streamable path found for '{audio.title}'")

    extra_ffmpeg = f"-ss {seek_secs}" if seek_secs > 0 else ""
    reconnect_params = "-reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    ffmpeg_opts = f"{reconnect_params} {extra_ffmpeg}".strip()
    
    LOGGER.info("Creating MediaStream for %s (video=%s)", audio.title, audio.is_video)
    if audio.is_video:
        return MediaStream(
            stream_path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.SD_480p,
            ffmpeg_parameters=ffmpeg_opts or None,
        )
    else:
        return MediaStream(
            stream_path,
            audio_parameters=AudioQuality.HIGH,
            ffmpeg_parameters=ffmpeg_opts or None,
        )


# ── Stream starter ───────────────────────────────────────────────────────────────

async def start_stream(call: PyTgCalls, chat_id: int, audio: AudioInfo) -> bool:
    """Start or replace the current stream in a group voice chat."""
    from bot import app, assistant
    queue = get_queue(chat_id)
    try:
        # ── Robust Assistant Join Logic ───────────────────────────────────────────
        # Resolves "CHANNEL_INVALID" by ensuring the Assistant account "sees" the chat.
        try:
            me_assistant = await assistant.get_me()
            
            # 1. Try to add directly
            try:
                await app.add_chat_members(chat_id, me_assistant.id)
                LOGGER.info("Assistant added to group %s by Bot", chat_id)
            except Exception: pass

            # 2. Assistant must resolve the peer to avoid ChannelInvalid
            try:
                await assistant.get_chat(chat_id)
            except Exception:
                # 3. Fallback: Join via invite link
                LOGGER.info("Assistant needs invite link for group %s", chat_id)
                invite_link = await app.export_chat_invite_link(chat_id)
                await assistant.join_chat(invite_link)
                LOGGER.info("Assistant joined group %s via link", chat_id)

        except Exception as join_err:
            LOGGER.warning("Assistant join attempt failed (might already be in): %s", join_err)

        stream = _make_stream(audio)
        LOGGER.info("Attempting to play %s in chat %s", audio.title, chat_id)
        
        try:
            await call.play(chat_id, stream)
        except Exception as play_err:
            LOGGER.error("play() failed: %s", play_err)
            raise play_err

        queue.is_playing = True
        queue.is_paused = False
        queue.last_active = time.monotonic()
        LOGGER.info("Streaming started for '%s'", audio.title)
        return True
    except Exception as e:
        err_msg = str(e)
        LOGGER.error("CRITICAL start_stream error [%s]: %s", type(e).__name__, err_msg)
        
        if "No active group call" in err_msg:
             LOGGER.error("ERROR: No active voice chat in this group. Please start one first!")
        elif "USER_ALREADY_PARTICIPANT" in err_msg:
             # Already in, maybe just need to change stream
             try:
                 await call.play(chat_id, stream)
                 return True
             except Exception: pass
        
        await log_error(e, context="start_stream", chat_id=chat_id)
        return False


async def pause_stream(call: PyTgCalls, chat_id: int) -> bool:
    queue = get_queue(chat_id)
    try:
        await call.pause(chat_id)
        queue.is_paused = True
        return True
    except Exception as e:
        await log_error(e, context="pause_stream", chat_id=chat_id)
        return False


async def resume_stream(call: PyTgCalls, chat_id: int) -> bool:
    queue = get_queue(chat_id)
    try:
        await call.resume(chat_id)
        queue.is_paused = False
        return True
    except Exception as e:
        await log_error(e, context="resume_stream", chat_id=chat_id)
        return False


async def stop_stream(call: PyTgCalls, chat_id: int) -> bool:
    queue = get_queue(chat_id)
    try:
        await call.leave_call(chat_id)
    except Exception:
        pass
    await queue.clear()
    delete_queue(chat_id)
    return True


async def skip_stream(call: PyTgCalls, chat_id: int) -> Optional[AudioInfo]:
    """Skip to next track. Returns next AudioInfo or None if queue ended."""
    queue = get_queue(chat_id)
    next_track = await queue.skip()
    if next_track:
        await start_stream(call, chat_id, next_track)
    else:
        await stop_stream(call, chat_id)
    return next_track


async def set_volume(call: PyTgCalls, chat_id: int, volume: int) -> bool:
    """Set volume (0-200)."""
    volume = max(0, min(200, volume))
    queue = get_queue(chat_id)
    try:
        await call.change_volume_call(chat_id, volume)
        queue.volume = volume
        return True
    except Exception as e:
        await log_error(e, context="set_volume", chat_id=chat_id)
        return False


async def seek_stream(call: PyTgCalls, chat_id: int, seconds: int) -> bool:
    """Seek to `seconds` position in current track."""
    queue = get_queue(chat_id)
    current = queue.current_track
    if not current:
        return False
    try:
        stream = _make_stream(current, seek_secs=seconds)
        await call.play(chat_id, stream)
        return True
    except Exception as e:
        await log_error(e, context="seek_stream", chat_id=chat_id)
        return False


# ── Stream-end callback ──────────────────────────────────────────────────────────

def register_callbacks(call: PyTgCalls, app) -> None:
    """Register PyTgCalls v2 event handlers. Call once at startup."""

    # Fix: Use on_update with an INSTANCE of stream_end filter. 
    # filters.stream_end is a class; it must be called to create a filter instance.
    @call.on_update(tgfilters.stream_end())
    async def on_stream_end(client: PyTgCalls, update: Update):
        chat_id = update.chat_id
        queue = get_queue(chat_id)
        next_track = await queue.skip()
        if next_track:
            ok = await start_stream(call, chat_id, next_track)
            if ok and queue.now_playing_msg_id:
                from bot.music.helpers import update_now_playing
                await update_now_playing(app, chat_id, queue.now_playing_msg_id, next_track, queue)
        else:
            await log_event("Queue ended", f"Chat: `{chat_id}`")
            try:
                await call.leave_call(chat_id)
            except Exception:
                pass
            await queue.clear()
            delete_queue(chat_id)


# ── Auto-leave inactive groups ───────────────────────────────────────────────────

async def auto_leave_task(call: PyTgCalls) -> None:
    """Background task: leave voice chats idle for AUTO_LEAVE_DELAY seconds."""
    from bot.music.queue import active_queues
    while True:
        await asyncio.sleep(60)
        now = time.monotonic()
        for cid, q in list(active_queues().items()):
            if q.is_playing and not q.is_paused:
                q.last_active = now
            elif now - q.last_active > config.AUTO_LEAVE_DELAY:
                LOGGER.info("Auto-leaving idle group %s", cid)
                try:
                    await call.leave_call(cid)
                except Exception:
                    pass
                await q.clear()
                delete_queue(cid)
