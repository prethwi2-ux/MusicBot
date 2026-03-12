from pytgcalls import PyTgCalls
from pyrogram import Client

def check():
    client = Client("dummy", api_id=123, api_hash="abc")
    call = PyTgCalls(client)
    
    potential_names = [
        "pause_stream", "resume_stream",
        "pause", "resume",
        "mute_stream", "unmute_stream",
        "mute", "unmute",
        "change_stream", "change_volume_call", "leave_group_call"
    ]
    
    print("Checking methods:")
    for name in potential_names:
        has = hasattr(call, name)
        print(f" - {name}: {'FOUND' if has else 'MISSING'}")

if __name__ == "__main__":
    try:
        check()
    except Exception as e:
        print(f"Error checking: {e}")
