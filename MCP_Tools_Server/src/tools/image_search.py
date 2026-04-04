import asyncio
from typing import Any, Dict, List, Tuple

import aiohttp

from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

SEARXNG_URL = "http://localhost:8080/search"


# ---------------------------
# SINGLE QUERY FETCH
# ---------------------------
async def fetch_images(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int = 10,
) -> List[str]:

    params = {"q": query, "categories": "images", "format": "json"}

    await event_bus.broadcast(
        message={"msg": f"Searching images for {query}...", "tool_param": query}
    )

    await scheduler.schedule(
        quickLog,
        params={
            "level": "info",
            "message": f"Fetching images for {query}",
            "module": ["CRAWLER"],
            "urgency": "none",
        },
    )

    try:
        async with session.get(SEARXNG_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        results = data.get("results", [])

        images = [item["img_src"] for item in results if "img_src" in item][
            :max_results
        ]

        await event_bus.broadcast(
            message={
                "msg": f"Found {len(images)} images",
                "tool_param": query,
                "tool_result": images,
            }
        )

        await scheduler.schedule(
            quickLog,
            params={
                "level": "success",
                "message": f"{len(images)} images fetched for {query}",
                "module": ["CRAWLER"],
                "urgency": "none",
            },
        )

        return images

    except Exception as e:
        await event_bus.broadcast(
            message={
                "msg": "Image search failed",
                "tool_param": query,
                "tool_result": str(e),
            }
        )

        await scheduler.schedule(
            quickLog,
            params={
                "level": "error",
                "message": f"Error fetching {query}: {str(e)}",
                "module": ["CRAWLER"],
                "urgency": "moderate",
            },
        )

        return []


# ---------------------------
# MULTI QUERY PARALLEL SEARCH
# ---------------------------
async def search_images(queries: List[Tuple[str, int]]) -> Dict[str, List[str]]:
    """
    queries: [(query, num_images), ...]
    returns: {query: [image_urls]}
    """

    results = {}

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_images(session, query, num) for query, num in queries]

        responses = await asyncio.gather(*tasks)

    for (query, _), images in zip(queries, responses):
        results[query] = images

    return results


async def main():
    queries = [("cats", 5), ("bali", 10), ("airplane", 6)]

    result = await search_images(queries)

    for q, imgs in result.items():
        print(f"\n🔍 {q} -> {len(imgs)} images")
        for url in imgs:
            print(url)


if __name__ == "__main__":
    asyncio.run(main())
