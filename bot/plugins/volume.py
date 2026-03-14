"""
bot/plugins/volume.py
/volume command — admin-only, 0–200 range.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import call
from bot.music.player import set_volume
from bot.music.queue import get_queue
from bot.music.helpers import delete_later
from bot.utils.decorators import admin_only, anti_spam, log_cmd, fast_cmd
import asyncio


@Client.on_message(filters.command("volume") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def volume_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    args = message.command[1:]
    if not args or not args[0].lstrip("-").isdigit():
        msg = await message.reply(
            f"🔊 Current volume: **{queue.volume}%**\n"
            f"Usage: `/volume <0-200>`"
        )
        asyncio.create_task(delete_later(msg))
        return
    vol = int(args[0])
    ok = await set_volume(call, message.chat.id, vol)
    if ok:
        emoji = "🔇" if vol == 0 else "🔉" if vol < 50 else "🔊"
        msg = await message.reply(f"{emoji} Volume set to **{min(200, max(0, vol))}%**")
        asyncio.create_task(delete_later(msg))
    else:
        msg = await message.reply("❌ Failed to change volume. Is the bot in a voice chat?")
        asyncio.create_task(delete_later(msg))
