"""
bot/plugins/callbacks.py
Handles InlineKeyboard button presses for music controls.
All callbacks check if user is admin before acting.
"""
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

from bot import config, call, assistant
from bot.music.player import pause_stream, resume_stream, stop_stream, skip_stream, set_volume
from bot.music.queue import get_queue, active_queues
from bot.music.helpers import build_now_playing_text, build_control_buttons
from bot.utils.admin_check import is_admin
from bot.logger import LOGGER, log_error
from bot.database.settings_db import db

LOGGER.info("PLUGINS: Loading callbacks.py...")


async def _check_admin(client: Client, query: CallbackQuery) -> bool:
    if not query.from_user:
        await query.answer("⚠️ Cannot verify identity.", show_alert=True)
        return False
    ok = await is_admin(client, query.message.chat.id, query.from_user.id)
    if not ok:
        await query.answer("🚫 Only admins can use controls.", show_alert=True)
    return ok


@Client.on_callback_query(filters.regex("^ctrl_"))
async def music_callback(client: Client, query: CallbackQuery):
    action = query.data
    user = query.from_user
    chat_id = query.message.chat.id
    queue = get_queue(chat_id)

    # Log the interaction to terminal as requested
    username = user.username or user.first_name
    LOGGER.info("BTNCALL [%s] | user=%s (%s) | chat=%s", action, user.id, username, chat_id)

    # In "Community Mode", everyone can use buttons. 
    # Logic: Only check admin if specific group policies are needed later.
    # For now, we allow all for better usability as requested.

    try:
        if action == "ctrl_pause":
            LOGGER.info("Action: Pausing stream in %s", chat_id)
            if queue.is_paused:
                await query.answer("Already paused.", show_alert=True)
                return
            ok = await pause_stream(call, chat_id)
            await query.answer("⏸ Paused" if ok else "❌ Failed")

        elif action == "ctrl_resume":
            LOGGER.info("Action: Resuming stream in %s", chat_id)
            if not queue.is_paused:
                await query.answer("Already playing.", show_alert=True)
                return
            ok = await resume_stream(call, chat_id)
            await query.answer("▶️ Resumed" if ok else "❌ Failed")

        elif action == "ctrl_skip":
            LOGGER.info("Action: Skipping track in %s", chat_id)
            next_track = await skip_stream(call, chat_id)
            if next_track:
                text = build_now_playing_text(next_track, queue)
                buttons = build_control_buttons(queue.loop_mode)
                await query.message.edit_text(text, reply_markup=buttons)
                await query.answer("⏭ Skipped")
            else:
                await query.answer("✅ Queue ended.")
                try:
                    await query.message.delete()
                except Exception:
                    pass

        elif action == "ctrl_stop":
            LOGGER.info("Action: Stopping playback in %s", chat_id)
            await stop_stream(call, chat_id)
            await query.answer("⏹ Stopped")
            try:
                await query.message.delete()
            except Exception:
                pass

        elif action == "ctrl_loop":
            LOGGER.info("Action: Cycling loop mode in %s", chat_id)
            new_mode = queue.cycle_loop()
            if queue.current_track:
                text = build_now_playing_text(queue.current_track, queue)
                buttons = build_control_buttons(new_mode)
                await query.message.edit_reply_markup(reply_markup=buttons)
            await query.answer(f"🔁 Loop: {new_mode.value.upper()}")

        elif action == "ctrl_vol_down":
            LOGGER.info("Action: Volume down in %s", chat_id)
            new_vol = max(0, queue.volume - 10)
            await set_volume(call, chat_id, new_vol)
            await query.answer(f"🔉 Volume: {new_vol}%")

        elif action == "ctrl_vol_up":
            LOGGER.info("Action: Volume up in %s", chat_id)
            new_vol = min(200, queue.volume + 10)
            await set_volume(call, chat_id, new_vol)
            await query.answer(f"🔊 Volume: {new_vol}%")

    except Exception as e:
        LOGGER.error("Callback Error [%s]: %s", action, e)
        await log_error(e, context=f"callback:{action}", chat_id=chat_id)
        await query.answer("❌ An error occurred.", show_alert=True)


@Client.on_callback_query(filters.regex("^menu_"))
async def menu_callbacks(client: Client, query: CallbackQuery):
    action = query.data
    
    if action == "menu_start":
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
        await query.message.edit_text(text, reply_markup=buttons)

    elif action == "menu_tutorial":
        text = (
            "📖 **MusicBot Setup Tutorial**\n\n"
            "**Step 1:** Add me to your Telegram Group.\n"
            "**Step 2:** Promote me to **Admin** (need message & voice chat permissions).\n"
            "**Step 3:** Start a Voice Chat in the group.\n"
            "**Step 4:** Send `/play <song name>` to start streaming!\n\n"
            "💡 *Tip: You can skip tracks or pause music using the buttons on the now-playing card.*"
        )
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_start")]])
        await query.message.edit_text(text, reply_markup=buttons)

    elif action == "menu_help":
        # We reuse the text from admin.py help_cmd but slightly adjusted for back button
        text = (
             "🎵 **MusicBot Commands**\n\n"
             "**▶ Playback**: `/play`, `/pause`, `/resume`, `/skip`, `/stop`\n"
             "**📋 Queue**: `/queue`, `/shuffle`, `/loop`\n"
             "**🔊 Audio**: `/volume`, `/np`\n"
             "**ℹ️ Info**: `/ping`, `/stats`, `/help`"
        )
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_start")]])
        await query.message.edit_text(text, reply_markup=buttons)


@Client.on_callback_query(filters.regex("^(owner_|set_join_link)"))
async def owner_callbacks(client: Client, query: CallbackQuery):
    if query.from_user.id != config.OWNER_ID:
        await query.answer("🚫 Owner only.", show_alert=True)
        return

    action = query.data

    if action == "owner_stats":
        active = len(active_queues())
        text = (
            "📊 **Bot Statistics**\n\n"
            f"├ Total Users: `{len(db.users)}`\n"
            f"├ Total Groups: `{len(db.groups)}`\n"
            f"├ Active VCs : `{active}`\n"
            f"└ Globally Banned: `{len(db._data['gbanned'])}`"
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="owner_settings")]]))

    elif action == "owner_settings":
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
        await query.message.edit_text(text, reply_markup=buttons)

    elif action == "owner_gban_list":
        text = db.get_gban_list_text()
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="owner_settings")]])
        await query.message.edit_text(text, reply_markup=buttons)

    elif action == "set_join_link":
        await query.message.reply(
            "📝 **Send the new join link.**\nReply to this message with the URL.",
            reply_markup=ForceReply(selective=True)
        )
        await query.answer()

    elif action == "owner_gban":
        await query.message.reply(
            "🚫 **GBan Member**\nSend the User ID to ban globally.",
            reply_markup=ForceReply(selective=True)
        )
        await query.answer()

    elif action == "owner_manual":
        from bot.plugins.admin import get_owner_manual_text
        text = get_owner_manual_text()
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="owner_settings")]])
        await query.message.edit_text(text, reply_markup=buttons)

    elif action.startswith("owner_broadcast_fast_"):
        msg_id = int(action.split("_")[-1])
        target_msg = await client.get_messages(query.message.chat.id, msg_id)
        if not target_msg or target_msg.empty:
            await query.answer("❌ Message not found or too old.", show_alert=True)
            return
        
        await query.answer("🚀 Starting Broadcast...")
        await query.message.edit_text("🚀 **Broadcasting in progress...**")
        
        from bot.plugins.admin import _execute_broadcast
        await _execute_broadcast(client, query.message, target_msg)

    elif action == "owner_refresh_groups":
        await query.answer("🔄 Refreshing...", show_alert=False)
        await query.message.edit_text("🔄 **Refreshing group list...**\nScanning all dialogs. Please wait.")
        new_count = await db.refresh_groups(assistant)
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="owner_settings")]])
        await query.message.edit_text(f"✅ **Refresh Completed**\nAdded `{new_count}` new groups to the database.", reply_markup=buttons)

    elif action == "owner_broadcast_info":
        await query.message.edit_text(
            "📢 **Easy Broadcast**\n\n"
            "Just **send or forward** any message to this chat.\n"
            "I will automatically show a button to broadcast it!"
        )


@Client.on_message(filters.reply & filters.private)
async def reply_handler(client: Client, message: Message):
    if not message.from_user or message.from_user.id != config.OWNER_ID:
        return
    
    if not message.reply_to_message or not message.reply_to_message.text:
        return

    reply_text = message.reply_to_message.text

    if "Send the new join link" in reply_text:
        link = message.text.strip()
        db.set_join_link(link)
        await message.reply(f"✅ Join link updated to: {link}")

    elif "Send the User ID to ban globally" in reply_text:
        try:
            uid = int(message.text.strip())
            name = "Unknown"
            username = None
            try:
                user = await client.get_users(uid)
                name = user.first_name
                username = user.username
            except Exception:
                pass
            db.gban_user(uid, name, username)
            await message.reply(f"✅ User `{uid}` ({name}) globally banned.")
        except ValueError:
            await message.reply("Invalid User ID.")
