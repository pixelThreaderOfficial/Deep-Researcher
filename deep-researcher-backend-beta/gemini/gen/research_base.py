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
from typing import Dict, List, Optional, Any, AsyncGenerator
from urllib.request import urlopen
from google import genai
from google.genai import types
from dotenv import load_dotenv

from gemini.tools.web_search import (
    web_search,
    _scrape_urls_async,
    image_search,
    news_search
)
from gemini.rag_store.rag_stores import (
    create_documents,
    query_documents,
    save_scraped_content
)
from bucket.stores import store_generated_content

load_dotenv()

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
        
        result = response.text.strip().upper()
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
        
        result_text = response.text.strip()
        # Extract JSON from response (in case model adds extra text)
        if "{" in result_text:
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            result_text = result_text[json_start:json_end]
        
        result = json.loads(result_text)
        return {
            "needs_images": result.get("needs_images", False),
            "needs_news": result.get("needs_news", False),
            "is_clear": result.get("is_clear", True)
        }
        
    except Exception as e:
        print(f"Error analyzing query needs: {e}")
        # Default to safe values
        return {
            "needs_images": False,
            "needs_news": False,
            "is_clear": True
        }


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
        
        image_content = await asyncio.run_in_executor(None, download_image)
        
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
                "saved_at": datetime.now().isoformat()
            }
        )
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save image: {str(e)}",
            "image_url": image_url
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
        news_bytes = news_json.encode('utf-8')
        
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
                "saved_at": datetime.now().isoformat()
            }
        )
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save news: {str(e)}"
        }


# ========================================
# MAIN RESEARCH AGENT
# ========================================

async def research_agent_stream(
    query: str,
    model: str = DEFAULT_MODEL,
    session_id: Optional[str] = None,
    progress_callback: Optional[callable] = None
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
        "news": [],
        "rag_results": [],
        "web_search_results": []
    }
    
    try:
        # Step 1: Check sexual content
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "analyzing",
                "message": "Checking content safety..."
            })
        
        if check_sexual_content(query):
            yield {
                "type": "error",
                "message": "Sorry, I can't help with that."
            }
            return
        
        # Step 2: Analyze query needs
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "analyzing",
                "message": "Analyzing query requirements..."
            })
        
        query_analysis = analyze_query_needs(query)
        needs_images = query_analysis.get("needs_images", False)
        needs_news = query_analysis.get("needs_news", False)
        is_clear = query_analysis.get("is_clear", True)
        
        # Step 3: Web search
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "searching",
                "message": "Searching web for relevant information..."
            })
        
        web_results = web_search(query, max_results=10)
        research_metadata["web_search_results"] = web_results
        
        if not web_results:
            yield {
                "type": "error",
                "message": "No relevant information found. Please try rephrasing your query."
            }
            return
        
        # Extract URLs from search results
        urls = [result.get("href", "") for result in web_results if result.get("href")]
        
        # Step 4: Scrape URLs
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "scraping",
                "message": f"Scraping {len(urls)} URLs..."
            })
        
        scraped_content = {}
        if urls:
            try:
                scraped_content = await _scrape_urls_async(urls[:5])  # Limit to top 5 URLs
                # Filter out error messages from scraped content
                scraped_content = {
                    url: content for url, content in scraped_content.items() 
                    if not (isinstance(content, str) and content.startswith("Error:"))
                }
            except Exception as e:
                # If scraping fails, continue with empty content but log the error
                print(f"Error scraping URLs: {str(e)}")
                scraped_content = {}
        
        # Step 5: Save to RAG
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "saving",
                "message": "Saving scraped content to database..."
            })
        
        rag_save_success = False
        if scraped_content:
            try:
                save_result = save_scraped_content(scraped_content)
                if save_result.get("success"):
                    rag_save_success = True
                    research_metadata["sources"].extend(list(scraped_content.keys()))
                    print(f"RAG save successful: {save_result.get('count', 0)} documents saved")
                else:
                    print(f"RAG save failed: {save_result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"Error saving to RAG: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Step 6: Query RAG
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "rag_query",
                "message": "Querying knowledge base for relevant information..."
            })
        
        rag_results = {"success": False, "results": []}
        try:
            rag_results = query_documents(query, max_results=5)
            if not rag_results.get("success"):
                print(f"RAG query failed: {rag_results.get('error', 'Unknown error')}")
            elif rag_results.get("results"):
                research_metadata["rag_results"] = rag_results.get("results", [])
                print(f"RAG query successful: {len(rag_results.get('results', []))} results found")
            else:
                print("RAG query returned no results")
        except Exception as e:
            print(f"Error querying RAG: {str(e)}")
            import traceback
            traceback.print_exc()
            rag_results = {"success": False, "results": [], "error": str(e)}
        
        # Step 7: Check if relevant info found
        # Use scraped content even if RAG doesn't work
        relevant_info_found = (
            len(scraped_content) > 0 or  # We have scraped content
            (rag_results.get("success") and len(rag_results.get("results", [])) > 0)  # Or RAG found results
        )
        
        if not relevant_info_found:
            # Check query clarity only if we have no content at all
            if not is_clear:
                yield {
                    "type": "error",
                    "message": "I'm not sure what you mean. Please try again with a more specific query."
                }
                return
        
        # Step 8: Optional image search
        saved_images = []
        if needs_images:
            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "image_search",
                    "message": "Searching for relevant images..."
                })
            
            image_results = image_search(query, max_results=5)
            
            if image_results:
                for img_result in image_results[:3]:  # Limit to top 3 images
                    image_url = img_result.get("image") or img_result.get("url")
                    if image_url:
                        save_result = await save_image_to_bucket(image_url, query)
                        if save_result.get("success"):
                            saved_images.append({
                                "url": image_url,
                                "file_url": save_result.get("file_url"),
                                "file_id": save_result.get("file_id"),
                                "title": img_result.get("title", "")
                            })
            
            research_metadata["images"] = saved_images
        
        # Step 9: Optional news search
        saved_news = []
        if needs_news:
            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "news_search",
                    "message": "Searching for recent news..."
                })
            
            news_results = news_search(query, max_results=5)
            
            if news_results:
                save_result = save_news_to_bucket(news_results, query)
                if save_result.get("success"):
                    saved_news = news_results
                    research_metadata["news"] = {
                        "file_url": save_result.get("file_url"),
                        "file_id": save_result.get("file_id"),
                        "items": news_results
                    }
        
        # Step 10: Combine all content and generate final answer
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "analyzing_data",
                "message": "Analyzing collected data..."
            })
        
        # Prepare context for final answer
        context_parts = []
        
        # Add RAG results (if available)
        if rag_results.get("success") and rag_results.get("results"):
            for result in rag_results["results"][:3]:
                content = result.get('content', '')
                if content:
                    context_parts.append(f"Source: {content[:500]}")
        
        # Add scraped content snippets (always use these if available)
        if scraped_content:
            for url, content in list(scraped_content.items())[:3]:
                if content and not (isinstance(content, str) and content.startswith("Error:")):
                    context_parts.append(f"Source ({url}): {str(content)[:500]}")
        
        # If we have no context, use web search results
        if not context_parts and web_results:
            for result in web_results[:3]:
                title = result.get("title", "")
                body = result.get("body", "")
                if title or body:
                    context_parts.append(f"Source: {title}\n{body[:300]}")
        
        context = "\n\n".join(context_parts) if context_parts else "No specific sources found, but conducting research based on general knowledge."
        
        # Generate final answer prompt
        final_prompt = f"""You are a professional researcher. Based on the following information, provide a comprehensive and well-structured answer to the user's query.

User Query: {query}

Research Context:
{context}

Please provide a detailed, accurate answer based on the research context. Include citations when relevant. If images or news were found, mention them appropriately."""

        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "generating",
                "message": "Generating final answer..."
            })
        
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
                yield {
                    "type": "answer_chunk",
                    "chunk": chunk.text
                }
                await asyncio.sleep(0)  # Allow other tasks to run
        
        # Send final result metadata
        research_time = time.time() - start_time
        yield {
            "type": "result",
            "data": {
                "answer": full_answer,
                "sources": research_metadata["sources"],
                "images": research_metadata["images"],
                "news": research_metadata["news"],
                "rag_results": research_metadata["rag_results"],
                "metadata": {
                    "research_time": research_time,
                    "sources_count": len(research_metadata["sources"]),
                    "images_count": len(research_metadata["images"]),
                    "news_count": len(news_results) if needs_news else 0,
                    "model": model,
                    "session_id": session_id
                }
            }
        }
        
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        print(f"Research agent error: {error_msg}")
        import traceback
        traceback.print_exc()
        yield {
            "type": "error",
            "message": f"Research failed: {error_msg}"
        }


# ========================================
# SYNCHRONOUS VERSION (for non-streaming use)
# ========================================

async def deep_research_agent(
    query: str,
    model: str = DEFAULT_MODEL,
    session_id: Optional[str] = None
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
    
    async for update in research_agent_stream(query, model, session_id, collect_results):
        if update.get("type") == "error":
            return {
                "success": False,
                "error": update.get("message")
            }
    
    if result_data:
        return {
            "success": True,
            **result_data
        }
    
    return {
        "success": False,
        "error": "No results generated"
    }
