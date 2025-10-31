from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import asyncio
import time
from gemini.sqlite_crud import chat_db
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

MODEL_NAME = "gemini-2.0-flash"
TITLE_MODEL = "gemini-2.0-flash"  # Use lightweight model for title generation

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def format_context_for_prompt(context_messages: list) -> str:
    """Format context messages into a conversation history string"""
    if not context_messages:
        return ""
    
    formatted_context = []
    for msg in context_messages:
        user_msg = msg.get('prompt', '')
        ai_msg = msg.get('response', '')
        formatted_context.append(f"User: {user_msg}")
        formatted_context.append(f"Assistant: {ai_msg}")
    
    return "\n".join(formatted_context) + "\n\n"


def generate_content(prompt: str, thinking: bool = False, model: str = MODEL_NAME,
                     session_id: Optional[str] = None, context_messages: Optional[list] = None):
    start_time = time.time()

    # Build the full prompt with context
    full_prompt = prompt
    if context_messages:
        context_str = format_context_for_prompt(context_messages)
        full_prompt = context_str + prompt

    response = client.generate_content(
        model=model,
        contents=full_prompt,
        thinking=thinking,
    )

    generation_time = time.time() - start_time

    # Extract token usage if available
    tokens_used = None
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens_used = response.usage_metadata.total_token_count

    # Prepare metadata
    metadata = {
        "thinking_enabled": thinking,
        "model_version": model,
        "has_usage_metadata": hasattr(response, 'usage_metadata'),
        "finish_reason": getattr(response, 'finish_reason', None),
        "session_id": session_id,
    }

    # Save to database
    chatid = chat_db.create_chat_entry(
        prompt=prompt,
        response=response.text,
        model=model,
        thinking=thinking,
        generation_time=generation_time,
        tokens_used=tokens_used,
        metadata=metadata,
        session_id=session_id
    )

    # Update session timestamp if session_id provided
    if session_id:
        chat_db.update_session_updated_at(session_id)

    # Return both response and chatid
    return {
        "response": response.text,
        "chatid": chatid,
        "generation_time": generation_time,
        "tokens_used": tokens_used,
        "session_id": session_id
    }


async def generate_content_stream(prompt: str, thinking: bool = False, model: str = MODEL_NAME,
                                  session_id: Optional[str] = None, context_messages: Optional[list] = None):
    """Async generator that yields streaming response chunks and saves to database"""
    start_time = time.time()
    full_response = ""

    # Build the full prompt with context
    full_prompt = prompt
    if context_messages:
        context_str = format_context_for_prompt(context_messages)
        full_prompt = context_str + prompt

    # Get the stream synchronously
    # We iterate it synchronously but yield asynchronously
    response = client.models.generate_content_stream(
        model=model,
        contents=[full_prompt],
        config=types.GenerateContentConfig(
            thinking=thinking,
        ) if thinking else None
    )
    
    tokens_used = None
    
    # Iterate chunks synchronously (this blocks, but we need to consume the generator)
    # Yield chunks asynchronously to allow other tasks to run
    for chunk in response:
        if chunk.text:
            full_response += chunk.text
            yield chunk.text
            # Allow other async tasks to run between chunks
            await asyncio.sleep(0)

        # Extract token usage from the last chunk if available
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            tokens_used = chunk.usage_metadata.total_token_count

    # Save to database after streaming is complete
    generation_time = time.time() - start_time

    # Prepare metadata
    metadata = {
        "thinking_enabled": thinking,
        "model_version": model,
        "is_streaming": True,
        "has_usage_metadata": tokens_used is not None,
        "session_id": session_id,
    }

    # Save to database
    chatid = chat_db.create_chat_entry(
        prompt=prompt,
        response=full_response,
        model=model,
        thinking=thinking,
        generation_time=generation_time,
        tokens_used=tokens_used,
        metadata=metadata,
        session_id=session_id
    )

    # Update session timestamp if session_id provided
    if session_id:
        chat_db.update_session_updated_at(session_id)

    # Yield the chatid as the last item for the client to know
    yield f"CHATID:{chatid}"


def generate_session_title(first_message: str, model: str = TITLE_MODEL) -> str:
    """
    Generate a title for a chat session based on the first message
    
    Args:
        first_message: The first user message in the conversation
        model: The model to use for title generation
        
    Returns:
        title: Generated title string
    """
    try:
        title_prompt = f"""Generate a concise, descriptive title (maximum 6 words) for this conversation based on the first message. 
Only return the title, nothing else.

First message: {first_message[:500]}

Title:"""

        response = client.generate_content(
            model=model,
            contents=title_prompt,
        )
        
        title = response.text.strip()
        # Clean up title - remove quotes if present
        title = title.strip('"').strip("'").strip()
        # Limit to 60 characters
        if len(title) > 60:
            title = title[:57] + "..."
        
        return title if title else "New Chat"
    except Exception as e:
        # Fallback to a default title if generation fails
        return "New Chat"


async def generate_session_title_async(first_message: str, model: str = TITLE_MODEL) -> str:
    """Async wrapper for title generation"""
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor()
    return await loop.run_in_executor(executor, generate_session_title, first_message, model)

