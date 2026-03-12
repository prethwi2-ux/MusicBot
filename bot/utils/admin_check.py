"""
bot/utils/admin_check.py
Helpers for checking Telegram group admin status.
"""
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, PeerIdInvalid

from bot import config


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Returns True if user_id is an admin or owner in chat_id."""
    if user_id in config.SUDO_USERS:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except (UserNotParticipant, PeerIdInvalid, Exception):
        return False


async def is_owner(user_id: int) -> bool:
    return user_id == config.OWNER_ID


async def is_sudo(user_id: int) -> bool:
    return user_id in config.SUDO_USERS
