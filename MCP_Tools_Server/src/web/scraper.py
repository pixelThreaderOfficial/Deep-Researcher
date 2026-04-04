# test_crawler.py
# Run this file separately to test your crawler
# Make sure your project structure allows the import below

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from src.web.search_urls import SearXNGClient
from src.web.web_crawler import (
    get_crawler_engine,
)
from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

# Search the URLs using SearXNG
search_client = SearXNGClient()


async def search_urls(queries: List) -> List[str]:
    """
    Search for URLs across multiple queries using SearXNG and return a list of unique results.

    Args:
        queries: A list of search query strings.

    Returns:
        A list of unique URLs discovered from the search results.
    """
    await scheduler.schedule(
        quickLog,
        params={
            "level": "info",
            "message": f"Trying Collecting URLs {queries}",
            "module": ["CRAWLER"],
            "urgency": "none",
        },
    )

    await event_bus.broadcast(message={"msg": "I'm on the internet..."})
    # Fully async path to avoid cross-loop / run_until_complete conflicts
    # when multiple requests hit /scrape/search concurrently.
    results = await search_client.search_parallel_async(queries)

    # Normalize and extract URLs from a variety of possible response shapes:
    # - If response contains a 'results' list (typical Searx), extract item['url']
    # - If response has a top-level 'url' (or 'link'/'uri'), use it
    # - If response is a plain string, treat it as a URL
    urls: List[str] = []
    seen = set()
    if not results:
        return []

    for r in results:
        if not r:
            continue

        if isinstance(r, dict):
            # Prefer structured 'results' list if present
            res_list = r.get("results")
            if isinstance(res_list, list):
                for item in res_list:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url") or item.get("link") or item.get("uri")
                    if url and url not in seen:
                        seen.add(url)
                        urls.append(url)
                continue

            # Fall back to top-level url/link/uri
            url = r.get("url") or r.get("link") or r.get("uri")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
            continue

        # If the result is a simple string, treat it as a URL
        if isinstance(r, str) and r not in seen:
            seen.add(r)
            urls.append(r)

    await event_bus.broadcast(
        message={"msg": f"I've got {len(urls)} pages, on the internet..."}
    )
    return urls


async def read_pages(
    urls: List[str],
    *,
    max_urls: Optional[int] = None,
    max_concurrent_scrape_batches: int = 3,
    origin_research_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Scrape the provided URLs (no searching) and yield results in parallel batches.

    Yields dicts shaped for your `scrapes` / `scrapes_metadata` fill:
    - success: true/false
    - url
    - content
    - scrape_duration
    - datetime_Scrape
    """
    async for item in search_and_scrape_pages(
        urls,
        max_urls=max_urls,
        max_concurrent_scrape_batches=max_concurrent_scrape_batches,
        queries_are_urls=True,
        origin_research_id=origin_research_id,
    ):
        yield item


async def search_and_scrape_pages(
    queries_or_urls: List[str],
    *,
    max_urls: Optional[int] = None,
    max_concurrent_scrape_batches: int = 3,
    queries_are_urls: bool = False,
    origin_research_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    End-to-end pipeline:
    1) collect URLs (SearXNG) from `queries_or_urls` unless `queries_are_urls=True`
    2) scrape URLs using the shared crawl4ai engine
    3) yield per-page results as each scrape batch finishes

    Returned items include at least:
    - success, url, content, scrape_duration, datetime_Scrape
    plus extra fields useful for your DB inserts.
    """

    if not queries_or_urls:
        return
    if queries_are_urls:
        await event_bus.broadcast(
            message={"msg": f"I'm scraping {len(queries_or_urls)} provided URLs..."}
        )
    else:
        await event_bus.broadcast(
            message={
                "msg": f"I'm collecting search results for {len(queries_or_urls)} queries..."
            }
        )

    if queries_are_urls:
        urls: List[str] = list(queries_or_urls)
    else:
        urls = await search_urls(queries_or_urls)

    # Safety: avoid accidental huge crawls.
    if max_urls is not None:
        urls = urls[:max_urls]

    urls = list(dict.fromkeys(urls))  # stable de-dupe
    if not urls:
        await event_bus.broadcast(message={"msg": "No URLs found to scrape."})
        return

    await event_bus.broadcast(message={"msg": f"I'm scraping {len(urls)} pages..."})

    engine = await get_crawler_engine()
    batch_size = getattr(engine, "batch_size", 10) or 10

    batches: List[List[str]] = [
        urls[i : i + batch_size] for i in range(0, len(urls), batch_size)
    ]

    semaphore = asyncio.Semaphore(max_concurrent_scrape_batches)

    async def scrape_batch(
        batch_urls: List[str], batch_idx: int
    ) -> List[Dict[str, Any]]:
        scrape_dt = datetime.utcnow().isoformat()
        try:
            async with semaphore:
                await scheduler.schedule(
                    quickLog,
                    params={
                        "level": "info",
                        "message": (
                            f"Scrape batch {batch_idx + 1}/{len(batches)} "
                            f"({len(batch_urls)} urls) src:scraper: end-to-end"
                        ),
                        "module": ["SCRAPER", "CRAWLER"],
                        "urgency": "none",
                    },
                )
                results = await engine.crawl_batch(batch_urls)
        except Exception as e:
            # Never leak task exceptions outward: a single batch failure
            # must not terminate the stream while other batches keep running.
            results = [
                {
                    "url": u,
                    "status": "fail",
                    "title": None,
                    "description": None,
                    "favicon": None,
                    "banner_image": None,
                    "markdown": None,
                    "crawling_time_sec": 0.0,
                    "error": str(e),
                }
                for u in batch_urls
            ]

        items: List[Dict[str, Any]] = []
        for r in results:
            status = r.get("status")
            success = status == "success"
            content = r.get("markdown") if success else None

            metadata: Dict[str, Any] = {
                "title": r.get("title"),
                "description": r.get("description"),
                "banner_image": r.get("banner_image"),
                "favicon": r.get("favicon"),
                "status": status,
                "error": r.get("error"),
                "crawling_time_sec": r.get("crawling_time_sec"),
                "scraped_at": scrape_dt,
            }

            no_words = 0
            if content and isinstance(content, str):
                no_words = len(content.split())

            items.append(
                {
                    # ---- your minimum required fields ----
                    "success": success,
                    "url": r.get("url"),
                    "content": content,
                    "scrape_duration": r.get("crawling_time_sec"),
                    "datetime_Scrape": scrape_dt,
                    # ---- extra fields for your DB mapping ----
                    # Candidate deterministic identifiers (your DB layer can choose to use/update them).
                    "scrapes_id_candidate": hashlib.sha256(
                        r.get("url", "").encode("utf-8")
                    ).hexdigest(),
                    "scrape_id_candidate": hashlib.sha256(
                        r.get("url", "").encode("utf-8")
                    ).hexdigest(),
                    "scrapes_metadata_id_candidate": hashlib.sha256(
                        f"meta|{r.get('url', '')}".encode("utf-8")
                    ).hexdigest(),
                    "title": r.get("title"),
                    "favicon": r.get("favicon"),
                    "metadata": metadata,
                    "metadata_json": json.dumps(metadata, ensure_ascii=False),
                    "search_engine": "SearXNG",
                    "clawler": "crawl4ai",  # matches your schema spelling
                    "clawling_time_sec": r.get("crawling_time_sec"),
                    "no_words": no_words,
                    "created_at": scrape_dt,
                    "updated_at": scrape_dt,
                    "is_vector_stored": False,
                    # placeholders to be filled later by your pipeline
                    "chats_cited": None,
                    "research_cited": None,
                    "num_crawls": None,
                    "num_cited": None,
                    "origin_research_id": origin_research_id,
                }
            )

        return items

    tasks = [
        asyncio.create_task(scrape_batch(batch, i)) for i, batch in enumerate(batches)
    ]

    for fut in asyncio.as_completed(tasks):
        # Defensive await: even if something unexpected escapes scrape_batch,
        # keep consuming all task completions to avoid dangling background work.
        try:
            batch_items = await fut
        except Exception as e:  # pragma: no cover - safety net
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Unhandled batch task error: {e}",
                    "module": ["SCRAPER", "CRAWLER"],
                    "urgency": "critical",
                },
            )
            batch_items = []
        for item in batch_items:
            yield item

    await event_bus.broadcast(
        message={"msg": f"Finished scraping all batches ({len(urls)} urls)."}
    )


# async def run_test():
#     print(
#         f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting crawler test with {len(TEST_URLS)} URLs..."
#     )

#     # Optional: warm up engine first (helps avoid cold-start lag)
#     engine = await get_crawler_engine(batch_size=10)
#     print("Engine warmed up.")

#     # Run the batch crawl
#     results: List[Dict[str, Any]] = await crawl_urls(TEST_URLS, batch_size=10)

#     # Print summary stats
#     success = sum(1 for r in results if r.get("status") == "success")
#     blocked_empty = sum(
#         1 for r in results if r.get("status") in ["empty_or_blocked", "blocked"]
#     )
#     fail = sum(1 for r in results if r.get("status") == "fail")
#     total_time = max(r.get("crawling_time_sec", 0) for r in results)  # rough batch    time

#     print("\n" + "=" * 60)
#     print(f"RESULTS SUMMARY ({len(results)} URLs)")
#     print(f"Success       : {success}")
#     print(f"Blocked/Empty : {blocked_empty}")
#     print(f"Fail/Timeout  : {fail}")
#     print(f"Rough total time: ~{total_time:.1f} sec (parallel batches)")
#     print("=" * 60 + "\n")

#     # Print short report for each (you can save to file too)
#     for r in results:
#         status_emoji = (
#             "✅"
#             if r["status"] == "success"
#             else "⚠️"
#             if r["status"] in ["empty_or_blocked", "fail"]
#             else "❌"
#         )
#         js_note = " (used JS)" if r.get("used_js") else ""
#         print(
#             f"{status_emoji} {r['status'].upper():<12} | {r['crawling_time_sec']:.2f}s | {r['url'][:80]}{'...' if len(r['url']) > 80 else ''}{js_note}"
#         )

#     # Optional: save full results to JSON for inspection
#     with open("crawler_test_results_2026.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, indent=2, ensure_ascii=False)
#     print("\nFull results saved to: crawler_test_results_2026.json")


# if __name__ == "__main__":
#     asyncio.run(run_test())
