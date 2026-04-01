import uuid
import json
import time
import redis

from main.src.research.input.m0_inputProcessing import InputProcessing
from main.src.research.research_process.researchOrchestrator import ResearchOrchestrator
from main.src.research.research_process.researchOrchestratorII import OutputOrchestrator
from main.src.utils.DRLogger import quickLog
from main.src.utils.core.task_schedular import scheduler
from main.src.store.DBManager import researches_db_manager, history_db_manager
from main.sse.event_bus import event_bus

redis_client = redis.Redis(host="localhost", port=6379, db=0)


class MasterOrchestrator:
    """
    Coordinates all three phases end-to-end:

    Phase 0 — InputProcessing
        Validates input, generates confirmation questions, builds ResearchPlan,
        enhances the prompt. Returns (processed_input, plan, enhanced_prompt).

    Phase 1 — ResearchOrchestrator
        Knowledge gathering: parallel agents → processing pipeline → Thinker loop.
        Writes {research_id}.md and populates the vector store.

    Phase 2 — OutputOrchestrator
        Analysis: parallel analysis agents → fact check → structured output.
        Writes final artifacts to DB.

    Redis key : dr:research:{research_id}   (TTL 24h, written by every phase)
    """

    def __init__(self, ollama_url: str, gemini_api_key: str):
        self.ollama_url = ollama_url
        self.gemini_api_key = gemini_api_key

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_state(self, research_id: str) -> dict:
        raw = redis_client.get(f"dr:research:{research_id}")
        if isinstance(raw, (str, bytes, bytearray)):
            return json.loads(raw)
        return {}

    def _set_state(self, research_id: str, update: dict) -> None:
        key = f"dr:research:{research_id}"
        state = self._get_state(research_id)
        state.update(update)
        redis_client.setex(key, 86400, json.dumps(state))

    async def _broadcast(self, research_id: str, event_type: str, **payload) -> None:
        await event_bus.broadcast(
            message={
                "type": event_type,
                "research": research_id,
                **payload,
            }
        )

    async def _mark_failed(self, research_id: str, phase: str, error: str) -> None:
        self._set_state(
            research_id,
            {
                "master_status": "failed",
                "failed_phase": phase,
                "error": error,
            },
        )
        await scheduler.schedule(
            researches_db_manager.update,
            params={
                "table_name": "researches",
                "data": {"status": "failed"},
                "where": {"id": research_id},
            },
        )
        await self._broadcast(research_id, "research_failed", phase=phase, error=error)
        quickLog(
            level="error",
            message=f"Research {research_id} failed at {phase}: {error}",
            module=["RESEARCH"],
            urgency="critical",
        )

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    async def execute(self, job_id: str, payload: dict) -> None:
        """
        payload keys (all from the incoming job/request):
            prompt, title, desc, username, workspaceId,
            sources, research_template, custom_prompt,
            system_prompt, ai_personality,
            chat_access, background_processing
        """
        master_start = time.time()
        research_id: str = ""  # will be set after Phase 0

        # =====================================================================
        # Phase 0 — Input Processing
        # =====================================================================
        quickLog(
            level="info",
            message=f"[MasterOrchestrator] job_id={job_id} — Phase 0 starting",
            module=["RESEARCH"],
        )

        try:
            input_processor = InputProcessing(
                r=redis_client,
                ai_personality=payload.get("ai_personality", ""),
                background_processing=payload.get("background_processing", True),
                chat_access=payload.get("chat_access", True),
                custom_prompt=payload.get("custom_prompt", ""),
                desc=payload.get("desc", ""),
                prompt=payload.get("prompt", ""),
                research_template=(
                    payload.get("research_template_id")
                    or payload.get("research_template", "")
                ),
                sources=payload.get("sources", []),
                system_prompt=payload.get("system_prompt", ""),
                title=payload.get("title", ""),
                username=payload.get("username", ""),
                workspaceId=payload.get("workspaceId", ""),
            )

            # Returns (processed_input, plan, enhanced_prompt, research_id)
            processed_input, plan, enhanced_prompt, research_id = (
                await input_processor.process()
            )

        except Exception as e:
            # research_id may still be empty here — use job_id as fallback key
            fallback_id = research_id or job_id
            await self._mark_failed(fallback_id, "phase0_input_processing", str(e))
            return

        quickLog(
            level="success",
            message=f"[MasterOrchestrator] Phase 0 complete — research_id={research_id}",
            module=["RESEARCH"],
        )

        # Write master-level state so any reconnecting client knows we're alive
        self._set_state(
            research_id,
            {
                "master_status": "running",
                "job_id": job_id,
                "research_id": research_id,
                "title": plan.title,
                "objective": plan.objective,
                "total_steps": len(plan.steps),
                "phase": "phase1",
            },
        )

        # =====================================================================
        # Phase 1 — Knowledge Gathering
        # =====================================================================
        quickLog(
            level="info",
            message=f"[MasterOrchestrator] Phase 1 starting",
            module=["RESEARCH"],
        )

        try:
            research_executor = ResearchOrchestrator(
                redis_client=redis_client,
                processed_input=processed_input,
                plan=plan,
                enhanced_prompt=enhanced_prompt,
                research_id=research_id,
                ollama_url=self.ollama_url,
                gemini_api_key=self.gemini_api_key,
            )
            await research_executor.execute()

        except Exception as e:
            await self._mark_failed(research_id, "phase1_research", str(e))
            return

        # Grab counters Phase 1 wrote to Redis so Phase 2 continues from them
        phase1_state = self._get_state(research_id)
        phase1_tokens = phase1_state.get("tokens_used", 0)
        phase1_generations = phase1_state.get("generations", 0)
        phase1_sources = research_executor.sources  # live list from the executor

        self._set_state(research_id, {"phase": "phase2"})
        quickLog(
            level="success",
            message=f"[MasterOrchestrator] Phase 1 complete — tokens={phase1_tokens} gens={phase1_generations}",
            module=["RESEARCH"],
        )

        # =====================================================================
        # Phase 2 — Analysis & Structured Output
        # =====================================================================
        quickLog(
            level="info",
            message=f"[MasterOrchestrator] Phase 2 starting",
            module=["RESEARCH"],
        )

        try:
            output_processor = OutputOrchestrator(
                redis_client=redis_client,
                research_id=research_id,
                plan=plan,
                enhanced_prompt=enhanced_prompt,
                processed_input=processed_input,
                research_template=payload.get("research_template", {}),
                workspace_id=payload.get("workspaceId", ""),
                gemini_api_key=self.gemini_api_key,
                ollama_url=self.ollama_url,
                phase1_sources=phase1_sources,
                phase1_tokens=phase1_tokens,
                phase1_generations=phase1_generations,
            )
            structured_output = await output_processor.execute()

        except Exception as e:
            await self._mark_failed(research_id, "phase2_output", str(e))
            return

        # =====================================================================
        # Finalize — master-level DB writes & Redis cleanup
        # =====================================================================
        elapsed = int(time.time() - master_start)

        # researches table — mark fully done, write workspace linkage
        await scheduler.schedule(
            researches_db_manager.update,
            params={
                "table_name": "researches",
                "data": {
                    "status": "complete",
                    "workspace_id": payload.get("workspaceId", ""),
                    "artifacts": json.dumps(structured_output),
                    "sources": json.dumps(phase1_sources),
                    "prompt_order": json.dumps([p.description for p in plan.steps]),
                },
                "where": {"id": research_id},
            },
        )

        # research_plans table — persist the final approved plan
        await scheduler.schedule(
            researches_db_manager.insert,
            params={
                "table_name": "research_plans",
                "data": {
                    "id": str(uuid.uuid4()),
                    "plan": json.dumps(
                        {
                            "title": plan.title,
                            "objective": plan.objective,
                            "steps": [
                                {
                                    "description": s.description,
                                    "tools_required": s.tools_required,
                                    "depends_on": getattr(s, "depends_on", []),
                                }
                                for s in plan.steps
                            ],
                            "expected_tools": getattr(plan, "expected_tools", []),
                        }
                    ),
                    "workspace_id": payload.get("workspaceId", ""),
                    "research_id": research_id,
                    "research_template_id": payload.get("research_template_id", ""),
                    "prompt_order": json.dumps([s.description for s in plan.steps]),
                },
            },
        )

        # Final Redis state — clients rejoining after completion get full context
        self._set_state(
            research_id,
            {
                "master_status": "complete",
                "phase": "done",
                "elapsed_sec": elapsed,
                "structured_output_preview": json.dumps(structured_output)[:500],
            },
        )

        await self._broadcast(
            research_id,
            "master_complete",
            elapsed_sec=elapsed,
            title=plan.title,
            total_steps=len(plan.steps),
            sources_count=len(phase1_sources),
            tokens=phase1_state.get("tokens_used", 0),
            generations=phase1_state.get("generations", 0),
        )

        quickLog(
            level="success",
            message=(
                f"[MasterOrchestrator] DONE — research_id={research_id} "
                f"elapsed={elapsed}s steps={len(plan.steps)} sources={len(phase1_sources)}"
            ),
            module=["RESEARCH"],
        )
