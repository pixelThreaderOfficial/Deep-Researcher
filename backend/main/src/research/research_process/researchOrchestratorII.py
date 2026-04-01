"""
OutputOrchestrator — Phase 2: Analysis, Fact-Check & Structured Output
=======================================================================

Architecture (matches diagram):
  Input: Phase 1 .md knowledge base + ResearchPlan + research_template (JSON)

  Task Orchestrator 2 — 5 parallel analysis agents:
    1. Summary & visualization agent   — detailed summary + patterns for charts/graphs
    2. Chunk classifier agent          — important vs noise, classifies for storage
    3. Key answer extractor agent      — highlighted facts (numbers, rates, entities)
    4. Conclusion agent                — quality conclusion derived from all sources
    5. Assets agent                    — surfaces images, blogs, websites, YouTube links

  Sequential post-processing:
    → Fact check                       — cross-checks key claims against vector store
    → Structure for output layer       — formats everything per research_template JSON

  Storage:
    - Redis          (live state, crash recovery, user can join at any time)
    - research_metadata table
    - research_sources table
    - research_workflow table
    - researches table  (status + final output)
    - Scheduler      (all DB writes are fire-and-forget)
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, cast

from redis import Redis

from main.src.research.input.m0_inputProcessing import ResearchPlan
from main.src.research.research_process.thinker import Thinker
from main.src.store.DBManager import history_db_manager, researches_db_manager
from main.src.store.vector import vector_store
from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import quickLog
from main.sse.event_bus import event_bus

CURR_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# .md reader — reads the Phase 1 output
# ---------------------------------------------------------------------------


def _read_phase1_md(research_id: str) -> str:
    p = CURR_DIR / "temp_files" / f"{research_id}.md"
    if not p.exists():
        raise FileNotFoundError(f"Phase 1 .md not found for research_id: {research_id}")
    return p.read_text()


def _append_phase2_md(research_id: str, content: str) -> None:
    """Appends Phase 2 analysis sections to the same .md (Phase 2 enriches it further)."""
    p = CURR_DIR / "temp_files" / f"{research_id}.md"
    with p.open("a") as f:
        f.write("\n\n" + content)


# ---------------------------------------------------------------------------
# OutputOrchestrator
# ---------------------------------------------------------------------------


class OutputOrchestrator:
    def __init__(
        self,
        redis_client: Redis,
        research_id: str,
        plan: ResearchPlan,
        enhanced_prompt: str,
        processed_input: dict,
        research_template: dict,  # JSON template that defines output structure
        workspace_id: str,
        gemini_api_key: str,
        ollama_url: str,
        phase1_sources: list[dict],  # sources list carried over from Phase 1
        phase1_tokens: int = 0,
        phase1_generations: int = 0,
    ):
        self.redis_client = redis_client
        self.research_id = research_id
        self.plan = plan
        self.enhanced_prompt = enhanced_prompt
        self.processed_input = processed_input
        self.research_template = research_template
        self.workspace_id = workspace_id
        self.gemini_api_key = gemini_api_key
        self.ollama_url = ollama_url
        self.phase1_sources = phase1_sources

        self.redis_key = f"dr:research:{research_id}"
        self.thinker = Thinker()

        # Counters — start where Phase 1 left off
        self.total_tokens: int = phase1_tokens
        self.total_generations: int = phase1_generations
        self.start_time: float = time.time()

        # Accumulated output — built up across agents
        self.summary: str = ""
        self.visualizable_patterns: list[dict] = []
        self.classified_chunks: list[dict] = []
        self.key_answers: list[dict] = []
        self.conclusion: str = ""
        self.assets: dict[str, list[dict]] = {"web_assets": [], "images": []}
        self.fact_check_report: str = ""
        self.structured_output: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------

    def _get_state(self) -> dict[str, Any]:
        raw = self.redis_client.get(self.redis_key)
        raw_value = cast(Any, raw)
        if isinstance(raw_value, (bytes, bytearray)):
            raw_str = raw_value.decode("utf-8")
        elif isinstance(raw_value, str):
            raw_str = raw_value
        else:
            raw_str = ""
        return json.loads(raw_str) if raw_str else {}

    def _set_state(self, update: dict) -> None:
        state = self._get_state()
        state.update(update)
        self.redis_client.setex(self.redis_key, 86400, json.dumps(state))

    # -------------------------------------------------------------------------
    # SSE broadcast
    # -------------------------------------------------------------------------

    async def _broadcast(self, event_type: str, **payload) -> None:
        await event_bus.broadcast(
            message={
                "type": event_type,
                "research": self.research_id,
                "phase": "phase2",
                "tokens": self.total_tokens,
                "generations": self.total_generations,
                **payload,
            }
        )

    # -------------------------------------------------------------------------
    # DB helpers (scheduler = fire-and-forget background)
    # -------------------------------------------------------------------------

    async def _update_research_status(self, status: str, **extra) -> None:
        await scheduler.schedule(
            researches_db_manager.update,
            params={
                "table_name": "researches",
                "data": {"status": status, **extra},
                "where": {"id": self.research_id},
            },
        )

    async def _insert_source(
        self,
        source_type: str,
        source_url: str,
        source_content: str,
        source_citations: str = "",
        vector_id: str = "",
    ) -> None:
        await scheduler.schedule(
            researches_db_manager.insert,
            params={
                "table_name": "research_sources",
                "data": {
                    "id": str(uuid.uuid4()),
                    "research_id": self.research_id,
                    "source_type": source_type,
                    "source_url": source_url,
                    "source_content": source_content[:2000],
                    "source_citations": source_citations,
                    "source_vector_id": vector_id,
                },
            },
        )

    async def _upsert_metadata(self, **fields) -> None:
        """Insert or update research_metadata for this research."""
        elapsed = int(time.time() - self.start_time)
        await scheduler.schedule(
            researches_db_manager.insert,
            params={
                "table_name": "research_metadata",
                "data": {
                    "id": str(uuid.uuid4()),
                    "research_id": self.research_id,
                    "workspace_id": self.workspace_id,
                    "token_count": self.total_tokens,
                    "num_api_calls": self.total_generations,
                    "source_count": len(self.phase1_sources),
                    "websites_count": sum(
                        1 for s in self.phase1_sources if s.get("tool") == "web_search"
                    ),
                    "file_count": sum(
                        1
                        for s in self.phase1_sources
                        if s.get("tool") in ("document_search", "image_understanding")
                    ),
                    "citations": json.dumps(self.key_answers),
                    "time_taken_sec": elapsed,
                    "status": True,
                    **fields,
                },
            },
        )

    async def _save_workflow(self, success: bool, workflow_log: list[str]) -> None:
        elapsed = int(time.time() - self.start_time)
        await scheduler.schedule(
            history_db_manager.insert,
            params={
                "table_name": "research_workflow",
                "data": {
                    "id": str(uuid.uuid4()),
                    "workspace_id": self.workspace_id,
                    "research_id": self.research_id,
                    "workflow": json.dumps(workflow_log),
                    "steps": len(self.plan.steps),
                    "tokens_used": self.total_tokens,
                    "resources_used": self.total_generations,
                    "time_taken_sec": elapsed,
                    "success": success,
                },
            },
        )

    # -------------------------------------------------------------------------
    # Thinker wrapper — tracks generation count
    # -------------------------------------------------------------------------

    async def _think(self, topic: str, context: str, intensity: float = 0.6) -> str:
        self.total_generations += 1
        result = await self.thinker.think(
            topic=topic, context=context, thinking_intensity=intensity
        )
        return str(result)

    # -------------------------------------------------------------------------
    # Task Orchestrator 2 — 5 parallel analysis agents
    # -------------------------------------------------------------------------

    async def _agent_summary_and_viz(self, knowledge: str) -> dict:
        """
        Agent 1: Detailed summary + find patterns that can be visualized graphically.
        Looks for tables, trends, comparisons, timelines, distributions.
        """
        response = await self._think(
            topic=f"Summarize and find visualizable patterns for: {self.plan.objective}",
            context=(
                f"Research title: {self.plan.title}\n"
                f"User prompt: {self.enhanced_prompt}\n\n"
                f"Knowledge base:\n{knowledge}\n\n"
                "Reply in this format:\n"
                "SUMMARY:\n<detailed multi-paragraph summary>\n\n"
                "VISUALIZABLE_PATTERNS:\n"
                "<one per line, format: TYPE|TITLE|DATA_DESCRIPTION>\n"
                "Types: bar_chart, line_chart, table, timeline, comparison, pie_chart, stat_card\n\n"
                "VISUALIZATION_DATA:\n<JSON array of chart-ready data objects>"
            ),
            intensity=0.8,
        )

        summary = ""
        patterns = []
        viz_data = []

        sections = response.split("\n\n")
        current_section = None
        for line in response.splitlines():
            lne = line.strip()
            if lne.startswith("SUMMARY:"):
                current_section = "summary"
            elif lne.startswith("VISUALIZABLE_PATTERNS:"):
                current_section = "patterns"
            elif lne.startswith("VISUALIZATION_DATA:"):
                current_section = "viz_data"
                raw_json = response.split("VISUALIZATION_DATA:")[1].strip()
                try:
                    viz_data = json.loads(raw_json.split("\n\n")[0])
                except Exception:
                    viz_data = []
            elif current_section == "summary" and lne:
                summary += line + "\n"
            elif current_section == "patterns" and "|" in lne:
                parts = lne.split("|", 2)
                if len(parts) == 3:
                    patterns.append(
                        {
                            "type": parts[0].strip(),
                            "title": parts[1].strip(),
                            "description": parts[2].strip(),
                        }
                    )

        quickLog(
            level="info",
            message=f"[Phase2] Summary agent done — {len(patterns)} patterns found",
            module=["RESEARCH"],
        )
        return {"summary": summary.strip(), "patterns": patterns, "viz_data": viz_data}

    async def _agent_chunk_classifier(self, knowledge: str) -> dict:
        """
        Agent 2: Find important chunks, filter noise, classify for storage.
        Labels each chunk: key_finding | supporting | context | noise
        """
        response = await self._think(
            topic=f"Classify and filter the most important information chunks for: {self.plan.objective}",
            context=(
                f"Knowledge base:\n{knowledge[:4000]}\n\n"
                "Extract the most important chunks of information.\n"
                "Reply as a JSON array only, no other text:\n"
                "[\n"
                '  {"chunk": "<text>", "label": "key_finding|supporting|context|noise",'
                '   "topic": "<topic>", "importance": 1-10}\n'
                "]\n"
            ),
            intensity=0.5,
        )

        chunks = []
        try:
            raw = response.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            chunks = json.loads(raw)
        except Exception:
            quickLog(
                level="error",
                message="Chunk classifier JSON parse failed",
                module=["RESEARCH"],
            )

        # Store classified chunks in vector store for retrieval in output structuring
        key_chunks = [
            c for c in chunks if c.get("label") in ("key_finding", "supporting")
        ]
        for chunk in key_chunks:
            try:
                await vector_store.add_text(
                    text=chunk["chunk"],
                    collection="research",
                    source_uri=f"classified:{self.research_id}:{chunk.get('topic', 'general')}",
                    metadata={
                        "research_id": self.research_id,
                        "label": chunk.get("label", ""),
                        "topic": chunk.get("topic", ""),
                        "importance": str(chunk.get("importance", 5)),
                        "type": "classified_chunk",
                        "phase": "2",
                    },
                )
                await self._insert_source(
                    source_type="classified_chunk",
                    source_url=f"internal:{chunk.get('topic', 'general')}",
                    source_content=chunk["chunk"],
                    source_citations=chunk.get("label", ""),
                )
            except Exception as e:
                quickLog(
                    level="error",
                    message=f"Chunk vector store failed: {e}",
                    module=["RESEARCH"],
                )

        quickLog(
            level="info",
            message=f"[Phase2] Classifier done — {len(key_chunks)} key chunks",
            module=["RESEARCH"],
        )
        return {"chunks": chunks, "key_count": len(key_chunks)}

    async def _agent_key_answer_extractor(self, knowledge: str) -> dict:
        """
        Agent 3: Extract highlighted key answer points.
        Like Google's featured snippet — numbers, rates, entities, direct answers.
        """
        response = await self._think(
            topic=f"Extract the key highlighted answer points for: {self.plan.objective}",
            context=(
                f"User query: {self.enhanced_prompt}\n\n"
                f"Knowledge base:\n{knowledge[:4000]}\n\n"
                "Find the most direct, precise answer points — numbers, facts, rates, named entities.\n"
                "Reply as JSON array only:\n"
                "[\n"
                '  {"answer": "<the fact>", "value": "<numeric or entity if applicable>",'
                '   "unit": "<unit if numeric>", "source_hint": "<where this came from>",'
                '   "confidence": "high|medium|low", "type": "stat|fact|entity|definition|rate"}\n'
                "]\n"
            ),
            intensity=0.6,
        )

        answers = []
        try:
            raw = response.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            answers = json.loads(raw)
        except Exception:
            quickLog(
                level="error",
                message="Key answer extractor JSON parse failed",
                module=["RESEARCH"],
            )

        quickLog(
            level="info",
            message=f"[Phase2] Key answers: {len(answers)} extracted",
            module=["RESEARCH"],
        )
        return {"answers": answers}

    async def _agent_conclusion(self, knowledge: str) -> dict:
        """
        Agent 4: Derive a high-quality research conclusion.
        Synthesizes everything into a coherent final verdict.
        """
        response = await self._think(
            topic=f"Derive a quality conclusion for the research: {self.plan.objective}",
            context=(
                f"Research title: {self.plan.title}\n"
                f"User prompt: {self.enhanced_prompt}\n\n"
                f"Knowledge base:\n{knowledge[:4000]}\n\n"
                "Write a high-quality, nuanced conclusion.\n"
                "Reply in this format:\n"
                "CONCLUSION:\n<multi-paragraph conclusion>\n\n"
                "CONFIDENCE: high|medium|low\n"
                "CAVEATS:\n<bullet points of limitations or things the research couldn't fully answer>"
            ),
            intensity=0.8,
        )

        conclusion = ""
        confidence = "medium"
        caveats = []
        current = None
        for line in response.splitlines():
            lne = line.strip()
            if lne.startswith("CONCLUSION:"):
                current = "conclusion"
            elif lne.startswith("CONFIDENCE:"):
                confidence = lne.split(":", 1)[1].strip()
                current = None
            elif lne.startswith("CAVEATS:"):
                current = "caveats"
            elif current == "conclusion" and lne:
                conclusion += line + "\n"
            elif current == "caveats" and lne:
                caveats.append(lne.lstrip("- •"))

        quickLog(
            level="info",
            message=f"[Phase2] Conclusion derived — confidence={confidence}",
            module=["RESEARCH"],
        )
        return {
            "conclusion": conclusion.strip(),
            "confidence": confidence,
            "caveats": caveats,
        }

    async def _agent_assets(self, knowledge: str) -> dict:
        """
        Agent 5: Surface useful assets — images, blogs, websites, YouTube links.
        Searches the vector image store + extracts URLs from knowledge base.
        """
        # Pull relevant images from vector store
        image_results = []
        try:
            image_results = await vector_store.search(
                query=self.plan.objective,
                collection="images",
                n_results=10,
                where={"research_id": self.research_id},
            )
        except Exception as e:
            quickLog(
                level="error",
                message=f"Image vector search failed: {e}",
                module=["RESEARCH"],
            )

        # Ask thinker to extract useful web assets from the knowledge text
        response = await self._think(
            topic=f"Extract useful assets (links, images, videos) from this research for: {self.plan.objective}",
            context=(
                f"Knowledge base:\n{knowledge[:3000]}\n\n"
                "Find all useful URLs, image references, YouTube links, blog posts.\n"
                "Reply as JSON array only:\n"
                "[\n"
                '  {"type": "image|website|youtube|blog|document",'
                '   "url": "<url>", "title": "<title>", "relevance": "<one sentence why>"}\n'
                "]\n"
            ),
            intensity=0.4,
        )

        web_assets = []
        try:
            raw = response.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            web_assets = json.loads(raw)
        except Exception:
            quickLog(
                level="error",
                message="Assets extractor JSON parse failed",
                module=["RESEARCH"],
            )

        # Save assets to research_sources table
        for asset in web_assets:
            await self._insert_source(
                source_type=asset.get("type", "website"),
                source_url=asset.get("url", ""),
                source_content=asset.get("relevance", ""),
                source_citations=asset.get("title", ""),
            )

        quickLog(
            level="info",
            message=f"[Phase2] Assets: {len(web_assets)} web + {len(image_results)} images",
            module=["RESEARCH"],
        )
        return {"web_assets": web_assets, "images": image_results}

    # -------------------------------------------------------------------------
    # Fact check — cross-references key answers against vector store
    # -------------------------------------------------------------------------

    async def _fact_check(self, key_answers: list[dict]) -> str:
        """
        Cross-checks each key answer against the vector store.
        Flags anything that can't be corroborated.
        """
        self._set_state({"phase2_stage": "fact_check"})
        await self._broadcast("phase2_stage", stage="fact_check")

        if not key_answers:
            return "No key answers to fact-check."

        fact_check_lines = ["## Fact Check Report\n"]

        for answer in key_answers[:10]:  # cap at 10 to avoid runaway calls
            claim = answer.get("answer", "")
            if not claim:
                continue

            # Search vector store for corroborating evidence
            try:
                evidence = await vector_store.search(
                    query=claim,
                    collection="research",
                    n_results=3,
                    where={"research_id": self.research_id},
                )
                evidence_text = str(evidence)[:800]
            except Exception:
                evidence_text = "Vector search unavailable"

            response = await self._think(
                topic=f"Fact-check this claim: {claim}",
                context=(
                    f"Claim: {claim}\n"
                    f"Corroborating evidence from sources:\n{evidence_text}\n\n"
                    "Reply in this format:\n"
                    "VERDICT: verified|unverified|contradicted|partial\n"
                    "REASON: <one sentence>"
                ),
                intensity=0.3,
            )

            verdict = "unverified"
            reason = ""
            for line in response.splitlines():
                lne = line.strip()
                if lne.lower().startswith("verdict:"):
                    verdict = lne.split(":", 1)[1].strip()
                elif lne.lower().startswith("reason:"):
                    reason = lne.split(":", 1)[1].strip()

            icon = {"verified": "✓", "contradicted": "✗", "partial": "~"}.get(
                verdict, "?"
            )
            fact_check_lines.append(f"- {icon} **{claim}** — {verdict}: {reason}")

        report = "\n".join(fact_check_lines)
        _append_phase2_md(self.research_id, report)
        return report

    # -------------------------------------------------------------------------
    # Structure output per research_template
    # -------------------------------------------------------------------------

    async def _structure_output(
        self,
        summary: str,
        patterns: list[dict],
        viz_data: list,
        key_answers: list[dict],
        conclusion: str,
        caveats: list[str],
        confidence: str,
        assets: dict[str, list[dict]],
        fact_check_report: str,
    ) -> dict[str, Any]:
        """
        Formats all Phase 2 outputs into the structure defined by research_template.
        research_template JSON defines what sections, what order, what format the output layer expects.
        """
        self._set_state({"phase2_stage": "structuring_output"})
        await self._broadcast("phase2_stage", stage="structuring_output")

        template_str = json.dumps(self.research_template, indent=2)

        context = (
            f"Research title: {self.plan.title}\n"
            f"Objective: {self.plan.objective}\n"
            f"User prompt: {self.enhanced_prompt}\n\n"
            f"Output template to follow:\n{template_str}\n\n"
            f"--- AVAILABLE DATA ---\n\n"
            f"SUMMARY:\n{summary}\n\n"
            f"KEY ANSWERS:\n{json.dumps(key_answers, indent=2)}\n\n"
            f"CONCLUSION:\n{conclusion}\n\n"
            f"CONFIDENCE: {confidence}\n"
            f"CAVEATS: {json.dumps(caveats)}\n\n"
            f"VISUALIZABLE PATTERNS:\n{json.dumps(patterns, indent=2)}\n\n"
            f"VISUALIZATION DATA:\n{json.dumps(viz_data, indent=2)}\n\n"
            f"ASSETS:\n{json.dumps(assets.get('web_assets', []), indent=2)}\n\n"
            f"FACT CHECK:\n{fact_check_report}\n\n"
            "Fill the template with the above data. Reply as valid JSON only matching the template structure."
        )

        response = await self._think(
            topic=f"Structure the final research output for: {self.plan.objective}",
            context=context,
            intensity=0.7,
        )

        structured = {}
        try:
            raw = response.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            structured = json.loads(raw)
        except Exception:
            # If JSON parse fails, fall back to a sensible default structure
            quickLog(
                level="error",
                message="Output structuring JSON parse failed — using fallback",
                module=["RESEARCH"],
            )
            structured = {
                "title": self.plan.title,
                "objective": self.plan.objective,
                "summary": summary,
                "key_answers": key_answers,
                "conclusion": conclusion,
                "confidence": confidence,
                "caveats": caveats,
                "visualizations": patterns,
                "viz_data": viz_data,
                "assets": assets.get("web_assets", []),
                "fact_check": fact_check_report,
                "sources": self.phase1_sources,
            }

        return structured

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    async def execute(self) -> dict:
        """
        Runs Phase 2 end-to-end.
        Returns the structured output dict for the output layer.
        """
        quickLog(
            level="info",
            message=f"Phase 2 OutputOrchestrator starting — research_id={self.research_id}",
            module=["RESEARCH"],
        )

        workflow_log: list[str] = []

        # ---- Resume check ----
        existing_state = self._get_state()
        phase2_done = existing_state.get("phase2_status") == "complete"
        if phase2_done:
            quickLog(
                level="info",
                message="Phase 2 already complete — returning cached output",
                module=["RESEARCH"],
            )
            return existing_state.get("structured_output", {})

        # ---- Load Phase 1 knowledge base ----
        try:
            knowledge = _read_phase1_md(self.research_id)
        except FileNotFoundError as e:
            quickLog(
                level="error", message=str(e), module=["RESEARCH"], urgency="critical"
            )
            raise

        self._set_state(
            {
                "phase2_status": "running",
                "phase2_stage": "agents_start",
                "tokens": self.total_tokens,
                "generations": self.total_generations,
            }
        )
        await self._broadcast("phase2_start", title=self.plan.title)
        await self._update_research_status("phase2_in_progress")

        # ---- Task Orchestrator 2: 5 agents in parallel ----
        await self._broadcast("phase2_stage", stage="parallel_agents")
        self._set_state({"phase2_stage": "parallel_agents"})

        (
            summary_result,
            classifier_result,
            key_answer_result,
            conclusion_result,
            assets_result,
        ) = await asyncio.gather(
            self._agent_summary_and_viz(knowledge),
            self._agent_chunk_classifier(knowledge),
            self._agent_key_answer_extractor(knowledge),
            self._agent_conclusion(knowledge),
            self._agent_assets(knowledge),
            return_exceptions=True,
        )

        # Handle any agent exceptions gracefully — don't let one failure kill everything
        def _safe(result: object, default: dict[str, Any]) -> dict[str, Any]:
            if isinstance(result, Exception):
                quickLog(
                    level="error",
                    message=f"Agent failed: {result}",
                    module=["RESEARCH"],
                )
                return default
            return cast(dict[str, Any], result)

        summary_result = _safe(
            summary_result, {"summary": "", "patterns": [], "viz_data": []}
        )
        classifier_result = _safe(classifier_result, {"chunks": [], "key_count": 0})
        key_answer_result = _safe(key_answer_result, {"answers": []})
        conclusion_result = _safe(
            conclusion_result, {"conclusion": "", "confidence": "low", "caveats": []}
        )
        assets_result = _safe(assets_result, {"web_assets": [], "images": []})

        self.summary = summary_result["summary"]
        self.visualizable_patterns = summary_result["patterns"]
        self.classified_chunks = classifier_result["chunks"]
        self.key_answers = key_answer_result["answers"]
        self.conclusion = conclusion_result["conclusion"]
        self.assets = assets_result

        workflow_log.append("parallel_agents_complete")

        # Push intermediate state to Redis so user can see progress live
        self._set_state(
            {
                "phase2_stage": "agents_complete",
                "summary_preview": self.summary[:300],
                "key_answers_count": len(self.key_answers),
                "patterns_count": len(self.visualizable_patterns),
                "tokens": self.total_tokens,
                "generations": self.total_generations,
            }
        )
        await self._broadcast(
            "phase2_agents_complete",
            key_answers_count=len(self.key_answers),
            patterns_count=len(self.visualizable_patterns),
        )

        # Append agent outputs to .md
        _append_phase2_md(
            self.research_id,
            f"\n\n---\n## Phase 2 Analysis\n\n"
            f"### Summary\n{self.summary}\n\n"
            f"### Conclusion\n{self.conclusion}\n\n"
            f"**Confidence:** {conclusion_result['confidence']}\n\n"
            f"**Caveats:**\n"
            + "\n".join(f"- {c}" for c in conclusion_result["caveats"]),
        )

        # ---- Fact check ----
        self.fact_check_report = await self._fact_check(self.key_answers)
        workflow_log.append("fact_check_complete")

        self._set_state(
            {
                "phase2_stage": "fact_check_complete",
                "tokens": self.total_tokens,
                "generations": self.total_generations,
            }
        )
        await self._broadcast("phase2_fact_check_complete")

        # ---- Structure output per template ----
        self.structured_output = await self._structure_output(
            summary=self.summary,
            patterns=self.visualizable_patterns,
            viz_data=summary_result["viz_data"],
            key_answers=self.key_answers,
            conclusion=self.conclusion,
            caveats=conclusion_result["caveats"],
            confidence=conclusion_result["confidence"],
            assets=self.assets,
            fact_check_report=self.fact_check_report,
        )
        workflow_log.append("output_structured")

        # ---- Save everything to DB ----
        elapsed = int(time.time() - self.start_time)

        # researches table — final output + status
        await scheduler.schedule(
            researches_db_manager.update,
            params={
                "table_name": "researches",
                "data": {
                    "status": "complete",
                    "artifacts": json.dumps(self.structured_output),
                    "sources": json.dumps(self.phase1_sources),
                },
                "where": {"id": self.research_id},
            },
        )

        # research_metadata table
        await self._upsert_metadata(
            citations=json.dumps(self.key_answers),
            exported="json",
        )

        # research_workflow table
        await self._save_workflow(success=True, workflow_log=workflow_log)

        # ---- Final Redis state ----
        self._set_state(
            {
                "phase2_status": "complete",
                "phase2_stage": "done",
                "structured_output": self.structured_output,
                "tokens": self.total_tokens,
                "generations": self.total_generations,
                "elapsed_sec": elapsed,
            }
        )

        await self._broadcast(
            "phase2_complete",
            title=self.plan.title,
            elapsed_sec=elapsed,
            tokens=self.total_tokens,
            generations=self.total_generations,
            key_answers_count=len(self.key_answers),
            sources_count=len(self.phase1_sources),
        )

        quickLog(
            level="success",
            message=(
                f"Phase 2 complete — {self.research_id} | "
                f"elapsed={elapsed}s tokens={self.total_tokens} gens={self.total_generations}"
            ),
            module=["RESEARCH"],
        )

        return self.structured_output
