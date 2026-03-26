import yt_dlp

opts = {
    "quiet": True, 
    "skip_download": True, 
    "format": "bestaudio/best"
}
try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=QjjMshasIQo", download=False)
        print("SUCCESS! " + str(info.get('title')))
except Exception as e:
    print("FAILED", e)
