import uuid
from datetime import datetime
from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Query, Response, status

from main.apis.models.research import (
    ResearchCreate,
    ResearchListResponse,
    ResearchPatch,
    ResearchRecord,
    ResearchRunRequest,
    ResearchSourceCreate,
    ResearchSourceListResponse,
    ResearchSourcePatch,
    ResearchSourceRecord,
)
from main.src.research import ResearchOrchestrator as ResearchPipeline
from main.src.research import research_api_orchestrator

router = APIRouter(prefix="/research", tags=["research"])

research_view = research_api_orchestrator.ResearchOrchestrator()
pipeline = ResearchPipeline()


def _raise_research_http_error(action: str, exc: Exception) -> NoReturn:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, KeyError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc).strip("'"),
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or f"Invalid request for {action.lower()}",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to {action.lower()}",
    ) from exc


@router.get("/", response_model=ResearchListResponse)
def get_all_research(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    title_contains: str | None = Query(default=None, alias="titleContains"),
    desc_contains: str | None = Query(default=None, alias="descContains"),
    prompt_contains: str | None = Query(default=None, alias="promptContains"),
    chat_access: bool | None = Query(default=None, alias="chatAccess"),
    background_processing: bool | None = Query(
        default=None, alias="backgroundProcessing"
    ),
    sort_by: Literal["id", "title", "workspace_id"] = Query(
        default="id", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> ResearchListResponse:
    try:
        return research_view.getAllResearch(
            page=page,
            size=size,
            workspace_id=workspace_id,
            title_contains=title_contains,
            desc_contains=desc_contains,
            prompt_contains=prompt_contains,
            chat_access=chat_access,
            background_processing=background_processing,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as exc:
        _raise_research_http_error("List research items", exc)


@router.get("/urls", response_model=ResearchSourceListResponse)
@router.get(
    "/sources", response_model=ResearchSourceListResponse, include_in_schema=False
)
def get_research_source_urls(
    research_id: str | None = Query(default=None, alias="researchId"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    created_from: datetime | None = Query(default=None, alias="createdFrom"),
    created_to: datetime | None = Query(default=None, alias="createdTo"),
    updated_from: datetime | None = Query(default=None, alias="updatedFrom"),
    updated_to: datetime | None = Query(default=None, alias="updatedTo"),
    source_type: str | None = Query(default=None, alias="sourceType"),
    url_contains: str | None = Query(default=None, alias="urlContains"),
    sort_by: Literal[
        "created_at", "updated_at", "research_id", "source_type", "source_url"
    ] = Query(default="created_at", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> ResearchSourceListResponse:
    try:
        return research_view.getResearchSourceUrls(
            research_id=research_id,
            page=page,
            size=size,
            created_from=created_from,
            created_to=created_to,
            updated_from=updated_from,
            updated_to=updated_to,
            source_type=source_type,
            url_contains=url_contains,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as exc:
        _raise_research_http_error("List research source urls", exc)


@router.get("/{research_id}", response_model=ResearchRecord)
def get_research_by_id(research_id: str) -> ResearchRecord:
    try:
        return research_view.getResearch(research_id)
    except Exception as exc:
        _raise_research_http_error(f"Fetch research {research_id}", exc)


@router.post("/", response_model=ResearchRecord, status_code=status.HTTP_201_CREATED)
def create_research(payload: ResearchCreate) -> ResearchRecord:
    try:
        return research_view.createResearch(payload)
    except Exception as exc:
        _raise_research_http_error("Create research", exc)


@router.put("/{research_id}", response_model=ResearchRecord)
def replace_research(research_id: str, payload: ResearchCreate) -> ResearchRecord:
    try:
        return research_view.updateResearch(research_id, payload)
    except Exception as exc:
        _raise_research_http_error(f"Replace research {research_id}", exc)


@router.patch("/{research_id}", response_model=ResearchRecord)
def update_research(research_id: str, payload: ResearchPatch) -> ResearchRecord:
    try:
        return research_view.patchResearch(research_id, payload)
    except Exception as exc:
        _raise_research_http_error(f"Patch research {research_id}", exc)


@router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research(research_id: str) -> Response:
    try:
        research_view.deleteResearch(research_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _raise_research_http_error(f"Delete research {research_id}", exc)


@router.get("/sources/{source_id}", response_model=ResearchSourceRecord)
def get_research_source(source_id: str) -> ResearchSourceRecord:
    try:
        return research_view.getResearchSource(source_id)
    except Exception as exc:
        _raise_research_http_error(f"Fetch research source {source_id}", exc)


@router.post(
    "/sources",
    response_model=ResearchSourceRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_research_source(payload: ResearchSourceCreate) -> ResearchSourceRecord:
    try:
        return research_view.createResearchSource(payload)
    except Exception as exc:
        _raise_research_http_error("Create research source", exc)


@router.patch("/sources/{source_id}", response_model=ResearchSourceRecord)
def patch_research_source(
    source_id: str,
    payload: ResearchSourcePatch,
) -> ResearchSourceRecord:
    try:
        return research_view.patchResearchSource(source_id, payload)
    except Exception as exc:
        _raise_research_http_error(f"Patch research source {source_id}", exc)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research_source(source_id: str) -> Response:
    try:
        research_view.deleteResearchSource(source_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _raise_research_http_error(f"Delete research source {source_id}", exc)


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_research(payload: ResearchRunRequest) -> dict:
    """
    ## Description

    Triggers a live research execution pipeline for the given prompt.
    Runs asynchronously in the background and emits state updates via SSE.

    ## Parameters

    - `payload` (`ResearchRunRequest`)
      - Contains ``prompt``, optional ``context``, ``workspace_id``, etc.

    ## Returns

    `dict`
    ```json
    { "job_id": "uuid-string", "status": "accepted" }
    ```

    ## Side Effects

    - Starts a background ``asyncio.create_task`` for the research pipeline.
    - Emits SSE events to `/events/research`.
    """
    import asyncio

    job_id = payload.research_id or str(uuid.uuid4())

    async def _runner():
        try:
            await pipeline.execute(job_id, payload.model_dump())
        except Exception as exc:
            import logging
            logging.getLogger("research").error(f"Pipeline error for {job_id}: {exc}")

    # Fire and forget locally (orchestrator handles SSE broadcasting)
    asyncio.create_task(_runner())

    return {"job_id": job_id, "status": "accepted"}
