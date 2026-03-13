"""
bot/plugins/controls.py
/pause, /resume, /stop, /skip commands — admin-only.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import call
from bot.music.player import pause_stream, resume_stream, stop_stream, skip_stream
from bot.music.queue import get_queue
from bot.music.helpers import build_now_playing_text, build_control_buttons
from bot.utils.decorators import admin_only, anti_spam, log_cmd
from bot.config import COMMAND_PREFIXES


@Client.on_message(filters.command("pause", prefixes=COMMAND_PREFIXES) & filters.group)
@anti_spam
@admin_only
@log_cmd
async def pause_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_playing or queue.is_paused:
        await message.reply("▶️ Nothing is playing or already paused.")
        return
    ok = await pause_stream(call, message.chat.id)
    await message.reply("⏸ Paused." if ok else "❌ Could not pause.")


@Client.on_message(filters.command("resume", prefixes=COMMAND_PREFIXES) & filters.group)
@anti_spam
@admin_only
@log_cmd
async def resume_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_paused:
        await message.reply("⏸ Not paused.")
        return
    ok = await resume_stream(call, message.chat.id)
    await message.reply("▶️ Resumed." if ok else "❌ Could not resume.")


@Client.on_message(filters.command("stop", prefixes=COMMAND_PREFIXES) & filters.group)
@anti_spam
@admin_only
@log_cmd
async def stop_cmd(client: Client, message: Message):
    await stop_stream(call, message.chat.id)
    await message.reply("⏹ Stopped and cleared the queue.")


@Client.on_message(filters.command(["skip", "next"], prefixes=COMMAND_PREFIXES) & filters.group)
@anti_spam
@admin_only
@log_cmd
async def skip_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    if not queue.is_playing:
        await message.reply("❌ Nothing is playing.")
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
                await message.reply(np_text, reply_markup=buttons)
        else:
            await message.reply(np_text, reply_markup=buttons)
    else:
        await message.reply("✅ Queue ended. Leaving voice chat.")
