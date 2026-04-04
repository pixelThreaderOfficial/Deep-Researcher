import json
import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from src import (
    get_youtube_data,
    process_files,
    read_pages,
    search_and_scrape_pages,
    search_images,
    search_urls,
    understand_images,
)
from src.web.web_crawler import close_crawler_engine, init_crawler_engine
from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

# 🔥 Logging Setup (REAL server vibes)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("MCP-Server")


# ─────────────────────────── LIFESPAN ──────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastMCP):
    # -------- SERVER START --------
    await scheduler.start()
    await init_crawler_engine(batch_size=10, concurrency=8)

    yield

    # -------- SERVER SHUTDOWN --------
    await close_crawler_engine()
    await scheduler.shutdown()


mcp_server = FastMCP(
    name="Deep Researcher v2 Agent MCP Tools",
    host="0.0.0.0",
    port=8002,
    lifespan=lifespan,
)

# ========================
# 🧰 TOOLS
# ========================


@mcp_server.tool(
    description="Search the web for a given query, collect relevant URLs using SearXNG, and scrape the pages using crawl4ai. Returns a JSON string containing a dictionary with 'results' key holding a list of dictionaries, each with page details like success status, URL, content, scrape duration, and metadata."
)
async def web_search(query: str):
    quickLog(f"Searching web: {query}", "info", module="CRAWLER")

    await event_bus.broadcast({"type": "search", "query": query})

    results = [item async for item in search_and_scrape_pages([query])]

    return json.dumps({"results": results})


@mcp_server.tool(
    description="Scrape a list of provided URLs directly without searching. Returns a JSON string containing a dictionary with 'results' key holding a list of dictionaries with page details including success, URL, content, scrape duration, and metadata."
)
async def read_webpages(urls: list[str]):
    quickLog(f"Reading pages: {len(urls)} URLs", "info", module="CRAWLER")

    return json.dumps({"results": [item async for item in read_pages(urls)]})


@mcp_server.tool(
    description="Search YouTube for videos matching the query using yt-dlp. Returns a JSON string containing a dictionary with query, total results, scrape time, and a list of video details including title, URL, description, channel, duration, views, upload date, and thumbnail."
)
async def youtube_search(query: str):
    quickLog(f"YouTube search: {query}", "info", module="AGENTS")

    return json.dumps(await get_youtube_data(query))


@mcp_server.tool(
    description="Search for images related to multiple queries using SearXNG. Takes a list of tuples (query, num_images) and returns a JSON string containing a dictionary mapping each query to a list of image URLs."
)
async def image_search_tool(queries: list[tuple[str, int]]):
    quickLog(f"Image search: {queries}", "info", module="AGENTS")

    return json.dumps(await search_images(queries))


@mcp_server.tool(
    description="Analyze a list of images (URLs or local paths) using Ollama AI model. Downloads and processes images, then generates titles and descriptions. Returns a JSON string containing a dictionary with total files, success count, tokens used, time taken, and content mapping filenames to analysis results."
)
async def understand_images_tool(paths: list[str]):
    quickLog(f"Understanding {len(paths)} images", "info", module="AI")

    return json.dumps(await understand_images(paths))


@mcp_server.tool(
    description="Process a list of document files (PDF, DOCX, PPTX, XLSX, TXT, MD) or URLs. Extracts text, cleans it, and summarizes using Ollama AI. Returns a JSON string containing a dictionary with total files, success count, tokens used, time taken, and content mapping filenames to summaries."
)
async def process_docs(paths: list[str]):
    quickLog(f"Processing docs: {paths}", "info", module="UTILS")

    return json.dumps(await process_files(paths, "http://localhost:11434"))


@mcp_server.tool(
    description="Search for URLs related to the query using SearXNG without scraping the pages. Returns a JSON string containing a list of unique URLs."
)
async def search_urls_tool(query: str):
    quickLog(f"Searching URLs for: {query}", "info", module="CRAWLER")

    return json.dumps(await search_urls([query]))


@mcp_server.tool(
    description="Scrape a single URL and return its details. Returns a JSON string containing a dictionary with 'results' key holding a list with a single dictionary of success status, URL, content, scrape duration, and metadata."
)
async def scrape_single_url(url: str):
    quickLog(f"Scraping single URL: {url}", "info", module="CRAWLER")

    return json.dumps({"results": [item async for item in read_pages([url])]})


# ========================
# 🏁 ENTRY POINT
# ========================


def main():
    logger.info("🔥 Starting MCP Tools Server on port 8002")
    mcp_server.run(
        transport="streamable-http",
    )


if __name__ == "__main__":
    main()
