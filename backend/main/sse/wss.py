import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect


@dataclass
class QuestionResponse:
    request_id: str
    _future: "asyncio.Future[Dict[str, Any]]"

    async def get_answers(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        if timeout is None:
            return await self._future
        return await asyncio.wait_for(self._future, timeout=timeout)

    # Alias to match requested usage style.
    async def getAnswers(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        return await self.get_answers(timeout=timeout)


class WSSManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._incoming_by_user: Dict[str, "asyncio.Queue[Dict[str, Any]]"] = {}
        self._pending_questions: Dict[str, "asyncio.Future[Dict[str, Any]]"] = {}
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def shutdown(self) -> None:
        self._running = False
        async with self._lock:
            pending = list(self._pending_questions.values())
            self._pending_questions.clear()
        for future in pending:
            if not future.done():
                future.cancel()

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(client_id, set()).add(websocket)
            self._incoming_by_user.setdefault(client_id, asyncio.Queue())

    async def disconnect(self, client_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(client_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(client_id, None)

    async def handle_connection(self, websocket: WebSocket, client_id: str) -> None:
        await self.connect(client_id, websocket)
        try:
            while True:
                message = await websocket.receive_json()
                await self._handle_incoming_message(
                    client_id=client_id, message=message
                )
        except WebSocketDisconnect:
            pass
        finally:
            await self.disconnect(client_id, websocket)

    async def _handle_incoming_message(
        self, client_id: str, message: Dict[str, Any]
    ) -> None:
        message_type = message.get("type")
        if message_type == "answer" and message.get("request_id"):
            request_id = str(message["request_id"])
            async with self._lock:
                future = self._pending_questions.pop(request_id, None)
            if future and not future.done():
                future.set_result(message)
            return

        queue = self._incoming_by_user.setdefault(client_id, asyncio.Queue())
        await queue.put(message)

    async def send_message(self, client_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(client_id, set()))

        if not sockets:
            raise RuntimeError(
                f"No active websocket connection for client_id={client_id}"
            )

        stale_sockets = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                stale_sockets.append(ws)

        if stale_sockets:
            async with self._lock:
                current = self._connections.get(client_id, set())
                for ws in stale_sockets:
                    current.discard(ws)
                if not current:
                    self._connections.pop(client_id, None)

    async def receive_message(
        self, client_id: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        queue = self._incoming_by_user.setdefault(client_id, asyncio.Queue())
        if timeout is None:
            return await queue.get()
        return await asyncio.wait_for(queue.get(), timeout=timeout)

    async def send_questions(
        self,
        payload: Dict[str, Any],
        client_id: Optional[str] = None,
    ) -> QuestionResponse:
        target_client = (
            client_id
            or payload.get("client_id")
            or payload.get("user_id")
            or payload.get("userId")
        )
        if not target_client:
            raise ValueError(
                "client_id is required: pass it explicitly or include in payload"
            )

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: "asyncio.Future[Dict[str, Any]]" = loop.create_future()

        async with self._lock:
            self._pending_questions[request_id] = future

        message = {
            "type": "question",
            "request_id": request_id,
            "payload": payload,
        }

        try:
            await self.send_message(str(target_client), message)
        except Exception:
            async with self._lock:
                popped = self._pending_questions.pop(request_id, None)
            if popped and not popped.done():
                popped.cancel()
            raise

        return QuestionResponse(request_id=request_id, _future=future)

    # Alias to match requested usage style.
    async def sendQuestions(
        self,
        payload: Dict[str, Any],
        client_id: Optional[str] = None,
    ) -> QuestionResponse:
        return await self.send_questions(payload=payload, client_id=client_id)

    async def publish(self, client_id: str, payload: Dict[str, Any]) -> None:
        await self.send_message(client_id=client_id, payload=payload)

    async def ask_and_wait(
        self,
        payload: Dict[str, Any],
        client_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        response = await self.send_questions(payload=payload, client_id=client_id)
        try:
            return await response.get_answers(timeout=timeout)
        finally:
            # Make sure no leaked future remains if caller cancels while waiting.
            with contextlib.suppress(Exception):
                if response.request_id in self._pending_questions:
                    async with self._lock:
                        pending = self._pending_questions.pop(response.request_id, None)
                    if pending and not pending.done():
                        pending.cancel()


wss = WSSManager()
