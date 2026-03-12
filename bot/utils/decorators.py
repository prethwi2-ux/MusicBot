"""
bot/utils/decorators.py
Decorators: @admin_only, @anti_spam, @log_command.
"""
import time
import functools

from pyrogram import Client
from pyrogram.types import Message

from bot import config
from bot.database.cache import spam_cache
from bot.utils.admin_check import is_admin
from bot.logger import log_command, log_error


def admin_only(func):
    """Reject non-admins in group commands."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        if not message.from_user:
            return
        uid = message.from_user.id
        cid = message.chat.id
        if not await is_admin(client, cid, uid):
            try:
                await message.reply("🚫 This command is restricted to group admins.")
            except Exception:
                pass
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def anti_spam(func):
    """Rate-limit: max SPAM_LIMIT commands per SPAM_WINDOW seconds per user."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        if not message.from_user:
            return await func(client, message, *args, **kwargs)
        uid = str(message.from_user.id)
        now = time.monotonic()
        history = spam_cache.get(uid, [])
        history = [t for t in history if now - t < config.SPAM_WINDOW]
        if len(history) >= config.SPAM_LIMIT:
            try:
                await message.reply(f"⏳ Slow down! Try again in {config.SPAM_WINDOW}s.")
            except Exception:
                pass
            return
        history.append(now)
        spam_cache[uid] = history
        return await func(client, message, *args, **kwargs)
    return wrapper


def log_cmd(func):
    """Auto-log executed commands to the log channel."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        if message.from_user and message.chat:
            cmd = (message.text or "").split()[0] if message.text else func.__name__
            try:
                await log_command(
                    command=cmd,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Private",
                )
            except Exception:
                pass
        try:
            return await func(client, message, *args, **kwargs)
        except Exception as e:
            await log_error(
                e,
                context=func.__name__,
                chat_id=message.chat.id if message.chat else None,
                user_id=message.from_user.id if message.from_user else None,
            )
    return wrapper
