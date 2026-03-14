"""
bot/plugins/info.py
/ping, /stats, /np (now playing) commands.
"""
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from bot import config
from bot.music.queue import get_queue, active_queues
from bot.music.helpers import build_now_playing_text, build_control_buttons, format_duration, delete_later
from bot.database.cache import audio_cache
from bot.utils.decorators import anti_spam, log_cmd, fast_cmd

_START_TIME = time.time()


@Client.on_message(filters.command("ping") & (filters.group | filters.private), group=1)
@fast_cmd
@anti_spam
@log_cmd
async def ping_cmd(client: Client, message: Message):
    start = time.monotonic()
    msg = await message.reply("🏓 Pong!")
    elapsed = (time.monotonic() - start) * 1000
    await msg.edit(f"🏓 **Pong!**\n📶 Latency: `{elapsed:.1f}ms`")
    asyncio.create_task(delete_later(msg))


@Client.on_message(filters.command("stats") & (filters.group | filters.private), group=1)
@fast_cmd
@anti_spam
@log_cmd
async def stats_cmd(client: Client, message: Message):
    from bot import config
    from bot.database.settings_db import db
    
    uptime_secs = int(time.time() - _START_TIME)
    h = uptime_secs // 3600
    m = (uptime_secs % 3600) // 60
    s = uptime_secs % 60

    active = active_queues()
    playing = sum(1 for q in active.values() if q.is_playing)
    cached = len(audio_cache)

    text = (
        "📊 **Bot Statistics**\n\n"
        f"├ 🕐 Uptime        : `{h}h {m}m {s}s`\n"
        f"├ 🎵 Active Streams: `{playing}`\n"
        f"├ 📦 Active Groups : `{len(active)}`\n"
        f"└ 💾 Cached Songs  : `{cached}`"
    )
    
    # Add owner-only metrics if requested by owner in private
    if message.from_user and message.from_user.id == config.OWNER_ID and message.chat.type == "private":
        text += (
            f"\n\n👑 **Owner Metrics**\n"
            f"├ Total Users: `{len(db.users)}`\n"
            f"├ Total Groups: `{len(db.groups)}`\n"
            f"└ Globally Banned: `{len(db._data['gbanned'])}`"
        )

    msg = await message.reply(text)
    asyncio.create_task(delete_later(msg, delay=15))


@Client.on_message(filters.command(["np", "now", "nowplaying"]) & filters.group, group=1)
@fast_cmd
@anti_spam
@log_cmd
async def np_cmd(client: Client, message: Message):
    queue = get_queue(message.chat.id)
    track = queue.current_track
    if not track:
        msg = await message.reply("❌ Nothing is currently playing.")
        asyncio.create_task(delete_later(msg))
        return
    text = build_now_playing_text(track, queue)
    buttons = build_control_buttons(queue.loop_mode)
    np_msg = await message.reply(text, reply_markup=buttons)

    # Delete the old now playing message to keep chat clean
    if queue.now_playing_msg_id:
        try:
            old_msg = await client.get_messages(message.chat.id, queue.now_playing_msg_id)
            if old_msg:
                await old_msg.delete()
        except Exception:
            pass
    queue.now_playing_msg_id = np_msg.id
