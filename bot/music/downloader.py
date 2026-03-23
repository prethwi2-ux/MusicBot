"""
bot/music/downloader.py
Downloads audio from YouTube (via yt-dlp) or uses a Telegram file_id.
Checks the DB channel cache first to avoid redundant downloads.
"""
import asyncio
import os
import re
import json
from dataclasses import dataclass, field
from typing import Optional

import yt_dlp
import aiohttp

from bot import config
from bot.database.cache import audio_cache
from bot.logger import LOGGER, log_error

# ── Cookie Handlers ──────────────────────────────────────────────────────────────
_TEMP_COOKIES = os.path.join(config.DOWNLOAD_DIR, "session_cookies.txt")

def _initialize_cookies():
    """Write COOKIES_CONTENT to a temp file if needed."""
    if not config.COOKIES_FILE and config.COOKIES_CONTENT:
        try:
            with open(_TEMP_COOKIES, "w", encoding="utf-8") as f:
                f.write(config.COOKIES_CONTENT)
            config.COOKIES_FILE = _TEMP_COOKIES
            LOGGER.info("Created cookies file from COOKIES_CONTENT environment variable.")
        except Exception as e:
            LOGGER.error("Failed to create cookies from content: %s", e)

_initialize_cookies()

# ── Audio info dataclass ─────────────────────────────────────────────────────────

@dataclass
class AudioInfo:
    title: str
    duration: int               # seconds
    video_id: str               # YouTube ID or empty
    source_url: str             # original URL
    stream_url: Optional[str] = None    # Direct URL for streaming (PyTgCalls)
    file_path: Optional[str] = None     # local path (fallback/Telegram files)
    thumb_path: Optional[str] = None   # local thumbnail path
    file_id: Optional[str] = None       # Telegram file_id (if from DB)
    message_id: Optional[int] = None    # DB channel message_id
    requested_by: Optional[int] = None  # user_id
    requested_name: Optional[str] = None
    is_video: bool = False


# ── yt-dlp options ───────────────────────────────────────────────────────────────

def _ydl_opts() -> dict:
    """Options for extracting streaming URL only."""
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "force_generic_extractor": False,
        "nocheckcertificate": True,
    }
    if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
        opts["cookiefile"] = config.COOKIES_FILE
    return opts


def _search_opts() -> dict:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
        opts["cookiefile"] = config.COOKIES_FILE
    return opts


_YT_REGEX = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_\-]{11})"
)


def _extract_video_id(url: str) -> Optional[str]:
    m = _YT_REGEX.search(url)
    return m.group(1) if m else None


# ── Main download function (Refactored to Streamer) ──────────────────────────────

async def download_audio(query: str, requested_by: int = 0, requested_name: str = "", is_video: bool = False) -> Optional[AudioInfo]:
    """
    Given a YouTube URL or search query, return an AudioInfo with direct stream URLs.
    1. Resolve to a YouTube URL.
    2. Extract metadata and the direct format URL.
    """
    loop = asyncio.get_event_loop()

    is_url = query.startswith("http://") or query.startswith("https://")

    # Step 1 – resolve to a YouTube URL if needed
    if not is_url:
        url = await search_youtube(query)
        if not url:
            return None
    else:
        url = query

    video_id = _extract_video_id(url)

    # Step 2 – Check DB Cache if results exist (we still want metadata from DB if possible)
    if video_id:
        cached = audio_cache.get(video_id)
        if cached and cached.get("stream_url"): # Optional: cache the stream URL (expires fast though)
             pass 

    # Step 3 – Fetch Metadata & Stream URL
    try:
        info = await loop.run_in_executor(None, _fetch_info, url)
        if not info:
            return None

        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)
        
        # Robust stream URL extraction
        stream_url = None
        # Use the most reliable streamable URL found by yt-dlp
        # Combined formats (audio+video) are much more stable for direct streaming than adaptive DASH fragments.
        # PyTgCalls will automatically ignore the video track if we don't provide video_parameters in start_stream.
        stream_url = info.get("url")

        if not stream_url:
            # Fallback to searching formats if 'url' is missing
            formats = info.get("formats", [])
            # Prefer combined formats with height <= 480
            combined = [f for f in formats if f.get("vcodec") != "none" and f.get("acodec") != "none"]
            if combined:
                best_combined = sorted(combined, key=lambda x: x.get("height", 0) or 0, reverse=True)[0]
                stream_url = best_combined.get("url")
            elif formats:
                stream_url = formats[-1].get("url")
        
        # Guard: if it's video but we didn't find a stream yet (unlikely)
        if is_video and not stream_url:
             # Just use the default info.get("url") but it might be 720p+ (PyTgCalls will downscale)
             stream_url = info.get("url")

        if not stream_url:
            LOGGER.error("No streamable URL found for %s", title)
            return None

        effective_video_id = video_id or info.get("id", "")

        # Duration guard
        if duration and duration > config.MAX_DURATION:
            raise ValueError(f"Duration {duration}s exceeds MAX_DURATION {config.MAX_DURATION}s")

        # Handle thumbnails (still useful for UI)
        thumb_url = info.get("thumbnail")
        thumb_path = None
        if thumb_url:
            # We can download thumb locally for send_photo
            safe_id = re.sub(r"[^\w\-]", "_", effective_video_id or title[:30])
            thumb_path = os.path.join(config.DOWNLOAD_DIR, f"{safe_id}.jpg")
            if not os.path.exists(thumb_path):
                # Simple async download for thumb
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(thumb_url) as resp:
                            if resp.status == 200:
                                with open(thumb_path, "wb") as f:
                                    f.write(await resp.read())
                except Exception:
                    thumb_path = None

        result = AudioInfo(
            title=title,
            duration=int(duration or 0),
            video_id=effective_video_id,
            source_url=url,
            stream_url=stream_url,
            thumb_path=thumb_path,
            requested_by=requested_by,
            requested_name=requested_name,
            is_video=is_video,
        )

        return result

    except Exception as e:
        await log_error(e, context="get_audio_stream")
        return None


# ── YouTube Data API v3 logic ───────────────────────────────────────────────────

async def _search_youtube_api(query: str) -> Optional[str]:
    """Search YouTube using official API (v3)."""
    if not config.YOUTUBE_API_KEY:
        return None
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": 1,
        "type": "video",
        "key": config.YOUTUBE_API_KEY
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if "items" in data and data["items"]:
                    video_id = data["items"][0]["id"]["videoId"]
                    return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        LOGGER.error("YouTube API search failed: %s", e)
    return None


async def search_youtube_results_api(query: str, limit: int = 5) -> list[dict]:
    """Search YouTube using official API (v3) for multiple results."""
    if not config.YOUTUBE_API_KEY:
        return []

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": limit,
        "type": "video",
        "key": config.YOUTUBE_API_KEY
    }
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                for item in data.get("items", []):
                    video_id = item["id"]["videoId"]
                    snippet = item["snippet"]
                    results.append({
                        "title": snippet.get("title", "Unknown"),
                        "duration": 0, # API search doesn't return duration in one call
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "video_id": video_id,
                        "thumb": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    })
    except Exception as e:
        LOGGER.error("YouTube API multi-search failed: %s", e)
    return results


async def search_youtube(query: str) -> Optional[str]:
    """Search YouTube - try API first, then fallback to yt-dlp."""
    # 1. Try API
    if config.YOUTUBE_API_KEY:
        url = await _search_youtube_api(query)
        if url:
            return url
    
    # 2. Fallback to yt-dlp search
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_youtube_ydl, query)


def _search_youtube_ydl(query: str) -> Optional[str]:
    """Original blocking yt-dlp search."""
    search_query = f"ytsearch1:{query}"
    try:
        with yt_dlp.YoutubeDL(_search_opts()) as ydl:
            result = ydl.extract_info(search_query, download=False)
            if result and result.get("entries"):
                entry = result["entries"][0]
                return entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
    except Exception as e:
        LOGGER.error("yt-dlp search failed: %s", e)
    return None


async def search_results(query: str, limit: int = 5) -> list[dict]:
    """Get multiple search results - try API first, then fallback to yt-dlp."""
    # 1. Try API
    if config.YOUTUBE_API_KEY:
        results = await search_youtube_results_api(query, limit)
        if results:
            return results
            
    # 2. Fallback to yt-dlp
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_youtube_results_ydl, query, limit)


def search_youtube_results_ydl(query: str, limit: int = 5) -> list[dict]:
    """Original blocking yt-dlp multi-search."""
    search_query = f"ytsearch{limit}:{query}"
    results = []
    try:
        opts = {**_search_opts(), "extract_flat": True}
        if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
            opts["cookiefile"] = config.COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(search_query, download=False)
            for entry in (data.get("entries") or [])[:limit]:
                vid_id = entry.get("id", "")
                results.append({
                    "title": entry.get("title", "Unknown"),
                    "duration": entry.get("duration", 0),
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "video_id": vid_id,
                    "thumb": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                })
    except Exception as e:
        LOGGER.error("yt-dlp multi-search failed: %s", e)
    return results


def _fetch_info(url: str) -> Optional[dict]:
    """Fetch video metadata without downloading - blocking."""
    opts = {
        "quiet": True, 
        "no_warnings": True, 
        "skip_download": True, 
        "noplaylist": True,
    }
    if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
        opts["cookiefile"] = config.COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        LOGGER.error("fetch_info failed for %s: %s", url, e)
    return None


def _download(url: str, out_template: str) -> None:
    """Blocking download - run in executor."""
    with yt_dlp.YoutubeDL(_ydl_opts(out_template)) as ydl:
        ydl.download([url])
