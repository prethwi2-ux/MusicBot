import json
import asyncio
import io
import os
from pathlib import Path
from bot.logger import LOGGER
from bot import config

_DB_CAPTION = "#MusicBot_SettingsDB"
_LOCAL_DB = "database.json"

_DEFAULT_DATA = {
    "users": [],        # List of user IDs who started the bot
    "groups": [],       # List of group IDs where bot is added
    "gbanned": [],      # List of user objects {id, name, username}
    "audios": {},       # Map of video_id -> metadata dict
    "join_link": None,   # The "Join Group" link setting
    "tutorial_text": "📖 **MusicBot Setup Tutorial**\n\n**Step 1:** Add me to your group.\n**Step 2:** Admin it.\n**Step 3:** Start VC.\n**Step 4:** /play.",
}

class SettingsDB:
    def __init__(self):
        self._data = _DEFAULT_DATA.copy()
        self._client = None
        self._is_loading = False
        self._save_lock = asyncio.Lock()
        self._pending_save = False

    def bind(self, client):
        """Bind the Telegram client for sync operations."""
        self._client = client

    async def load(self, client=None):
        """Fetch the latest DB document from local file or Telegram channel."""
        # Use provided client (assistant) or bound client (bot)
        target_client = client or self._client
        if not target_client:
            LOGGER.error("DB: No client provided. Cannot load.")
            return
        
        self._is_loading = True
        try:
            # 1. Try to load from local file first
            if os.path.exists(_LOCAL_DB):
                try:
                    with open(_LOCAL_DB, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        self._data.update(content)
                    LOGGER.info("DB: Loaded from local file.")
                except Exception as e:
                    LOGGER.error("DB: Failed to load from local file: %s", e)
            
            # 2. Search for the latest message in channel to sync/back up
            # Use target_client (assistant) here to avoid BOT_METHOD_INVALID
            async for msg in target_client.search_messages(config.DATABASE_CHANNEL_ID, query=_DB_CAPTION, limit=1):
                if msg.document:
                    file_data = await target_client.download_media(msg, in_memory=True)
                    content = json.loads(file_data.getvalue().decode("utf-8"))
                    # Merge data, ensuring we don't overwrite newer local data if it exists
                    # Actually, for "working continuously", we should merge them
                    for key, val in content.items():
                        if isinstance(val, list):
                            existing = self._data.get(key, [])
                            if key == "gbanned":
                                # Unique by ID for dicts
                                existing_ids = {u["id"] for u in existing}
                                for item in val:
                                    if item["id"] not in existing_ids:
                                        existing.append(item)
                                        existing_ids.add(item["id"])
                            else:
                                # Simple set for ints/strings
                                for item in val:
                                    if item not in existing:
                                        existing.append(item)
                            self._data[key] = existing
                        elif isinstance(val, dict):
                            self._data.get(key, {}).update(val)
                        else:
                            self._data[key] = val
                    LOGGER.info("DB: Synced from channel (msg_id=%s)", msg.id)
                    break
            else:
                LOGGER.info("DB: No record found in channel.")
            
            # Save local copy if it didn't exist or was updated
            self._save_local()
        except Exception as e:
            LOGGER.error("DB: Failed to load: %s", e)
        finally:
            self._is_loading = False

    async def save(self):
        """Upload the current state as a JSON document to the Telegram channel."""
        if not self._client:
            return
        
        try:
            # 1. Save locally first (compact format)
            self._save_local()
            
            # 2. Upload to channel
            json_str = json.dumps(self._data, separators=(',', ':'), ensure_ascii=False)
            bio = io.BytesIO(json_str.encode("utf-8"))
            bio.name = "database.json"
            
            await self._client.send_document(
                chat_id=config.DATABASE_CHANNEL_ID,
                document=bio,
                caption=_DB_CAPTION,
                file_name="database.json"
            )
            LOGGER.info("DB: Saved to local and channel.")
        except Exception as e:
            LOGGER.error("DB: Failed to save: %s", e)

    def _save_local(self):
        """Helper to save data to local JSON file."""
        try:
            with open(_LOCAL_DB, "w", encoding="utf-8") as f:
                json.dump(self._data, f, separators=(',', ':'), ensure_ascii=False)
        except Exception as e:
            LOGGER.error("DB: Local save error: %s", e)

    def _trigger_save(self):
        """Schedule a debounced save to prevent spamming the channel."""
        if self._pending_save:
            return
        self._pending_save = True
        asyncio.create_task(self._debounced_save())

    async def _debounced_save(self):
        # Wait 5 seconds before saving to batch multiple updates
        await asyncio.sleep(5)
        self._pending_save = False
        await self.save()

    async def refresh_groups(self, client=None):
        """Scan all dialogs to find groups the bot is currently in."""
        # Use provided client (assistant) or bound client (bot)
        target_client = client or self._client
        if not target_client:
            return 
        
        count = 0
        try:
            # Setting limit=None will scan all available dialogs
            async for dialog in target_client.get_dialogs(limit=None):
                if dialog.chat.type in ["group", "supergroup"]:
                    if dialog.chat.id not in self._data["groups"]:
                        self._data["groups"].append(dialog.chat.id)
                        count += 1
            
            if count > 0:
                await self.save()
            LOGGER.info("DB: Refreshed groups, added %s new ones.", count)
            return count
        except Exception as e:
            LOGGER.error("DB: Failed to refresh groups: %s", e)
            return 0

    def add_user(self, user_id: int):
        if user_id not in self._data["users"]:
            self._data["users"].append(user_id)
            self._trigger_save()

    def add_group(self, chat_id: int):
        if chat_id not in self._data["groups"]:
            self._data["groups"].append(chat_id)
            self._trigger_save()

    def remove_group(self, chat_id: int):
        if chat_id in self._data["groups"]:
            self._data["groups"].remove(chat_id)
            self._trigger_save()

    @property
    def users(self): return self._data["users"]

    @property
    def groups(self): return self._data["groups"]

    # ── Audio Cache Logic ──
    def set_audio(self, video_id: str, metadata: dict):
        self._data["audios"][video_id] = metadata
        self._trigger_save()

    def get_audio(self, video_id: str) -> Optional[dict]:
        return self._data["audios"].get(video_id)

    # ── GBan Logic ──
    def gban_user(self, user_id: int, name: str = "Unknown", username: str = None):
        if not any(u["id"] == user_id for u in self._data["gbanned"]):
            self._data["gbanned"].append({
                "id": user_id,
                "name": name,
                "username": username
            })
            self._trigger_save()
            return True
        return False

    def ungban_user(self, user_id: int):
        target = None
        for u in self._data["gbanned"]:
            if u["id"] == user_id:
                target = u
                break
        if target:
            self._data["gbanned"].remove(target)
            self._trigger_save()
            return True
        return False

    def is_gbanned(self, user_id: int):
        return any(u["id"] == user_id for u in self._data["gbanned"])

    def get_gban_list_text(self):
        gbanned = self._data["gbanned"]
        if not gbanned:
            return "The GBan list is currently empty."
        
        lines = ["🚫 **Global Ban List**\n"]
        for u in gbanned:
            tag = f"@{u['username']}" if u.get('username') else u.get('name', 'Unknown')
            lines.append(f"• `{u['id']}` — {tag}")
        return "\n".join(lines)

    # ── General Settings ──
    def set_join_link(self, link: str):
        self._data["join_link"] = link
        self._trigger_save()

    @property
    def join_link(self): return self._data["join_link"]

# Global Instance
db = SettingsDB()
