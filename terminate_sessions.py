from pyrogram import Client
from bot import config
import asyncio

async def main():
    print("Connecting to Telegram...")
    app = Client(
        name="MusicAssistant_Revoker",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=config.STRING_SESSION,
        in_memory=True,
    )
    
    await app.start()
    print("Connected successfully.")
    
    # Get all active sessions (authorizations)
    auths = await app.invoke(
        __import__("pyrogram.raw.functions").raw.functions.account.GetAuthorizations()
    )
    
    current_hash = None
    
    print("\n--- Active Sessions ---")
    for auth in auths.authorizations:
        print(f"Device: {auth.device_model}")
        print(f"Platform: {auth.platform}")
        print(f"App Version: {auth.app_version}")
        print(f"IP: {auth.ip}")
        print(f"Current session: {auth.current}")
        print("-------------")
        if getattr(auth, 'current', False):
            current_hash = auth.hash
            
    print("\nAttempting to terminate all *other* sessions...")
    count = 0
    for auth in auths.authorizations:
        if auth.hash != current_hash:
            try:
                await app.invoke(
                    __import__("pyrogram.raw.functions").raw.functions.auth.ResetAuthorizations()
                )
                print(f"Terminated session on {auth.device_model} ({auth.platform})")
                count += 1
            except Exception as e:
                print(f"Could not terminate a session: {e}")
                
    if count == 0:
        print("No other sessions found to terminate.")
    else:
        print(f"\nSuccessfully terminated {count} other active session(s).")
        print("You should now be able to run your bot locally without AUTH_KEY_DUPLICATED.")
        
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
