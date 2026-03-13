"""
bot/plugins/admin.py
Admin-only bot management commands.
"""
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import config
from bot.music.queue import get_queue, active_queues, delete_queue
from bot.music.player import stop_stream
from bot import call, app, assistant
from bot.utils.decorators import log_cmd, fast_cmd
from bot.utils.admin_check import is_sudo
from bot.database.settings_db import db
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import time

# Legacy storage — will be removed in next cleanup
PENDING_BROADCASTS = {}


def owner_only(func):
    import functools
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        if not message.from_user or message.from_user.id != config.OWNER_ID:
            await message.reply("🚫 Owner only.")
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    db.add_user(message.from_user.id)
    me = await client.get_me()
    
    text = (
        "🎵 **MusicBot** is online!\n\n"
        "I can play music in your group's voice chat with high quality. "
        "Use the buttons below to explore how to use me!"
    )
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Tutorial", callback_data="menu_tutorial"),
            InlineKeyboardButton("❓ Help", callback_data="menu_help"),
        ],
        [
            InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{me.username}?startgroup=true"),
        ],
        [
            InlineKeyboardButton("💬 Join Group", url=db.join_link or "https://t.me/your_support_group"),
        ]
    ])
    
    await message.reply(text, reply_markup=buttons)


@Client.on_message(filters.new_chat_members)
async def track_group_join(client: Client, message: Message):
    me = await client.get_me()
    for user in message.new_chat_members:
        if user.id == me.id:
            db.add_group(message.chat.id)
            await message.reply("🎵 **MusicBot Joined!**\nUse `/play` to start some music.")


@Client.on_message(filters.left_chat_member)
async def track_group_leave(client: Client, message: Message):
    me = await client.get_me()
    if message.left_chat_member.id == me.id:
        db.remove_group(message.chat.id)


@Client.on_message(filters.command("help") & (filters.group | filters.private), group=1)
@fast_cmd
async def help_cmd(client: Client, message: Message):
    text = (
        "🎵 **MusicBot Commands**\n\n"
        "**▶ Playback**\n"
        "`/play <query/url>` — Play a song\n"
        "`/pause` — Pause playback\n"
        "`/resume` — Resume playback\n"
        "`/skip` — Skip current song\n"
        "`/stop` — Stop and clear queue\n"
        "`/seek <sec>` — Seek to position\n\n"
        "**📋 Queue**\n"
        "`/queue` — Show queue\n"
        "`/shuffle` — Shuffle queue\n"
        "`/loop` — Cycle loop mode\n\n"
        "**🔊 Audio**\n"
        "`/volume <0-200>` — Set volume\n"
        "`/np` — Now playing\n\n"
        "**ℹ️ Info**\n"
        "`/ping` — Bot latency\n"
        "`/stats` — Bot statistics\n"
        "`/help` — This menu\n\n"
        "🔍 **Inline**: `@YourBot <song name>`"
    )
    if message.chat.type == "private":
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="menu_start")]])
        await message.reply(text, reply_markup=buttons)
    else:
        await message.reply(text)


@Client.on_message(filters.private & ~filters.command(["start", "help", "settings", "stats", "gban", "ungban", "gbanlist", "refresh", "ownerhelp", "activevc", "broadcast", "send"]))
async def owner_message_handler(client: Client, message: Message):
    """Detects messages from the owner and offers to broadcast them."""
    if not message.from_user or message.from_user.id != config.OWNER_ID:
        return
    
    # Exclude replies to ForceReply messages (like set join link)
    if message.reply_to_message and message.reply_to_message.reply_markup and \
       isinstance(message.reply_to_message.reply_markup, ForceReply):
        return

    # Add a simple broadcast button
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast to All", callback_data=f"owner_broadcast_fast_{message.id}")]
    ])
    await message.reply("Do you want to broadcast this message to all users and groups?", reply_markup=buttons)


@Client.on_message(filters.command("broadcast") & filters.private)
@owner_only
@log_cmd
async def broadcast_cmd(client: Client, message: Message):
    if message.reply_to_message:
        return await _execute_broadcast(client, message, message.reply_to_message)
    
    await message.reply(
        "📢 **Easy Broadcast**\n\n"
        "Just **forward or send** any message to this chat.\n"
        "I will then show a button to broadcast it instantly!"
    )


async def _execute_broadcast(client: Client, message: Message, target_msg: Message):
    users = db.users
    groups = db.groups
    
    if not users and not groups:
        await message.reply("❌ Database is empty. No targets found.")
        return

    status = await message.reply(f"🚀 **Broadcasting...**\nTargeting `{len(users)}` users and `{len(groups)}` groups.")
    
    sent_u = 0
    fail_u = 0
    sent_g = 0
    fail_g = 0
    
    for uid in users:
        try:
            await target_msg.copy(uid)
            sent_u += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_u += 1
            LOGGER.warning("Broadcast: Failed to user %s: %s", uid, e)
        
    for gid in groups:
        try:
            await target_msg.copy(gid)
            sent_g += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_g += 1
            LOGGER.warning("Broadcast: Failed to group %s: %s", gid, e)
        
    text = (
        f"✅ **Broadcast Completed**\n\n"
        f"👤 **Users**: `{sent_u}` sent, `{fail_u}` failed\n"
        f"👥 **Groups**: `{sent_g}` sent, `{fail_g}` failed"
    )
    await status.edit(text)


@Client.on_message(filters.command("settings") & filters.private)
@owner_only
async def settings_cmd(client: Client, message: Message):
    text = (
        "⚙️ **Owner Control Panel**\n\n"
        "Welcome, Owner! Use this menu to manage the bot's global state, "
        "track statistics, and perform administrative actions."
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="owner_stats"),
            InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast_info"),
        ],
        [
            InlineKeyboardButton("🚫 GBan Member", callback_data="owner_gban"),
            InlineKeyboardButton("📋 GBan List", callback_data="owner_gban_list"),
        ],
        [
            InlineKeyboardButton("🔗 Set Join Link", callback_data="set_join_link"),
            InlineKeyboardButton("📖 Owner Manual", callback_data="owner_manual"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh Groups", callback_data="owner_refresh_groups"),
        ]
    ])
    await message.reply(text, reply_markup=buttons)


@Client.on_message(filters.command("ownerhelp") & filters.private)
@owner_only
async def owner_help_cmd(client: Client, message: Message):
    # This is a manual command version of the manual
    text = get_owner_manual_text()
    await message.reply(text)

def get_owner_manual_text():
    return (
        "👑 **MusicBot Owner Manual**\n\n"
        "**📢 Easy Broadcast**\n"
        "1. Just **forward or send** a message to this bot.\n"
        "2. Click the **📢 Broadcast to All** button that appears.\n"
        "3. That's it! No commands needed.\n\n"
        "**🚫 Global Ban (GBan)**\n"
        "• `/gban <user_id>`: Blocks a user permanently.\n"
        "• Reply to a user with `/gban` to ban them instantly.\n"
        "• `/ungban <user_id>`: Unblocks a user.\n"
        "• `/gbanlist`: Lists all banned users.\n\n"
        "**📊 Statistics**\n"
        "• `/stats`: Detailed DB metrics (Owner DM only).\n"
        "• `/activevc`: Shows groups currently playing music.\n\n"
        "**⚙️ Settings & Tools**\n"
        "• `/settings`: Opens the control panel.\n"
        "• `/refresh`: Scans your account to find and sync all groups (helps if broadcast misses some).\n"
        "• `/activevc`: Shows groups currently playing music."
    )


@Client.on_message(filters.command("gban") & filters.private)
@owner_only
async def gban_cmd(client: Client, message: Message):
    query = " ".join(message.command[1:]).strip()
    if not query:
        await message.reply("Usage: `/gban <user_id>` (or reply to a user)")
        return
    
    # Support reply-to-gban
    uid = None
    name = "Unknown"
    username = None
    
    if message.reply_to_message:
        uid = message.reply_to_message.from_user.id
        name = message.reply_to_message.from_user.first_name
        username = message.reply_to_message.from_user.username
    else:
        try:
            uid = int(query)
            # Try to fetch user info if bot knows them
            try:
                user = await client.get_users(uid)
                name = user.first_name
                username = user.username
            except Exception: pass
        except ValueError:
            await message.reply("Invalid User ID.")
            return

    if db.gban_user(uid, name, username):
        await message.reply(f"✅ User `{uid}` ({name}) globally banned.")
    else:
        await message.reply(f"ℹ️ User `{uid}` is already globally banned.")


@Client.on_message(filters.command("ungban") & filters.private)
@owner_only
async def ungban_cmd(client: Client, message: Message):
    query = " ".join(message.command[1:]).strip()
    if not query:
        await message.reply("Usage: `/ungban <user_id>`")
        return
    try:
        uid = int(query)
        if db.ungban_user(uid):
            await message.reply(f"✅ User `{uid}` globally unbanned.")
        else:
            await message.reply(f"❌ User `{uid}` not found in GBan list.")
    except ValueError:
        await message.reply("Invalid User ID.")


@Client.on_message(filters.command("gbanlist") & filters.private)
@owner_only
async def gbanlist_cmd(client: Client, message: Message):
    await message.reply(db.get_gban_list_text())


@Client.on_message(filters.command("refresh") & filters.private)
@owner_only
async def refresh_cmd(client: Client, message: Message):
    status = await message.reply("🔄 **Refreshing group list...**\nScanning all dialogs for groups.")
    # Use assistant for get_dialogs as bot can't use it
    new_count = await db.refresh_groups(assistant)
    await status.edit(f"✅ **Refresh Completed**\nAdded `{new_count}` new groups to the database.")


@Client.on_message(filters.command("activevc") & filters.private)
@owner_only
async def activevc_cmd(client: Client, message: Message):
    import time
    queues = active_queues()
    if not queues:
        await message.reply("No active voice chats.")
        return
    lines = [f"🎵 **Active Voice Chats** ({len(queues)})\n"]
    for cid, q in queues.items():
        track = q.current_track
        lines.append(f"• `{cid}` — **{track.title if track else 'idle'}**")
    await message.reply("\n".join(lines))
