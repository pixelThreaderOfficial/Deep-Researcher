"""
external_services.py — Deep Researcher v2
==========================================
HTTP client layer that bridges the research orchestrator with the
application's existing API endpoints (scrape, summarize, validate)
and external services (SearXNG, YouTube, image search).

All methods are async and use ``httpx`` for non-blocking I/O.

## Description

Provides a unified interface for the research pipeline to interact
with web scraping, summarization, query validation, YouTube search,
and image search services.

## Side Effects

- Makes outgoing HTTP requests to internal and external APIs.
- Logs all API interactions via the standard logging infrastructure.

## Customization

Update ``SERVICES_BASE_URL`` or individual endpoint URLs to
point to different deployment targets.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVICES_BASE_URL = os.getenv("SERVICES_BASE_URL", "http://localhost:8001")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8081")
YOUTUBE_API_BASE = os.getenv("YOUTUBE_API_BASE", "https://www.googleapis.com/youtube/v3")


class ExternalServices:
    """
    ## Description

    Async HTTP client for all external service interactions required
    by the research pipeline. Wraps internal endpoints (scrape, summarize,
    validate) and external search APIs (SearXNG, YouTube, images).

    ## Parameters

    - None (uses environment variables for configuration).

    ## Returns

    `ExternalServices` instance.

    ## Side Effects

    - Creates and manages ``httpx.AsyncClient`` instances per request.
    - Logs all outbound API calls.

    ## Customization

    Override ``base_url`` or individual method URLs via env vars.
    """

    def __init__(self) -> None:
        self.base_url: str = SERVICES_BASE_URL
        self.timeout: float = float(os.getenv("SERVICES_TIMEOUT", "120"))

    # ------------------------------------------------------------------
    # Internal: Query Validation
    # ------------------------------------------------------------------

    async def validate_query(self, query: str, api_key: str) -> Dict[str, Any]:
        """
        ## Description

        Validates a user query for safety (prompt injection, harmful content)
        by calling the ``/query/validate`` SSE endpoint and collecting all
        events until ``done`` or ``error``.

        ## Parameters

        - `query` (`str`)
          - Description: The raw user query to validate.
          - Constraints: Must be non-empty.
          - Example: ``"What is quantum computing?"``

        - `api_key` (`str`)
          - Description: Gemini API key for the validation model.
          - Constraints: Must be a valid API key string.

        ## Returns

        `dict`

        Structure:

        ```json
        {
            "is_safe": true,
            "refined_query": "sanitized version of the query",
            "issues": [],
            "summary": "Query asks about quantum computing."
        }
        ```

        ## Raises

        - `httpx.HTTPStatusError` — When the upstream returns a non-2xx status.

        ## Side Effects

        - Makes HTTP POST to ``/query/validate`` SSE endpoint.
        """
        _log.info("[ExternalServices] Validating query: %s", query[:80])
        result: Dict[str, Any] = {
            "is_safe": True,
            "refined_query": query,
            "issues": [],
            "summary": "",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/query/validate",
                    json={"query": query, "api_key": api_key},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        if event.get("type") == "result":
                            result["is_safe"] = event.get("is_safe", True)
                            result["refined_query"] = event.get("safe_prompt", query)
                            result["issues"] = event.get("issue", [])
                            result["summary"] = event.get("summary", "")
                        if event.get("type") in ("done", "error"):
                            break
        except Exception as exc:
            _log.error("[ExternalServices] validate_query failed: %s", exc)
            result["is_safe"] = True
            result["refined_query"] = query

        return result

    # ------------------------------------------------------------------
    # Internal: Web Search + Scrape (SearXNG → crawl4ai)
    # ------------------------------------------------------------------

    async def search_web(
        self,
        query: str,
        max_urls: int = 10,
        origin_research_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        ## Description

        Searches the web via the ``/scrape/search`` SSE endpoint (SearXNG +
        crawl4ai pipeline) and collects all scraped page items.

        ## Parameters

        - `query` (`str`)
          - Description: Natural language search query for SearXNG.
          - Constraints: Must be non-empty.
          - Example: ``"latest AI research breakthroughs 2026"``

        - `max_urls` (`int`)
          - Description: Maximum number of URLs to scrape from search results.
          - Constraints: Must be >= 1.

        - `origin_research_id` (`Optional[str]`)
          - Description: Research session ID for traceability.

        ## Returns

        `List[Dict[str, Any]]`

        Structure:

        ```json
        [
            {
                "url": "https://example.com",
                "content": "# Page markdown content...",
                "title": "Page Title",
                "no_words": 1234
            }
        ]
        ```

        ## Raises

        - `httpx.HTTPStatusError` — On non-2xx upstream responses.

        ## Side Effects

        - Long-running SSE stream consuming search + scrape results.
        """
        _log.info("[ExternalServices] search_web: query='%s' max=%d", query[:60], max_urls)
        results: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/scrape/search",
                    json={
                        "query": query,
                        "max_no_url": max_urls,
                        "max_concurrent_scrape_batches": 3,
                        "origin_research_id": origin_research_id,
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        if event.get("success") and event.get("content"):
                            results.append({
                                "url": event.get("url", ""),
                                "content": event.get("content", ""),
                                "title": event.get("title", ""),
                                "no_words": event.get("no_words", 0),
                                "favicon": event.get("favicon", ""),
                                "scrape_duration": event.get("scrape_duration", 0),
                                "metadata": event.get("metadata", {}),
                            })
                        if event.get("type") in ("done", "error"):
                            break
        except Exception as exc:
            _log.error("[ExternalServices] search_web failed: %s", exc)

        _log.info("[ExternalServices] search_web returned %d results", len(results))
        return results

    # ------------------------------------------------------------------
    # Internal: Scrape specific URLs
    # ------------------------------------------------------------------

    async def scrape_urls(
        self,
        urls: List[str],
        origin_research_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        ## Description

        Scrapes a list of specific URLs via the ``/scrape/urls`` SSE endpoint
        using crawl4ai and collects all scraped page items.

        ## Parameters

        - `urls` (`List[str]`)
          - Description: URLs to scrape.
          - Constraints: Must contain at least one valid URL.

        - `origin_research_id` (`Optional[str]`)
          - Description: Research session ID for traceability.

        ## Returns

        `List[Dict[str, Any]]`

        Each item follows the same structure as ``search_web`` results.

        ## Side Effects

        - Makes HTTP POST to ``/scrape/urls`` SSE endpoint.
        """
        _log.info("[ExternalServices] scrape_urls: %d urls", len(urls))
        results: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/scrape/urls",
                    json={
                        "urls": urls,
                        "max_concurrent_scrape_batches": 3,
                        "origin_research_id": origin_research_id,
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        if event.get("success") and event.get("content"):
                            results.append({
                                "url": event.get("url", ""),
                                "content": event.get("content", ""),
                                "title": event.get("title", ""),
                                "no_words": event.get("no_words", 0),
                                "favicon": event.get("favicon", ""),
                                "scrape_duration": event.get("scrape_duration", 0),
                                "metadata": event.get("metadata", {}),
                            })
                        if event.get("type") in ("done", "error"):
                            break
        except Exception as exc:
            _log.error("[ExternalServices] scrape_urls failed: %s", exc)

        return results

    # ------------------------------------------------------------------
    # Internal: Summarization
    # ------------------------------------------------------------------

    async def summarize(
        self,
        query: str,
        content: str,
        api_key: str,
        origin_research_id: Optional[str] = None,
    ) -> str:
        """
        ## Description

        Summarizes content relative to a query by calling the ``/summarize``
        SSE endpoint (Gemini-powered).

        ## Parameters

        - `query` (`str`)
          - Description: The research query providing context for summarization.
          - Constraints: Must be non-empty.

        - `content` (`str`)
          - Description: Raw text content to summarize.
          - Constraints: Must be non-empty.

        - `api_key` (`str`)
          - Description: Gemini API key.

        - `origin_research_id` (`Optional[str]`)
          - Description: Research session ID for traceability.

        ## Returns

        `str` — The generated summary text.

        ## Side Effects

        - HTTP POST to ``/summarize`` SSE endpoint.
        """
        _log.info("[ExternalServices] summarize: query='%s' content_len=%d", query[:50], len(content))
        summary = ""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/summarize",
                    json={
                        "query": query,
                        "content": content,
                        "api_key": api_key,
                        "origin_research_id": origin_research_id,
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        if event.get("type") == "result":
                            summary = event.get("summary", "")
                        if event.get("type") in ("done", "error"):
                            break
        except Exception as exc:
            _log.error("[ExternalServices] summarize failed: %s", exc)
            summary = content[:500] + "... [summarization failed]"

        return summary

    # ------------------------------------------------------------------
    # External: YouTube Search via SearXNG
    # ------------------------------------------------------------------

    async def search_youtube(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        ## Description

        Searches for relevant YouTube videos using the SearXNG instance
        with the ``videos`` category filter.

        ## Parameters

        - `query` (`str`)
          - Description: Video search query string.
          - Constraints: Must be non-empty.

        - `max_results` (`int`)
          - Description: Maximum number of video results to return.
          - Constraints: Must be >= 1.

        ## Returns

        `List[Dict[str, str]]`

        Structure:

        ```json
        [
            { "title": "Video Title", "url": "https://youtube.com/..." }
        ]
        ```

        ## Side Effects

        - HTTP GET to SearXNG search API.
        """
        _log.info("[ExternalServices] search_youtube: query='%s'", query[:60])
        videos: List[Dict[str, str]] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{SEARXNG_URL}/search",
                    params={
                        "q": query,
                        "categories": "videos",
                        "engines": "youtube",
                        "format": "json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", [])[:max_results]:
                        videos.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "thumbnail": item.get("thumbnail", ""),
                        })
        except Exception as exc:
            _log.warning("[ExternalServices] search_youtube failed: %s", exc)

        return videos

    # ------------------------------------------------------------------
    # External: Image Search via SearXNG
    # ------------------------------------------------------------------

    async def search_images(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        ## Description

        Searches for relevant images using the SearXNG instance
        with the ``images`` category filter.

        ## Parameters

        - `query` (`str`)
          - Description: Image search query string.
          - Constraints: Must be non-empty.

        - `max_results` (`int`)
          - Description: Maximum number of image results.
          - Constraints: Must be >= 1.

        ## Returns

        `List[Dict[str, str]]`

        Structure:

        ```json
        [
            { "alt": "Image description", "url": "https://..." }
        ]
        ```

        ## Side Effects

        - HTTP GET to SearXNG search API with images category.
        """
        _log.info("[ExternalServices] search_images: query='%s'", query[:60])
        images: List[Dict[str, str]] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{SEARXNG_URL}/search",
                    params={
                        "q": query,
                        "categories": "images",
                        "format": "json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", [])[:max_results]:
                        images.append({
                            "alt": item.get("title", ""),
                            "url": item.get("img_src", item.get("url", "")),
                            "source": item.get("source", ""),
                        })
        except Exception as exc:
            _log.warning("[ExternalServices] search_images failed: %s", exc)

        return images
