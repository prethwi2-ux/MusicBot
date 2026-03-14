"""
bot/plugins/seek.py
/seek <seconds> — jump to a specific position in current track.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import call
from bot.music.player import seek_stream
from bot.music.queue import get_queue
from bot.music.helpers import format_duration, delete_later
from bot.utils.decorators import admin_only, anti_spam, log_cmd, fast_cmd
import asyncio


@Client.on_message(filters.command("seek") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def seek_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.current_track:
        msg = await message.reply("❌ Nothing is playing.")
        asyncio.create_task(delete_later(msg))
        return
    args = message.command[1:]
    if not args or not args[0].lstrip("-").isdigit():
        msg = await message.reply("Usage: `/seek <seconds>`\nExample: `/seek 90` (seek to 1:30)")
        asyncio.create_task(delete_later(msg))
        return
    secs = int(args[0])
    if secs < 0:
        secs = 0
    dur = queue.current_track.duration
    if dur and secs >= dur:
        msg = await message.reply(f"❌ Seek position exceeds track duration ({format_duration(dur)}).")
        asyncio.create_task(delete_later(msg))
        return
    ok = await seek_stream(call, message.chat.id, secs)
    if ok:
        msg = await message.reply(f"⏩ Seeked to `{format_duration(secs)}`")
        asyncio.create_task(delete_later(msg))
    else:
        msg = await message.reply("❌ Failed to seek.")
        asyncio.create_task(delete_later(msg))
