"""
bot/music/queue.py
Per-group queue manager with loop modes, thread-safe async operations.
"""
import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from bot.music.downloader import AudioInfo


class LoopMode(Enum):
    OFF = "off"
    SONG = "song"
    QUEUE = "queue"


@dataclass
class QueueEntry:
    audio: AudioInfo
    position: int = 0


class MusicQueue:
    """Async-safe queue for a single group."""

    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self._lock = asyncio.Lock()
        self._tracks: list[QueueEntry] = []
        self._current: int = 0          # index of current playing track
        self.loop_mode: LoopMode = LoopMode.OFF
        self.volume: int = 100
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.now_playing_msg_id: Optional[int] = None  # message to edit
        self.last_active: float = 0.0

    # ── Read-only helpers ────────────────────────────────────────────────────────

    @property
    def current_track(self) -> Optional[AudioInfo]:
        if 0 <= self._current < len(self._tracks):
            return self._tracks[self._current].audio
        return None

    @property
    def size(self) -> int:
        return len(self._tracks)

    @property
    def upcoming(self) -> list[AudioInfo]:
        return [e.audio for e in self._tracks[self._current + 1:]]

    def get_track_list(self) -> list[AudioInfo]:
        return [e.audio for e in self._tracks]

    # ── Mutators ─────────────────────────────────────────────────────────────────

    async def add(self, audio: AudioInfo) -> int:
        """Add to end of queue. Returns new queue size."""
        async with self._lock:
            entry = QueueEntry(audio=audio, position=len(self._tracks))
            self._tracks.append(entry)
            return len(self._tracks)

    async def skip(self) -> Optional[AudioInfo]:
        """Advance to next track based on loop mode. Returns new current track."""
        async with self._lock:
            if not self._tracks:
                return None
            if self.loop_mode == LoopMode.SONG:
                return self._tracks[self._current].audio
            if self.loop_mode == LoopMode.QUEUE:
                self._current = (self._current + 1) % len(self._tracks)
            else:
                self._current += 1
            if self._current >= len(self._tracks):
                return None
            return self._tracks[self._current].audio

    async def previous(self) -> Optional[AudioInfo]:
        """Go to previous track."""
        async with self._lock:
            if self._current > 0:
                self._current -= 1
            return self.current_track

    async def remove(self, position: int) -> bool:
        """Remove a track by 1-based position from the upcoming list."""
        async with self._lock:
            # position is relative to upcoming (1 = first upcoming)
            idx = self._current + position
            if 0 <= idx < len(self._tracks):
                self._tracks.pop(idx)
                # Renumber
                for i, e in enumerate(self._tracks):
                    e.position = i
                return True
            return False

    async def shuffle(self) -> None:
        """Shuffle the upcoming tracks (not the current)."""
        async with self._lock:
            if self._current + 1 < len(self._tracks):
                upcoming = self._tracks[self._current + 1:]
                random.shuffle(upcoming)
                self._tracks = self._tracks[:self._current + 1] + upcoming

    async def clear(self) -> None:
        """Clear all tracks."""
        async with self._lock:
            self._tracks.clear()
            self._current = 0
            self.is_playing = False
            self.is_paused = False

    def set_loop(self, mode: LoopMode) -> None:
        self.loop_mode = mode

    def cycle_loop(self) -> LoopMode:
        """Cycle OFF → SONG → QUEUE → OFF."""
        modes = list(LoopMode)
        idx = modes.index(self.loop_mode)
        self.loop_mode = modes[(idx + 1) % len(modes)]
        return self.loop_mode


# ── Global registry ──────────────────────────────────────────────────────────────

_queues: dict[int, MusicQueue] = {}


def get_queue(chat_id: int) -> MusicQueue:
    """Get or create the MusicQueue for a chat."""
    if chat_id not in _queues:
        _queues[chat_id] = MusicQueue(chat_id)
    return _queues[chat_id]


def delete_queue(chat_id: int) -> None:
    _queues.pop(chat_id, None)


def active_queues() -> dict[int, MusicQueue]:
    return dict(_queues)
