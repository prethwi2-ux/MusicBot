"""
bot/plugins/login.py
Implementation of /login command to trigger yt-dlp OAuth2 authentication.
"""
import asyncio
import re
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from bot import config
from bot.utils.decorators import log_cmd
from bot.logger import LOGGER

@Client.on_message(filters.command(["login", "auth"]) & filters.user(config.OWNER_ID) & filters.private)
@log_cmd
async def login_command(client: Client, message: Message):
    """
    Triggers yt-dlp's OAuth2 login flow.
    Sends the authentication URL and code to the Owner.
    """
    msg = await message.reply("⏳ Initializing YouTube OAuth2 login flow...")
    
    # Run yt-dlp in a subprocess with oauth2 username
    # We use a small video or just a dummy extraction to trigger the login
    cmd = [
        "yt-dlp",
        "--username", "oauth2",
        "--force-overwrites",
        "https://www.youtube.com/watch?v=aqz-KE-bpKQ", # Just a short classic song
        "--simulate"
    ]
    
    try:
        # We need to capture the stdout to get the URL and code
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # We will read line by line searching for the "To give [yt-dlp] access..." message
        auth_url = None
        user_code = None
        
        # Give it some time
        lines_checked = 0
        while lines_checked < 50:
            line_bytes = await process.stderr.readline()
            if not line_bytes:
                break
            
            line = line_bytes.decode().strip()
            LOGGER.info(f"YTDL-AUTH: {line}")
            
            # Pattern: To give [yt-dlp] access to your Google Account, on your computer or mobile device go to: https://www.google.com/device
            # And enters the code: XXX-XXX-XXX
            if "go to:" in line:
                auth_url = line.split("go to:")[-1].strip()
            if "enters the code:" in line:
                user_code = line.split("enters the code:")[-1].strip()
            
            if auth_url and user_code:
                break
            lines_checked += 1

        if auth_url and user_code:
            await msg.edit(
                "🔑 **YouTube Authentication Required**\n\n"
                f"1. Go to: {auth_url}\n"
                f"2. Enter the code: `{user_code}`\n\n"
                "Once you authorize, the bot will be logged in!"
            )
            # We let the process run in background for a bit so it can finish the handshake if the user is fast,
            # but usually it's better to tell the user to wait a bit.
        else:
            await msg.edit("❌ Failed to retrieve authentication URL. Check logs.")
            
    except Exception as e:
        LOGGER.error(f"Login command error: {e}")
        await msg.edit(f"❌ Error during login initialization: {e}")
