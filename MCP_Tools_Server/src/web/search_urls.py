import asyncio
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

BASE_DIR = Path(__file__).resolve().parent


class SearXNGClient:
    def __init__(
        self,
        base_url="http://localhost:8080",
        max_connections=50,
        max_concurrent_requests=5,
    ):
        self.base_url = base_url.rstrip("/")

        # 🔥 concurrency limiter (ANTI-DDOS MODE)
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

        # 🔄 user-agent rotation
        self._user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
            "Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
        ]

        # ⚡ connection pooling
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=20,
            ),
        )

    async def _search_async(self, query: str) -> Optional[Dict[str, Any]]:
        async with self._semaphore:  # 🚦 rate limiting
            headers = {
                "User-Agent": random.choice(self._user_agents),
                "Accept": "application/json",
            }

            retries = 2

            for attempt in range(retries + 1):
                try:
                    await scheduler.schedule(
                        quickLog,
                        params={
                            "level": "info",
                            "message": f"Try {attempt + 1}: Collecting URLs {query} src:search_urls:62",
                            "module": ["CRAWLER"],
                            "urgency": "none",
                        },
                    )
                    response = await self._client.get(
                        "/search",
                        params={"q": query, "format": "json"},
                        headers=headers,
                    )

                    response.raise_for_status()
                    return response.json()

                except Exception as e:
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (attempt + 1))  # ⏳ backoff
                    else:
                        await scheduler.schedule(
                            quickLog,
                            params={
                                "level": "info",
                                "message": f"Try {attempt + 1}: Collecting URLs {query} src:search_urls:84",
                                "module": ["CRAWLER"],
                                "urgency": "none",
                            },
                        )
                        print(f"[ERROR] {query} -> {e}")
                        return None

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for contexts that do not already run an event loop."""
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                "SearXNGClient.search() cannot be called from a running event loop. "
                "Use await _search_async(...) or await search_parallel_async(...)."
            )
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise
            return asyncio.run(self._search_async(query))

    def search_parallel(self, queries: List[str]):
        """Sync wrapper for contexts that do not already run an event loop."""
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                "SearXNGClient.search_parallel() cannot be called from a running event loop. "
                "Use await search_parallel_async(...)."
            )
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise
            return asyncio.run(self.search_parallel_async(queries))

    async def search_parallel_async(self, queries: List[str]):
        """Fully async parallel search for async server flows."""
        tasks = [self._search_async(q) for q in queries]
        await scheduler.schedule(
            quickLog,
            params={
                "level": "info",
                "message": f"Queries: {queries} src:search_urls:async",
                "module": ["CRAWLER"],
                "urgency": "none",
            },
        )
        return await asyncio.gather(*tasks)

    async def search_fire_and_forget(self, query: str):
        """🔥 non-blocking trigger"""
        asyncio.create_task(self._search_async(query))

    async def close(self):
        await self._client.aclose()
