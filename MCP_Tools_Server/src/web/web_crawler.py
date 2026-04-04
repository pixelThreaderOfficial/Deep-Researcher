# src/agents/webSearchAgent/core/web_crawler.py

import asyncio
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

# Helpers (unchanged)
EMPTY_PATTERNS = [
    r"(?i)enable javascript",
    r"(?i)javascript is disabled",
    r"(?i)turn on javascript",
    r"(?i)please wait while your request is being verified",
    r"(?i)loading.*please wait",
]


def _normalize_metadata(meta: Optional[dict], url: str) -> Dict[str, Any]:
    if not meta:
        parsed = urlparse(url)
        return {
            "title": None,
            "description": None,
            "banner_image": None,
            "favicon": f"{parsed.scheme}://{parsed.netloc}/favicon.ico",
        }

    icons = meta.get("icons") or meta.get("favicons")
    favicon = None
    if isinstance(icons, list) and icons:
        favicon = icons[0]
    elif isinstance(icons, str):
        favicon = icons

    return {
        "title": meta.get("title"),
        "description": (
            meta.get("description")
            or meta.get("og:description")
            or meta.get("twitter:description")
        ),
        "banner_image": (
            meta.get("image") or meta.get("og:image") or meta.get("twitter:image")
        ),
        "favicon": favicon
        or f"{urlparse(url).scheme}://{urlparse(url).netloc}/favicon.ico",
    }


class CrawlerEngine:
    def __init__(
        self,
        batch_size: int = 10,
        concurrency: int = 8,
    ):
        self.browser_cfg = BrowserConfig(
            headless=True,
            text_mode=True,
            light_mode=True,
            java_script_enabled=False,
        )

        self.batch_size = batch_size
        self.concurrency = concurrency

        self.crawler: Optional[AsyncWebCrawler] = None
        self.running = False

    async def start(self):
        if self.running:
            return

        self.crawler = AsyncWebCrawler(config=self.browser_cfg)
        await self.crawler.start()
        self.running = True

    async def stop(self):
        if self.crawler:
            await self.crawler.close()
        self.running = False

    async def crawl_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        if not self.running:
            await self.start()

        all_results = []
        start_all = time.time()

        for i in range(0, len(urls), self.batch_size):
            batch_urls = urls[i : i + self.batch_size]
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "info",
                    "message": f"🚀 Batch {i // self.batch_size + 1} ({len(batch_urls)} URLs) src:web_crawler:105",
                    "module": ["CRAWLER"],
                    "urgency": "none",
                },
            )

            run_configs = [
                CrawlerRunConfig(
                    page_timeout=12000,  # 12s per page
                    cache_mode=CacheMode.BYPASS,
                    semaphore_count=self.concurrency,
                    mean_delay=0.1,
                    max_range=0.3,
                )
                for _ in batch_urls
            ]

            crawler = self.crawler
            if crawler is None:
                await scheduler.schedule(
                    quickLog,
                    params={
                        "level": "error",
                        "message": "Crawler is not initilized... src:web_crawler:128",
                        "module": ["CRAWLER", "UTILS"],
                        "urgency": "critical",
                    },
                )
                raise RuntimeError("Crawler is not initialized")

            # Scale timeout with batch size: 15s per URL, minimum 30s
            batch_timeout = max(30.0, len(batch_urls) * 15.0)

            try:
                async with asyncio.timeout(batch_timeout):
                    batch_result_obj: Any = await crawler.arun_many(
                        urls=batch_urls,
                        configs=run_configs,
                    )

                    if hasattr(batch_result_obj, "__aiter__"):
                        batch_results = [result async for result in batch_result_obj]
                    elif hasattr(batch_result_obj, "_results"):
                        batch_results = list(batch_result_obj._results)
                    else:
                        batch_results = list(batch_result_obj)
            except asyncio.TimeoutError:
                await scheduler.schedule(
                    quickLog,
                    params={
                        "level": "error",
                        "message": f"⚠️ Batch timeout after {batch_timeout}s - skipping remaining in batch src:web_crawler:154",
                        "module": ["CRAWLER"],
                        "urgency": "critical",
                    },
                )
                # Mark remaining as timeout (approximate)
                for u in batch_urls:
                    all_results.append(
                        {
                            "url": u,
                            "status": "timeout",
                            "title": None,
                            "description": None,
                            "favicon": None,
                            "banner_image": None,
                            "markdown": None,
                            "crawling_time_sec": batch_timeout,
                            "error": f"Hard timeout after {batch_timeout} seconds",
                        }
                    )
                continue  # next batch

            for result in batch_results:
                meta = _normalize_metadata(result.metadata, result.url)

                status = "success" if result.success else "fail"
                if result.error_message and "timeout" in result.error_message.lower():
                    status = "timeout"

                desc = meta.get("description") or (
                    result.markdown[:300] if result.markdown else None
                )

                all_results.append(
                    {
                        "url": result.url,
                        "status": status,
                        "title": meta.get("title"),
                        "description": desc,
                        "favicon": meta.get("favicon"),
                        "banner_image": meta.get("banner_image"),
                        "markdown": result.markdown if result.success else None,
                        "crawling_time_sec": round(time.time() - start_all, 3),
                        "error": result.error_message if not result.success else None,
                    }
                )
        await scheduler.schedule(
            quickLog,
            params={
                "level": "info",
                "message": f"✅ Finished {len(urls)} URLs in {round(time.time() - start_all, 2)} s src:web_crawler:204",
                "module": ["CRAWLER"],
                "urgency": "none",
            },
        )

        return all_results


# Global Singleton Engine
_engine: Optional[CrawlerEngine] = None


async def init_crawler_engine(batch_size: int = 10, concurrency: int = 8):
    """Initialize the crawler engine. Call this during server startup."""
    global _engine
    if _engine is None:
        _engine = CrawlerEngine(batch_size=batch_size, concurrency=concurrency)
        await _engine.start()
        await scheduler.schedule(
            quickLog,
            params={
                "level": "info",
                "message": "CrawlerEngine initialized globally on server startup. src:web_crawler:227",
                "module": ["CRAWLER"],
                "urgency": "none",
            },
        )


async def close_crawler_engine():
    """Close the crawler engine. Call this during server shutdown."""
    global _engine
    if _engine is not None:
        await _engine.stop()
        _engine = None
        await scheduler.schedule(
            quickLog,
            params={
                "level": "info",
                "message": "CrawlerEngine closed gracefully on server shutdown. src:web_crawler:244",
                "module": ["CRAWLER"],
                "urgency": "none",
            },
        )


async def get_crawler_engine(
    batch_size: int = 10,
    concurrency: int = 8,
) -> CrawlerEngine:
    """Get the active crawler engine. Initializes it if not already running."""
    global _engine
    if _engine is None:
        await scheduler.schedule(
            quickLog,
            params={
                "level": "info",
                "message": "Initializing the Engine & Starting crawl of URLs src:web_crawler:262",
                "module": ["CRAWLER", "UTILS"],
                "urgency": "none",
            },
        )
        await init_crawler_engine(batch_size=batch_size, concurrency=concurrency)

    if _engine is None:
        await scheduler.schedule(
            quickLog,
            params={
                "level": "error",
                "message": "Failed to initialize CrawlerEngine src:web_crawler:274",
                "module": ["CRAWLER"],
                "urgency": "critical",
            },
        )
        raise RuntimeError("Failed to initialize CrawlerEngine")

    return _engine


async def crawl_urls(
    urls: List[str],
    batch_size: int = 10,
    concurrency: int = 8,
) -> List[Dict[str, Any]]:
    await scheduler.schedule(
        quickLog,
        params={
            "level": "info",
            "message": f"Initilizing the Engine & Starting crawl of {len(urls)} URLs src:web_crawler:293",
            "module": ["CRAWLER", "UTILS"],
            "urgency": "none",
        },
    )
    engine = await get_crawler_engine(batch_size=batch_size, concurrency=concurrency)
    return await engine.crawl_batch(urls)
