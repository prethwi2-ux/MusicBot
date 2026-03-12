import asyncio
import sys

# Create and set loop BEFORE any imports that might trigger it
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from pytgcalls import PyTgCalls

def check():
    print("Methods in PyTgCalls:")
    for name in dir(PyTgCalls):
        if not name.startswith("_"):
            print(f" - {name}")

if __name__ == "__main__":
    check()
