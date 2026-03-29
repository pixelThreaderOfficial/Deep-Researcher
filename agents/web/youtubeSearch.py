"""
youtubeSearch.py
────────────────
Resilient YouTube pipeline — no official API required.

Main public entry point:
    results = await search_and_summarize(
        query="Best resorts in Bali 2026",
        max_videos=5,
        ollama_url="http://localhost:11434/api/generate",
        summarize_video=True,
    )

Design principles:
- A single blocked/erroring video NEVER breaks the whole batch.
- Missing transcript → video is silently excluded from results.
- Missing metadata fields → filled with None, never raise.
- All blocking I/O (py_youtube, transcript API, Ollama) is run in
  threads so we never block the asyncio event loop.
"""

import asyncio
import logging
import sys
from asyncio import to_thread
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from py_youtube import Data, Search
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from docParsers.ollamaWorker import FastSummarizer

from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

# ──────────────────────── LOGGING ──────────────────────────────────────────

LOG_FORMAT = "%(asctime)s  %(levelname)-8s  [YouTubeSearch]  %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("YouTubeSearch")

# Re-use a single transcript API instance (thread-safe)
_ytt_api = YouTubeTranscriptApi()


# ──────────────────────── HELPERS ──────────────────────────────────────────


def _extract_video_id(video_input: str) -> Optional[str]:
    """
    Safely extract the video ID from a URL, a youtu.be short link, or a bare ID.
    Returns None if nothing useful can be extracted.
    """
    if not video_input:
        return None
    try:
        if "youtube.com" in video_input:
            parsed = urlparse(video_input)
            vid = parse_qs(parsed.query).get("v", [None])[0]
            return vid if vid and len(vid) >= 6 else None
        if "youtu.be" in video_input:
            vid = video_input.split("/")[-1].split("?")[0]
            return vid if vid and len(vid) >= 6 else None
        # Bare ID
        return video_input.strip() if len(video_input.strip()) >= 6 else None
    except Exception:
        return None


def _build_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _safe_get(d: Any, *keys, default=None):
    """Nested dict/attr safe-getter — never raises."""
    try:
        val = d
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                val = getattr(val, k, default)
            if val is None:
                return default
        return val
    except Exception:
        return default


def _transcript_to_text(transcript_list) -> str:
    """Convert the raw transcript SnippetList to a single plain-text string."""
    try:
        texts = []
        for entry in transcript_list:
            if isinstance(entry, dict):
                texts.append(str(entry.get("text", "")))
            elif hasattr(entry, "text"):
                texts.append(str(entry.text))
            else:
                texts.append(str(entry))
        return " ".join(texts).strip()
    except Exception:
        return ""


# ──────────────────────── LOW-LEVEL ASYNC WRAPPERS ─────────────────────────


async def youtube_search(query: str) -> List[Dict[str, Any]]:
    """
    Return the raw video list from py_youtube Search.
    Empty list on any failure — never raises.
    """
    try:
        results = await to_thread(lambda: Search(query).videos())
        return results if isinstance(results, list) else []
    except Exception as e:
        logger.warning(f"youtube_search failed for '{query}': {e}")
        return []


async def get_video_data(video_input: str) -> Optional[Dict[str, Any]]:
    """
    Fetch metadata for a single video via py_youtube Data.
    Returns None on any failure — never raises.
    """
    video_id = _extract_video_id(video_input)
    if not video_id:
        logger.warning(f"get_video_data: cannot extract video ID from '{video_input}'")
        return None
    try:
        url = _build_video_url(video_id)
        data = await to_thread(lambda: Data(url).data())
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning(f"get_video_data failed for '{video_input}': {e}")
        return None


async def get_video_transcript(video_input: str) -> Optional[str]:
    """
    Fetch the transcript for a single video and return it as plain text.

    Returns None when:
    - Transcripts are disabled on the video
    - No transcript is found (private, age-gated, regional block…)
    - The video is unavailable
    - Any other network/parse error

    Never raises — callers can treat None as "skip this video".
    """
    video_id = _extract_video_id(video_input)
    if not video_id:
        logger.warning(f"get_video_transcript: bad video input '{video_input}'")
        return None
    try:
        raw = await to_thread(lambda: _ytt_api.fetch(video_id))
        text = _transcript_to_text(raw)
        return text if text else None
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        logger.info(f"No transcript for video '{video_id}': {type(e).__name__}")
        return None
    except Exception as e:
        logger.warning(f"Transcript fetch error for '{video_id}': {e}")
        return None


# ──────────────────────── VIDEO BUNDLE (SINGLE VIDEO) ──────────────────────


async def get_video_bundle(video_input: str, query: str) -> tuple:
    """
    Parallel fetch: search + metadata + transcript for one video.
    None values signal partial failure — callers decide what to do.
    """
    video_id = _extract_video_id(video_input)
    video_url = _build_video_url(video_id) if video_id else video_input

    search_task = asyncio.create_task(youtube_search(query))
    data_task = asyncio.create_task(get_video_data(video_url))
    transcript_task = asyncio.create_task(get_video_transcript(video_url))

    search_results, video_data, transcript = await asyncio.gather(
        search_task, data_task, transcript_task, return_exceptions=False
    )
    return search_results, video_data, transcript


# ──────────────────────── MAIN PIPELINE ────────────────────────────────────


async def search_and_summarize(
    query: str,
    max_videos: int = 5,
    ollama_url: str = "http://localhost:11434/api/generate",
    ollama_model: str = "qwen3.5:9b",
    transcript_max_words: int = 1200,
    summarize_video: bool = True,
) -> Dict[str, Any]:
    """
    Full pipeline: search → metadata → transcript → Ollama summary (optional).

    Args:
        query:               User search query.
        max_videos:          Maximum number of videos to attempt (some will be
                             skipped if transcript/metadata is unavailable).
        ollama_url:          Ollama API endpoint (override for remote servers).
        ollama_model:        Model name for Ollama summarizer.
        transcript_max_words: Cap on transcript tokens fed to Ollama.
        summarize_video:     If True, run Ollama. If False, return raw transcript.

    Returns:
        {
            "query": str,
            "results": [
                {
                    "id":           video_id,
                    "title":        video_title,
                    "desc":         video_description,
                    "thumbnail":    thumbnail_url,
                    "summary":      ollama_summary,
                    "channelName":  channel_name,
                    "channelImage": channel_image_url,
                }
            ]
        }

    Error policy:
    - Any video that is blocked, has no transcript, or fails Ollama is silently
      excluded from `results`. The rest are returned normally.
    - The function itself never raises — on total failure it returns
      { "query": ..., "results": [], "error": "..." }
    """
    logger.info(f"search_and_summarize: query='{query}' max_videos={max_videos}")

    await scheduler.schedule(
        quickLog,
        params={
            "level": "info",
            "message": f"Starting YouTube Search for: {query}",
            "module": ["YOUTUBE"],
            "urgency": "none",
        },
    )
    await event_bus.broadcast(message={"msg": f"Searching YouTube for '{query}'..."})

    summarizer = FastSummarizer(
        model=ollama_model,
        base_url=ollama_url,
        max_words=transcript_max_words,
    ) if summarize_video else None

    # ── Step 1: Search YouTube ──────────────────────────────────────────────
    try:
        raw_videos = await youtube_search(query)
    except Exception as e:
        logger.error(f"Search failed entirely: {e}")
        await event_bus.broadcast(message={"msg": f"Search failed: {e}"})
        return {"query": query, "results": [], "error": str(e)}

    if not raw_videos:
        logger.warning("No videos returned from search.")
        await event_bus.broadcast(message={"msg": "No videos found."})
        return {"query": query, "results": []}

    # Limit how many we'll attempt
    candidates = raw_videos[:max_videos]
    logger.info(f"Found {len(raw_videos)} videos, attempting top {len(candidates)}")
    await event_bus.broadcast(message={"msg": f"Found videos! Analyzing the top {len(candidates)}..."})

    # ── Step 2: Process each candidate concurrently ─────────────────────────

    async def _process_one(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        For one raw search result:
        1. Extract the video ID.
        2. Fetch full metadata (py_youtube Data).
        3. Fetch transcript — skip if unavailable.
        4. Summarize with Ollama — skip if Ollama fails.
        Returns a result dict or None (to be filtered out).
        """
        # ─ Extract ID from the search result ─
        video_id = (
            _extract_video_id(raw.get("id") or "")
            or _extract_video_id(raw.get("url") or "")
            or _extract_video_id(raw.get("link") or "")
        )

        if not video_id:
            logger.info(f"Skipping: could not extract video ID from {raw}")
            return None

        video_url = _build_video_url(video_id)
        logger.info(f"Processing video: {video_id}")

        # ─ Fetch metadata and transcript in parallel ─
        meta_task = asyncio.create_task(get_video_data(video_url))
        transcript_task = asyncio.create_task(get_video_transcript(video_url))
        meta, transcript_text = await asyncio.gather(meta_task, transcript_task)

        # ─ Transcript is mandatory — skip if missing ─
        if not transcript_text:
            logger.info(f"Skipping {video_id}: no transcript available.")
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "warning",
                    "message": f"Dropped {video_id}: no transcript available",
                    "module": ["YOUTUBE"],
                    "urgency": "none",
                },
            )
            return None

        # ─ Try to summarize via Ollama (if requested) ─
        summary = transcript_text
        if summarize_video and summarizer:
            try:
                summary = await to_thread(lambda: summarizer.summarize(transcript_text))
            except Exception as e:
                logger.warning(f"Ollama summarization failed for {video_id}: {e} — skipping.")
                return None

        # ─ Extract metadata fields safely ─
        title = _safe_get(meta, "title") or _safe_get(raw, "title") or "Unknown Title"

        # NOTE: py_youtube doesn't reliably return descriptions or channel images.
        # Fallback cleanly.
        desc = ""

        thumbnail = _safe_get(meta, "thumbnails")
        if not thumbnail:
            thumb_list = _safe_get(raw, "thumb", default=[])
            if isinstance(thumb_list, list) and thumb_list:
                thumbnail = thumb_list[0]

        channel_name = _safe_get(meta, "channel_name") or "Unknown Channel"
        channel_image = ""

        await scheduler.schedule(
            quickLog,
            params={
                "level": "success",
                "message": f"Successfully processed video: {title[:30]}...",
                "module": ["YOUTUBE"],
                "urgency": "none",
            },
        )

        return {
            "id": video_id,
            "title": title,
            "desc": desc,
            "thumbnail": thumbnail,
            "summary": summary,
            "channelName": channel_name,
            "channelImage": channel_image,
        }

    # Run all candidates concurrently; isolate exceptions per video
    tasks = [asyncio.create_task(_process_one(v)) for v in candidates]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: List[Dict[str, Any]] = []
    for i, r in enumerate(raw_results):
        if isinstance(r, Exception):
            logger.warning("Unexpected error on video #%s: %s", i, r)
            continue
        if r is not None:
            results.append(r)

    logger.info(
        "search_and_summarize done: %s/%s videos succeeded.",
        len(results),
        len(candidates),
    )
    return {"query": query, "results": results}
