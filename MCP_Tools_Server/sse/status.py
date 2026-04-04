from typing import Any, Dict, Optional

from sse.event_bus import event_bus


async def emit_status(
    client_id: str, stage: str, message: str, meta: Optional[Dict[str, Any]] = None
):
    payload = {"stage": stage, "message": message, "meta": meta or {}}

    await event_bus.publish(client_id, payload)
