# Default File Scoped utility functions
import datetime
import socket
import os
import psutil
import subprocess
from py_youtube import Search, Data
from youtube_transcript_api import YouTubeTranscriptApi


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def utcnow_iso() -> str:
    return utcnow().isoformat()



# String utilities

def checkStringIsEmpty(s: str) -> bool:
    return s is None or s.strip() == ""

def convertExplicitToString(s: str) -> str:
    if s is None:
        return ""
    return s.strip()

# System Utilities

def check_online_status(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Checks if the system has internet connectivity. Default checks 8.8.8.8 via TCP."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False

def get_system_resources() -> dict:
    """Returns local system resource usage metrics including GPU if available."""
    metrics = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    }
    
    try:
        # Fetch GPU stats directly via nvidia-smi to avoid distutils dependency issues on Python 3.12+
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8"
        )
        lines = output.strip().split('\n')
        if lines:
            util, mem_used, mem_total = map(float, lines[0].split(','))
            metrics["gpu_percent"] = round(util, 1)
            metrics["gpu_mem_percent"] = round((mem_used / mem_total) * 100, 1)
    except Exception:
        pass # Silently handle systems without compatible GPUs or missing nvidia-smi
    
    return metrics
'''run this in backend to check system resources
uv run python -c "from main.src.utils.utilities import get_system_resources; print(get_system_resources())"

 this cmd will continuously print system resources for 1 minute
uv run python -c "from main.src.utils.utilities import get_system_resources; import time; [print(f'\r{get_system_resources()}', end='') or time.sleep(1) for _ in range(60)]; print()"
'''

# Resource Utilities

def check_static_resource_exists(filepath: str) -> bool:
    """Checks if a local static resource file exists."""
    if checkStringIsEmpty(filepath):
        return False
    return os.path.exists(filepath)


# YouTube Utilities

ytt_api = YouTubeTranscriptApi()
VALID_VIDEO_ID_PREFIXES = ("https://youtu.be/", "https://www.youtube.com/watch?v=")

def _is_valid_video_id(video_id: str) -> bool:
    if video_id.startswith(VALID_VIDEO_ID_PREFIXES):
        return True
    return False

def youtube_search(query: str):
    """Searches YouTube and returns matching videos."""
    videos = Search(query).videos()
    return videos

def get_video_data(video_id: str):
    """Fetches YouTube video metadata. The video_id here expects a valid URL prefix based on _is_valid_video_id."""
    if not _is_valid_video_id(video_id):
        raise ValueError("Invalid video ID URL or format")
    
    video = Data(video_id).data() # py_youtube Data accepts string ID/URL
    return video

def get_video_transcript(video_id: str):
    """Fetches the transcript for a given video ID."""
    transcript = ytt_api.fetch(video_id)
    return transcript
