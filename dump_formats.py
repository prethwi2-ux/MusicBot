import json
import yt_dlp

opts = {"cookiefile": "cookies.txt", "quiet": True, "skip_download": True, "ignoreerrors": True}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/watch?v=QjjMshasIQo", download=False)
    # Check if info exists and has formats
    if info:
        formats = info.get("formats", [])
        fmt_list = [{"id": f.get("format_id"), "ext": f.get("ext"), "vcodec": f.get("vcodec"), "acodec": f.get("acodec")} for f in formats]
        with open("formats.json", "w") as f:
            json.dump(fmt_list, f, indent=2)
    else:
        print("NO INFO EXTRACTED")
