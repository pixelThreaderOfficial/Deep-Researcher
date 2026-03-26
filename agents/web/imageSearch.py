"""
Async Image Search using SearXNG

Usage:
    from imageSearch import search_images

    results = await search_images("cyberpunk city", num_results=5)
"""

from typing import Any, Dict, List

import httpx

from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

BASE_URL = "http://localhost:8080/search"


async def search_images(
    query: str,
    num_results: int = 5,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Perform async image search.

    Args:
        query: Search query
        num_results: Number of results to return
        timeout: Request timeout

    Returns:
        List of image result dictionaries
    """
    params = {
        "q": query,
        "categories": "images",
        "format": "json",
    }
    await scheduler.schedule(
        quickLog,
        params={
            "level": "info",
            "message": f"Trying Collecting images for `{query}`",
            "module": ["CRAWLER"],
            "urgency": "none",
        },
    )
    await event_bus.broadcast(message={"msg": "I'm exploring some images..."})
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])[:num_results]
    await event_bus.broadcast(
        message={"msg": f"Got {len(results)} images! Finding relevent ones..."}
    )

    return [
        {
            "title": r.get("title"),
            "img_src": r.get("img_src"),
            "url": r.get("url"),
            "source": r.get("source"),
        }
        for r in results
    ]


# ------------------ TEST ------------------


async def _test():
    print("🔥 Testing Image Search...\n")
    results = await search_images("top Resorts in Bali", num_results=10)

    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   Image: {r['img_src']}\n")
