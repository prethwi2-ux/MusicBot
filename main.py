"""
main.py — MusicBot entry point.

IMPORTANT — Python 3.12+ asyncio fix:
  py-tgcalls and Pyrogram read the event loop at import time.
  We must create and set a new event loop BEFORE importing them.
"""
# ── asyncio compat fix (must come FIRST, before any Telegram library imports) ───
import asyncio
import sys

# Create and set an event loop explicitly — required for Python 3.12+
# (py-tgcalls and Pyrogram call asyncio.get_event_loop() at import time)
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

# ── Now safe to import Telegram libraries ────────────────────────────────────────
import signal
import os

from bot import app, assistant, call
from bot import config
from pytgcalls import filters as tgfilters
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from bot.music.player import register_callbacks, auto_leave_task
from bot.logger import LOGGER, log_event, set_client


# Diagnostic: Log ALL callback queries globally
@app.on_callback_query(group=-1)
async def _global_callback_logger(client: Client, query: CallbackQuery):
    LOGGER.info("GLOBAL_BTNCALL | data=%s | user=%s", query.data, query.from_user.id)
    # Don't acknowledge here, let the actual handler do it or it will vanish


async def startup():
    LOGGER.info("Starting MusicBot…")

    # Start assistant (userbot) first
    await assistant.start()
    LOGGER.info("Assistant client connected.")

    # Start bot client
    await app.start()
    me = await app.get_me()
    LOGGER.info("Bot connected as @%s (id=%s)", me.username, me.id)

    # Inject client reference into logger
    set_client(app)

    # Start PyTgCalls
    await call.start()
    LOGGER.info("PyTgCalls started.")

    # Register stream-end callbacks
    register_callbacks(call, app)
    
    # Bind and load settings database from Telegram channel
    from bot.database.settings_db import db
    db.bind(app)
    await db.load(assistant)

    # Start auto-leave background task
    asyncio.create_task(auto_leave_task(call))

    await log_event(
        "Bot Started",
        f"**@{me.username}** (`{me.id}`) is online and ready! 🎵",
    )

    LOGGER.info("✅ MusicBot is fully operational.")


async def shutdown():
    LOGGER.info("Shutting down MusicBot…")
    
    # 1. Stop core services
    try:
        await call.stop()
        LOGGER.info("PyTgCalls stopped.")
    except Exception: pass
    
    try:
        await assistant.stop()
        LOGGER.info("Assistant client stopped.")
    except Exception: pass
    
    try:
        await app.stop()
        LOGGER.info("Bot client stopped.")
    except Exception: pass

    # 2. Cancel ALL remaining background tasks (prevents 'loop is closed' errors)
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        LOGGER.info("Cleaning up %s background tasks...", len(tasks))
        for task in tasks:
            task.cancel()
        
        # Give tasks a moment to handle cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

    LOGGER.info("Goodbye!")


async def main():
    await startup()

    stop_event = asyncio.Event()

    def _handle_signal(*_):
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except (NotImplementedError, RuntimeError):
            # Windows doesn't fully support add_signal_handler
            pass

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass

    await shutdown()


if __name__ == "__main__":
    try:
        _loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        LOGGER.critical("CRITICAL ERROR DURING RUNTIME: %s", e, exc_info=True)
    finally:
        try:
            # Final loop resource cleanup
            _loop.run_until_complete(_loop.shutdown_asyncgens())
            _loop.close()
            LOGGER.info("Event loop closed.")
        except Exception:
            pass
