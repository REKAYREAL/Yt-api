import os
import uuid
import shutil
import yt_dlp
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="YouTube Downloader API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Path to the cookies.txt file (must be in the project root)
COOKIE_FILE = "cookies.txt"

def sanitize_filename(filename: str) -> str:
    return "".join(c for c in filename if c.isalnum() or c in (" ", "-", "_")).rstrip()

@app.get("/")
def read_root():
    return {
        "message": "YouTube Downloader API",
        "endpoints": {
            "/info": "Get video information",
            "/download": "Download video or audio"
        }
    }

@app.get("/info")
def get_video_info(url: str = Query(..., description="YouTube video URL")):
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": False,
            "extract_flat": False,
            "force_generic_extractor": False,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Sec-Fetch-Mode": "navigate",
            },
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "cookiefile": COOKIE_FILE,  # <-- Added cookie support
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "title": info.get("title"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "view_count": info.get("view_count"),
                "thumbnail": info.get("thumbnail"),
                "formats": [
                    {
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "resolution": f.get("resolution"),
                        "filesize": f.get("filesize")
                    }
                    for f in info.get("formats", [])
                    if f.get("vcodec") != "none" or f.get("acodec") != "none"
                ][:10]
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.get("/download")
def download_video(
    url: str = Query(..., description="YouTube video URL"),
    type: str = Query("video", description="Type: 'video' or 'audio'")
):
    unique_id = str(uuid.uuid4())

    try:
        common_opts = {
            "quiet": True,
            "no_warnings": False,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Sec-Fetch-Mode": "navigate",
            },
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "cookiefile": COOKIE_FILE,  # <-- Added cookie support
        }

        if type.lower() == "audio":
            ydl_opts = {
                **common_opts,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{unique_id}.%(ext)s"),
            }
        else:
            ydl_opts = {
                **common_opts,
                "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "merge_output_format": "mp4",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{unique_id}.%(ext)s"),
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if type.lower() == "audio":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

            if not os.path.exists(filename):
                raise Exception("Download failed - file not found")

            safe_title = sanitize_filename(info.get("title", "download"))
            extension = "mp3" if type.lower() == "audio" else "mp4"
            response_filename = f"{safe_title}.{extension}"

            return FileResponse(
                filename,
                media_type="audio/mpeg" if type.lower() == "audio" else "video/mp4",
                filename=response_filename,
                background=None
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

@app.on_event("shutdown")
def cleanup():
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)