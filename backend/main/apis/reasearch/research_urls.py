import asyncio
import uuid
from datetime import datetime
from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

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
from main.src.research.orchestrator_main import MasterOrchestrator
from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import quickLog

router = APIRouter(prefix="/research", tags=["research"])


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


# @router.get("/", response_model=ResearchListResponse)
# def get_all_research(
#     page: int = Query(default=1, ge=1),
#     size: int = Query(default=20, ge=1, le=200),
#     workspace_id: str | None = Query(default=None, alias="workspaceId"),
#     title_contains: str | None = Query(default=None, alias="titleContains"),
#     desc_contains: str | None = Query(default=None, alias="descContains"),
#     prompt_contains: str | None = Query(default=None, alias="promptContains"),
#     chat_access: bool | None = Query(default=None, alias="chatAccess"),
#     background_processing: bool | None = Query(
#         default=None, alias="backgroundProcessing"
#     ),
#     sort_by: Literal["id", "title", "workspace_id"] = Query(
#         default="id", alias="sortBy"
#     ),
#     sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
# ) -> ResearchListResponse:
#     try:
#         return research_view.getAllResearch(
#             page=page,
#             size=size,
#             workspace_id=workspace_id,
#             title_contains=title_contains,
#             desc_contains=desc_contains,
#             prompt_contains=prompt_contains,
#             chat_access=chat_access,
#             background_processing=background_processing,
#             sort_by=sort_by,
#             sort_order=sort_order,
#         )
#     except Exception as exc:
#         _raise_research_http_error("List research items", exc)


# @router.get("/urls", response_model=ResearchSourceListResponse)
# @router.get(
#     "/sources", response_model=ResearchSourceListResponse, include_in_schema=False
# )
# def get_research_source_urls(
#     research_id: str | None = Query(default=None, alias="researchId"),
#     page: int = Query(default=1, ge=1),
#     size: int = Query(default=20, ge=1, le=200),
#     created_from: datetime | None = Query(default=None, alias="createdFrom"),
#     created_to: datetime | None = Query(default=None, alias="createdTo"),
#     updated_from: datetime | None = Query(default=None, alias="updatedFrom"),
#     updated_to: datetime | None = Query(default=None, alias="updatedTo"),
#     source_type: str | None = Query(default=None, alias="sourceType"),
#     url_contains: str | None = Query(default=None, alias="urlContains"),
#     sort_by: Literal[
#         "created_at", "updated_at", "research_id", "source_type", "source_url"
#     ] = Query(default="created_at", alias="sortBy"),
#     sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
# ) -> ResearchSourceListResponse:
#     try:
#         return research_view.getResearchSourceUrls(
#             research_id=research_id,
#             page=page,
#             size=size,
#             created_from=created_from,
#             created_to=created_to,
#             updated_from=updated_from,
#             updated_to=updated_to,
#             source_type=source_type,
#             url_contains=url_contains,
#             sort_by=sort_by,
#             sort_order=sort_order,
#         )
#     except Exception as exc:
#         _raise_research_http_error("List research source urls", exc)


# @router.get("/{research_id}", response_model=ResearchRecord)
# def get_research_by_id(research_id: str) -> ResearchRecord:
#     try:
#         return research_view.getResearch(research_id)
#     except Exception as exc:
#         _raise_research_http_error(f"Fetch research {research_id}", exc)


# @router.post("/", response_model=ResearchRecord, status_code=status.HTTP_201_CREATED)
# def create_research(payload: ResearchCreate) -> ResearchRecord:
#     try:
#         return research_view.createResearch(payload)
#     except Exception as exc:
#         _raise_research_http_error("Create research", exc)


# @router.put("/{research_id}", response_model=ResearchRecord)
# def replace_research(research_id: str, payload: ResearchCreate) -> ResearchRecord:
#     try:
#         return research_view.updateResearch(research_id, payload)
#     except Exception as exc:
#         _raise_research_http_error(f"Replace research {research_id}", exc)


# @router.patch("/{research_id}", response_model=ResearchRecord)
# def update_research(research_id: str, payload: ResearchPatch) -> ResearchRecord:
#     try:
#         return research_view.patchResearch(research_id, payload)
#     except Exception as exc:
#         _raise_research_http_error(f"Patch research {research_id}", exc)


# @router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_research(research_id: str) -> Response:
#     try:
#         research_view.deleteResearch(research_id)
#         return Response(status_code=status.HTTP_204_NO_CONTENT)
#     except Exception as exc:
#         _raise_research_http_error(f"Delete research {research_id}", exc)


# @router.get("/sources/{source_id}", response_model=ResearchSourceRecord)
# def get_research_source(source_id: str) -> ResearchSourceRecord:
#     try:
#         return research_view.getResearchSource(source_id)
#     except Exception as exc:
#         _raise_research_http_error(f"Fetch research source {source_id}", exc)


# @router.post(
#     "/sources",
#     response_model=ResearchSourceRecord,
#     status_code=status.HTTP_201_CREATED,
# )
# def create_research_source(payload: ResearchSourceCreate) -> ResearchSourceRecord:
#     try:
#         return research_view.createResearchSource(payload)
#     except Exception as exc:
#         _raise_research_http_error("Create research source", exc)


# @router.patch("/sources/{source_id}", response_model=ResearchSourceRecord)
# def patch_research_source(
#     source_id: str,
#     payload: ResearchSourcePatch,
# ) -> ResearchSourceRecord:
#     try:
#         return research_view.patchResearchSource(source_id, payload)
#     except Exception as exc:
#         _raise_research_http_error(f"Patch research source {source_id}", exc)


# @router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_research_source(source_id: str) -> Response:
#     try:
#         research_view.deleteResearchSource(source_id)
#         return Response(status_code=status.HTTP_204_NO_CONTENT)
#     except Exception as exc:
#         _raise_research_http_error(f"Delete research source {source_id}", exc)


class ResearchRunRequest(BaseModel):
    prompt: str
    title: str = ""
    desc: str = ""
    username: str = ""
    workspaceId: str = ""
    sources: list = []
    research_template: dict = {}
    research_template_id: str = ""
    custom_prompt: str = ""
    system_prompt: str = ""
    ai_personality: str = ""
    chat_access: bool = True
    background_processing: bool = True
    research_id: str = ""  # optional — client can supply its own id


async def _run_pipeline(
    job_id: str, payload: dict, ollama_url: str, gemini_api_key: str
) -> None:
    """Thin async wrapper so the task stays fire-and-forget."""
    try:
        orchestrator = MasterOrchestrator(
            ollama_url=ollama_url,
            gemini_api_key=gemini_api_key,
        )
        await orchestrator.execute(job_id=job_id, payload=payload)
    except Exception as e:
        await scheduler.schedule(
            quickLog,
            params={
                "level": "error",
                "message": f"MasterOrchestrator crashed — job_id={job_id}: {e}",
                "module": ["RESEARCH"],
                "urgency": "critical",
            },
        )


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_research(
    payload: ResearchRunRequest,
    ollama_url: str = "http://localhost:11434/api/generate",
    gemini_api_key: str = "",
) -> dict:
    """
    ## Description
    Triggers a live research execution pipeline for the given prompt.
    Runs as a background asyncio task and emits state via SSE.

    ## Returns
    ```json
    { "job_id": "uuid-string", "status": "accepted" }
    ```

    ## SSE
    Listen on `GET /events/research` — every event has a `research` field
    matching this `job_id`.
    """
    job_id = payload.research_id or str(uuid.uuid4())

    # Fire-and-forget — response returns immediately
    asyncio.create_task(
        _run_pipeline(
            job_id=job_id,
            payload=payload.model_dump(),
            ollama_url=ollama_url,
            gemini_api_key=gemini_api_key,
        )
    )

    quickLog(
        level="info",
        message=f"Research job accepted — job_id={job_id}",
        module=["RESEARCH"],
    )

    return {"job_id": job_id, "status": "accepted"}
