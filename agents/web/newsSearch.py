"""
Async News Search using SearXNG

Usage:
    from newsSearch import search_news

    results = await search_news("AI trends 2026", num_results=5)
"""

from typing import Any, Dict, List

import httpx

from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler
from web.web_crawler import (
    crawl_urls,
)

BASE_URL = "http://localhost:8080/search"


async def search_news(
    query: str,
    num_results: int = 5,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Perform async news search.

    Args:
        query: Search query
        num_results: Number of results
        timeout: Request timeout

    Returns:
        List of news result dictionaries
    """
    params = {
        "q": query,
        "categories": "general",
        "format": "json",
    }

    await scheduler.schedule(
        quickLog,
        params={
            "level": "info",
            "message": f"Trying Collecting news for `{query}`",
            "module": ["CRAWLER"],
            "urgency": "none",
        },
    )
    await event_bus.broadcast(message={"msg": "I'm exploring some latest news..."})

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])[:num_results]

    # for now just use top 5 urls impliment the validation in future
    #
    urls_to_scrape = [i["url"] for i in results[0:5]]

    # Scrape the contnet

    results_crawl = await crawl_urls(urls_to_scrape)

    response = []

    for result in results_crawl:
        res_item = {}
        res_item["title"] = result["title"]
        res_item["content"] = result["markdown"]
        res_item["description"] = result["description"]
        res_item["url"] = result["url"]
        res_item["favicon"] = result["favicon"]
        response.append(res_item)

    return response


# ------------------ TEST ------------------


# async def _test():
#     print("📰 Testing News Search...\n")
#     results = await search_news(
#         "Latest news on Bali Tourism. Is it safe to travel in this season?",
#         num_results=5,
#     )

#     print(f"Found {len(results)} results.\n")
#     print("-" * 60)

#     for i, r in enumerate(results, 1):
#         print(f"{i}. {r['title']}")
#         print(f"   Link: {r['url']}\n")
#         print(f"   Favicon: {r['favicon']}\n")
#         print(f"   Desc: {r['description']}\n")
