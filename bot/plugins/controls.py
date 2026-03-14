"""
bot/plugins/controls.py
/pause, /resume, /stop, /skip commands — admin-only.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import call
import asyncio
from bot.music.player import pause_stream, resume_stream, stop_stream, skip_stream
from bot.music.queue import get_queue
from bot.music.helpers import build_now_playing_text, build_control_buttons, delete_later
from bot.utils.decorators import admin_only, anti_spam, log_cmd, fast_cmd


@Client.on_message(filters.command("pause") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def pause_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_playing or queue.is_paused:
        msg = await message.reply("▶️ Nothing is playing or already paused.")
        asyncio.create_task(delete_later(msg))
        return
    ok = await pause_stream(call, message.chat.id)
    msg = await message.reply("⏸ Paused." if ok else "❌ Could not pause.")
    asyncio.create_task(delete_later(msg))


@Client.on_message(filters.command("resume") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def resume_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_paused:
        msg = await message.reply("⏸ Not paused.")
        asyncio.create_task(delete_later(msg))
        return
    ok = await resume_stream(call, message.chat.id)
    msg = await message.reply("▶️ Resumed." if ok else "❌ Could not resume.")
    asyncio.create_task(delete_later(msg))


@Client.on_message(filters.command("stop") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def stop_cmd(client: Client, message: Message):
    await stop_stream(call, message.chat.id)
    msg = await message.reply("⏹ Stopped and cleared the queue.")
    asyncio.create_task(delete_later(msg))


@Client.on_message(filters.command("skip") & filters.group, group=1)
@fast_cmd
@anti_spam
@admin_only
@log_cmd
async def skip_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_playing:
        msg = await message.reply("❌ Nothing is playing.")
        asyncio.create_task(delete_later(msg))
        return
    next_track = await skip_stream(call, message.chat.id)
    if next_track:
        np_text = build_now_playing_text(next_track, queue)
        buttons = build_control_buttons(queue.loop_mode)
        # Edit existing now-playing message if possible
        if queue.now_playing_msg_id:
            try:
                await client.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=queue.now_playing_msg_id,
                    text=np_text,
                    reply_markup=buttons,
                )
            except Exception:
                np_msg = await message.reply(np_text, reply_markup=buttons)
                queue.now_playing_msg_id = np_msg.id
        else:
            np_msg = await message.reply(np_text, reply_markup=buttons)
            queue.now_playing_msg_id = np_msg.id
    else:
        msg = await message.reply("✅ Queue ended. Leaving voice chat.")
        asyncio.create_task(delete_later(msg))
