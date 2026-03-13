"""
bot/plugins/loop.py
/loop command — cycles through OFF, SONG, QUEUE modes.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot.music.queue import get_queue
from bot.utils.decorators import admin_only, anti_spam, log_cmd
from bot.config import COMMAND_PREFIXES

_LOOP_DESCRIPTIONS = {
    "off": "➡️ Loop is now **OFF** — queue plays once.",
    "song": "🔂 Loop is now **SONG** — current song repeats.",
    "queue": "🔁 Loop is now **QUEUE** — queue loops forever.",
}


@Client.on_message(filters.command("loop", prefixes=COMMAND_PREFIXES) & filters.group)
@anti_spam
@admin_only
@log_cmd
async def loop_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    new_mode = queue.cycle_loop()
    desc = _LOOP_DESCRIPTIONS.get(new_mode.value, "Loop mode changed.")
    await message.reply(desc)
