"""
bot/plugins/play.py
Handles /play command: YouTube URL, search query, or Telegram audio file.
"""
import asyncio
import os

from pyrogram import Client, filters
from pyrogram.types import Message

from bot import call
from bot.music.downloader import download_audio
from bot.music.player import start_stream
from bot.music.queue import get_queue
from bot.music.helpers import build_now_playing_text, build_control_buttons, delete_later, update_now_playing
from bot.database.settings_db import db
from bot.utils.decorators import anti_spam, log_cmd, fast_cmd
from bot.logger import log_error


@Client.on_message(filters.command(["play", "p", "vplay", "vp"]) & filters.group, group=1)
@fast_cmd
@anti_spam
@log_cmd
async def play_command(client: Client, message: Message):
    if message.from_user and db.is_gbanned(message.from_user.id):
        return await message.reply("🚫 You are globally banned from using this bot.")
    
    is_video = "v" in message.command[0].lower()
    query = " ".join(message.command[1:]).strip() if len(message.command) > 1 else ""
    queue = get_queue(message.chat.id)

    # ── Handle Telegram audio reply ──────────────────────────────────────────────
    if message.reply_to_message and message.reply_to_message.audio:
        audio_msg = message.reply_to_message.audio
        tg_audio = audio_msg
        file_path = os.path.join("downloads", f"{tg_audio.file_unique_id}.ogg")

        status_msg = await message.reply("⬇️ Downloading audio from Telegram...")
        if not os.path.exists(file_path):
            await client.download_media(message.reply_to_message, file_name=file_path)

        from bot.music.downloader import AudioInfo
        audio_info = AudioInfo(
            title=tg_audio.title or tg_audio.file_name or "Telegram Audio",
            duration=tg_audio.duration or 0,
            video_id=tg_audio.file_unique_id,
            source_url="",
            file_path=file_path,
            thumb_path=None,
            requested_by=message.from_user.id if message.from_user else 0,
            requested_name=message.from_user.mention if message.from_user else "Unknown",
        )
    elif not query:
        err_msg = await message.reply("❓ Please provide a song name or YouTube URL.\nExample: `/play Shape of You`")
        asyncio.create_task(delete_later(err_msg))
        return
    else:
        status_msg = await message.reply("🔍 Searching..." if not is_video else "🔍 Searching and preparing video...")
        audio_info = await download_audio(
            query,
            requested_by=message.from_user.id if message.from_user else 0,
            requested_name=message.from_user.mention if message.from_user else "Unknown",
            is_video=is_video,
        )

    if not audio_info:
        await status_msg.edit("❌ Could not find or download the song. Try another query.")
        asyncio.create_task(delete_later(status_msg))
        return

    # ── Add to queue ─────────────────────────────────────────────────────────────
    # We skip saving to the Database Channel for YouTube links in "Direct Stream" mode
    # because stream URLs are temporary.
    pos = await queue.add(audio_info)

    if queue.is_playing:
        await status_msg.edit(
            f"✅ Added to queue at position **#{pos}**\n🎵 **{audio_info.title}**"
        )
        asyncio.create_task(delete_later(status_msg))
        # Update existing control message with new queue count
        if queue.now_playing_msg_id and queue.current_track:
            await update_now_playing(client, message.chat.id, queue.now_playing_msg_id, queue.current_track, queue)
        return

    # ── Start streaming ──────────────────────────────────────────────────────────
    status_text = "▶️ Connecting to voice chat..." if not is_video else "🎥 Preparing video stream..."
    await status_msg.edit(status_text)
    
    ok = await start_stream(call, message.chat.id, audio_info)
    if not ok:
        error_text = "❌ Failed to start the stream. Make sure I'm an admin with voice chat permissions."
        if is_video:
            error_text = "❌ Failed to start video stream. This video might be protected or incompatible."
        await status_msg.edit(error_text)
        asyncio.create_task(delete_later(status_msg))
        return

    # ── Now Playing card ─────────────────────────────────────────────────────────
    np_text = build_now_playing_text(audio_info, queue)
    buttons = build_control_buttons(queue.loop_mode)

    try:
        if audio_info.thumb_path and os.path.exists(audio_info.thumb_path):
            np_msg = await client.send_photo(
                chat_id=message.chat.id,
                photo=audio_info.thumb_path,
                caption=np_text,
                reply_markup=buttons,
            )
            # Delete image after sending to keep server clean
            try: os.remove(audio_info.thumb_path)
            except: pass
        else:
            np_msg = await client.send_message(
                chat_id=message.chat.id,
                text=np_text,
                reply_markup=buttons,
            )
        if queue.now_playing_msg_id:
            try:
                old_msg = await client.get_messages(message.chat.id, queue.now_playing_msg_id)
                if old_msg:
                    await old_msg.delete()
            except Exception:
                pass
        queue.now_playing_msg_id = np_msg.id
        asyncio.create_task(delete_later(status_msg, delay=0))
    except Exception as e:
        await log_error(e, context="play_command:send_np", chat_id=message.chat.id)
    
    # Cleanup audio file if it was a Telegram download
    if audio_info.file_path and "downloads" in audio_info.file_path and os.path.exists(audio_info.file_path):
        # We only delete it if it's already playing or we don't need it locally anymore
        # (PyTgCalls needs the file if it's not a stream URL, but once started it's usually fine)
        # However, it's safer to wait until track starts or use a dedicated cleaner.
        # For now, let's at least delete it if it's a cached thumb.
        pass
