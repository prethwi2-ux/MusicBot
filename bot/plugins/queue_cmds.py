"""
bot/plugins/queue_cmds.py
/queue and /shuffle commands.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot.music.queue import get_queue
from bot.music.helpers import build_queue_text
from bot.utils.decorators import anti_spam, admin_only, log_cmd


@Client.on_message(filters.command(["queue", "q"]) & filters.group)
@anti_spam
@log_cmd
async def queue_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    page = 1
    args = message.command[1:]
    if args and args[0].isdigit():
        page = max(1, int(args[0]))
    text = build_queue_text(queue, page=page)
    await message.reply(text)


@Client.on_message(filters.command("shuffle") & filters.group)
@anti_spam
@admin_only
@log_cmd
async def shuffle_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if queue.size < 2:
        await message.reply("❌ Need at least 2 tracks in queue to shuffle.")
        return
    await queue.shuffle()
    await message.reply("🔀 Queue shuffled!")
