import json
from typing import Any, AsyncIterator, Optional

import httpx

from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import quickLog
from main.sse.event_bus import event_bus

API_BASE_URL = "http://localhost:8001/"


async def _post_query_stream(
    path: str, payload: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Internal helper to perform asynchronous SSE streaming POST requests to the Agent Server.

    ## Parameters

    - `path` (`str`)
      - Description: API endpoint path (e.g., "scrape/urls").
    - `payload` (`dict[str, Any]`)
      - Description: JSON payload for the request.

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": bool,
        "type": "start | progress | result | done | error",
        "message": "string",
        "...": "additional fields"
    }
    ```

    ## Raises

    - `httpx.HTTPError`
      - When the request fails.

    ## Side Effects

    - Opens a persistent HTTP connection.
    - Consumes memory via buffered SSE chunks.
    """
    url = f"{API_BASE_URL}{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream(
                "POST", url, json=payload, headers={"Accept": "text/event-stream"}
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        raw = line[6:].strip()
                        if not raw:
                            continue
                        try:
                            yield json.loads(raw)
                        except json.JSONDecodeError as exc:
                            yield {
                                "success": False,
                                "type": "error",
                                "message": f"Bad SSE JSON: {raw[:100]}...",
                                "error": str(exc),
                            }
        except Exception as exc:
            yield {
                "success": False,
                "type": "error",
                "message": f"Transport error: {str(exc)}",
            }


async def _post_query(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    ## Description

    Internal helper to perform asynchronous standard POST requests to the Agent Server.

    ## Parameters

    - `path` (`str`)
      - Description: API endpoint path (e.g., "imageSearch").
    - `payload` (`dict[str, Any]`)
      - Description: JSON payload for the request.

    ## Returns

    `dict[str, Any]`

    ## Raises

    - `httpx.HTTPError`
      - When the request fails.

    ## Debug Notes

    - Logs errors via `quickLog`.
    """
    url = f"{API_BASE_URL}{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"HTTP error while posting to {url}: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )
            return {"success": False, "error": str(exc)}


async def scrape_urls(
    urls: list[str], max_concurrent_batches: int = 3, research_id: Optional[str] = None
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Scrape specific URLs directly using the pre-warmed crawl4ai engine.

    ## Parameters

    - `urls` (`list[str]`)
      - Description: List of URLs to scrape.
    - `max_concurrent_batches` (`int`)
      - Description: Maximum batches to process in parallel.
    - `research_id` (`str | None`)
      - Description: Optional ID to associate with the research.

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "url": "https://example.com",
        "content": "markdown string",
        "title": "Example",
        "metadata": {}
    }
    ```

    ## Side Effects

    - Broadcasts progress events via `event_bus`.
    """
    payload = {
        "urls": urls,
        "max_concurrent_scrape_batches": max_concurrent_batches,
        "origin_research_id": research_id,
    }
    async for event in _post_query_stream("scrape/urls", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {"msg": event.get("message", "Scraping..."), "research": research_id}
            )
        yield event


async def search_and_scrape(
    query: str,
    max_urls: int = 10,
    max_concurrent_batches: int = 3,
    research_id: Optional[str] = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Search through SearXNG and automatically scrape the resulting URLs.

    ## Parameters

    - `query` (`str`)
      - Description: The search query.
    - `max_urls` (`int`)
      - Description: Max URLs to find and scrape.
    - `max_concurrent_batches` (`int`)
      - Description: Concurrency level.
    - `research_id` (`str | None`)
      - Description: Association ID.

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "type": "start | progress | item | done | error",
        "url": "https://example.com",
        "content": "markdown...",
        "title": "Page Title"
    }
    ```
    """
    payload = {
        "query": query,
        "max_no_url": max_urls,
        "max_concurrent_scrape_batches": max_concurrent_batches,
        "origin_research_id": research_id,
    }
    async for event in _post_query_stream("scrape/search", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {
                    "msg": event.get("message", f"Searching for: {query}"),
                    "research": research_id,
                }
            )
        yield event


async def web_search(
    query: str, max_urls: int = 10, research_id: Optional[str] = None
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Proxy for general web queries, identical to search_and_scrape.

    ## Parameters

    - `query` (`str`)
    - `max_urls` (`int`)
    - `research_id` (`str | None`)

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "type": "start | progress | item | done | error",
        "url": "https://example.com",
        "content": "markdown..."
    }
    ```
    """
    payload = {"query": query, "max_no_url": max_urls}
    async for event in _post_query_stream("webSearch", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {
                    "msg": event.get("message", "Broad search..."),
                    "research": research_id,
                }
            )
        yield event


async def summarize_content(
    query: str, content: str, api_key: str, research_id: Optional[str] = None
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Summarize raw text via Gemini given a research query.

    ## Parameters

    - `query` (`str`)
      - Description: Use this query context for the summary.
    - `content` (`str`)
      - Description: Raw text to summarize.
    - `api_key` (`str`)
      - Description: Gemini API key.
    - `research_id` (`str | None`)

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "type": "result",
        "summary": "This text discusses..."
    }
    ```
    """
    payload = {"query": query, "content": content, "api_key": api_key}
    async for event in _post_query_stream("summarize", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {"msg": "Generating summary...", "research": research_id}
            )
        yield event


async def validate_query(
    query: str, api_key: str, research_id: Optional[str] = None
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Safety check and normalization for research queries.

    ## Parameters

    - `query` (`str`)
    - `api_key` (`str`)
    - `research_id` (`str | None`)

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "type": "result",
        "is_safe": true,
        "issue": [],
        "safe_prompt": "Answer safely: ..."
    }
    ```
    """
    payload = {"query": query, "api_key": api_key}
    async for event in _post_query_stream("query/validate", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {"msg": "Validating safety and intent...", "research": research_id}
            )
        yield event


async def process_document(
    urls: list[str],
    summarize: bool = False,
    ollama_url: str = "http://localhost:11434/api/generate",
    research_id: Optional[str] = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Parse and optionally summarize multiple documents from a list of URLs.

    ## Parameters

    - `urls` (`list[str]`)
      - Description: List of document URLs (PDF/DOCX) to process.
    - `summarize` (`bool`)
      - Description: Whether to summarize the extracted text.
    - `ollama_url` (`str`)
    - `research_id` (`str | None`)
      - Description: Origin research ID for context and broadcasting.

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "type": "result",
        "filename": "document.pdf",
        "filetype": "pdf | docx",
        "summarized": true,
        "summary": "...",
        "content": "...",
        "url": "..."
    }
    ```
    """
    payload = {
        "urls": urls,
        "summarize": summarize,
        "ollama_url": ollama_url,
        "origin_research_id": research_id,
    }
    async for event in _post_query_stream("process-document", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {
                    "msg": event.get("message", "Processing documents..."),
                    "research": research_id,
                }
            )
        yield event


async def search_images(query: str, num_results: int = 5) -> dict[str, Any]:
    """
    ## Description

    Fetch image references from SearXNG.

    ## Parameters

    - `query` (`str`)
    - `num_results` (`int`)

    ## Returns

    `dict[str, Any]`

    Structure:

    ```json
    {
        "success": true,
        "query": "string",
        "results": [
            { "title": "...", "url": "...", "img_src": "..." }
        ]
    }
    ```
    """
    payload = {"query": query, "num_results": num_results}
    return await _post_query("imageSearch", payload)


async def search_news(query: str, num_results: int = 5) -> dict[str, Any]:
    """
    ## Description

    Fetch targeted news articles.

    ## Parameters

    - `query` (`str`)
    - `num_results` (`int`)

    ## Returns

    `dict[str, Any]`

    Structure:

    ```json
    {
        "success": true,
        "results": [
            { "title": "...", "url": "...", "content": "..." }
        ]
    }
    ```
    """
    payload = {"query": query, "num_results": num_results}
    return await _post_query("newsSearch", payload)


async def search_youtube(
    query: str,
    mode: str = "summarize",
    max_videos: int = 3,
    summarize: bool = False,
    ollama_url: str = "http://localhost:11434/api/generate",
    ollama_model: str = "qwen3.5:9b",
) -> dict[str, Any]:
    """
    ## Description

    Search and process YouTube videos (metadata, transcripts, summaries).

    ## Parameters

    - `query` (`str`)
    - `mode` (`str`)
      - Constraints: summarize, search_only, video_data, transcript, full_bundle.
    - `max_videos` (`int`)
    - `summarize` (`bool`)
      - Description: If True, executes LLM summarization.
    - `ollama_url` (`str`)
    - `ollama_model` (`str`)

    ## Returns

    `dict[str, Any]`

    Structure:

    ```json
    {
        "success": true,
        "mode": "summarize",
        "results": [
            {
                "id": "...",
                "title": "...",
                "thumbnail": "...",
                "summary": "..."
            }
        ]
    }
    ```
    """
    payload = {
        "query": query,
        "mode": mode,
        "max_videos": max_videos,
        "summarize": summarize,
        "ollama_url": ollama_url,
        "ollama_model": ollama_model,
    }
    return await _post_query("youtubeSearch", payload)


async def search_local_knowledge(
    context: str, top_k: int = 5, research_id: Optional[str] = None
) -> AsyncIterator[dict[str, Any]]:
    """
    ## Description

    Search through local knowledge base.

    ## Parameters

    - `context` (`str`)
      - Description: The context to search for.
    - `top_k` (`int`)
      - Description: Number of results to return.
    - `research_id` (`str | None`)
      - Description: Association ID.

    ## Returns

    `AsyncIterator[dict[str, Any]]`

    Structure:

    ```json
    {
        "success": true,
        "type": "start | progress | item | done | error",
        "url": "https://example.com",
        "content": "markdown..."
    }
    ```
    """
    payload = {"context": context, "origin_research_id": research_id}
    async for event in _post_query_stream("localKnowledgeSearch", payload):
        if event.get("type") == "progress":
            await event_bus.broadcast(
                {
                    "msg": event.get("message", "Searching local knowledge..."),
                    "research": research_id,
                }
            )
        yield event
