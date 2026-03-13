"""
bot/database/cache.py
In-memory LRU + TTL cache for audio metadata to reduce Telegram API calls.
"""
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLLRUCache:
    """
    Combined LRU + TTL cache.
    - Evicts least-recently-used when capacity is exceeded.
    - Evicts entries older than `ttl` seconds.
    """

    def __init__(self, maxsize: int = 500, ttl: int = 86400):
        self.maxsize = maxsize
        self.ttl = ttl
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        value, ts = self._store[key]
        if time.monotonic() - ts > self.ttl:
            del self._store[key]
            return None
        # Move to end (most recently used)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic())
        if len(self._store) > self.maxsize:
            self._store.popitem(last=False)  # evict LRU

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None


# ── Persistent Proxy ─────────────────────────────────────────────────────────────

class AudioPersistenceProxy:
    def get(self, key: str):
        from bot.database.settings_db import db
        return db.get_audio(key)
    
    def set(self, key: str, value: Any):
        from bot.database.settings_db import db
        db.set_audio(key, value)

audio_cache = AudioPersistenceProxy()

# Key: str(chat_id)  →  Value: dict with any per-group persistent settings
group_settings_cache = TTLLRUCache(maxsize=2000, ttl=3600 * 24)

# Anti-spam: Key: str(user_id) → Value: list of timestamps
spam_cache: dict[str, list[float]] = {}

# Command Deduplication: Key: str(msg_id) → Value: True
# To prevent bot and assistant from processing the same command twice
command_cache = TTLLRUCache(maxsize=1000, ttl=60)
