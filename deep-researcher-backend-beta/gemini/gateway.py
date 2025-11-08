from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket
from fastapi.responses import FileResponse, JSONResponse
from gemini.models.models import get_model_names, get_available_models
from gemini.gen.genText import generate_content_stream, generate_content, generate_session_title_async
from gemini.gen.research_base import research_agent_stream
from gemini.sqlite_crud import chat_db
import json
import asyncio
from pydantic import BaseModel
from typing import Optional
from bucket.stores import get_file_by_url_path, log_file_access

app = FastAPI()

# Configure CORS
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:1420",
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
            return JSONResponse({"success": False, "error": "File not found"}, status_code=404)

        # Log access
        log_file_access(
            file_data["file_id"],
            "serve",
            user_agent=user_agent,
        )

        return FileResponse(file_data["file_path"], media_type=file_data.get("mime_type") or "application/octet-stream")
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

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
                context_messages = chat_db.get_session_context(session_id, max_chars=1000, max_messages=10)
        else:
            # Create new session
            session_id = chat_db.create_chat_session()
            is_new_session = True

        # Stream the response
        chatid = None
        async for chunk in generate_content_stream(prompt, thinking, model, session_id, context_messages):
            if chunk.startswith("CHATID:"):
                # Extract chatid from the special marker
                chatid = chunk.split("CHATID:", 1)[1]
            else:
                await websocket.send_text(json.dumps({"chunk": chunk}))

        # Generate title in background if this is a new session
        if is_new_session:
            # Start title generation as background task
            asyncio.create_task(
                _generate_and_update_title(session_id, prompt)
            )

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
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "No query provided"
            }))
            return

        # Progress callback to send updates via WebSocket
        async def send_progress(update: dict):
            await websocket.send_text(json.dumps(update))

        # Stream research results
        async for update in research_agent_stream(
            query=query,
            model=model,
            session_id=session_id,
            progress_callback=send_progress
        ):
            # Send update to client
            await websocket.send_text(json.dumps(update))
            
            # If error or final result, we're done
            if update.get("type") in ["error", "result"]:
                break

    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Research failed: {str(e)}"
        }))
    finally:
        await websocket.close()


# ========================================
# CHAT HISTORY API ENDPOINTS
# ========================================

@app.post("/api/chat/generate")
def generate_chat(prompt: str, thinking: bool = False, model: str = "gemini-2.0-flash", session_id: str = None):
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
                context_messages = chat_db.get_session_context(session_id, max_chars=1000, max_messages=10)
        else:
            # Create new session
            session_id = chat_db.create_chat_session()
            is_new_session = True
        
        result = generate_content(prompt, thinking, model, session_id, context_messages)
        
        # Generate title in background if this is a new session
        if is_new_session:
            asyncio.create_task(
                _generate_and_update_title(session_id, prompt)
            )
        
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
            session_id = session.get('session_id')
            if session_id:
                stats = chat_db.get_session_stats(session_id)
                session['stats'] = stats
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
        
        session['messages'] = messages
        session['stats'] = stats
        
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
        
        first_message = messages[0].get('prompt', '')
        if not first_message:
            return {"success": False, "error": "No prompt found in first message"}
        
        # Generate new title
        title = await generate_session_title_async(first_message)
        updated = chat_db.update_session_title(session_id, title)
        
        if updated:
            return {"success": True, "title": title, "message": "Title regenerated successfully"}
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
    max_previous_memory_retention: int = 5
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
            max_previous_memory_retention=max_previous_memory_retention
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
    max_previous_memory_retention: int = 5
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
            is_global=False
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
    max_previous_memory_retention: int = None
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
            max_previous_memory_retention=max_previous_memory_retention
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
    max_previous_memory_retention: int = None
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
            is_global=True
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

