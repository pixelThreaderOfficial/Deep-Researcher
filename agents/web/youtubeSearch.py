import asyncio
from asyncio import to_thread
from urllib.parse import parse_qs, urlparse

from py_youtube import Data, Search
from youtube_transcript_api import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()


# ------------------ HELPERS ------------------


def extract_video_id(video_input: str) -> str:
    """Extract video ID from URL or return if already ID"""
    if "youtube.com" in video_input:
        parsed = urlparse(video_input)
        return parse_qs(parsed.query).get("v", [None])[0]

    if "youtu.be" in video_input:
        return video_input.split("/")[-1]

    return video_input  # already ID


def build_video_url(video_id: str) -> str:
    """Convert ID → full YouTube URL"""
    return f"https://www.youtube.com/watch?v={video_id}"


def validate_video_id(video_id: str):
    if not video_id or len(video_id) < 6:
        raise ValueError("Invalid YouTube video ID")


# ------------------ CORE ------------------


async def youtube_search(query: str):
    return await to_thread(lambda: Search(query).videos())


async def get_video_data(video_input: str):
    """
    py_youtube NEEDS FULL URL (this was your bug 💀)
    """
    video_id = extract_video_id(video_input)
    validate_video_id(video_id)

    video_url = build_video_url(video_id)

    return await to_thread(lambda: Data(video_url).data())


async def get_video_transcript(video_input: str):
    """
    transcript API NEEDS ONLY ID
    """
    video_id = extract_video_id(video_input)
    validate_video_id(video_id)

    return await to_thread(lambda: ytt_api.fetch(video_id))


async def get_video_bundle(video_input: str, query: str):
    """
    Parallel execution ⚡ (fast AF now)
    """
    video_id = extract_video_id(video_input)
    validate_video_id(video_id)

    video_url = build_video_url(video_id)

    return await asyncio.gather(
        youtube_search(query),
        to_thread(lambda: Data(video_url).data()),
        to_thread(lambda: ytt_api.fetch(video_id)),
    )


# ------------------ TEST ------------------


async def _demo():
    video_url = "https://www.youtube.com/watch?v=_Vccl1Iulws"
    query = "Best ways to spend holidays in Bali"

    search_results, video_data, transcript = await get_video_bundle(video_url, query)

    print("=== youtube_search ===")
    print(search_results[:2])

    print("\n=== get_video_data ===")
    print(video_data)

    print("\n=== get_video_transcript ===")
    print(transcript[:3])
