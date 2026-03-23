"""
tools.py — Deep Researcher v2 Research Tools
=============================================
Implements the concrete tool handlers used by the ReAct reasoning engine.
Each tool is an async callable that receives structured parameters and
returns a ``ToolResult``.

Architecture
------------
::

    ReActEngine
        │  selects tool from ToolRegistry
        ▼
    ToolHandler.execute(params)
        │  calls ExternalServices / SearchEngine / IngestionService
        ▼
    ToolResult  { success, data, error, duration_sec }

## Description

Registry of research tools available to the ReAct engine, including
WebSearch, Summarizer, DocumentSearch, SemanticSearch, YouTubeSearch,
ImageUnderstanding, WebScrape, and ArtifactGenerator.

## Side Effects

- Individual tools make HTTP requests, vector DB queries, and LLM calls.
- Background ingestion tasks are scheduled via the task scheduler.

## Customization

Add new tools by subclassing ``BaseTool`` and registering in ``TOOL_REGISTRY``.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from main.src.research.external_services import ExternalServices
from main.src.research.models import ToolName, ToolResult

_log = logging.getLogger(__name__)


# ===========================================================================
# Base tool interface
# ===========================================================================


class BaseTool(ABC):
    """
    ## Description

    Abstract base class for all research tools. Each tool must implement
    ``execute()`` which receives a parameter dict and returns a ``ToolResult``.

    ## Parameters

    - `services` (`ExternalServices`) — Shared HTTP client for API calls.
    - `api_key` (`str`) — Gemini API key for LLM-backed tools.

    ## Returns

    `BaseTool` instance.

    ## Customization

    Subclass and register in ``TOOL_REGISTRY`` to add new capabilities.
    """

    name: ToolName
    description: str = ""

    def __init__(self, services: ExternalServices, api_key: str = "") -> None:
        self.services = services
        self.api_key = api_key

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        ## Description

        Execute the tool with the given parameters.

        ## Parameters

        - `params` (`Dict[str, Any]`)
          - Description: Tool-specific input parameters.
          - Constraints: Keys vary by tool implementation.

        ## Returns

        `ToolResult` — Encapsulated execution outcome.
        """
        ...

    def _make_result(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        duration: float = 0.0,
    ) -> ToolResult:
        """
        ## Description

        Helper factory for constructing ``ToolResult`` instances
        with the tool's name pre-filled.

        ## Parameters

        - `success` (`bool`) — Whether the tool succeeded.
        - `data` (`Any`) — Output payload.
        - `error` (`Optional[str]`) — Error description if failed.
        - `duration` (`float`) — Execution wall-clock seconds.

        ## Returns

        `ToolResult` instance.
        """
        return ToolResult(
            tool=self.name,
            success=success,
            data=data,
            error=error,
            duration_sec=duration,
        )


# ===========================================================================
# Tool implementations
# ===========================================================================


class WebSearchTool(BaseTool):
    """
    ## Description

    Searches the web via SearXNG → crawl4ai pipeline. Returns
    scraped page content with metadata.

    ## Parameters

    - `query` (`str`) — Search query.
    - `max_urls` (`int`, optional) — Max results. Default: 10.
    - `origin_research_id` (`str`, optional) — Session traceability.

    ## Returns

    `ToolResult` with ``data`` as ``List[Dict]`` of scraped pages.
    """

    name = ToolName.WEB_SEARCH
    description = "Search the web and scrape results using SearXNG and crawl4ai"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        query = params.get("query", "")
        max_urls = params.get("max_urls", 10)
        research_id = params.get("origin_research_id")

        if not query:
            return self._make_result(False, error="query is required")

        try:
            results = await self.services.search_web(
                query=query,
                max_urls=max_urls,
                origin_research_id=research_id,
            )
            return self._make_result(
                success=True,
                data=results,
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[WebSearchTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


class WebScrapeTool(BaseTool):
    """
    ## Description

    Scrapes specific URLs via the crawl4ai pipeline.

    ## Parameters

    - `urls` (`List[str]`) — URLs to scrape.
    - `origin_research_id` (`str`, optional) — Session traceability.

    ## Returns

    `ToolResult` with ``data`` as ``List[Dict]`` of scraped pages.
    """

    name = ToolName.WEB_SCRAPE
    description = "Scrape specific URLs using crawl4ai"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        urls = params.get("urls", [])
        research_id = params.get("origin_research_id")

        if not urls:
            return self._make_result(False, error="urls list is required")

        try:
            results = await self.services.scrape_urls(
                urls=urls,
                origin_research_id=research_id,
            )
            return self._make_result(
                success=True,
                data=results,
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[WebScrapeTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


class SummarizerTool(BaseTool):
    """
    ## Description

    Summarizes content relative to a query using the Gemini-powered
    ``/summarize`` endpoint.

    ## Parameters

    - `query` (`str`) — Research query providing context.
    - `content` (`str`) — Raw text to summarize.
    - `origin_research_id` (`str`, optional) — Session traceability.

    ## Returns

    `ToolResult` with ``data`` as the summary string.
    """

    name = ToolName.SUMMARIZER
    description = "Summarize content relative to a query using Gemini LLM"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        query = params.get("query", "")
        content = params.get("content", "")
        research_id = params.get("origin_research_id")

        if not content:
            return self._make_result(False, error="content is required")

        try:
            summary = await self.services.summarize(
                query=query,
                content=content,
                api_key=self.api_key,
                origin_research_id=research_id,
            )
            return self._make_result(
                success=True,
                data=summary,
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[SummarizerTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


class DocumentSearchTool(BaseTool):
    """
    ## Description

    Searches the local document vector store (PDFs collection)
    using semantic similarity via ChromaDB + Ollama embeddings.

    ## Parameters

    - `query` (`str`) — Natural language query.
    - `n_results` (`int`, optional) — Max results. Default: 10.

    ## Returns

    `ToolResult` with ``data`` as ``MergedContext.to_dict()``.

    ## Side Effects

    - Reads from the ChromaDB ``pdfs`` collection.
    """

    name = ToolName.DOCUMENT_SEARCH
    description = "Search ingested documents (PDFs) using semantic vector search"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        query = params.get("query", "")
        n_results = params.get("n_results", 10)

        if not query:
            return self._make_result(False, error="query is required")

        try:
            from main.src.store.vector.SearchEngine import search_engine

            context = await search_engine.search(
                query=query,
                collections=["pdfs"],
                n_results=n_results,
            )
            return self._make_result(
                success=True,
                data=context.to_dict(),
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[DocumentSearchTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


class SemanticSearchTool(BaseTool):
    """
    ## Description

    Performs semantic search across ALL vector collections
    (websites, PDFs, images, custom) using ChromaDB + Ollama.

    ## Parameters

    - `query` (`str`) — Natural language query.
    - `collections` (`List[str]`, optional) — Target collections.
      Default: all collections.
    - `n_results` (`int`, optional) — Max results per collection. Default: 10.

    ## Returns

    `ToolResult` with ``data`` as ``MergedContext.to_dict()``.

    ## Side Effects

    - Fan-out queries to multiple ChromaDB collections.
    """

    name = ToolName.SEMANTIC_SEARCH
    description = "Search all vector store collections with semantic similarity"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        query = params.get("query", "")
        collections = params.get("collections")
        n_results = params.get("n_results", 10)

        if not query:
            return self._make_result(False, error="query is required")

        try:
            from main.src.store.vector.SearchEngine import search_engine

            context = await search_engine.search(
                query=query,
                collections=collections,
                n_results=n_results,
            )
            return self._make_result(
                success=True,
                data=context.to_dict(),
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[SemanticSearchTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


class YouTubeSearchTool(BaseTool):
    """
    ## Description

    Searches YouTube for relevant videos using SearXNG's video
    category filter with the YouTube engine.

    ## Parameters

    - `query` (`str`) — Video search query.
    - `max_results` (`int`, optional) — Max videos. Default: 5.

    ## Returns

    `ToolResult` with ``data`` as ``List[Dict]`` of video metadata.
    """

    name = ToolName.YOUTUBE_SEARCH
    description = "Search YouTube for relevant videos via SearXNG"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        query = params.get("query", "")
        max_results = params.get("max_results", 5)

        if not query:
            return self._make_result(False, error="query is required")

        try:
            videos = await self.services.search_youtube(query, max_results)
            return self._make_result(
                success=True,
                data=videos,
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[YouTubeSearchTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


class ImageUnderstandingTool(BaseTool):
    """
    ## Description

    Searches for relevant images via SearXNG and performs basic
    image understanding by collecting metadata. For deeper analysis,
    images can be ingested into the vector store via SigLIP.

    ## Parameters

    - `query` (`str`) — Image search query.
    - `max_results` (`int`, optional) — Max images. Default: 5.

    ## Returns

    `ToolResult` with ``data`` as ``List[Dict]`` of image metadata.
    """

    name = ToolName.IMAGE_UNDERSTANDING
    description = "Search and analyze images related to the query"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        t0 = time.perf_counter()
        query = params.get("query", "")
        max_results = params.get("max_results", 5)

        if not query:
            return self._make_result(False, error="query is required")

        try:
            images = await self.services.search_images(query, max_results)
            return self._make_result(
                success=True,
                data=images,
                duration=time.perf_counter() - t0,
            )
        except Exception as exc:
            _log.error("[ImageUnderstandingTool] %s", exc)
            return self._make_result(
                False, error=str(exc), duration=time.perf_counter() - t0
            )


# ===========================================================================
# Tool Registry
# ===========================================================================

TOOL_CLASSES: Dict[ToolName, Type[BaseTool]] = {
    ToolName.WEB_SEARCH: WebSearchTool,
    ToolName.WEB_SCRAPE: WebScrapeTool,
    ToolName.SUMMARIZER: SummarizerTool,
    ToolName.DOCUMENT_SEARCH: DocumentSearchTool,
    ToolName.SEMANTIC_SEARCH: SemanticSearchTool,
    ToolName.YOUTUBE_SEARCH: YouTubeSearchTool,
    ToolName.IMAGE_UNDERSTANDING: ImageUnderstandingTool,
}


class ToolRegistry:
    """
    ## Description

    Manages instantiation and lookup of tool handlers. Provides a
    formatted tool description string for the ReAct engine's system prompt.

    ## Parameters

    - `services` (`ExternalServices`) — Shared HTTP client.
    - `api_key` (`str`) — Gemini API key for LLM-backed tools.

    ## Returns

    `ToolRegistry` instance.

    ## Customization

    Register additional tools by adding to ``TOOL_CLASSES`` mapping.
    """

    def __init__(self, services: ExternalServices, api_key: str = "") -> None:
        self._tools: Dict[ToolName, BaseTool] = {}
        for tool_name, tool_cls in TOOL_CLASSES.items():
            self._tools[tool_name] = tool_cls(services=services, api_key=api_key)

    def get(self, tool_name: ToolName) -> Optional[BaseTool]:
        """
        ## Description

        Retrieve a tool handler by its enum name.

        ## Parameters

        - `tool_name` (`ToolName`) — The tool to retrieve.

        ## Returns

        `Optional[BaseTool]` — The tool instance, or None if not found.
        """
        return self._tools.get(tool_name)

    def get_tool_descriptions(self) -> str:
        """
        ## Description

        Generates a formatted string describing all available tools,
        suitable for injection into the ReAct engine's system prompt.

        ## Parameters

        - None

        ## Returns

        `str` — Multi-line tool description block.
        """
        lines: List[str] = []
        for name, tool in self._tools.items():
            lines.append(f"- **{name.value}**: {tool.description}")
        return "\n".join(lines)

    @property
    def available_tools(self) -> List[str]:
        """
        ## Description

        Returns a list of all registered tool names as strings.

        ## Returns

        `List[str]`
        """
        return [t.value for t in self._tools.keys()]
