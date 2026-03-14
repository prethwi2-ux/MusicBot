"""
bot/music/helpers.py
UI string builders: progress bar, now-playing card, control buttons.
"""
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import MessageIdInvalid, MessageNotModified
from bot.music.queue import MusicQueue, LoopMode
from bot.music.downloader import AudioInfo
from bot.logger import LOGGER

# ── Helpers for Auto-Delete & NP Updates ─────────────────────────────────────────

async def delete_later(message: Message, delay: int = 5):
    """Wait for `delay` seconds, then delete the message."""
    if not message:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

async def update_now_playing(app, chat_id: int, message_id: int, audio: AudioInfo, queue: MusicQueue):
    """Robustly update the Now Playing message (text or photo)."""
    if not message_id:
        return

    text = build_now_playing_text(audio, queue)
    buttons = build_control_buttons(queue.loop_mode)

    try:
        # Try to edit it as a text message first (if it had no thumbnail)
        await app.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=buttons
        )
    except MessageNotModified:
        pass
    except Exception:
        # If it's a photo, edit_message_text will fail. Fallback to editing the caption.
        try:
            await app.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=buttons
            )
        except MessageNotModified:
            pass
        except Exception as e:
            LOGGER.error("Failed to update NP message in %s: %s", chat_id, e)


# ── Time formatting ──────────────────────────────────────────────────────────────

def format_duration(seconds: int) -> str:
    """Convert seconds to mm:ss or h:mm:ss."""
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ── Progress bar ─────────────────────────────────────────────────────────────────

def progress_bar(current: int, total: int, width: int = 12) -> str:
    """
    Build a visual progress bar.
    Example: ██████░░░░░░ 2:14 / 4:30
    """
    if total <= 0:
        return "▒" * width
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {format_duration(current)} / {format_duration(total)}"


# ── Now-playing text ─────────────────────────────────────────────────────────────

_LOOP_EMOJI = {
    LoopMode.OFF: "➡️",
    LoopMode.SONG: "🔂",
    LoopMode.QUEUE: "🔁",
}


def build_now_playing_text(audio: AudioInfo, queue: MusicQueue) -> str:
    loop_icon = _LOOP_EMOJI.get(queue.loop_mode, "➡️")
    upcoming = len(queue.upcoming)
    req_text = ""
    if audio.requested_name:
        req_text = f"├ Requested by : {audio.requested_name}\n"
    text = (
        "🎵 **Now Playing**\n\n"
        f"**{audio.title}**\n\n"
        f"╔ Duration   : `{format_duration(audio.duration)}`\n"
        f"{req_text}"
        f"├ Loop       : {loop_icon} `{queue.loop_mode.value.upper()}`\n"
        f"├ Volume     : 🔊 `{queue.volume}%`\n"
        f"└ In Queue   : `{upcoming}` track(s)\n"
    )
    if audio.source_url:
        text += f"\n🔗 [Source]({audio.source_url})"
    return text


def build_queue_text(queue: MusicQueue, page: int = 1, per_page: int = 10) -> str:
    tracks = queue.get_track_list()
    if not tracks:
        return "📭 The queue is empty."

    current = queue._current
    total = len(tracks)
    start = (page - 1) * per_page
    end = min(start + per_page, total)
    lines = [f"📋 **Queue** — {total} track(s)\n"]

    for i in range(start, end):
        t = tracks[i]
        marker = "▶️" if i == current else f"`{i + 1}.`"
        lines.append(f"{marker} **{t.title}** — `{format_duration(t.duration)}`")

    total_pages = (total + per_page - 1) // per_page
    lines.append(f"\n📄 Page {page}/{total_pages}")
    return "\n".join(lines)


# ── Inline control buttons ───────────────────────────────────────────────────────

def build_control_buttons(loop_mode: LoopMode = LoopMode.OFF) -> InlineKeyboardMarkup:
    loop_label = {
        LoopMode.OFF: "🔁 Loop: Off",
        LoopMode.SONG: "🔂 Loop: Song",
        LoopMode.QUEUE: "🔁 Loop: Queue",
    }.get(loop_mode, "🔁 Loop: Off")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause", callback_data="ctrl_pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="ctrl_resume"),
            InlineKeyboardButton("⏭ Skip", callback_data="ctrl_skip"),
        ],
        [
            InlineKeyboardButton("⏹ Stop", callback_data="ctrl_stop"),
            InlineKeyboardButton(loop_label, callback_data="ctrl_loop"),
        ],
        [
            InlineKeyboardButton("🔉 Vol -10", callback_data="ctrl_vol_down"),
            InlineKeyboardButton("🔊 Vol +10", callback_data="ctrl_vol_up"),
        ],
    ])
