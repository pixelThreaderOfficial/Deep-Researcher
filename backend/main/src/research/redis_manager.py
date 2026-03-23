"""
redis_manager.py — Deep Researcher v2
========================================
Manages Redis interactions for storing job states, emitting events,
and managing research query queues.

## Description

Provides the ``RedisManager`` class that bridges the research pipeline
with Redis for real-time state management, event streaming, and job
queue management. Complements the SSE-based ``event_bus`` for direct
Redis stream event broadcasting.

## Side Effects

- Reads/writes to Redis hashes, streams, and lists.
- Requires ``REDIS_URL`` environment variable (default: localhost:6379).

## Customization

Override ``REDIS_URL`` env var to point to a different Redis instance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import redis.asyncio as redis

from main.src.research.models import JobStatus, RedisEvent

_log = logging.getLogger(__name__)


class RedisManager:
    """
    ## Description

    Async Redis client for research job state management and
    event streaming. Stores job states in Redis hashes and
    emits events to a Redis Stream for fan-out consumption.

    ## Parameters

    - None (reads ``REDIS_URL`` from environment).

    ## Returns

    `RedisManager` instance.

    ## Side Effects

    - Maintains persistent Redis connections.
    - Creates Redis keys for jobs and event streams.

    ## Customization

    Change ``event_stream_key`` or ``job_store_prefix`` to
    namespace different environments.
    """

    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.event_stream_key = "research:events"
        self.job_store_prefix = "research:job:"

    async def update_job_state(self, job_id: str, state: dict) -> None:
        """
        ## Description

        Updates the full state of a research job in Redis.

        ## Parameters

        - `job_id` (`str`)
          - Description: Unique job identifier.
          - Constraints: Must be a valid UUID string.

        - `state` (`dict`)
          - Description: Full job state to persist.

        ## Returns

        `None`

        ## Side Effects

        - Updates the Redis hash for this job.
        """
        key = f"{self.job_store_prefix}{job_id}"
        await self.client.hset(key, "state", json.dumps(state, default=str))
        await self.client.hset(
            key, "updated_at", datetime.now(timezone.utc).isoformat()
        )

    async def get_job_state(self, job_id: str) -> Optional[dict]:
        """
        ## Description

        Retrieves the stored state for a research job.

        ## Parameters

        - `job_id` (`str`) — The job identifier.

        ## Returns

        `Optional[dict]` — Parsed job state, or None if not found.

        ## Side Effects

        - Reads from Redis.
        """
        key = f"{self.job_store_prefix}{job_id}"
        state = await self.client.hget(key, "state")
        return json.loads(state) if state else None

    async def get_multiple_job_states(
        self, job_ids: List[str]
    ) -> Dict[str, dict]:
        """
        ## Description

        Retrieves states for multiple jobs in one call.

        ## Parameters

        - `job_ids` (`List[str]`) — List of job identifiers.

        ## Returns

        `Dict[str, dict]` — Map of job_id → state.

        ## Side Effects

        - Multiple Redis reads.
        """
        results: Dict[str, dict] = {}
        for job_id in job_ids:
            state = await self.get_job_state(job_id)
            if state:
                results[job_id] = state
        return results

    async def emit_event(self, event: RedisEvent) -> None:
        """
        ## Description

        Emits a research event to the Redis Stream and updates the
        job's status/last_message in its Redis hash.

        ## Parameters

        - `event` (`RedisEvent`) — The event to emit.

        ## Returns

        `None`

        ## Side Effects

        - Adds an entry to the Redis event stream.
        - Updates the job hash with latest status and message.
        """
        payload = event.model_dump_json()

        # Push to Redis Stream
        await self.client.xadd(
            self.event_stream_key,
            {"event": payload, "job_id": event.job_id},
        )

        # Update job status in hash
        key = f"{self.job_store_prefix}{event.job_id}"
        await self.client.hset(key, "status", event.status.value)
        await self.client.hset(key, "last_message", event.message)

    async def get_stream_events(
        self, job_id: str, last_id: str = "0"
    ) -> AsyncIterator[str]:
        """
        ## Description

        Async generator that yields new events from the Redis stream
        filtered for a specific job ID.

        ## Parameters

        - `job_id` (`str`) — The job to filter events for.
        - `last_id` (`str`) — Redis stream ID to start from. Default: ``"0"``.

        ## Returns

        `AsyncIterator[str]` — Yields JSON event strings.

        ## Side Effects

        - Blocks on Redis XREAD with 5s timeout.
        """
        while True:
            events = await self.client.xread(
                {self.event_stream_key: last_id}, count=10, block=5000
            )
            if events:
                for stream, stream_events in events:
                    for event_id, event_data in stream_events:
                        last_id = event_id
                        if event_data.get("job_id") == job_id:
                            yield event_data.get("event", "")
            await asyncio.sleep(0.1)

    async def push_to_pending_queue(self, query: dict) -> None:
        """
        ## Description

        Pushes a research query to the pending queries list for
        asynchronous processing by a worker.

        ## Parameters

        - `query` (`dict`) — The research query payload.

        ## Returns

        `None`

        ## Side Effects

        - Adds entry to the ``research:pending_queries`` Redis list.
        """
        await self.client.lpush(
            "research:pending_queries", json.dumps(query, default=str)
        )
