import asyncio
import logging
import os
import time
from typing import Any, Dict, List

import yt_dlp

from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

# 🔥 ensure nvm node is visible
os.environ["PATH"] += ":/home/pixelthreader/.nvm/versions/node/v24.14.1/bin"

# 🔇 silence yt-dlp warnings
logging.getLogger("yt_dlp").setLevel(logging.ERROR)


# ---------- GLOBAL CONFIG ----------
COMMON_OPTS: Dict[str, Any] = {
    "quiet": True,
    "skip_download": True,
    "ignoreerrors": True,
    "nocheckcertificate": True,
    "extract_flat": True,
    "js_runtimes": {
        "node": {"path": "/home/pixelthreader/.nvm/versions/node/v24.14.1/bin/node"}
    },
    "remote_components": ["ejs:github"],
}


# ---------- SEARCH ----------
def search_youtube(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    with yt_dlp.YoutubeDL(COMMON_OPTS) as ydl:
        result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        return result.get("entries", [])


# ---------- EXTRACT ----------
def extract_info(url: str) -> Dict[str, Any]:
    with yt_dlp.YoutubeDL(COMMON_OPTS) as ydl:
        return ydl.extract_info(url, download=False)


# ---------- PROCESS ----------
async def process_video(video: Dict[str, Any]):
    url = video.get("url") or video.get("webpage_url")
    if not url:
        return None

    info = await asyncio.to_thread(extract_info, url)

    return {
        "title": info.get("title"),
        "url": info.get("webpage_url"),
        "description": info.get("description"),
        "channel": info.get("channel"),
        "duration": info.get("duration"),
        "views": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "thumbnail": info.get("thumbnail"),
    }


# ---------- MAIN ----------
async def get_youtube_data(query: str) -> Dict[str, Any]:
    start_time = time.time()

    # ✅ LOG START (VALID PARAMS)
    await scheduler.schedule(
        quickLog,
        params={
            "message": f"Searching YouTube for query: {query}",
            "level": "info",
            "module": ["CRAWLER"],
            "urgency": "none",
        },
    )

    # 📡 BROADCAST START
    await event_bus.broadcast(
        message={
            "msg": "Searching YouTube...",
            "tool_param": query,
        }
    )

    # ---------- SEARCH ----------
    videos = await asyncio.to_thread(search_youtube, query, 10)

    # ---------- PROCESS ----------
    tasks = [process_video(v) for v in videos]
    results = await asyncio.gather(*tasks)

    results = [r for r in results if r]

    scrape_time = round(time.time() - start_time, 2)

    final_output = {
        "query": query,
        "total_results": len(results),
        "scrape_time": scrape_time,
        "videos": results,
    }

    # ✅ LOG COMPLETE (VALID PARAMS)
    await scheduler.schedule(
        quickLog,
        params={
            "message": f"YouTube scrape completed in {scrape_time}s",
            "level": "success",
            "module": ["CRAWLER"],
            "urgency": "none",
        },
    )

    # 📡 BROADCAST RESULT
    await event_bus.broadcast(
        message={
            "msg": "YouTube scraping completed",
            "tool_param": query,
            "tool_result": final_output,
        }
    )

    return final_output


# ---------- RUN ----------
if __name__ == "__main__":
    import json

    query = "black hole mystery"
    filename = "youtube_results.json"

    data = asyncio.run(get_youtube_data(query))

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved to {filename}")
