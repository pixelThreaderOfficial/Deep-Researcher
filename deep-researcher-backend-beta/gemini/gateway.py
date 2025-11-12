from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request
from gemini.models.models import get_model_names, get_available_models
from gemini.gen.genText import (
    generate_content_stream,
    generate_content,
    generate_session_title_async,
)
from gemini.gen.research_base import research_agent_stream
from gemini.sqlite_crud import chat_db
import json
import asyncio
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import sqlite3
from bucket.stores import (
    get_file_by_url_path,
    log_file_access,
    list_files_from_db,
    get_file_from_db,
    search_files as bucket_search_files,
    get_file_content_by_id,
    update_file_metadata,
    delete_file_from_db,
    store_uploaded_file,
    store_multiple_files,
    get_bucket_stats,
    get_file_access_stats,
    get_relative_path,
    get_file_by_relative_path,
    store_downloaded_file,
)

app = FastAPI()

# Configure CORS
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:1420",
    "http://tauri.localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TitleUpdate(BaseModel):
    title: str


@app.get("/")
def read_root():
    return {"Hello": "World"}


# ==============================
# File serving endpoint
# ==============================
@app.get("/files/{file_type}/{filename}")
def serve_file(file_type: str, filename: str, user_agent: Optional[str] = None):
    """Serve stored files from bucket using DB metadata.

    - file_type: one of 'uploads', 'downloads', 'generated'
    - filename: the exact stored filename (e.g., generated_images_YYYYMMDD_HHMMSS_uuid.jpg)
    """
    try:
        # Compose path portion to look up
        url_path = f"{file_type}/{filename}"
        file_data = get_file_by_url_path(url_path)
        if not file_data:
            return JSONResponse(
                {"success": False, "error": "File not found"}, status_code=404
            )

        # Log access
        log_file_access(
            file_data["file_id"],
            "serve",
            user_agent=user_agent,
        )

        return FileResponse(
            file_data["file_path"],
            media_type=file_data.get("mime_type") or "application/octet-stream",
        )
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ========================================
# FILES API ENDPOINTS
# ========================================


def _map_io_tag(source_type: Optional[str]) -> str:
    if not source_type:
        return "unknown"
    if str(source_type).startswith("upload"):
        return "uploaded"
    if str(source_type).startswith("download"):
        return "downloaded"
    if str(source_type).startswith("generation"):
        return "generated"
    return str(source_type)


def _friendly_type(file_type: str) -> str:
    return file_type.lstrip("_") if isinstance(file_type, str) else file_type


def _format_file_record(rec: Dict[str, Any], include_content: bool = False, content_mode: str = "auto", content_limit: Optional[int] = None) -> Dict[str, Any]:
    src_meta = rec.get("source_metadata") or {}
    out: Dict[str, Any] = {
        "file_id": rec.get("file_id"),
        "document_name": rec.get("original_filename") or rec.get("stored_filename"),
        "document_type": rec.get("category"),
        "mime_type": rec.get("mime_type"),
        "chat_id": src_meta.get("chat_id"),
        "size_bytes": rec.get("size_bytes"),
        "date_created": rec.get("created_at"),
        "io_tag": _map_io_tag(rec.get("source_type")),
        "type": _friendly_type(rec.get("file_type", "")),
        "file_url": rec.get("file_url"),
        "serve_path": rec.get("serve_path"),
        "stored_filename": rec.get("stored_filename"),
        "tags": rec.get("tags") or [],
    }
    if include_content:
        fid = rec.get("file_id")
        content_res = get_file_content_by_id(
            str(fid), mode=content_mode, limit=content_limit
        )
        out["content"] = content_res.get("content") or content_res.get("content_base64")
        out["content_mode"] = content_res.get("mode")
    return out


@app.get("/api/files")
def list_files(
    type: Optional[str] = Query(None, description="uploads|downloads|generated or internal _uploads/_downloads/_generated"),
    category: Optional[str] = Query(None, description="documents|images|audios|videos|crawls|docs etc."),
    q: Optional[str] = Query(None, description="Search query"),
    limit: int = 50,
    offset: int = 0,
    include_content: bool = False,
    content_mode: str = "auto",
    content_limit: Optional[int] = None,
):
    try:
        file_type = None
        if type:
            file_type = type if type.startswith("_") else f"_{type}"

        if q:
            records = bucket_search_files(q=q, file_type=file_type, category=category, limit=limit, offset=offset)
        else:
            records = list_files_from_db(file_type=file_type, category=category, limit=limit, offset=offset)

        items = [
            _format_file_record(r, include_content=include_content, content_mode=content_mode, content_limit=content_limit)
            for r in records
        ]
        return {"success": True, "count": len(items), "files": items}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/files/{file_id}")
def get_file(file_id: str, include_content: bool = False, content_mode: str = "auto", content_limit: Optional[int] = None):
    try:
        rec = get_file_from_db(file_id)
        if not rec:
            return {"success": False, "error": "File not found"}
        item = _format_file_record(rec, include_content=include_content, content_mode=content_mode, content_limit=content_limit)
        return {"success": True, "file": item}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/files/{file_id}/download")
def download_file(file_id: str):
    try:
        rec = get_file_from_db(file_id)
        if not rec:
            return JSONResponse({"success": False, "error": "File not found"}, status_code=404)

        log_file_access(file_id, "download")

        file_path = rec.get("file_path")
        if not file_path:
            return JSONResponse({"success": False, "error": "File path missing"}, status_code=500)
        return FileResponse(
            str(file_path),
            media_type=rec.get("mime_type") or "application/octet-stream",
            filename=rec.get("original_filename") or rec.get("stored_filename"),
        )
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/files/{file_id}/content")
def file_content(file_id: str, mode: str = "auto", limit: Optional[int] = None):
    try:
        res = get_file_content_by_id(file_id, mode=mode, limit=limit)
        if not res.get("success"):
            return {"success": False, "error": res.get("error")}
        return {"success": True, **res}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/files/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    chat_id: Optional[str] = Form(None),
    content_description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string list
):
    try:
        md: Dict[str, Any] = {}
        if chat_id:
            md["chat_id"] = chat_id
        if content_description:
            md["content_description"] = content_description
        if tags:
            try:
                md["tags"] = json.loads(tags)
            except Exception:
                md["tags"] = [tags]

        result = store_multiple_files(files, metadata=md)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/api/files/{file_id}")
def update_file(file_id: str, content_description: Optional[str] = None, tags: Optional[List[str]] = Query(None), is_active: Optional[bool] = None, chat_id: Optional[str] = None):
    try:
        rec = get_file_from_db(file_id)
        if not rec:
            return {"success": False, "error": "File not found"}

        updates: Dict[str, Any] = {}
        if content_description is not None:
            updates["content_description"] = content_description
        if tags is not None:
            updates["tags"] = tags
        if is_active is not None:
            updates["is_active"] = 1 if is_active else 0

        # Merge chat_id into source_metadata if provided
        if chat_id is not None:
            src_meta = rec.get("source_metadata") or {}
            src_meta["chat_id"] = chat_id
            updates["source_metadata"] = src_meta

        ok = update_file_metadata(file_id, updates)
        return {"success": bool(ok)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/files/{file_id}")
def delete_file(file_id: str, hard: bool = False):
    try:
        ok = delete_file_from_db(file_id, soft_delete=not hard)
        return {"success": bool(ok)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/files/stats")
def files_stats():
    try:
        stats = get_bucket_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/files/{file_id}/stats")
def file_stats(file_id: str, days: int = 30):
    try:
        stats = get_file_access_stats(file_id, days=days)
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/files/search")
def search_files(q: str, type: Optional[str] = None, category: Optional[str] = None, limit: int = 50, offset: int = 0):
    try:
        file_type = None
        if type:
            file_type = type if type.startswith("_") else f"_{type}"
        records = bucket_search_files(q=q, file_type=file_type, category=category, limit=limit, offset=offset)
        items = [_format_file_record(r) for r in records]
        return {"success": True, "count": len(items), "files": items}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/files/sync-crawls")
def sync_crawls(dry_run: bool = False, max_import: int = 200):
    """Import entries from crawl4ai crawls DB into bucket files DB so they appear in Files tab."""
    try:
        crawls_db = Path("bucket/_downloads/crawls/crawls.sqlite3")
        if not crawls_db.exists():
            return {"success": False, "error": "Crawls database not found"}

        imported = 0
        skipped = 0
        with sqlite3.connect(str(crawls_db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT url, title, file_path, favicon, status_code, word_count, crawl_duration, timestamp FROM crawls ORDER BY timestamp DESC").fetchall()
            for row in rows:
                rel = get_relative_path(row["file_path"]) if row["file_path"] else None
                if rel:
                    existing = get_file_by_relative_path(rel)
                    if existing:
                        skipped += 1
                        continue
                if dry_run:
                    imported += 1
                else:
                    # Store this file into bucket DB using existing file path content
                    try:
                        res = store_downloaded_file(
                            file_path=row["file_path"],
                            content_type="crawls",
                            metadata={
                                "url": row["url"],
                                "title": row["title"],
                                "favicon": row["favicon"],
                                "status_code": row["status_code"],
                                "word_count": row["word_count"],
                                "crawl_duration": row["crawl_duration"],
                                "original_crawl_path": rel,
                                "timestamp": row["timestamp"],
                            },
                        )
                        if res.get("success"):
                            imported += 1
                    except Exception:
                        continue
                if imported >= max_import:
                    break
        return {"success": True, "imported": imported, "skipped": skipped, "dry_run": dry_run}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/models")
def get_models():
    try:
        models = get_model_names()
        return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": "Error getting models", "message": str(e)}


@app.get("/models/list")
def get_models_list():
    try:
        models = get_available_models()
        return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": "Error getting models", "message": str(e)}


@app.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    await websocket.accept()
    try:
        # Receive the prompt from client
        data = await websocket.receive_text()
        prompt_data = json.loads(data)
        prompt = prompt_data.get("prompt", "")
        thinking = prompt_data.get("thinking", False)
        model = prompt_data.get("model", "gemini-2.0-flash")
        session_id = prompt_data.get("session_id")  # Optional session_id

        if not prompt:
            await websocket.send_text(json.dumps({"error": "No prompt provided"}))
            return

        # Handle session creation/retrieval
        context_messages = []
        is_new_session = False

        if session_id:
            # Check if session exists
            session = chat_db.get_session_by_id(session_id)
            if not session:
                # Session doesn't exist, create new one
                session_id = chat_db.create_chat_session()
                is_new_session = True
            else:
                # Get context for existing session
                context_messages = chat_db.get_session_context(
                    session_id, max_chars=1000, max_messages=10
                )
        else:
            # Create new session
            session_id = chat_db.create_chat_session()
            is_new_session = True

        # Stream the response
        chatid = None
        async for chunk in generate_content_stream(
            prompt, thinking, model, session_id, context_messages
        ):
            if chunk.startswith("CHATID:"):
                # Extract chatid from the special marker
                chatid = chunk.split("CHATID:", 1)[1]
            else:
                await websocket.send_text(json.dumps({"chunk": chunk}))

        # Generate title in background if this is a new session
        if is_new_session:
            # Start title generation as background task
            asyncio.create_task(_generate_and_update_title(session_id, prompt))

        # Send completion signal with chatid and session_id
        completion_data = {"done": True}
        if chatid:
            completion_data["chatid"] = chatid
        if session_id:
            completion_data["session_id"] = session_id
        await websocket.send_text(json.dumps(completion_data))

    except Exception as e:
        await websocket.send_text(json.dumps({"error": str(e)}))
    finally:
        await websocket.close()


async def _generate_and_update_title(session_id: str, first_message: str):
    """Background task to generate and update session title"""
    try:
        title = await generate_session_title_async(first_message)
        chat_db.update_session_title(session_id, title)
    except Exception as e:
        # If title generation fails, set a default title
        chat_db.update_session_title(session_id, "New Chat")


@app.websocket("/ws/research")
async def websocket_research(websocket: WebSocket):
    """
    WebSocket endpoint for deep research agent.

    Provides real-time progress updates and streams the final answer.
    """
    await websocket.accept()
    try:
        # Receive the query from client
        data = await websocket.receive_text()
        request_data = json.loads(data)
        query = request_data.get("query", "")
        model = request_data.get("model", "gemini-2.0-flash")
        session_id = request_data.get("session_id")  # Optional session_id

        if not query:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "No query provided"})
            )
            return

        # Progress callback to send updates via WebSocket
        async def send_progress(update: dict):
            await websocket.send_text(json.dumps(update))

        # Stream research results
        async for update in research_agent_stream(
            query=query,
            model=model,
            session_id=session_id,
            progress_callback=send_progress,
        ):
            # Send update to client
            await websocket.send_text(json.dumps(update))

            # If error or final result, we're done
            if update.get("type") in ["error", "result"]:
                break

    except Exception as e:
        await websocket.send_text(
            json.dumps({"type": "error", "message": f"Research failed: {str(e)}"})
        )
    finally:
        await websocket.close()


# ========================================
# CHAT HISTORY API ENDPOINTS
# ========================================


@app.post("/api/chat/generate")
def generate_chat(
    prompt: str,
    thinking: bool = False,
    model: str = "gemini-2.0-flash",
    session_id: str = None,
):
    """Generate content and save to chat history (non-streaming)"""
    try:
        # Handle session creation/retrieval
        context_messages = []
        is_new_session = False

        if session_id:
            # Check if session exists
            session = chat_db.get_session_by_id(session_id)
            if not session:
                # Session doesn't exist, create new one
                session_id = chat_db.create_chat_session()
                is_new_session = True
            else:
                # Get context for existing session
                context_messages = chat_db.get_session_context(
                    session_id, max_chars=1000, max_messages=10
                )
        else:
            # Create new session
            session_id = chat_db.create_chat_session()
            is_new_session = True

        result = generate_content(prompt, thinking, model, session_id, context_messages)

        # Generate title in background if this is a new session
        if is_new_session:
            asyncio.create_task(_generate_and_update_title(session_id, prompt))

        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/chat/history")
def get_chat_history(limit: int = 50, offset: int = 0, session_id: str = None):
    """Get chat history with pagination. Optionally filter by session_id."""
    try:
        if session_id:
            chats = chat_db.get_chats_by_session_id(session_id, limit, offset)
        else:
            chats = chat_db.get_all_chats(limit, offset)
        return {"success": True, "chats": chats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/chat/{chatid}")
def get_chat_by_id(chatid: str):
    """Get a specific chat by ID"""
    try:
        chat = chat_db.get_chat_by_id(chatid)
        if chat:
            return {"success": True, "chat": chat}
        else:
            return {"success": False, "error": "Chat not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/chat/search/{query}")
def search_chats(query: str, limit: int = 50):
    """Search chats by prompt or response content"""
    try:
        chats = chat_db.search_chats(query, limit)
        return {"success": True, "chats": chats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/chat/stats")
def get_chat_stats():
    """Get chat history statistics"""
    try:
        stats = chat_db.get_chat_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/chat/{chatid}")
def delete_chat(chatid: str):
    """Delete a chat by ID"""
    try:
        deleted = chat_db.delete_chat(chatid)
        if deleted:
            return {"success": True, "message": "Chat deleted successfully"}
        else:
            return {"success": False, "error": "Chat not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========================================
# CHAT SESSION API ENDPOINTS
# ========================================


@app.get("/api/sessions")
def get_all_sessions(limit: int = 100, offset: int = 0):
    """Get all chat sessions with pagination"""
    try:
        sessions = chat_db.get_all_sessions(limit, offset)
        # Add message count and stats to each session
        for session in sessions:
            session_id = session.get("session_id")
            if session_id:
                stats = chat_db.get_session_stats(session_id)
                session["stats"] = stats
        return {"success": True, "sessions": sessions}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    """Get session details with messages"""
    try:
        session = chat_db.get_session_by_id(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Get messages for this session
        messages = chat_db.get_session_messages(session_id)
        stats = chat_db.get_session_stats(session_id)

        session["messages"] = messages
        session["stats"] = stats

        return {"success": True, "session": session}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str, limit: int = 100):
    """Get messages in a session"""
    try:
        session = chat_db.get_session_by_id(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        messages = chat_db.get_session_messages(session_id, limit)
        return {"success": True, "messages": messages}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/api/sessions/{session_id}/title")
def update_session_title(session_id: str, title_update: TitleUpdate):
    """Update session title"""
    try:
        session = chat_db.get_session_by_id(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        updated = chat_db.update_session_title(session_id, title_update.title)
        if updated:
            return {"success": True, "message": "Title updated successfully"}
        else:
            return {"success": False, "error": "Failed to update title"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a session and all its messages"""
    try:
        deleted = chat_db.delete_session(session_id)
        if deleted:
            return {"success": True, "message": "Session deleted successfully"}
        else:
            return {"success": False, "error": "Session not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/sessions/{session_id}/regenerate-title")
async def regenerate_session_title(session_id: str):
    """Regenerate title for a session based on its first message"""
    try:
        session = chat_db.get_session_by_id(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Get first message
        messages = chat_db.get_session_messages(session_id, limit=1)
        if not messages:
            return {"success": False, "error": "No messages found in session"}

        first_message = messages[0].get("prompt", "")
        if not first_message:
            return {"success": False, "error": "No prompt found in first message"}

        # Generate new title
        title = await generate_session_title_async(first_message)
        updated = chat_db.update_session_title(session_id, title)

        if updated:
            return {
                "success": True,
                "title": title,
                "message": "Title regenerated successfully",
            }
        else:
            return {"success": False, "error": "Failed to update title"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/sessions/{session_id}/stats")
def get_session_stats(session_id: str):
    """Get statistics for a session"""
    try:
        session = chat_db.get_session_by_id(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        stats = chat_db.get_session_stats(session_id)
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========================================
# CHAT SETTINGS API ENDPOINTS
# ========================================


@app.post("/api/settings/global")
def create_or_update_global_settings(
    model: str,
    system_prompt: str = None,
    user_name: str = None,
    prompt_template_id: str = None,
    top_p: float = 0.9,
    top_k: float = 0.9,
    document_analysis_mode: str = "off",
    enable_thinking: bool = False,
    max_previous_memory_retention: int = 5,
):
    """Create or update global chat settings"""
    try:
        settings_id = chat_db.create_or_update_global_settings(
            model=model,
            system_prompt=system_prompt,
            user_name=user_name,
            prompt_template_id=prompt_template_id,
            top_p=top_p,
            top_k=top_k,
            document_analysis_mode=document_analysis_mode,
            enable_thinking=enable_thinking,
            max_previous_memory_retention=max_previous_memory_retention,
        )
        return {"success": True, "settings_id": settings_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/settings/chat/{chat_id}")
def create_chat_settings(
    chat_id: str,
    model: str,
    system_prompt: str = None,
    user_name: str = None,
    prompt_template_id: str = None,
    top_p: float = 0.9,
    top_k: float = 0.9,
    document_analysis_mode: str = "off",
    enable_thinking: bool = False,
    max_previous_memory_retention: int = 5,
):
    """Create settings for a specific chat"""
    try:
        settings_id = chat_db.create_chat_settings(
            model=model,
            system_prompt=system_prompt,
            user_name=user_name,
            prompt_template_id=prompt_template_id,
            top_p=top_p,
            top_k=top_k,
            document_analysis_mode=document_analysis_mode,
            enable_thinking=enable_thinking,
            max_previous_memory_retention=max_previous_memory_retention,
            chat_id=chat_id,
            is_global=False,
        )
        return {"success": True, "settings_id": settings_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/settings/global")
def get_global_settings():
    """Get global chat settings"""
    try:
        settings = chat_db.get_global_settings()
        if settings:
            return {"success": True, "settings": settings}
        else:
            return {"success": False, "error": "No global settings found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/settings/chat/{chat_id}")
def get_chat_settings(chat_id: str):
    """Get settings for a specific chat"""
    try:
        settings = chat_db.get_chat_settings(chat_id=chat_id)
        if settings:
            return {"success": True, "settings": settings}
        else:
            return {"success": False, "error": "No settings found for this chat"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/api/settings/chat/{chat_id}")
def update_chat_settings(
    chat_id: str,
    system_prompt: str = None,
    user_name: str = None,
    model: str = None,
    prompt_template_id: str = None,
    top_p: float = None,
    top_k: float = None,
    document_analysis_mode: str = None,
    enable_thinking: bool = None,
    max_previous_memory_retention: int = None,
):
    """Update settings for a specific chat"""
    try:
        updated = chat_db.update_chat_settings_by_chat_id(
            chat_id=chat_id,
            system_prompt=system_prompt,
            user_name=user_name,
            model=model,
            prompt_template_id=prompt_template_id,
            top_p=top_p,
            top_k=top_k,
            document_analysis_mode=document_analysis_mode,
            enable_thinking=enable_thinking,
            max_previous_memory_retention=max_previous_memory_retention,
        )
        if updated:
            return {"success": True, "message": "Settings updated successfully"}
        else:
            return {"success": False, "error": "No settings found for this chat"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/api/settings/global")
def update_global_settings(
    system_prompt: str = None,
    user_name: str = None,
    model: str = None,
    prompt_template_id: str = None,
    top_p: float = None,
    top_k: float = None,
    document_analysis_mode: str = None,
    enable_thinking: bool = None,
    max_previous_memory_retention: int = None,
):
    """Update global settings"""
    try:
        updated = chat_db.update_chat_settings_by_chat_id(
            chat_id=None,  # This will update global settings
            system_prompt=system_prompt,
            user_name=user_name,
            model=model,
            prompt_template_id=prompt_template_id,
            top_p=top_p,
            top_k=top_k,
            document_analysis_mode=document_analysis_mode,
            enable_thinking=enable_thinking,
            max_previous_memory_retention=max_previous_memory_retention,
            is_global=True,
        )
        if updated:
            return {"success": True, "message": "Global settings updated successfully"}
        else:
            return {"success": False, "error": "No global settings found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/settings")
def get_all_settings(limit: int = 100, offset: int = 0):
    """Get all chat settings with pagination"""
    try:
        settings = chat_db.get_all_chat_settings(limit, offset)
        return {"success": True, "settings": settings}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/settings/chat/{chat_id}")
def delete_chat_settings(chat_id: str):
    """Delete settings for a specific chat"""
    try:
        deleted = chat_db.delete_chat_settings_by_chat_id(chat_id)
        if deleted:
            return {"success": True, "message": "Settings deleted successfully"}
        else:
            return {"success": False, "error": "No settings found for this chat"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========================================
# RAG STORE FILES & Documents
# ========================================
# @app.post("/api/v0/rag/store_files")
# def store_files(files: List[UploadFile] = File(...)):
#     pass

# @app.post("/api/v0/rag/store_documents")
# def store_documents(documents: List[str] = Form(...)):
#     pass

# @app.post("/api/v0/rag/index_documents")
# def index_documents(documents: List[str] = Form(...)):
#     pass

# @app.post("/api/v0/rag/query_documents")
# def query_documents(query: str = Form(...)):
#     pass


# ========================================
# RESEARCH SESSION MANAGEMENT API
# ========================================


@app.get("/api/research/sessions")
def get_research_sessions(
    limit: int = 50, offset: int = 0, status: Optional[str] = None
):
    """
    Get all research sessions with pagination and optional status filtering

    Args:
        limit: Maximum number of results (default: 50)
        offset: Number of results to skip (default: 0)
        status: Filter by status - 'running', 'completed', or 'failed' (optional)

    Returns:
        List of research sessions with metadata
    """
    try:
        researches = chat_db.get_all_researches(
            limit=limit, offset=offset, status=status
        )
        return {
            "success": True,
            "researches": researches,
            "count": len(researches),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/research/sessions/{slug}")
def get_research_session(slug: str):
    """
    Get a specific research session by its slug

    Args:
        slug: Research session UUID

    Returns:
        Research session details including query, answer, resources, and metadata
    """
    try:
        research = chat_db.get_research_by_slug(slug)
        if research:
            return {"success": True, "research": research}
        else:
            return {"success": False, "error": "Research session not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/research/sessions/{slug}")
def delete_research_session(slug: str):
    """
    Delete a research session by its slug

    Args:
        slug: Research session UUID

    Returns:
        Success status
    """
    try:
        deleted = chat_db.delete_research(slug)
        if deleted:
            return {"success": True, "message": "Research session deleted successfully"}
        else:
            return {"success": False, "error": "Research session not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/research/stats")
def get_research_statistics():
    """
    Get statistics about all research sessions

    Returns:
        Statistics including total, completed, failed, running counts,
        average duration, and unique models used
    """
    try:
        stats = chat_db.get_research_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/research/search")
def search_research_sessions(q: str, limit: int = 50):
    """
    Search research sessions by query, title, or answer content

    Args:
        q: Search query string
        limit: Maximum number of results (default: 50)

    Returns:
        List of matching research sessions
    """
    try:
        results = chat_db.search_researches(query=q, limit=limit)
        return {"success": True, "results": results, "count": len(results), "query": q}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/api/research/sessions/{slug}/title")
def update_research_title(slug: str, title: str):
    """
    Update the title of a research session

    Args:
        slug: Research session UUID
        title: New title for the research

    Returns:
        Success status
    """
    try:
        updated = chat_db.update_research_title(slug=slug, title=title)
        if updated:
            return {"success": True, "message": "Research title updated successfully"}
        else:
            return {"success": False, "error": "Research session not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
