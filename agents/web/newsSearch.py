"""
Async News Search using SearXNG

Usage:
    from newsSearch import search_news

    results = await search_news("AI trends 2026", num_results=5)
"""

from typing import Any, Dict, List

import httpx

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
        "categories": "news",
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])[:num_results]

    return [
        {
            "title": r.get("title"),
            "content": r.get("content"),
            "url": r.get("url"),
            "published_date": r.get("publishedDate"),
            "source": r.get("source"),
        }
        for r in results
    ]


# ------------------ TEST ------------------


async def _test():
    print("📰 Testing News Search...\n")
    results = await search_news("AI breakthroughs", num_results=3)

    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   Link: {r['url']}\n")
