import yt_dlp
import json

opts = {
    "cookiefile": "cookies.txt",
    "quiet": True,
    "skip_download": True
}
try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=QjjMshasIQo", download=False)
        formats = info.get("formats", [])
        for f in formats:
            print(f"{f.get('format_id')} - {f.get('ext')} - {f.get('acodec')} - {f.get('vcodec')}")
except Exception as e:
    print(f"ERROR: {e}")
