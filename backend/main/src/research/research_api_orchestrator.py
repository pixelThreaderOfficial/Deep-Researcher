"""
research_api_orchestrator.py — Deep Researcher v2
====================================================
CRUD orchestrator for the research API endpoints defined in
``research_urls.py``. Provides synchronous database operations
for creating, reading, updating, and deleting research records
and research sources.

## Description

This module bridges the FastAPI route handlers (``research_urls.py``)
and the SQLite database layer (``researches_db_manager``). It handles
pagination, filtering, sorting, and data validation for all CRUD
operations on the ``researches`` and ``research_sources`` tables.

## Side Effects

- Reads/writes to the ``researches.db.sqlite3`` database.
- Logs operations via the DRLogger system.

## Customization

Modify the table names or query logic to adapt to schema changes.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from main.apis.models.research import (
    ResearchCreate,
    ResearchListResponse,
    ResearchPatch,
    ResearchRecord,
    ResearchSourceCreate,
    ResearchSourceListResponse,
    ResearchSourcePatch,
    ResearchSourceRecord,
)
from main.src.store.DBManager import researches_db_manager

_log = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """
    ## Description

    Returns the current UTC timestamp as an ISO-8601 string.

    ## Parameters

    - None

    ## Returns

    `str` — ISO-formatted UTC timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """
    ## Description

    Generates a new UUID4 string identifier.

    ## Parameters

    - None

    ## Returns

    `str` — UUID4 string.
    """
    return str(uuid.uuid4())


class ResearchOrchestrator:
    """
    ## Description

    Synchronous CRUD orchestrator for research records and sources.
    Called by the FastAPI route handlers in ``research_urls.py``.

    ## Parameters

    - None (uses the global ``researches_db_manager``).

    ## Returns

    `ResearchOrchestrator` instance.

    ## Side Effects

    - Reads/writes to ``researches.db.sqlite3``.

    ## Customization

    Modify table names or add validation logic as needed.
    """

    # ------------------------------------------------------------------
    # Researches CRUD
    # ------------------------------------------------------------------

    def getAllResearch(
        self,
        page: int = 1,
        size: int = 20,
        workspace_id: Optional[str] = None,
        title_contains: Optional[str] = None,
        desc_contains: Optional[str] = None,
        prompt_contains: Optional[str] = None,
        chat_access: Optional[bool] = None,
        background_processing: Optional[bool] = None,
        sort_by: str = "id",
        sort_order: str = "desc",
    ) -> ResearchListResponse:
        """
        ## Description

        Retrieves a paginated, filtered, and sorted list of all research records.

        ## Parameters

        - `page` (`int`) — Page number (1-indexed). Default: 1.
        - `size` (`int`) — Items per page. Default: 20.
        - `workspace_id` (`Optional[str]`) — Filter by workspace ID.
        - `title_contains` (`Optional[str]`) — Title substring filter.
        - `desc_contains` (`Optional[str]`) — Description substring filter.
        - `prompt_contains` (`Optional[str]`) — Prompt substring filter.
        - `chat_access` (`Optional[bool]`) — Filter by chat access flag.
        - `background_processing` (`Optional[bool]`) — Filter by background processing flag.
        - `sort_by` (`str`) — Column to sort by. Default: `"id"`.
        - `sort_order` (`str`) — Sort direction: `"asc"` or `"desc"`. Default: `"desc"`.

        ## Returns

        `ResearchListResponse` — Paginated list of research records.

        ## Raises

        - `Exception` — On database errors.

        ## Side Effects

        - Reads from the ``researches`` table.
        """
        where: Dict[str, Any] = {}
        if workspace_id:
            where["workspace_id"] = workspace_id

        result = researches_db_manager.fetch_all("researches", where=where or None)

        if not result.get("success"):
            _log.error("[ResearchOrchestrator] getAllResearch failed: %s", result.get("message"))
            return ResearchListResponse(
                items=[], page=page, size=size, total_items=0, total_pages=0, offset=0
            )

        rows: List[Dict[str, Any]] = result.get("data", [])

        # Apply text filters (SQLiteManager only supports equality, so we filter in Python)
        if title_contains:
            rows = [r for r in rows if title_contains.lower() in (r.get("title") or "").lower()]
        if desc_contains:
            rows = [r for r in rows if desc_contains.lower() in (r.get("desc") or "").lower()]
        if prompt_contains:
            rows = [r for r in rows if prompt_contains.lower() in (r.get("prompt") or "").lower()]
        if chat_access is not None:
            rows = [r for r in rows if bool(r.get("chat_access")) == chat_access]
        if background_processing is not None:
            rows = [r for r in rows if bool(r.get("background_processing")) == background_processing]

        # Sort
        reverse = sort_order.lower() == "desc"
        rows.sort(key=lambda r: r.get(sort_by, ""), reverse=reverse)

        total_items = len(rows)
        total_pages = max(1, math.ceil(total_items / size))
        offset = (page - 1) * size
        paginated = rows[offset : offset + size]

        items = [ResearchRecord(**r) for r in paginated]

        return ResearchListResponse(
            items=items,
            page=page,
            size=size,
            total_items=total_items,
            total_pages=total_pages,
            offset=offset,
        )

    def getResearch(self, research_id: str) -> ResearchRecord:
        """
        ## Description

        Retrieves a single research record by its ID.

        ## Parameters

        - `research_id` (`str`)
          - Description: The UUID of the research record.
          - Constraints: Must exist in the database.

        ## Returns

        `ResearchRecord`

        ## Raises

        - `KeyError` — When the research record is not found.

        ## Side Effects

        - Reads from the ``researches`` table.
        """
        result = researches_db_manager.fetch_one("researches", where={"id": research_id})

        if not result.get("success") or not result.get("data"):
            raise KeyError(f"Research {research_id} not found")

        return ResearchRecord(**result["data"])

    def createResearch(self, payload: ResearchCreate) -> ResearchRecord:
        """
        ## Description

        Creates a new research record in the database.

        ## Parameters

        - `payload` (`ResearchCreate`)
          - Description: The research creation payload.

        ## Returns

        `ResearchRecord` — The created research record.

        ## Raises

        - `ValueError` — On validation or insertion errors.

        ## Side Effects

        - Inserts a row into the ``researches`` table.
        """
        data = payload.model_dump()
        if not data.get("id"):
            data["id"] = _new_id()

        template_id = data.get("research_template_id")
        if template_id:
            # Catch string representations of null/undefined or empty space
            if str(template_id).strip().lower() in ("", "null", "undefined", "none"):
                data["research_template_id"] = None
            else:
                # verify it exists to prevent FK violation
                check = researches_db_manager.fetch_one("research_templates", where={"id": template_id})
                if not check.get("data"):
                    _log.warning(f"Research template '{template_id}' not found. Ignoring to prevent FK constraint failure.")
                    data["research_template_id"] = None

        result = researches_db_manager.insert("researches", data)
        if not result.get("success"):
            raise ValueError(f"Failed to create research: {result.get('message')}")

        return ResearchRecord(**data)

    def updateResearch(self, research_id: str, payload: ResearchCreate) -> ResearchRecord:
        """
        ## Description

        Replaces a research record entirely with the provided payload.

        ## Parameters

        - `research_id` (`str`) — The research record ID to replace.
        - `payload` (`ResearchCreate`) — Full replacement payload.

        ## Returns

        `ResearchRecord` — The updated research record.

        ## Raises

        - `KeyError` — When the research record is not found.
        - `ValueError` — On update failures.

        ## Side Effects

        - Updates the row in the ``researches`` table.
        """
        # Verify existence
        self.getResearch(research_id)

        data = payload.model_dump()
        data["id"] = research_id

        template_id = data.get("research_template_id")
        if template_id:
            if str(template_id).strip().lower() in ("", "null", "undefined", "none"):
                data["research_template_id"] = None
            else:
                check = researches_db_manager.fetch_one("research_templates", where={"id": template_id})
                if not check.get("data"):
                    data["research_template_id"] = None

        result = researches_db_manager.update(
            "researches",
            data=data,
            where={"id": research_id},
        )
        if not result.get("success"):
            raise ValueError(f"Failed to update research: {result.get('message')}")

        return ResearchRecord(**data)

    def patchResearch(self, research_id: str, payload: ResearchPatch) -> ResearchRecord:
        """
        ## Description

        Partially updates a research record with only the provided fields.

        ## Parameters

        - `research_id` (`str`) — The research record ID to patch.
        - `payload` (`ResearchPatch`) — Partial update payload.

        ## Returns

        `ResearchRecord` — The patched research record.

        ## Raises

        - `KeyError` — When the research record is not found.
        - `ValueError` — On update failures.

        ## Side Effects

        - Updates specific columns in the ``researches`` table row.
        """
        existing = self.getResearch(research_id)
        update_data = payload.model_dump(exclude_none=True)

        if not update_data:
            return existing

        template_id = update_data.get("research_template_id")
        if template_id is not None:
            if str(template_id).strip().lower() in ("", "null", "undefined", "none"):
                update_data["research_template_id"] = None
            else:
                check = researches_db_manager.fetch_one("research_templates", where={"id": template_id})
                if not check.get("data"):
                    update_data["research_template_id"] = None

        result = researches_db_manager.update(
            "researches",
            data=update_data,
            where={"id": research_id},
        )
        if not result.get("success"):
            raise ValueError(f"Failed to patch research: {result.get('message')}")

        # Merge and return
        merged = existing.model_dump()
        merged.update(update_data)
        return ResearchRecord(**merged)

    def deleteResearch(self, research_id: str) -> None:
        """
        ## Description

        Deletes a research record by its ID.

        ## Parameters

        - `research_id` (`str`) — The research record ID to delete.

        ## Returns

        `None`

        ## Raises

        - `KeyError` — When the research record is not found.
        - `ValueError` — On deletion failures.

        ## Side Effects

        - Removes the row from the ``researches`` table.
        """
        # Verify existence
        self.getResearch(research_id)

        result = researches_db_manager.delete("researches", where={"id": research_id})
        if not result.get("success"):
            raise ValueError(f"Failed to delete research: {result.get('message')}")

    # ------------------------------------------------------------------
    # Research Sources CRUD
    # ------------------------------------------------------------------

    def getResearchSourceUrls(
        self,
        research_id: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        updated_from: Optional[datetime] = None,
        updated_to: Optional[datetime] = None,
        source_type: Optional[str] = None,
        url_contains: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> ResearchSourceListResponse:
        """
        ## Description

        Retrieves a paginated, filtered list of research source records.

        ## Parameters

        - `research_id` (`Optional[str]`) — Filter by research ID.
        - `page` (`int`) — Page number. Default: 1.
        - `size` (`int`) — Items per page. Default: 20.
        - `created_from` / `created_to` — Date range filters for creation.
        - `updated_from` / `updated_to` — Date range filters for last update.
        - `source_type` (`Optional[str]`) — Filter by source type.
        - `url_contains` (`Optional[str]`) — URL substring filter.
        - `sort_by` (`str`) — Sort column. Default: `"created_at"`.
        - `sort_order` (`str`) — Direction. Default: `"desc"`.

        ## Returns

        `ResearchSourceListResponse`

        ## Side Effects

        - Reads from the ``research_sources`` table.
        """
        where: Dict[str, Any] = {}
        if research_id:
            where["research_id"] = research_id
        if source_type:
            where["source_type"] = source_type

        result = researches_db_manager.fetch_all("research_sources", where=where or None)

        if not result.get("success"):
            return ResearchSourceListResponse(
                items=[], page=page, size=size, total_items=0, total_pages=0, offset=0
            )

        rows: List[Dict[str, Any]] = result.get("data", [])

        # Apply text/date filters in Python
        if url_contains:
            rows = [r for r in rows if url_contains.lower() in (r.get("source_url") or "").lower()]

        # Sort
        reverse = sort_order.lower() == "desc"
        rows.sort(key=lambda r: r.get(sort_by, ""), reverse=reverse)

        total_items = len(rows)
        total_pages = max(1, math.ceil(total_items / size))
        offset = (page - 1) * size
        paginated = rows[offset : offset + size]

        items = [ResearchSourceRecord(**r) for r in paginated]

        return ResearchSourceListResponse(
            items=items,
            page=page,
            size=size,
            total_items=total_items,
            total_pages=total_pages,
            offset=offset,
        )

    def getResearchSource(self, source_id: str) -> ResearchSourceRecord:
        """
        ## Description

        Retrieves a single research source record by its ID.

        ## Parameters

        - `source_id` (`str`) — The source record UUID.

        ## Returns

        `ResearchSourceRecord`

        ## Raises

        - `KeyError` — When the source record is not found.
        """
        result = researches_db_manager.fetch_one("research_sources", where={"id": source_id})

        if not result.get("success") or not result.get("data"):
            raise KeyError(f"Research source {source_id} not found")

        return ResearchSourceRecord(**result["data"])

    def createResearchSource(self, payload: ResearchSourceCreate) -> ResearchSourceRecord:
        """
        ## Description

        Creates a new research source record.

        ## Parameters

        - `payload` (`ResearchSourceCreate`) — Source creation payload.

        ## Returns

        `ResearchSourceRecord`

        ## Raises

        - `ValueError` — On insertion failures.

        ## Side Effects

        - Inserts a row into the ``research_sources`` table.
        """
        data = payload.model_dump()
        if not data.get("id"):
            data["id"] = _new_id()

        # Ensure timestamps
        now = _utcnow_iso()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)

        # Convert datetime objects to ISO strings for SQLite
        for key in ("created_at", "updated_at"):
            if isinstance(data.get(key), datetime):
                data[key] = data[key].isoformat()

        result = researches_db_manager.insert("research_sources", data)
        if not result.get("success"):
            raise ValueError(f"Failed to create research source: {result.get('message')}")

        return ResearchSourceRecord(**data)

    def patchResearchSource(
        self, source_id: str, payload: ResearchSourcePatch
    ) -> ResearchSourceRecord:
        """
        ## Description

        Partially updates a research source record.

        ## Parameters

        - `source_id` (`str`) — The source record ID to patch.
        - `payload` (`ResearchSourcePatch`) — Partial update payload.

        ## Returns

        `ResearchSourceRecord`

        ## Raises

        - `KeyError` — When the source is not found.
        - `ValueError` — On update failures.
        """
        existing = self.getResearchSource(source_id)
        update_data = payload.model_dump(exclude_none=True)

        if not update_data:
            return existing

        update_data["updated_at"] = _utcnow_iso()

        # Convert datetime objects to ISO strings for SQLite
        for key in ("created_at", "updated_at"):
            if isinstance(update_data.get(key), datetime):
                update_data[key] = update_data[key].isoformat()

        result = researches_db_manager.update(
            "research_sources",
            data=update_data,
            where={"id": source_id},
        )
        if not result.get("success"):
            raise ValueError(f"Failed to patch research source: {result.get('message')}")

        merged = existing.model_dump()
        merged.update(update_data)
        return ResearchSourceRecord(**merged)

    def deleteResearchSource(self, source_id: str) -> None:
        """
        ## Description

        Deletes a research source record by its ID.

        ## Parameters

        - `source_id` (`str`) — The source record ID to delete.

        ## Returns

        `None`

        ## Raises

        - `KeyError` — When the source is not found.
        - `ValueError` — On deletion failures.
        """
        # Verify existence
        self.getResearchSource(source_id)

        result = researches_db_manager.delete("research_sources", where={"id": source_id})
        if not result.get("success"):
            raise ValueError(f"Failed to delete research source: {result.get('message')}")
