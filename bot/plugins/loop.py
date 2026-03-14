"""
bot/plugins/loop.py
/loop command — cycles through OFF, SONG, QUEUE modes.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot.music.queue import get_queue
from bot.music.helpers import build_control_buttons, delete_later, update_now_playing
from bot.utils.decorators import admin_only, anti_spam, log_cmd, fast_cmd
import asyncio

_LOOP_DESCRIPTIONS = {
    "off": "➡️ Loop is now **OFF** — queue plays once.",
    "song": "🔂 Loop is now **SONG** — current song repeats.",
    "queue": "🔁 Loop is now **QUEUE** — queue loops forever.",
}


@Client.on_message(filters.command("loop") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def loop_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_playing:
        msg = await message.reply("❌ Nothing is playing to loop.")
        asyncio.create_task(delete_later(msg))
        return
        
    new_mode = queue.cycle_loop()
    desc = _LOOP_DESCRIPTIONS.get(new_mode.value, "Loop mode changed.")
    msg = await message.reply(desc)
    asyncio.create_task(delete_later(msg))
    
    # Update NP message to reflect new loop mode
    if queue.now_playing_msg_id and queue.current_track:
        await update_now_playing(client, message.chat.id, queue.now_playing_msg_id, queue.current_track, queue)
