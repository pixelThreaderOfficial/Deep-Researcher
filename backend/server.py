"""
This is the main entry point for the Deep Researcher v2 API.
It is used to start and stop the background workers.
"""

from contextlib import asynccontextmanager
import json
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from main.apis.bucket.bucket_urls import router as bucket_router
from main.apis.chats.chat_urls import router as chats_router
from main.apis.history.history_urls import router as history_router
from main.apis.reasearch.research_urls import router as research_router
from main.apis.settings.settings_urls import router as settings_router
from main.apis.workspace.workspace_urls import router as workspace_router
from main.src.utils.core.task_schedular import scheduler
from main.sse.event_bus import event_bus
from main.sse.wss import wss

# Initilize the queue workers: queue system for entire application so add temprory non important task to background processing queue.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """A context manager for the FastAPI application lifespan.
    It is used to start and stop the background workers.
    """
    # -------- SERVER START --------
    await scheduler.start()
    await wss.start()

    yield

    # -------- SERVER SHUTDOWN --------
    await wss.shutdown()
    await scheduler.shutdown()


app = FastAPI(title="Research API", version="1.0.0", lifespan=lifespan)

# Include the scheme (http) and port. Add 127.0.0.1 as well if needed.
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8001",
    "http://127.0.0.1:001",
]

# Register CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # or ["*"] for all origins (not recommended for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def format_sse(data: dict):
    return f"data: {json.dumps(data)}\n\n"


@app.get("/events/{client_id}")
async def stream(request: Request, client_id: str):
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


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await wss.handle_connection(websocket=websocket, client_id=client_id)


app.include_router(research_router)
app.include_router(workspace_router)
app.include_router(history_router)
app.include_router(chats_router)
app.include_router(bucket_router)
app.include_router(settings_router)

app.get("/health", tags=["health"])(lambda: {"status": "ok"})


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, workers=1)
