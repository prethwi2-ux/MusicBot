"""
bot/plugins/user_tracking.py
Ensures all users and groups interacting with the bot are stored in the database.
This is critical for the /broadcast feature.
"""
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from bot.database.settings_db import db

@Client.on_message(group=-1)
async def track_everything(client: Client, message: Message):
    if not message.from_user:
        return
    
    # Track User
    db.add_user(message.from_user.id)
    
    # Track Group
    if message.chat and message.chat.type in ["group", "supergroup"]:
        db.add_group(message.chat.id)
        # Also track if it's a new or changed group
        if message.chat.id not in db.groups:
            LOGGER.info("Tracking: New group discovered: %s", message.chat.id)

@Client.on_chat_member_updated()
async def track_membership(client: Client, update: ChatMemberUpdated):
    me = await client.get_me()
    if update.new_chat_member and update.new_chat_member.user.id == me.id:
        db.add_group(update.chat.id)
    elif update.old_chat_member and update.old_chat_member.user.id == me.id:
        # If bot is removed
        db.remove_group(update.chat.id)
