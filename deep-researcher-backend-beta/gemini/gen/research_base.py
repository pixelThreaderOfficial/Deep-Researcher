"""
Deep Researcher Agent

This module implements a professional deep research agent that:
1. Filters sexual content before processing
2. Performs multi-step research (web search → scrape → RAG → optional images/news)
3. Provides real-time progress updates via WebSocket
4. Saves all research artifacts to appropriate storage systems
"""

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable, Awaitable
from urllib.request import urlopen
from google import genai
from google.genai import types
from dotenv import load_dotenv

from gemini.tools.web_search import (
    web_search,
    scrape_urls,
    image_search,
    news_search,
)
from gemini.tools.youtube_Search import (
    youtube_search,
    get_video_data,
    get_video_transcript,
)
from gemini.rag_store.rag_stores import (
    create_documents,
    query_documents,
    save_scraped_content,
)
from bucket.stores import store_generated_content, init_bucket_system
from gemini.sqlite_crud import chat_db

load_dotenv()

# Ensure bucket system (directories + DB) is initialized before any saves
try:
    init_bucket_system()
except Exception as _e:
    # Defer hard failure; individual save functions will still attempt and log
    print(f"Bucket init warning: {_e}")

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
DEFAULT_MODEL = "gemini-2.0-flash"


def validate_model_name(model_name: str) -> str:
    """
    Validate and normalize model name. Returns default if invalid.

    Args:
        model_name: Model name to validate

    Returns:
        Validated model name or default
    """
    if not model_name:
        return DEFAULT_MODEL

    # Normalize model name (remove spaces, ensure lowercase)
    model_name = model_name.strip().lower()

    # Check if it's a valid gemini model format
    if model_name.startswith("gemini-"):
        return model_name

    # If it doesn't start with gemini-, try to prepend it
    if "gemini" in model_name.lower():
        # Extract version if present (e.g., "2.5-pro" -> "gemini-2.5-pro")
        parts = model_name.split("-")
        if len(parts) >= 2:
            return f"gemini-{'-'.join(parts[1:])}"

    # Default fallback
    return DEFAULT_MODEL


# ========================================
# CONTENT SAFETY CHECK
# ========================================


def check_sexual_content(query: str) -> bool:
    """
    Check if the query contains sexual content.

    Args:
        query: User query to check

    Returns:
        True if sexual content detected, False otherwise
    """
    try:
        safety_prompt = f"""Analyze the following query and determine if it contains sexual content, explicit material, or inappropriate content.

Query: {query}

Respond with ONLY "YES" if sexual content is detected, or "NO" if it's safe. Do not provide any explanation."""

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[safety_prompt],
        )

        result_text = getattr(response, "text", None)
        result = (result_text or "").strip().upper()
        return result == "YES"

    except Exception as e:
        # If check fails, default to safe (allow through)
        print(f"Error checking sexual content: {e}")
        return False


# ========================================
# QUERY ANALYSIS
# ========================================


def analyze_query_needs(query: str) -> Dict[str, Any]:
    """
    Analyze query to determine if it needs images, news, and if it's clear.

    Args:
        query: User query to analyze

    Returns:
        Dict with:
            - needs_images: bool
            - needs_news: bool
            - is_clear: bool
    """
    try:
        analysis_prompt = f"""Analyze the following query and determine:
1. Does this query need images? (e.g., "show me pictures of", "images of", visual content)
2. Does this query need news? (e.g., "latest news", "recent updates", "current events")
3. Is this query clear and specific enough to research? (vs vague/ambiguous)

Query: {query}

Respond with ONLY a JSON object in this exact format:
{{
    "needs_images": true/false,
    "needs_news": true/false,
    "is_clear": true/false
}}"""

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[analysis_prompt],
        )

        resp_text = getattr(response, "text", None)
        result_text = (resp_text or "").strip()
        # Extract JSON from response (in case model adds extra text)
        if "{" in result_text:
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            result_text = result_text[json_start:json_end]

        result = json.loads(result_text)
        return {
            "needs_images": result.get("needs_images", False),
            "needs_news": result.get("needs_news", False),
            "is_clear": result.get("is_clear", True),
        }

    except Exception as e:
        print(f"Error analyzing query needs: {e}")
        # Default to safe values
        return {"needs_images": False, "needs_news": False, "is_clear": True}


def generate_sub_questions(query: str) -> List[str]:
    """
    Generate relevant sub-questions based on the user's query for comprehensive research.

    Args:
        query: User's main query

    Returns:
        List of 3-5 relevant sub-questions
    """
    try:
        sub_questions_prompt = f"""Based on the following user query, generate 3-5 relevant sub-questions that would help provide a comprehensive answer.

User Query: {query}

Generate sub-questions that:
1. Break down the main topic into specific aspects
2. Cover different angles of the topic
3. Help gather complete information
4. Are clear and specific

Respond with ONLY a JSON array of questions:
["question 1", "question 2", "question 3", ...]"""

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[sub_questions_prompt],
        )

        resp_text = getattr(response, "text", None)
        result_text = (resp_text or "").strip()

        # Extract JSON array from response
        if "[" in result_text:
            json_start = result_text.find("[")
            json_end = result_text.rfind("]") + 1
            result_text = result_text[json_start:json_end]

        sub_questions = json.loads(result_text)
        return sub_questions[:5]  # Limit to 5 questions

    except Exception as e:
        print(f"Error generating sub-questions: {e}")
        return []


# Note: save_scraped_content is imported from gemini.rag_store.rag_stores


# ========================================
# IMAGE STORAGE HELPER
# ========================================


async def save_image_to_bucket(image_url: str, query: str) -> Dict[str, Any]:
    """
    Download image from URL and save to bucket with timestamp and SHA256 hash.

    Args:
        image_url: URL of the image to download
        query: Original query for metadata

    Returns:
        Dict with file_id, file_url, stored_filename
    """
    try:
        # Download image (using asyncio.run_in_executor for async-friendly urllib)
        def download_image():
            with urlopen(image_url, timeout=30) as response:
                return response.read()

        # Use asyncio.to_thread for thread offloading
        image_content = await asyncio.to_thread(download_image)

        # Determine file extension from URL or content-type
        ext = "jpg"  # default
        if "." in image_url:
            url_ext = image_url.split(".")[-1].split("?")[0].lower()
            if url_ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                ext = url_ext

        # Generate filename with timestamp and SHA256 hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(image_content).hexdigest()[:16]
        filename = f"{timestamp}_{content_hash}.{ext}"

        # Save to bucket
        result = store_generated_content(
            content=image_content,
            filename=filename,
            content_type="images",
            metadata={
                "source_url": image_url,
                "query": query,
                "saved_at": datetime.now().isoformat(),
            },
        )

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save image: {str(e)}",
            "image_url": image_url,
        }


# ========================================
# NEWS STORAGE HELPER
# ========================================


def save_news_to_bucket(news_items: List[Dict], query: str) -> Dict[str, Any]:
    """
    Save news items to bucket as JSON file with timestamp and SHA256 hash.

    Args:
        news_items: List of news item dictionaries
        query: Original query for metadata

    Returns:
        Dict with file_id, file_url, stored_filename
    """
    try:
        # Convert news items to JSON
        news_json = json.dumps(news_items, indent=2, ensure_ascii=False)
        news_bytes = news_json.encode("utf-8")

        # Generate filename with timestamp and SHA256 hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(news_bytes).hexdigest()[:16]
        filename = f"{timestamp}_{content_hash}.json"

        # Save to bucket
        result = store_generated_content(
            content=news_bytes,
            filename=filename,
            content_type="docs",
            metadata={
                "query": query,
                "news_count": len(news_items),
                "saved_at": datetime.now().isoformat(),
            },
        )

        return result

    except Exception as e:
        return {"success": False, "error": f"Failed to save news: {str(e)}"}


# ========================================
# YOUTUBE STORAGE HELPER
# ========================================


def save_youtube_videos_to_bucket(videos: List[Dict], query: str) -> Dict[str, Any]:
    """
    Save YouTube video data to bucket as JSON file with timestamp and SHA256 hash.

    Args:
        videos: List of video dictionaries with metadata
        query: Original query for metadata

    Returns:
        Dict with file_id, file_url, stored_filename
    """
    try:
        # Convert videos to JSON
        videos_json = json.dumps(videos, indent=2, ensure_ascii=False)
        videos_bytes = videos_json.encode("utf-8")

        # Generate filename with timestamp and SHA256 hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(videos_bytes).hexdigest()[:16]
        filename = f"youtube_{timestamp}_{content_hash}.json"

        # Save to bucket
        result = store_generated_content(
            content=videos_bytes,
            filename=filename,
            content_type="docs",
            metadata={
                "type": "youtube_videos",
                "query": query,
                "video_count": len(videos),
                "saved_at": datetime.now().isoformat(),
            },
        )

        return result

    except Exception as e:
        return {"success": False, "error": f"Failed to save YouTube videos: {str(e)}"}


# ========================================
# NEWS NORMALIZATION HELPER
# ========================================

from urllib.parse import urlparse


def _normalize_news_results(raw_news: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize DDGS news results to a consistent schema and dedupe by domain.

    Expected keys per item after normalization:
      - date, title, body, url, image, source, domain

    Returns up to 5 unique sources (by domain), preserving order.
    """
    normalized: List[Dict[str, Any]] = []
    seen_domains = set()

    for item in raw_news or []:
        try:
            title = str(item.get("title", "")).strip()
            body = str(item.get("body", "")).strip()
            url = str(item.get("url", "")).strip()
            image = item.get("image")
            date = str(item.get("date", "")).strip()
            source = str(item.get("source", "")).strip()

            if not url or not url.lower().startswith("http"):
                continue

            domain = urlparse(url).netloc.lower()
            if not domain or domain in seen_domains:
                continue

            seen_domains.add(domain)
            normalized.append(
                {
                    "date": date,
                    "title": title,
                    "body": body,
                    "url": url,
                    "image": image,
                    "source": source or domain,
                    "domain": domain,
                }
            )

            if len(normalized) >= 5:
                break
        except Exception:
            # Skip malformed items
            continue

    return normalized


# ========================================
# YOUTUBE SEARCH PARSING HELPER
# ========================================

import re


def _parse_simple_youtube_data(simple_data: str) -> Dict[str, str]:
    """Parse the simple_data string returned by py_youtube Search().

    Heuristics extract channel, views, duration.
    The format is inconsistent so we best-effort with regex.

    Examples:
        "BMW M 1000 XR REVIEW | Executive Lunacy 18 minutes"
        "Kerala's most expensive ... by ambro 46 302,369 views 6 months ago 55 seconds – play Short"

    Returns:
        {"channel": str, "views": str, "duration": str, "published": str}
    """
    channel = ""
    views = ""
    duration = ""
    published = ""

    # Duration patterns
    duration_patterns = re.findall(
        r"(\d+\s+hours?(?:,\s+\d+\s+minutes?)?|\d+\s+minutes?(?:,\s+\d+\s+seconds?)?|\d+\s+seconds?)",
        simple_data,
    )
    if duration_patterns:
        duration = duration_patterns[-1]  # take the last occurrence

    # Views pattern
    m_views = re.search(r"([0-9,.]+)\s+views", simple_data)
    if m_views:
        views = m_views.group(1)

    # Channel extraction: look for ' by ' then capture until views or duration or end
    if " by " in simple_data:
        after_by = simple_data.split(" by ", 1)[1].strip()
        # remove leading possible counts like 'ambro 46' -> channel 'ambro'
        # If views match, truncate before it
        cut_pos = len(after_by)
        if m_views:
            pos = after_by.find(m_views.group(0))
            if pos != -1:
                cut_pos = pos
        # If duration appears earlier than views
        if duration:
            m_duration = re.search(re.escape(duration), after_by)
            if m_duration and m_duration.start() < cut_pos:
                cut_pos = m_duration.start()
        channel_raw = after_by[:cut_pos].strip()
        # Heuristic: channel name seldom contains digits at end; trim trailing digits
        channel = re.sub(r"\s*\d.*$", "", channel_raw).strip()
        # If still too long (contains 'views'), clean again
        channel = channel.replace("views", "").strip()

    # Published time heuristic: look for patterns like 'months ago', 'days ago'
    m_pub = re.search(
        r"(\d+\s+(?:days|day|weeks|week|months|month|years|year)\s+ago)", simple_data
    )
    if m_pub:
        published = m_pub.group(1)

    return {
        "channel": channel,
        "views": views,
        "duration": duration,
        "published": published,
    }


# ========================================
# MAIN RESEARCH AGENT
# ========================================


async def research_agent_stream(
    query: str,
    model: str = DEFAULT_MODEL,
    session_id: Optional[str] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Deep research agent with streaming support.

    Args:
        query: User query to research
        model: Model to use for generation
        session_id: Optional session ID
        progress_callback: Optional callback function for progress updates

    Yields:
        Dict with type and data for progress updates and answer chunks
    """
    start_time = time.time()
    research_metadata = {
        "sources": [],
        "images": [],
        # Will hold either {} or {file_url, file_id, items}
        "news": {},
        "youtube": {},  # Will hold {file_url, file_id, videos}
        "sub_questions": [],  # List of generated sub-questions
        "rag_results": [],
    }
    # Predefine variables to satisfy static analyzers and ensure availability
    full_answer: str = ""
    saved_videos: List[Dict[str, Any]] = []
    news_results: List[Dict[str, Any]] = []
    transcript_save: Optional[Dict[str, Any]] = None
    references: List[Dict[str, Any]] = []
    research_time: float = 0.0

    # Initialize DB research session
    research_slug = None
    try:
        research_slug = chat_db.create_research_session(
            query=query,
            model=validate_model_name(model),
            tags=None,
        )
    except Exception as e:
        # Non-fatal; proceed with research even if DB create fails
        print(f"Failed to create research session: {e}")
    # Safety check: block sexual content
    try:
        if check_sexual_content(query):
            # Mark session as failed due to safety violation
            if research_slug:
                try:
                    chat_db.update_research_status(
                        slug=research_slug,
                        status="failed",
                        duration=time.time() - start_time,
                        answer=None,
                        resources_used=[],
                        metadata={"error": "sexual_content_detected"},
                    )
                except Exception as _upd_err:
                    print(f"Failed to update research status (safety): {_upd_err}")
            yield {
                "type": "error",
                "message": "This query appears to contain sexual content that can't be processed.",
                "research_slug": research_slug,
            }
            return
    except Exception:
        # On failure to check, proceed as safe
        pass

    # Analyze query for needs
    try:
        needs = analyze_query_needs(query)
        needs_images = needs.get("needs_images", False)
        needs_news = needs.get("needs_news", False)
        is_clear = needs.get("is_clear", True)
    except Exception:
        needs_images = False
        needs_news = False
        is_clear = True

    # Generate sub-questions
    try:
        sub_questions = generate_sub_questions(query)
        research_metadata["sub_questions"] = sub_questions
    except Exception:
        sub_questions = []

    # Perform initial web search
    web_results = web_search(
        query, region="us-en", safesearch="on", timelimit="y", max_results=10
    )
    research_metadata["web_search_results"] = web_results

    if not web_results:
        # Update failed status for no results
        if research_slug:
            try:
                chat_db.update_research_status(
                    slug=research_slug,
                    status="failed",
                    duration=time.time() - start_time,
                    answer=None,
                    resources_used=[],
                    metadata={"error": "no_web_results"},
                )
            except Exception as _upd_err:
                print(f"Failed to update research status (no results): {_upd_err}")
        yield {
            "type": "error",
            "message": "No relevant information found. Please try rephrasing your query.",
            "research_slug": research_slug,
        }
        return

    # Extract URLs from search results
    urls = [result.get("href", "") for result in web_results if result.get("href")]

    # Step 4: Scrape URLs
    if progress_callback:
        await progress_callback(
            {
                "type": "progress",
                "stage": "scraping",
                "message": f"Scraping {len(urls)} URLs...",
            }
        )

    scraped_content = {}
    if urls:
        try:
            # Use scrape_urls (synchronous wrapper) in thread executor for async compatibility
            scraped_content = await asyncio.to_thread(
                scrape_urls, urls[:5]
            )  # Limit to top 5 URLs

            # Filter out error messages from scraped content
            scraped_content = {
                url: content
                for url, content in scraped_content.items()
                if not (isinstance(content, str) and content.startswith("Error:"))
            }

            print(f"Successfully scraped {len(scraped_content)} URLs")
            for url, content in scraped_content.items():
                print(f"  - {url}: {len(content)} characters")

        except Exception as e:
            # If scraping fails, continue with empty content but log the error
            print(f"Error scraping URLs: {str(e)}")
            import traceback

            traceback.print_exc()
            scraped_content = {}

        # Step 5: Save to RAG
        if progress_callback:
            await progress_callback(
                {
                    "type": "progress",
                    "stage": "saving",
                    "message": "Saving scraped content to knowledge base...",
                }
            )

        rag_save_success = False
        if scraped_content:
            try:
                print(f"Attempting to save {len(scraped_content)} documents to RAG...")
                save_result = save_scraped_content(scraped_content)

                if save_result.get("success"):
                    rag_save_success = True
                    research_metadata["sources"].extend(list(scraped_content.keys()))
                    print(
                        f"✓ RAG save successful: {save_result.get('count', 0)} documents saved"
                    )
                else:
                    print(
                        f"✗ RAG save failed: {save_result.get('error', 'Unknown error')}"
                    )
            except Exception as e:
                print(f"✗ Error saving to RAG: {str(e)}")
                import traceback

                traceback.print_exc()
        else:
            print("No scraped content to save to RAG")

        # Step 6: Query RAG
        if progress_callback:
            await progress_callback(
                {
                    "type": "progress",
                    "stage": "rag_query",
                    "message": "Querying knowledge base for relevant information...",
                }
            )

        rag_results = {"success": False, "results": []}
        try:
            rag_results = query_documents(query, max_results=5)
            if not rag_results.get("success"):
                print(f"RAG query failed: {rag_results.get('error', 'Unknown error')}")
            elif rag_results.get("results"):
                research_metadata["rag_results"] = rag_results.get("results", [])
                print(
                    f"RAG query successful: {len(rag_results.get('results', []))} results found"
                )
            else:
                print("RAG query returned no results")
        except Exception as e:
            print(f"Error querying RAG: {str(e)}")
            import traceback

            traceback.print_exc()
            rag_results = {"success": False, "results": [], "error": str(e)}

        # Step 7: Check if relevant info found
        # Use scraped content even if RAG doesn't work
        relevant_info_found = len(scraped_content) > 0 or (  # We have scraped content
            rag_results.get("success") and len(rag_results.get("results", [])) > 0
        )  # Or RAG found results

        if not relevant_info_found:
            # Check query clarity only if we have no content at all
            if not is_clear:
                # Update failed due to unclear query
                if research_slug:
                    try:
                        ref_links: List[str] = []
                        for r in web_results:
                            href = r.get("href")
                            if isinstance(href, str) and href:
                                ref_links.append(href)
                        chat_db.update_research_status(
                            slug=research_slug,
                            status="failed",
                            duration=time.time() - start_time,
                            answer=None,
                            resources_used=ref_links,
                            metadata={"error": "unclear_query"},
                        )
                    except Exception as _upd_err:
                        print(f"Failed to update research status (unclear): {_upd_err}")
                yield {
                    "type": "error",
                    "message": "I'm not sure what you mean. Please try again with a more specific query.",
                    "research_slug": research_slug,
                }
                return

        # Step 8: Optional image search
        saved_images = []
        if needs_images:
            if progress_callback:
                await progress_callback(
                    {
                        "type": "progress",
                        "stage": "image_search",
                        "message": "Searching for relevant images...",
                    }
                )

            image_results = image_search(query, max_results=5)

            if image_results:
                for img_result in image_results[:3]:  # Limit to top 3 images
                    image_url = img_result.get("image") or img_result.get("url")
                    if image_url:
                        save_result = await save_image_to_bucket(image_url, query)
                        if save_result.get("success"):
                            saved_images.append(
                                {
                                    "url": image_url,
                                    "file_url": save_result.get("file_url"),
                                    "file_id": save_result.get("file_id"),
                                    "title": img_result.get("title", ""),
                                }
                            )

            research_metadata["images"] = saved_images

        # Step 9: News search (always on)
        saved_news = []
        news_results: List[Dict[str, Any]] = []
        if progress_callback:
            await progress_callback(
                {
                    "type": "progress",
                    "stage": "news_search",
                    "message": "Searching recent news sources...",
                }
            )

        try:
            raw_news = news_search(
                f"{query}",
                region="in",
                timelimit="w",
                max_results=5,
            ) or []

            # Map directly to expected keys; keep full body for LLM context
            for item in raw_news:
                news_results.append(
                    {
                        "date": item.get("date"),
                        "title": item.get("title", "Untitled"),
                        "body": item.get("body", ""),
                        "url": item.get("url", ""),
                        "image": item.get("image"),
                        "source": item.get("source", "Unknown"),
                    }
                )

            if news_results:
                save_result = save_news_to_bucket(news_results, query)
                if save_result.get("success"):
                    saved_news = news_results
                    research_metadata["news"] = {
                        "file_url": save_result.get("file_url"),
                        "file_id": save_result.get("file_id"),
                        "items": news_results,
                    }
                else:
                    research_metadata["news"] = {
                        "error": save_result.get("error"),
                        "items": news_results,
                    }
        except Exception as e:
            print(f"Error during news search: {e}")
            research_metadata["news"] = {"error": str(e), "items": []}

        # Step 9.5: YouTube video search (always search for videos)
        if progress_callback:
            await progress_callback(
                {
                    "type": "progress",
                    "stage": "youtube_search",
                    "message": "Searching for relevant YouTube videos...",
                }
            )

        saved_videos = []
        try:
            # Search for videos using py_youtube (returns list of dicts: id, title, thumb, simple_data)
            raw_videos = await asyncio.to_thread(youtube_search, query)
            if raw_videos:
                for video in raw_videos[:2]:  # Top 2
                    vid_id = video.get("id")
                    title = video.get("title", "")
                    thumbs = video.get("thumb", []) or []
                    simple_data = video.get("simple_data", "")
                    parsed = _parse_simple_youtube_data(simple_data)
                    video_url = (
                        f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""
                    )
                    description = ""
                    thumbnail = thumbs[0] if thumbs else ""
                    transcript = None
                    if video_url:
                        try:
                            video_data = await asyncio.to_thread(
                                get_video_data, video_url
                            )
                            description = (
                                video_data.get("description", "") or description
                            )
                            if video_data.get("thumbnail"):
                                thumbnail = video_data.get("thumbnail")
                            if not parsed.get("channel"):
                                channel_obj = video_data.get("channel") or {}
                                if isinstance(channel_obj, dict):
                                    parsed["channel"] = channel_obj.get(
                                        "name", parsed.get("channel", "")
                                    )
                        except Exception as vd_err:
                            print(
                                f"YouTube detailed fetch failed for {vid_id}: {vd_err}"
                            )
                        try:
                            transcript = await asyncio.to_thread(
                                get_video_transcript, vid_id
                            )
                        except Exception as trans_error:
                            print(f"Transcript unavailable for {vid_id}: {trans_error}")

                    saved_videos.append(
                        {
                            "url": video_url,
                            "id": vid_id,
                            "title": title,
                            "description": description,
                            "thumbnail": thumbnail,
                            "channel": parsed.get("channel", ""),
                            "views": parsed.get("views", ""),
                            "duration": parsed.get("duration", ""),
                            "published": parsed.get("published", ""),
                            "has_transcript": transcript is not None,
                        }
                    )

                # Save videos to bucket
                if saved_videos:
                    save_result = save_youtube_videos_to_bucket(saved_videos, query)
                    if save_result.get("success"):
                        research_metadata["youtube"] = {
                            "file_url": save_result.get("file_url"),
                            "file_id": save_result.get("file_id"),
                            "videos": saved_videos,
                        }
                    print(f"✓ Found and saved {len(saved_videos)} YouTube videos")
                else:
                    print("No YouTube videos found")
        except Exception as e:
            print(f"Error searching YouTube: {str(e)}")
            import traceback

            traceback.print_exc()

        # Step 10: Combine all content and generate final answer
        if progress_callback:
            await progress_callback(
                {
                    "type": "progress",
                    "stage": "analyzing_data",
                    "message": "Analyzing collected data...",
                }
            )

        # Prepare context for final answer
        context_parts = []

        # Add RAG results (if available)
        if rag_results.get("success") and rag_results.get("results"):
            for result in rag_results["results"][:3]:
                content = result.get("content", "")
                if content:
                    context_parts.append(f"Source: {content[:500]}")

        # Add scraped content snippets (always use these if available)
        if scraped_content:
            for url, content in list(scraped_content.items())[:3]:
                if content and not (
                    isinstance(content, str) and content.startswith("Error:")
                ):
                    context_parts.append(f"Source ({url}): {str(content)[:500]}")

        # If we have no context, use web search results
        if not context_parts and web_results:
            for result in web_results[:3]:
                title = result.get("title", "")
                body = result.get("body", "")
                if title or body:
                    context_parts.append(f"Source: {title}\n{body[:300]}")

        context = (
            "\n\n".join(context_parts)
            if context_parts
            else "No specific sources found, but conducting research based on general knowledge."
        )

        # Prepare sub-questions context
        sub_questions_text = ""
        if sub_questions:
            sub_questions_text = "\n".join(
                [f"{i+1}. {q}" for i, q in enumerate(sub_questions)]
            )

        # Prepare images context
        images_context = ""
        if saved_images:
            images_context = f"\nImages found: {len(saved_images)} relevant images"

        # Prepare YouTube context
        youtube_context = ""
        if saved_videos:
            youtube_context = "\n\nYouTube Videos Found:\n"
            for i, video in enumerate(saved_videos, 1):
                youtube_context += f"{i}. {video.get('title', 'Untitled')} by {video.get('channel', 'Unknown')}\n"
                youtube_context += f"   URL: {video.get('url', '')}\n"
                if video.get("description"):
                    youtube_context += (
                        f"   Description: {video.get('description', '')[:200]}...\n"
                    )

        # Prepare news context with proper citation (title — source (date) + URL) and include full body
        news_context = ""
        if news_results:
            news_context = "\n\nRecent News (last 7 days):\n"
            for i, news_item in enumerate(news_results[:5], 1):
                title_n = news_item.get("title", "Untitled")
                source_n = news_item.get("source", "Unknown")
                date_n = news_item.get("date", "")
                url_n = news_item.get("url", "")
                body_n = news_item.get("body", "")
                news_context += f"{i}. {title_n} — {source_n}{f' ({date_n})' if date_n else ''}\n"
                if body_n:
                    news_context += f"   {body_n}\n"
                if url_n:
                    news_context += f"   Source: {url_n}\n"

        # Prepare sources/references context for explicit links
        sources_context = ""
        web_source_urls: List[str] = []
        news_source_urls: List[str] = []

        # Collect scraped web sources
        if research_metadata["sources"]:
            web_source_urls.extend(research_metadata["sources"])

        # Collect news sources
        if news_results:
            news_source_urls.extend([n.get("url", "") for n in news_results if n.get("url")])

        # Build sources list sections
        if web_source_urls:
            sources_context += "\n\nWeb Sources:\n"
            for i, url in enumerate(web_source_urls, 1):
                # Try to get title from web_results if available
                source_title = f"Source {i}"
                for web_result in web_results:
                    href = web_result.get("href") or web_result.get("url")
                    if href == url:
                        source_title = web_result.get("title", source_title)
                        break
                sources_context += f"{i}. {source_title}\n   {url}\n"

        if news_source_urls:
            sources_context += "\nNews Sources:\n"
            for j, url in enumerate(news_source_urls, 1):
                # Try to get matching news title
                match = next((n for n in news_results if n.get("url") == url), None)
                title = (match or {}).get("title", f"News {j}")
                source = (match or {}).get("source", "")
                label = f"{title} — {source}" if source else title
                sources_context += f"{j}. {label}\n   {url}\n"

        # Generate final answer prompt with structured format
        final_prompt = f"""You are a professional deep researcher. Generate a comprehensive research report in the following EXACT structure:

User Query: {query}

Sub-Questions to Address:
{sub_questions_text}

Research Context:
{context}{images_context}{youtube_context}{news_context}{sources_context}

Generate your response in this EXACT format:

## Introduction
Provide a clear, engaging introduction to the topic (2-3 paragraphs). Set context and explain why this topic matters.

## Main Analysis
Provide detailed, comprehensive analysis addressing the user's query and sub-questions. Use proper formatting with headings and bullet points. Include:
- Key concepts and definitions
- Detailed explanations
- Important facts and data
- Expert insights from sources
- Practical applications or examples

Reference sources naturally in your text like: "According to [source]..." or "Research shows..."

## YouTube Resources
{f"We found {len(saved_videos)} highly relevant videos:" if saved_videos else "No video resources were found for this topic."}
{chr(10).join([f"{i+1}. **{v.get('title', 'Untitled')}** by {v.get('channel', 'Unknown')}" + chr(10) + f"   - {v.get('description', 'No description available')[:200]}..." + chr(10) + f"   - Watch: {v.get('url', '')}" for i, v in enumerate(saved_videos)]) if saved_videos else ""}

## Related News
{f"Recent developments and news:" if news_results else "No recent news found for this topic."}
{chr(10).join([f"{i+1}. **{n.get('title', 'Untitled')}** - {n.get('source', 'Unknown')}" + chr(10) + f"   {n.get('body', '')[:150]}..." for i, n in enumerate(news_results[:5])]) if news_results else ""}

## Sources & References
List all web and news sources used in this research:
{chr(10).join([f"[{i+1}] {url}" for i, url in enumerate(web_source_urls + news_source_urls)]) if (web_source_urls or news_source_urls) else "No sources were collected for this research."}

## Conclusion
Provide a strong conclusion that:
- Summarizes key findings
- Answers the original query clearly
- Provides actionable insights or recommendations
- Suggests next steps or areas for further exploration

IMPORTANT: Follow this structure EXACTLY. Do not skip any sections. In the Sources & References section, list each URL on a new line with its number."""

        if progress_callback:
            await progress_callback(
                {
                    "type": "progress",
                    "stage": "generating",
                    "message": "Generating structured research report...",
                }
            )

        # Stream the final answer
        full_answer = ""
        # Validate model name
        validated_model = validate_model_name(model)

        response = client.models.generate_content_stream(
            model=validated_model,
            contents=[final_prompt],
        )

        for chunk in response:
            if chunk.text:
                full_answer += chunk.text
                yield {"type": "answer_chunk", "chunk": chunk.text}
                await asyncio.sleep(0)  # Allow other tasks to run

        # Persist the research transcript (answer + metadata) to bucket as JSON
        try:
            if progress_callback:
                await progress_callback(
                    {
                        "type": "progress",
                        "stage": "saving",
                        "message": "Saving research transcript...",
                    }
                )

            transcript = {
                "query": query,
                "answer": full_answer,
                "sub_questions": research_metadata["sub_questions"],
                "sources": research_metadata["sources"],
                "web_search_results": research_metadata["web_search_results"],
                "rag_results": research_metadata["rag_results"],
                "images": research_metadata["images"],
                "youtube": research_metadata["youtube"],
                "news": research_metadata["news"],
                "model": validated_model,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            }
            transcript_bytes = json.dumps(
                transcript, ensure_ascii=False, indent=2
            ).encode("utf-8")
            transcript_save = store_generated_content(
                content=transcript_bytes,
                filename="research_transcript.json",
                content_type="docs",
                metadata={
                    "type": "research_transcript",
                    "query": query,
                    "model": validated_model,
                },
            )
        except Exception as e:
            transcript_save = {"success": False, "error": str(e)}

        # Send final result metadata
        research_time = time.time() - start_time

        # Collect all resource URLs
        all_resources = []
        all_resources.extend(research_metadata["sources"])
        all_resources.extend([img["url"] for img in research_metadata["images"]])
        # Add raw web search URLs as references as well
        try:
            ref_links2: List[str] = []
            for r in research_metadata.get("web_search_results", []):
                href = r.get("href") if isinstance(r, dict) else None
                if isinstance(href, str) and href:
                    ref_links2.append(href)
            all_resources.extend(ref_links2)
        except Exception:
            pass

        # Add YouTube video URLs
        if research_metadata.get("youtube") and isinstance(
            research_metadata["youtube"], dict
        ):
            youtube_videos = research_metadata["youtube"].get("videos", [])
            all_resources.extend(
                [video.get("url", "") for video in youtube_videos if video.get("url")]
            )

        # Add news URLs
        if research_metadata.get("news") and isinstance(
            research_metadata["news"], dict
        ):
            news_items = research_metadata["news"].get("items", [])
            all_resources.extend(
                [item.get("url", "") for item in news_items if item.get("url")]
            )

        # Update research session in database
        if research_slug:
            try:
                chat_db.update_research_status(
                    slug=research_slug,
                    status="completed",
                    duration=research_time,
                    answer=full_answer,
                    resources_used=all_resources,
                    metadata={
                        "sub_questions": research_metadata["sub_questions"],
                        "images": research_metadata["images"],
                        "youtube": research_metadata["youtube"],
                        "news": research_metadata["news"],
                        "rag_results_count": len(research_metadata["rag_results"]),
                        "web_search_results_count": len(
                            research_metadata["web_search_results"]
                        ),
                        "transcript_file": {
                            "file_id": (
                                transcript_save.get("file_id")
                                if isinstance(transcript_save, dict)
                                else None
                            ),
                            "file_url": (
                                transcript_save.get("file_url")
                                if isinstance(transcript_save, dict)
                                else None
                            ),
                        },
                    },
                )
            except Exception as e:
                print(f"Failed to update research session: {e}")

        # Build structured references list for frontend
        references = []
        for i, url in enumerate(research_metadata["sources"], 1):
            ref_obj = {"id": i, "url": url, "title": f"Source {i}", "type": "web"}
            # Try to get title from web_results
            for web_result in web_results:
                if web_result.get("href") == url:
                    ref_obj["title"] = web_result.get("title", ref_obj["title"])
                    ref_obj["snippet"] = web_result.get("body", "")[:200]
                    break
            references.append(ref_obj)

        # Add YouTube references
        for video in saved_videos:
            references.append(
                {
                    "id": len(references) + 1,
                    "url": video.get("url", ""),
                    "title": video.get("title", ""),
                    "type": "youtube",
                    "channel": video.get("channel", ""),
                    "thumbnail": video.get("thumbnail", ""),
                }
            )

        # Add news references (normalized)
        if news_results:
            for news_item in news_results:
                url_n = news_item.get("url", "")
                if not url_n:
                    continue
                references.append(
                    {
                        "id": len(references) + 1,
                        "url": url_n,
                        "title": news_item.get("title", ""),
                        "type": "news",
                        "source": news_item.get("source", ""),
                        "date": news_item.get("date", ""),
                        "image": news_item.get("image"),
                    }
                )

    yield {
            "type": "result",
            "data": {
                "answer": full_answer,
                "sub_questions": research_metadata["sub_questions"],
                "sources": research_metadata["sources"],
                "references": references,  # NEW: Structured references for easy manipulation
                "images": research_metadata["images"],
                "youtube": research_metadata["youtube"],
                "news": research_metadata["news"],
                "rag_results": research_metadata["rag_results"],
        "research_slug": research_slug,  # Include slug in response
                "metadata": {
                    "research_time": research_time,
                    "sources_count": len(research_metadata["sources"]),
                    "images_count": len(research_metadata["images"]),
                    "youtube_count": len(saved_videos),
                    "news_count": len(news_results) if needs_news else 0,
                    "sub_questions_count": len(sub_questions),
                    "model": model,
                    "session_id": session_id,
                    "transcript_file": {
                        "file_id": (
                            transcript_save.get("file_id")
                            if isinstance(transcript_save, dict)
                            else None
                        ),
                        "file_url": (
                            transcript_save.get("file_url")
                            if isinstance(transcript_save, dict)
                            else None
                        ),
                        "success": (
                            transcript_save.get("success")
                            if isinstance(transcript_save, dict)
                            else False
                        ),
                        "error": (
                            transcript_save.get("error")
                            if isinstance(transcript_save, dict)
                            else None
                        ),
                    },
                },
            },
        }

    # End of research_agent_stream


# ========================================
# SYNCHRONOUS VERSION (for non-streaming use)
# ========================================


async def deep_research_agent(
    query: str, model: str = DEFAULT_MODEL, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deep research agent (non-streaming version).

    Args:
        query: User query to research
        model: Model to use for generation
        session_id: Optional session ID

    Returns:
        Dict with complete research results
    """
    result_data = None

    async def collect_results(update: Dict[str, Any]):
        nonlocal result_data
        if update.get("type") == "result":
            result_data = update.get("data")
        elif update.get("type") == "error":
            raise Exception(update.get("message"))

    async for update in research_agent_stream(
        query, model, session_id, collect_results
    ):
        if update.get("type") == "error":
            return {"success": False, "error": update.get("message")}

    if result_data:
        return {"success": True, **result_data}

    return {"success": False, "error": "No results generated"}
