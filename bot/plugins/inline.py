"""
bot/plugins/inline.py
Inline mode: @botusername <query> → returns YouTube search results.
Users tap a result to trigger /play in the group.
"""
import asyncio
import uuid

from pyrogram import Client
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from bot.music.downloader import search_results
from bot.music.helpers import format_duration
from bot.logger import log_error


@Client.on_inline_query()
async def inline_search(client: Client, query: InlineQuery):
    q = query.query.strip()
    if not q:
        await query.answer(
            results=[],
            cache_time=1,
            switch_pm_text="Type a song name to search",
            switch_pm_parameter="start",
        )
        return

    try:
        results_data = await search_results(q, 5)
        results = []
        for r in results_data:
            dur_raw = r.get("duration", 0)
            dur = format_duration(dur_raw) if dur_raw else "Unknown"
            title = r["title"]
            url = r["url"]
            vid_id = r["video_id"]
            thumb = r.get("thumb", "")

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=f"⏱ {dur} • YouTube",
                    thumb_url=thumb,
                    input_message_content=InputTextMessageContent(
                        message_text=f"/play {url}",
                    ),
                )
            )
        await query.answer(results=results, cache_time=30)
    except Exception as e:
        await log_error(e, context="inline_search")
        await query.answer(results=[], cache_time=1)
