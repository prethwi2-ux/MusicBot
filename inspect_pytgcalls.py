import asyncio
from pytgcalls import PyTgCalls
from pyrogram import Client

async def main():
    # Use empty/dummy config just to instantiate the object
    client = Client("dummy", api_id=123, api_hash="abc")
    call = PyTgCalls(client)
    print("Methods in PyTgCalls:")
    for method in dir(call):
        if not method.startswith("_"):
            print(f" - {method}")

if __name__ == "__main__":
    asyncio.run(main())
