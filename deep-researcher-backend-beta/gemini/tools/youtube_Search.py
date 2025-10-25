from py_youtube import Search, Data
import json
from youtube_transcript_api import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()
# ytt_api.fetch(video_id)

VALID_VIDEO_ID_PREFIXES = ["https://youtu.be/", "https://www.youtube.com/watch?v="]

def _is_valid_video_id(video_id: str):
    if video_id.startswith(VALID_VIDEO_ID_PREFIXES):
        return True
    
    return False


def youtube_search(query: str):
    videos = Search(query).videos()
    return videos

def get_video_data(video_id: str):
    if not _is_valid_video_id(video_id):
        raise ValueError("Invalid video ID")
    
    video = Data(video_id).data()
    return video

def get_video_transcript(video_id: str):
    transcript = ytt_api.fetch(video_id)
    return transcript

if __name__ == "__main__":
    videos = get_video_data("https://youtu.be/RGaW82k4dK4?si=SCuRsvaRBxlZv0Yk")
    print(json.dumps(videos, indent=2))