"""
bot/plugins/volume.py
/volume command — admin-only, 0–200 range.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import call
from bot.music.player import set_volume
from bot.music.queue import get_queue
from bot.utils.decorators import admin_only, anti_spam, log_cmd


@Client.on_message(filters.command("volume") & filters.group)
@anti_spam
@admin_only
@log_cmd
async def volume_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    args = message.command[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.reply(
            f"🔊 Current volume: **{queue.volume}%**\n"
            f"Usage: `/volume <0-200>`"
        )
        return
    vol = int(args[0])
    ok = await set_volume(call, message.chat.id, vol)
    if ok:
        emoji = "🔇" if vol == 0 else "🔉" if vol < 50 else "🔊"
        await message.reply(f"{emoji} Volume set to **{min(200, max(0, vol))}%**")
    else:
        await message.reply("❌ Failed to change volume. Is the bot in a voice chat?")
