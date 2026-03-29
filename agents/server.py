import json
from contextlib import asynccontextmanager
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from docParsers.pdfParser import (
    extract_pdf_to_md,
    extract_text_summarized as pdf_extract_summarized,
    bulk_extract_text_summarized as bulk_pdf_summarize,
    bulk_extract_pdf_to_md,
)
from docParsers.docsParser import (
    extract_docx_to_md,
    extract_text_summarized as docx_extract_summarized,
    bulk_extract_text_summarized as bulk_docx_summarize,
    bulk_extract_docx_to_md,
)
from query.query import run_query_validation
from sse.event_bus import event_bus
from summarizer.summarizer import run_summarizer
from utils.task_scheduler import scheduler
from web.imageSearch import search_images
from web.newsSearch import search_news
from web.scraper import read_pages, search_and_scrape_pages
from web.web_crawler import close_crawler_engine, init_crawler_engine
from web.youtubeSearch import (
    search_and_summarize as youtube_search_and_summarize,
    youtube_search,
    get_video_data,
    get_video_transcript,
)


# ─────────────────────────── LIFESPAN ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # -------- SERVER START --------
    await scheduler.start()
    await init_crawler_engine(batch_size=10, concurrency=8)

    yield

    # -------- SERVER SHUTDOWN --------
    await close_crawler_engine()
    await scheduler.shutdown()


# ─────────────────────────── APP SETUP ─────────────────────────────────────

app = FastAPI(title="Agent Server DRv2!", version="1.0.0", lifespan=lifespan)

# Include the scheme (http) and port. Add 127.0.0.1 as well if needed.
allowed_origins = [
    # frontend api requests
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # backend api requests
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:8000",
]

# Register CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # or ["*"] for all origins (not recommended for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────── SSE HELPERS ───────────────────────────────────

def format_sse(data: dict):
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────── REQUEST MODELS ────────────────────────────────

class ScrapeUrlsRequest(BaseModel):
    urls: list[str]
    max_urls: int | None = None
    max_concurrent_scrape_batches: int = 3
    origin_research_id: str | None = None


class SearchScrapeRequest(BaseModel):
    query: str
    # Cap for how many search result URLs we want to scrape.
    # If SearXNG returns fewer than this number, we scrape all returned URLs.
    max_no_url: int | None = None
    max_concurrent_scrape_batches: int = 3
    origin_research_id: str | None = None


class SummarizeRequest(BaseModel):
    query: str
    content: str
    api_key: str
    origin_research_id: str | None = None


class QueryValidateRequest(BaseModel):
    query: str
    api_key: str
    origin_research_id: str | None = None


class ImageSearchRequest(BaseModel):
    query: str
    num_results: int = 5
    timeout: float = 10.0
    origin_research_id: str | None = None


class NewsSearchRequest(BaseModel):
    query: str
    num_results: int = 5
    timeout: float = 10.0
    origin_research_id: str | None = None


class YouTubeSearchRequest(BaseModel):
    """
    Modes:

    summarize     → (DEFAULT) search + transcript + Ollama summary — primary use case
    search_only   → just search and return raw video list
    video_data    → return metadata for a single video_input
    transcript    → return transcript text for a single video_input
    full_bundle   → search + metadata + transcript in parallel (needs video_input + query)
    """

    query: str
    mode: Literal["summarize", "search_only", "video_data", "transcript", "full_bundle"] = "summarize"
    video_input: str | None = None  # URL or video-ID; required for video_data/transcript/full_bundle
    max_videos: int = 5             # for summarize mode
    summarize: bool = False         # if True, use Ollama; if False, return raw transcript
    ollama_url: str = "http://localhost:11434/api/generate"  # override for remote Ollama
    ollama_model: str = "qwen3.5:9b"
    origin_research_id: str | None = None


class WebSearchRequest(BaseModel):
    query: str
    max_no_url: int | None = None
    max_concurrent_scrape_batches: int = 3
    origin_research_id: str | None = None


class ProcessDocumentRequest(BaseModel):
    urls: list[str]
    summarize: bool = False
    ollama_url: str = "http://localhost:11434/api/generate"
    origin_research_id: str | None = None


# ─────────────────────────── SSE EVENT STREAM ──────────────────────────────

@app.get("/events/{client_id}")
async def stream(request: Request, client_id: str):
    """
    Persistent SSE channel — subscribe once, receive all broadcasts.

    Connect with:
        GET /events/{client_id}

    The server pushes JSON objects whenever any agent calls event_bus.broadcast().
    """
    queue = event_bus.register(client_id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                data = await queue.get()
                yield format_sse(data)

        finally:
            event_bus.unregister(client_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── SCRAPE ────────────────────────────────────────

@app.post("/scrape/urls")
async def scrape_urls(req: ScrapeUrlsRequest):
    """
    Scrape a list of URLs directly (no web search step).

    SSE response (text/event-stream):
    - type: "start"
    - one item per scraped page
    - type: "done"
    - type: "error" on failure

    Body example:
      {
        "urls": ["https://example.com"],
        "max_urls": null,
        "max_concurrent_scrape_batches": 3,
        "origin_research_id": null
      }
    """

    async def event_generator():
        yield format_sse(
            {
                "success": True,
                "type": "start",
                "message": f"Starting scrape of {len(req.urls)} urls",
            }
        )

        try:
            async for item in read_pages(
                req.urls,
                max_urls=req.max_urls,
                max_concurrent_scrape_batches=req.max_concurrent_scrape_batches,
                origin_research_id=req.origin_research_id,
            ):
                yield format_sse(item)
            yield format_sse(
                {
                    "success": True,
                    "type": "done",
                    "message": f"Finished scraping {len(req.urls)} urls",
                }
            )
        except Exception as e:
            yield format_sse(
                {
                    "success": False,
                    "type": "error",
                    "message": str(e),
                }
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/scrape/search")
async def scrape_search(req: SearchScrapeRequest):
    """
    Search URLs with SearXNG, then scrape them (crawl4ai).

    Semantics:
    - If `max_no_url` is set, we scrape up to that many URLs.
    - If the search returns fewer than `max_no_url`, we scrape all returned URLs.

    SSE response (text/event-stream):
    - type: "start"
    - then one scraped item per `data:` event
    - type: "done" at the end
    """

    async def event_generator():
        yielded_items = 0
        yield format_sse(
            {
                "success": True,
                "type": "start",
                "message": f"Searching & scraping for query: {req.query}",
            }
        )

        try:
            async for item in search_and_scrape_pages(
                [req.query],
                max_urls=req.max_no_url,
                max_concurrent_scrape_batches=req.max_concurrent_scrape_batches,
                queries_are_urls=False,
                origin_research_id=req.origin_research_id,
            ):
                yielded_items += 1
                yield format_sse(item)

            yield format_sse(
                {
                    "success": True,
                    "type": "done",
                    "message": (
                        f"Finished search+scrape stream. "
                        f"Yielded {yielded_items} scrape item(s)."
                    ),
                    "yielded_items": yielded_items,
                }
            )
        except Exception as e:
            yield format_sse(
                {
                    "success": False,
                    "type": "error",
                    "message": str(e),
                }
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── QUERY VALIDATION ──────────────────────────────

@app.post("/query/validate")
async def validate_query(req: QueryValidateRequest):
    """
    Validate and pre-process a user query for safety and sanitization.

    SSE response (text/event-stream):
    - type: "start"
    - type: "progress" — intermediate status updates
    - type: "result"   — the validation result
    - type: "done"     — stream finished
    - type: "error"    — on failure

    Body example:
      {
        "query": "What is the capital of France?",
        "api_key": "your-gemini-api-key",
        "origin_research_id": null
      }
    """

    async def event_generator():
        yield format_sse(
            {
                "success": True,
                "type": "start",
                "message": f"Starting query validation for: {req.query[:80]}",
            }
        )

        try:
            async for item in run_query_validation(
                query=req.query,
                api_key=req.api_key,
                origin_research_id=req.origin_research_id,
            ):
                yield format_sse(item)

            yield format_sse(
                {
                    "success": True,
                    "type": "done",
                    "message": "Query validation complete.",
                }
            )
        except Exception as e:
            yield format_sse(
                {
                    "success": False,
                    "type": "error",
                    "message": str(e),
                }
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── SUMMARIZE ─────────────────────────────────────

@app.post("/summarize")
async def summarize_content(req: SummarizeRequest):
    """
    Summarize the provided content with respect to the query using Gemini.

    SSE response (text/event-stream):
    - type: "start"
    - type: "progress" — intermediate status updates
    - type: "result"   — the final summary
    - type: "done"     — stream finished
    - type: "error"    — on failure

    Body example:
      {
        "query": "What is quantum computing?",
        "content": "Quantum computing is ...",
        "api_key": "your-gemini-api-key",
        "origin_research_id": null
      }
    """

    async def event_generator():
        yield format_sse(
            {
                "success": True,
                "type": "start",
                "message": f"Starting summarization for query: {req.query[:80]}",
            }
        )

        try:
            async for item in run_summarizer(
                query=req.query,
                content=req.content,
                api_key=req.api_key,
                origin_research_id=req.origin_research_id,
            ):
                yield format_sse(item)

            yield format_sse(
                {
                    "success": True,
                    "type": "done",
                    "message": "Summarization complete.",
                }
            )
        except Exception as e:
            yield format_sse(
                {
                    "success": False,
                    "type": "error",
                    "message": str(e),
                }
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── DOCUMENT PROCESSING ───────────────────────────

@app.post("/process-document")
async def process_document(req: ProcessDocumentRequest):
    """
    Parse and optionally summarize multiple documents from a list of URLs.

    SSE response (text/event-stream):
    - type: "start"
    - type: "progress"
    - type: "result"   — { content: str } or { summary: str }
    - type: "done"
    - type: "error"
    """

    async def event_generator():
        yield format_sse(
            {
                "success": True,
                "type": "start",
                "message": f"Processing {len(req.urls)} document(s) from URLs",
            }
        )

        pdf_urls = [u for u in req.urls if u.lower().endswith(".pdf")]
        docx_urls = [u for u in req.urls if u.lower().endswith((".docx", ".doc"))]

        # Process PDFs
        if pdf_urls:
            await event_bus.broadcast(message={"msg": f"Processing {len(pdf_urls)} PDF(s)..."})
            if req.summarize:
                results = await bulk_pdf_summarize(pdf_urls, req.ollama_url)
                for url, result in results.items():
                    filename = url.split("/")[-1].split("?")[0] or "document.pdf"
                    yield format_sse({
                        "success": "ERROR" not in result,
                        "type": "result",
                        "filename": filename,
                        "filetype": "pdf",
                        "summarized": True,
                        "ollama_url": req.ollama_url,
                        "summary": result,
                        "url": url,
                        "origin_research_id": req.origin_research_id,
                    })
            else:
                results = await bulk_extract_pdf_to_md(pdf_urls)
                for url, result in results.items():
                    filename = url.split("/")[-1].split("?")[0] or "document.pdf"
                    yield format_sse({
                        "success": "ERROR" not in result,
                        "type": "result",
                        "filename": filename,
                        "filetype": "pdf",
                        "summarized": False,
                        "content": result,
                        "url": url,
                        "origin_research_id": req.origin_research_id,
                    })

        # Process DOCXs
        if docx_urls:
            await event_bus.broadcast(message={"msg": f"Processing {len(docx_urls)} DOCX(s)..."})
            if req.summarize:
                results = await bulk_docx_summarize(docx_urls, req.ollama_url)
                for url, result in results.items():
                    filename = url.split("/")[-1].split("?")[0] or "document.docx"
                    yield format_sse({
                        "success": "ERROR" not in result,
                        "type": "result",
                        "filename": filename,
                        "filetype": "docx",
                        "summarized": True,
                        "ollama_url": req.ollama_url,
                        "summary": result,
                        "url": url,
                        "origin_research_id": req.origin_research_id,
                    })
            else:
                results = await bulk_extract_docx_to_md(docx_urls)
                for url, result in results.items():
                    filename = url.split("/")[-1].split("?")[0] or "document.docx"
                    yield format_sse({
                        "success": "ERROR" not in result,
                        "type": "result",
                        "filename": filename,
                        "filetype": "docx",
                        "summarized": False,
                        "content": result,
                        "url": url,
                        "origin_research_id": req.origin_research_id,
                    })

        yield format_sse(
            {
                "success": True,
                "type": "done",
                "message": f"Document processing complete for {len(req.urls)} URLs.",
            }
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── IMAGE SEARCH ──────────────────────────────────

@app.post("/imageSearch")
async def image_search(req: ImageSearchRequest):
    """
    Search for images using SearXNG.

    Returns a JSON response (not SSE) with a list of image results.

    Body example:
      {
        "query": "cyberpunk city",
        "num_results": 5,
        "timeout": 10.0,
        "origin_research_id": null
      }

    Response:
      {
        "success": true,
        "query": "cyberpunk city",
        "results": [
          { "title": "...", "img_src": "...", "url": "...", "source": "..." },
          ...
        ]
      }
    """
    try:
        results = await search_images(
            query=req.query,
            num_results=req.num_results,
            timeout=req.timeout,
        )
        return {
            "success": True,
            "query": req.query,
            "num_results": len(results),
            "results": results,
            "origin_research_id": req.origin_research_id,
        }
    except Exception as e:
        return {
            "success": False,
            "query": req.query,
            "error": str(e),
            "origin_research_id": req.origin_research_id,
        }


# ─────────────────────────── NEWS SEARCH ───────────────────────────────────

@app.post("/newsSearch")
async def news_search(req: NewsSearchRequest):
    """
    Search recent news via SearXNG, then scrape the top URLs for full content.

    Returns a JSON response with scraped news articles.

    Body example:
      {
        "query": "AI trends 2026",
        "num_results": 5,
        "timeout": 10.0,
        "origin_research_id": null
      }

    Response:
      {
        "success": true,
        "query": "AI trends 2026",
        "results": [
          {
            "title": "...",
            "url": "...",
            "description": "...",
            "content": "...(scraped markdown)...",
            "favicon": "..."
          },
          ...
        ]
      }
    """
    try:
        results = await search_news(
            query=req.query,
            num_results=req.num_results,
            timeout=req.timeout,
        )
        return {
            "success": True,
            "query": req.query,
            "num_results": len(results),
            "results": results,
            "origin_research_id": req.origin_research_id,
        }
    except Exception as e:
        return {
            "success": False,
            "query": req.query,
            "error": str(e),
            "origin_research_id": req.origin_research_id,
        }


# ─────────────────────────── YOUTUBE SEARCH ────────────────────────────────

@app.post("/youtubeSearch")
async def youtube_search_endpoint(req: YouTubeSearchRequest):
    """
    YouTube search, metadata, transcript and Ollama summarization.

    Modes (set via `mode` field):

    | mode         | what it does                                               | needs video_input? |
    |--------------|------------------------------------------------------------|--------------------|
    | summarize    | search → transcript → Ollama summary (PRIMARY use case)    | No                 |
    | search_only  | raw video list from search — no metadata or transcript     | No                 |
    | video_data   | metadata for a single video                                | Yes                |
    | transcript   | transcript text for a single video                         | Yes                |
    | full_bundle  | search + metadata + transcript in parallel                 | Yes                |

    Primary body example:
      {
        "query": "Best resorts in Bali 2026",
        "mode": "summarize",
        "max_videos": 5,
        "ollama_url": "http://localhost:11434/api/generate",
        "ollama_model": "qwen3.5:9b"
      }

    Response (summarize mode):
      {
        "success": true,
        "query": "...",
        "results": [
          {
            "id": "...",
            "title": "...",
            "desc": "...",
            "thumbnail": "...",
            "summary": "...",
            "channelName": "...",
            "channelImage": "..."
          }
        ]
      }
    """
    try:
        # ── PRIMARY MODE: full pipeline ──────────────────────────────────────
        if req.mode == "summarize":
            result = await youtube_search_and_summarize(
                query=req.query,
                max_videos=req.max_videos,
                ollama_url=req.ollama_url,
                ollama_model=req.ollama_model,
                summarize_video=req.summarize,
            )
            return {
                "success": True,
                "mode": req.mode,
                "origin_research_id": req.origin_research_id,
                **result,
            }

        # ── search_only ──────────────────────────────────────────────────────
        if req.mode == "search_only":
            videos = await youtube_search(req.query)
            return {
                "success": True,
                "mode": req.mode,
                "query": req.query,
                "results": videos,
                "origin_research_id": req.origin_research_id,
            }

        # ── modes that need video_input ──────────────────────────────────────
        if not req.video_input:
            return {
                "success": False,
                "mode": req.mode,
                "error": f"`video_input` is required for mode '{req.mode}'",
            }

        if req.mode == "video_data":
            data = await get_video_data(req.video_input)
            return {
                "success": True,
                "mode": req.mode,
                "video_input": req.video_input,
                "data": data,
                "origin_research_id": req.origin_research_id,
            }

        if req.mode == "transcript":
            transcript = await get_video_transcript(req.video_input)
            return {
                "success": True,
                "mode": req.mode,
                "video_input": req.video_input,
                "transcript": transcript,
                "origin_research_id": req.origin_research_id,
            }

        if req.mode == "full_bundle":
            from web.youtubeSearch import get_video_bundle
            search_results, video_data, transcript = await get_video_bundle(
                req.video_input, req.query
            )
            return {
                "success": True,
                "mode": req.mode,
                "query": req.query,
                "video_input": req.video_input,
                "search_results": search_results,
                "video_data": video_data,
                "transcript": transcript,
                "origin_research_id": req.origin_research_id,
            }

        return {"success": False, "error": f"Unknown mode: {req.mode}"}

    except Exception as e:
        return {
            "success": False,
            "mode": req.mode,
            "error": str(e),
            "origin_research_id": req.origin_research_id,
        }


# ─────────────────────────── WEB SEARCH ────────────────────────────────────

@app.post("/webSearch")
async def web_search(req: WebSearchRequest):
    """
    Search the web via SearXNG and scrape the result pages.
    Streams each scraped page as an SSE event.

    This is identical to /scrape/search but exposed under a cleaner URL
    for consumer convenience.

    SSE response (text/event-stream):
    - type: "start"
    - one item per scraped page
    - type: "done"
    - type: "error" on failure

    Body example:
      {
        "query": "latest AI research papers 2026",
        "max_no_url": 10,
        "max_concurrent_scrape_batches": 3,
        "origin_research_id": null
      }
    """

    async def event_generator():
        yielded_items = 0
        yield format_sse(
            {
                "success": True,
                "type": "start",
                "message": f"Web search started for: {req.query}",
            }
        )

        try:
            async for item in search_and_scrape_pages(
                [req.query],
                max_urls=req.max_no_url,
                max_concurrent_scrape_batches=req.max_concurrent_scrape_batches,
                queries_are_urls=False,
                origin_research_id=req.origin_research_id,
            ):
                yielded_items += 1
                yield format_sse(item)

            yield format_sse(
                {
                    "success": True,
                    "type": "done",
                    "message": f"Web search complete. Scraped {yielded_items} page(s).",
                    "yielded_items": yielded_items,
                }
            )
        except Exception as e:
            yield format_sse(
                {
                    "success": False,
                    "type": "error",
                    "message": str(e),
                }
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────── ENTRYPOINT ────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
