"""
generate_session.py
Standalone script to generate a Pyrogram StringSession for the assistant account.
Run: python generate_session.py
"""
# ── asyncio compat fix for Python 3.12+ ─────────────────────────────────────────
import asyncio
import sys

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


# ── Now safe to import Pyrogram ──────────────────────────────────────────────────
from pyrogram import Client


async def main():
    print("═" * 50)
    print("   MusicBot – Session String Generator")
    print("═" * 50)
    api_id = int(input("Enter API_ID: ").strip())
    api_hash = input("Enter API_HASH: ").strip()

    async with Client(
        name="session_gen",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    ) as client:
        session_string = await client.export_session_string()
        print("\n✅ Your STRING_SESSION:\n")
        print(session_string)
        
        # Save to file to prevent terminal truncation/copy-paste issues
        with open("assistant_session.txt", "w") as f:
            f.write(session_string)
            
        print("\n✨ ALSO SAVED TO: assistant_session.txt (Open this file to copy the full string!)")
        print("⚠️  Keep this secret! Add it to your .env file as STRING_SESSION=<content_of_file>")


if __name__ == "__main__":
    _loop.run_until_complete(main())
