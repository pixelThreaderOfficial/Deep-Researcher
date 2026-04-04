import asyncio
from typing import Dict


class EventBus:
    def __init__(self):
        self.clients: Dict[str, asyncio.Queue] = {}

    def register(self, client_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.clients[client_id] = queue
        return queue

    def unregister(self, client_id: str):
        self.clients.pop(client_id, None)

    async def publish(self, client_id: str, message: dict):
        if client_id in self.clients:
            await self.clients[client_id].put(message)

    async def broadcast(self, message: dict):
        for queue in self.clients.values():
            await queue.put(message)


event_bus = EventBus()
