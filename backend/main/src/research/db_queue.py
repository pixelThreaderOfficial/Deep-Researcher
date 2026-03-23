"""
db_queue.py — Deep Researcher v2
==================================
Background database queue for research data persistence. Uses the
existing task scheduler to process non-critical database writes
asynchronously without blocking the main research pipeline.

## Description

Provides helper functions for enqueueing database saves (research
sources, artifacts, metadata) onto the background task scheduler,
plus a legacy ``DatabaseQueue`` for direct queue-based processing.

## Side Effects

- Inserts rows into SQLite tables via ``researches_db_manager``.
- Scheduled via ``scheduler.schedule()`` for non-blocking execution.

## Customization

Add new ``enqueue_*`` functions for additional background DB operations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from main.src.store.DBManager import researches_db_manager
from main.src.utils.core.task_schedular import scheduler

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background task functions (called by scheduler workers)
# ---------------------------------------------------------------------------


async def save_research_source(
    research_id: str,
    source_url: str,
    source_type: str = "website",
    source_content: Optional[str] = None,
    source_vector_id: Optional[str] = None,
) -> None:
    """
    ## Description

    Persists a single research source record to the ``research_sources``
    table. Intended to be scheduled via the background task scheduler.

    ## Parameters

    - `research_id` (`str`)
      - Description: The parent research record ID.
      - Constraints: Must be a valid UUID.

    - `source_url` (`str`)
      - Description: The URL of the source.
      - Constraints: Must be non-empty.

    - `source_type` (`str`)
      - Description: Type classification (website, pdf, youtube, image).
      - Constraints: Default: ``"website"``.

    - `source_content` (`Optional[str]`)
      - Description: Optional scraped/summarized content.

    - `source_vector_id` (`Optional[str]`)
      - Description: Optional ChromaDB vector ID for this source.

    ## Returns

    `None`

    ## Side Effects

    - Inserts a row into the ``research_sources`` table.
    """
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "id": str(uuid.uuid4()),
        "research_id": research_id,
        "source_type": source_type,
        "source_url": source_url,
        "source_content": (source_content or "")[:5000],
        "source_vector_id": source_vector_id,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = researches_db_manager.insert("research_sources", data)
        if result.get("success"):
            _log.debug("[DBQueue] Saved source: %s → %s", source_url[:60], research_id)
        else:
            _log.warning("[DBQueue] Failed to save source: %s", result.get("message"))
    except Exception as exc:
        _log.error("[DBQueue] save_research_source error: %s", exc)


async def save_research_artifact(
    research_id: str,
    artifact_json: str,
) -> None:
    """
    ## Description

    Updates the ``artifacts`` column of the parent research record
    with the serialized artifact JSON. Scheduled via background workers.

    ## Parameters

    - `research_id` (`str`)
      - Description: The research record ID to update.

    - `artifact_json` (`str`)
      - Description: JSON-serialized artifact data.

    ## Returns

    `None`

    ## Side Effects

    - Updates the ``artifacts`` column on the ``researches`` table.
    """
    try:
        result = researches_db_manager.update(
            "researches",
            data={"artifacts": artifact_json},
            where={"id": research_id},
        )
        if result.get("success"):
            _log.debug("[DBQueue] Saved artifact for research %s", research_id)
        else:
            _log.warning("[DBQueue] Failed to save artifact: %s", result.get("message"))
    except Exception as exc:
        _log.error("[DBQueue] save_research_artifact error: %s", exc)


# ---------------------------------------------------------------------------
# Enqueue helpers (convenience wrappers)
# ---------------------------------------------------------------------------


async def enqueue_save_sources(
    research_id: str,
    sources: List[Dict[str, Any]],
) -> None:
    """
    ## Description

    Schedules background saves for a batch of research sources.
    Each source is saved as a separate background task.

    ## Parameters

    - `research_id` (`str`)
      - Description: Parent research record ID.

    - `sources` (`List[Dict[str, Any]]`)
      - Description: List of source dicts with ``url``, ``content``, ``title``.

    ## Returns

    `None`

    ## Side Effects

    - Schedules N background tasks via the scheduler.
    """
    for source in sources:
        await scheduler.schedule(
            save_research_source,
            params={
                "research_id": research_id,
                "source_url": source.get("url", ""),
                "source_type": source.get("type", "website"),
                "source_content": source.get("content", ""),
                "source_vector_id": source.get("vector_id"),
            },
        )

    _log.info("[DBQueue] Enqueued %d sources for research %s", len(sources), research_id)


async def enqueue_save_artifact(
    research_id: str,
    artifact_data: dict,
) -> None:
    """
    ## Description

    Schedules a background save of the research artifact.

    ## Parameters

    - `research_id` (`str`) — Parent research record ID.
    - `artifact_data` (`dict`) — Serialized artifact model.

    ## Returns

    `None`

    ## Side Effects

    - Schedules one background task via the scheduler.
    """
    await scheduler.schedule(
        save_research_artifact,
        params={
            "research_id": research_id,
            "artifact_json": json.dumps(artifact_data, default=str),
        },
    )


# ---------------------------------------------------------------------------
# Legacy queue class (backward compatibility)
# ---------------------------------------------------------------------------


class DatabaseQueue:
    """
    ## Description

    Simple asyncio-queue-based background processor for database
    operations. Maintained for backward compatibility; new code
    should use ``scheduler.schedule()`` directly.

    ## Parameters

    - None

    ## Returns

    `DatabaseQueue` instance.

    ## Side Effects

    - Creates an ``asyncio.Queue`` on instantiation.

    ## Customization

    Prefer using ``enqueue_*`` functions above for new integrations.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()

    async def put(self, task: dict) -> None:
        """
        ## Description

        Adds a task dict to the queue.

        ## Parameters

        - `task` (`dict`) — Task payload.

        ## Returns

        `None`
        """
        await self.queue.put(task)

    async def process(self) -> None:
        """
        ## Description

        Continuously processes tasks from the queue.

        ## Returns

        `None`

        ## Side Effects

        - Runs indefinitely, processing queued tasks.
        """
        while True:
            task = await self.queue.get()
            try:
                action = task.get("action")
                if action == "save_source":
                    await save_research_source(**task.get("params", {}))
                elif action == "save_artifact":
                    await save_research_artifact(**task.get("params", {}))
                else:
                    _log.warning("[DatabaseQueue] Unknown action: %s", action)
            except Exception as exc:
                _log.error("[DatabaseQueue] Task processing error: %s", exc)
            finally:
                self.queue.task_done()
