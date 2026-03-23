"""
orchestrator.py — Deep Researcher v2 Research Orchestrator
===========================================================
The main pipeline controller that drives a complete research session:
validate → plan → ReAct loop → ingest vectors → generate artifact → save.

Architecture
------------
::

    Client POST /research/execute
        │
        ▼
    ResearchOrchestrator.execute(job_id, input_data)
        │
        ├── validate_query()
        ├── create_plan()
        ├── ReActEngine.run()  ← iterative Reasoning + Acting
        │       ├── WebSearch → Summarize
        │       ├── SemanticSearch
        │       ├── DocumentSearch
        │       ├── YouTubeSearch
        │       └── ImageUnderstanding
        │
        ├── BG Worker: ingest findings into vectors
        ├── BG Worker: save findings to database
        ├── ArtifactGenerator.generate()
        └── BG Worker: save artifact to database

## Description

Orchestrates the full research lifecycle using ReAct reasoning,
background task scheduling for non-critical I/O (database saves,
vector ingestion), and SSE event emission for real-time updates.

## Side Effects

- Emits SSE events via ``event_bus.broadcast``.
- Schedules background tasks via the ``scheduler``.
- Ingests content into ChromaDB vector store.
- Persists research data to SQLite database.

## Customization

Modify ``MAX_REACT_STEPS`` in ``react_engine.py`` to control depth.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from main.src.research.artifact_generator import ArtifactGenerator
from main.src.research.external_services import ExternalServices
from main.src.utils.llms.gemini.DRGeminiWrapper import getAsyncClient
from main.src.research.models import (
    Artifact,
    JobStatus,
    ResearchPlan,
    ResearchSession,
    ResearchStage,
    ThinkingStep,
)
from main.src.research.planner import ResearchPlanner
from main.src.research.question_asker import QuestionAsker
from main.src.research.react_engine import ReActEngine
from main.src.research.tools import ToolRegistry
from main.src.store.DBManager import researches_db_manager
from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import dr_logger
from main.src.utils.versionManagement import getAppVersion
from main.sse.event_bus import event_bus

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background task helpers (scheduled via BG workers)
# ---------------------------------------------------------------------------


async def _bg_save_event_to_db(research_id: str, event_data: dict) -> None:
    """
    ## Description

    Background worker task: persists a research SSE event to the database
    for historical replay and auditing.

    ## Parameters

    - `research_id` (`str`)
      - Description: The research record ID.
      - Constraints: Must be a valid UUID string.

    - `event_data` (`dict`)
      - Description: The serialized event payload.

    ## Returns

    `None`

    ## Side Effects

    - Log entry via ``dr_logger``.
    """
    _log.debug("[BG] Saving event for research %s", research_id)
    try:
        dr_logger.log(
            log_type="info",
            message=event_data.get("message", ""),
            origin="system",
            module="RESEARCH",
            urgency="none",
            app_version=getAppVersion(),
        )
    except Exception as exc:
        _log.error("[BG] Failed to log event: %s", exc)


async def _bg_save_findings_to_db(
    research_id: str,
    findings: list,
    sources: list,
) -> None:
    """
    ## Description

    Background worker task: persists accumulated research findings and
    source URLs to the research_sources table.

    ## Parameters

    - `research_id` (`str`)
      - Description: The research record ID.

    - `findings` (`list`)
      - Description: List of finding dicts with url, content, summary.

    - `sources` (`list`)
      - Description: List of source URL strings.

    ## Returns

    `None`

    ## Side Effects

    - Inserts rows into the ``research_sources`` table via ``researches_db_manager``.
    """
    _log.debug("[BG] Saving %d findings for research %s", len(findings), research_id)
    now = datetime.now(timezone.utc).isoformat()
    
    # Save each unique source
    processed_urls = set()
    for item in findings:
        url = item.get("url")
        if not url or url in processed_urls: continue
        processed_urls.add(url)
        
        data = {
            "id": str(uuid.uuid4()),
            "research_id": research_id,
            "source_type": item.get("type", "website"),
            "source_url": url,
            "source_content": (item.get("content") or item.get("summary", ""))[:5000],
            "created_at": now,
            "updated_at": now
        }
        researches_db_manager.insert("research_sources", data)

    # Save additional sources that might not have finding content
    for url in sources:
        if url in processed_urls: continue
        processed_urls.add(url)
        data = {
            "id": str(uuid.uuid4()),
            "research_id": research_id,
            "source_type": "website",
            "source_url": url,
            "created_at": now,
            "updated_at": now
        }
        researches_db_manager.insert("research_sources", data)


async def _bg_save_artifact_to_db(research_id: str, artifact_data: dict) -> None:
    """
    ## Description

    Background worker task: persists the generated artifact to the
    research record's ``artifacts`` column.

    ## Parameters

    - `research_id` (`str`)
      - Description: The research record ID.

    - `artifact_data` (`dict`)
      - Description: Serialized Artifact model.

    ## Returns

    `None`

    ## Side Effects

    - Updates the ``artifacts`` column on the ``researches`` table.
    """
    _log.debug("[BG] Saving artifact for research %s", research_id)
    try:
        researches_db_manager.update(
            "researches",
            data={"artifacts": json.dumps(artifact_data, default=str)},
            where={"id": research_id}
        )
    except Exception as exc:
        _log.error("[BG] Failed to save artifact to DB: %s", exc)


async def _bg_ingest_to_vectors(
    research_id: str,
    scraped_content: list,
) -> None:
    """
    ## Description

    Background worker task: ingests scraped web content into the ChromaDB
    vector store for future semantic search retrieval.

    ## Parameters

    - `research_id` (`str`)
      - Description: The research record ID used as metadata tag.

    - `scraped_content` (`list`)
      - Description: List of dicts with ``url`` and ``content`` keys.

    ## Returns

    `None`

    ## Side Effects

    - Submits ingestion tasks to the ``IngestionService`` singleton.
    - Content is chunked, embedded via Ollama, and stored in ChromaDB.
    """
    try:
        from main.src.store.vector.IngestionService import (
            ingestion_service,
            make_task,
            Priority,
        )

        for item in scraped_content:
            url = item.get("url", "")
            content = item.get("content", "")
            if not content:
                continue

            task = make_task(
                collection="websites",
                content=content,
                source_uri=url,
                metadata={
                    "research_id": research_id,
                    "title": item.get("title", ""),
                },
                priority=Priority.LOW,
            )
            await ingestion_service.submit(task)

        _log.info(
            "[BG] Ingested %d items into vectors for research %s",
            len(scraped_content),
            research_id,
        )
    except Exception as exc:
        _log.error("[BG] Vector ingestion failed: %s", exc)


# ===========================================================================
# Main Orchestrator
# ===========================================================================


class ResearchOrchestrator:
    """
    ## Description

    The top-level controller that runs a complete research session.
    Coordinates query validation, research planning, the ReAct reasoning
    loop, vector ingestion, artifact generation, and persistence — all
    with real-time SSE event emission and background task scheduling
    for non-critical I/O.

    ## Parameters

    - None (initializes internal services from environment variables).

    ## Returns

    `ResearchOrchestrator` instance.

    ## Side Effects

    - Instantiates ``ExternalServices``, ``ToolRegistry``,
      ``ResearchPlanner``, ``ArtifactGenerator``, ``QuestionAsker``,
      and ``ReActEngine``.

    ## Customization

    Modify tool registration, ReAct step limits, or planning prompts
    to change research behavior.
    """

    def __init__(self) -> None:
        self.gemini = getAsyncClient()
        self.services = ExternalServices()

        api_key = os.getenv("GEMINI_API_KEY", "")
        self.tool_registry = ToolRegistry(
            services=self.services,
            api_key=api_key,
        )
        self.react_engine = ReActEngine(
            gemini=self.gemini,
            tool_registry=self.tool_registry,
        )
        self.planner = ResearchPlanner(self.gemini)
        self.artifact_gen = ArtifactGenerator(self.gemini)
        self.question_asker = QuestionAsker(self.gemini)

    # ------------------------------------------------------------------
    # SSE event emission
    # ------------------------------------------------------------------

    async def _emit(
        self,
        job_id: str,
        stage: ResearchStage,
        message: str,
        status: JobStatus = JobStatus.RUNNING,
        data: Optional[dict] = None,
    ) -> None:
        """
        ## Description

        Broadcasts a structured SSE event to all connected clients and
        schedules a background task to persist the event to the database.

        ## Parameters

        - `job_id` (`str`)
          - Description: Unique research job identifier.

        - `stage` (`ResearchStage`)
          - Description: Current pipeline stage.

        - `message` (`str`)
          - Description: Human-readable progress message.

        - `status` (`JobStatus`)
          - Description: Job lifecycle status. Default: RUNNING.

        - `data` (`Optional[dict]`)
          - Description: Optional payload data attached to the event.

        ## Returns

        `None`

        ## Side Effects

        - Broadcasts to all SSE clients via ``event_bus``.
        - Schedules background persistence via the ``scheduler``.
        """
        event_payload = {
            "job_id": job_id,
            "stage": stage.value,
            "status": status.value,
            "message": message,
            "data": data,
        }

        # Broadcast to all connected SSE clients
        await event_bus.broadcast(event_payload)

        # Schedule BG persistence (non-blocking, low-priority)
        await scheduler.schedule(
            _bg_save_event_to_db,
            params={
                "research_id": job_id,
                "event_data": event_payload,
            },
        )

    # ------------------------------------------------------------------
    # Main execution pipeline
    # ------------------------------------------------------------------

    async def execute(self, job_id: str, input_data: dict) -> Artifact:
        """
        ## Description

        Runs the full research pipeline for a given job:

        1. **Validate** — Checks query safety via ``/query/validate``.
        2. **Plan** — Generates a multi-step research plan via Gemini.
        3. **ReAct Loop** — Iterative reasoning + tool execution.
        4. **Ingest** — BG worker ingests scraped content into vectors.
        5. **Artifact Generation** — Produces the final markdown report.
        6. **Save** — BG workers persist findings and artifact to DB.

        ## Parameters

        - `job_id` (`str`)
          - Description: Unique identifier for this research session.
          - Constraints: Should be a UUID string.

        - `input_data` (`dict`)
          - Description: Research request payload.
          - Constraints: Must contain ``prompt``. Optional: ``context``,
            ``research_id``, ``workspace_id``, ``api_key``.
          - Example:
            ```json
            {
                "prompt": "What are the latest breakthroughs in quantum computing?",
                "context": "Focus on error correction",
                "research_id": "uuid-string",
                "api_key": "gemini-api-key"
            }
            ```

        ## Returns

        `Artifact` — The generated research artifact.

        ## Raises

        - `Exception` — On critical pipeline failures.

        ## Side Effects

        - Emits SSE events throughout the pipeline.
        - Schedules multiple background tasks for DB saves and vector ingestion.
        - Makes external HTTP requests (Gemini, SearXNG, crawl4ai).
        """
        session = ResearchSession(
            job_id=job_id,
            prompt=input_data.get("prompt", ""),
            context=input_data.get("context"),
            research_id=input_data.get("research_id"),
            workspace_id=input_data.get("workspace_id"),
        )

        api_key = input_data.get("api_key", os.getenv("GEMINI_API_KEY", ""))

        try:
            # ═══════════════════════════════════════════════════════
            # 1. VALIDATE QUERY
            # ═══════════════════════════════════════════════════════
            await self._emit(
                job_id, ResearchStage.VALIDATING,
                "Validating query for safety and sanitization...",
            )

            validation = await self.services.validate_query(session.prompt, api_key)
            if not validation.get("is_safe", True):
                issues = validation.get("issues", [])
                await self._emit(
                    job_id, ResearchStage.VALIDATING,
                    f"Query flagged as unsafe: {issues}",
                    status=JobStatus.FAILED,
                )
                raise ValueError(f"Unsafe query: {issues}")

            session.refined_query = validation.get("refined_query", session.prompt)
            await self._emit(
                job_id, ResearchStage.VALIDATING,
                "Query validated successfully.",
                data={"refined_query": session.refined_query},
            )

            # ═══════════════════════════════════════════════════════
            # 2. GENERATE RESEARCH PLAN
            # ═══════════════════════════════════════════════════════
            await self._emit(
                job_id, ResearchStage.PLANNING,
                "Generating research plan...",
            )

            plan = await self.planner.create_plan(
                session.refined_query, session.context
            )
            session.plan = plan

            # Ask clarifying questions (non-blocking insight)
            questions = await self.question_asker.ask_clarifying_questions(
                session.refined_query, session.context
            )

            await self._emit(
                job_id, ResearchStage.PLANNING,
                "Research plan generated.",
                data={
                    "plan": plan.model_dump(),
                    "clarifying_questions": questions,
                },
            )

            # ═══════════════════════════════════════════════════════
            # 3. ReAct REASONING LOOP
            # ═══════════════════════════════════════════════════════
            await self._emit(
                job_id, ResearchStage.THINKING,
                "Starting ReAct reasoning loop...",
                status=JobStatus.THINKING,
            )

            async def _on_react_step(step: ThinkingStep) -> None:
                """
                ## Description

                Callback invoked after each ReAct iteration. Emits
                appropriate SSE events for thinking and acting phases.

                ## Parameters

                - `step` (`ThinkingStep`) — The completed thinking step.

                ## Returns

                `None`
                """
                stage = ResearchStage.THINKING
                status = JobStatus.THINKING

                if step.action:
                    stage = ResearchStage.ACTING
                    status = JobStatus.ACTING

                step_data = {
                    "step": step.step,
                    "thought": step.thought[:500],
                }
                if step.action:
                    step_data["tool"] = step.action.tool.value
                    step_data["parameters"] = step.action.parameters
                if step.observation:
                    step_data["observation_preview"] = step.observation[:300]

                await self._emit(
                    job_id, stage,
                    f"Step {step.step}: {step.thought[:200]}",
                    status=status,
                    data=step_data,
                )

            react_result = await self.react_engine.run(
                query=session.refined_query,
                context=session.context or "",
                on_step=_on_react_step,
            )

            session.thinking_steps = react_result["thinking_steps"]
            session.sources = react_result["sources"]
            session.videos = react_result["videos"]
            session.images = react_result["images"]

            # ═══════════════════════════════════════════════════════
            # 4. BG WORKER: Ingest scraped content into vectors
            # ═══════════════════════════════════════════════════════
            scraped_content = react_result.get("scraped_content", [])
            if scraped_content:
                await self._emit(
                    job_id, ResearchStage.INGESTING,
                    f"Scheduling vector ingestion for {len(scraped_content)} pages...",
                )

                await scheduler.schedule(
                    _bg_ingest_to_vectors,
                    params={
                        "research_id": session.research_id or job_id,
                        "scraped_content": scraped_content,
                    },
                )

            # ═══════════════════════════════════════════════════════
            # 5. BG WORKER: Save findings to database
            # ═══════════════════════════════════════════════════════
            await scheduler.schedule(
                _bg_save_findings_to_db,
                params={
                    "research_id": session.research_id or job_id,
                    "findings": scraped_content,
                    "sources": session.sources,
                },
            )

            # ═══════════════════════════════════════════════════════
            # 6. GENERATE ARTIFACT
            # ═══════════════════════════════════════════════════════
            await self._emit(
                job_id, ResearchStage.ARTIFACT_GEN,
                "Generating final research artifact...",
            )

            # Build findings for artifact generator from scraped content + summaries
            findings_for_artifact = []
            for item in scraped_content:
                findings_for_artifact.append({
                    "source": item.get("url", ""),
                    "summary": item.get("content", "")[:1000],
                })

            # Add ReAct final summary
            if react_result.get("final_summary"):
                findings_for_artifact.append({
                    "source": "ReAct Research Agent",
                    "summary": react_result["final_summary"],
                })

            artifact = await self.artifact_gen.generate(
                session.refined_query,
                findings_for_artifact,
                session.videos,
                session.images,
            )

            # Attach the thinking trace to the artifact
            artifact.thinking_trace = session.thinking_steps
            session.artifact = artifact

            # ═══════════════════════════════════════════════════════
            # 7. BG WORKER: Save artifact to database
            # ═══════════════════════════════════════════════════════
            await scheduler.schedule(
                _bg_save_artifact_to_db,
                params={
                    "research_id": session.research_id or job_id,
                    "artifact_data": artifact.model_dump(),
                },
            )

            # ═══════════════════════════════════════════════════════
            # 8. FINALIZE
            # ═══════════════════════════════════════════════════════
            await self._emit(
                job_id, ResearchStage.FINALIZING,
                "Research complete.",
                status=JobStatus.COMPLETED,
                data={
                    "artifact": artifact.model_dump(),
                    "total_sources": len(session.sources),
                    "total_steps": len(session.thinking_steps),
                    "total_videos": len(session.videos),
                    "total_images": len(session.images),
                },
            )

            _log.info(
                "[Orchestrator] Job %s completed. Sources=%d Steps=%d",
                job_id,
                len(session.sources),
                len(session.thinking_steps),
            )

            return artifact

        except Exception as exc:
            _log.error("[Orchestrator] Job %s failed: %s", job_id, exc)
            await self._emit(
                job_id, ResearchStage.FINALIZING,
                f"Research failed: {str(exc)}",
                status=JobStatus.FAILED,
            )
            raise
