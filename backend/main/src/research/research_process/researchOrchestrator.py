"""
ResearchOrchestrator — Phase 1: Knowledge Gathering
=====================================================

Architecture (matches diagram):
  Task Orchestrator 1
    └─ For each plan step, runs 4 search agents IN PARALLEL:
         • Web search agent
         • Local knowledge base agent
         • Image search agent
         • YouTube search agent
    └─ Each result → Processing Pipeline (sequential):
         1. Source credibility check
         2. Session knowledge builder  (appends to .md)
         3. Entity & relationship extraction
         4. Contradiction & consensus detector
         5. Summarize all
    └─ Thinker diamond: "Need more context?"
         • Yes → loop back with gap queries
         • No  → finalize

All results are stored in:
  - Redis (live state + crash recovery)
  - Vector store (text collection + image collection)
  - Temp .md file ({research_id}.md)  — the Phase 2 knowledge source
  - DB via scheduler (fire-and-forget)
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Protocol, cast

from redis import Redis

from main.src.research.input.m0_inputProcessing import ResearchPlan
from main.src.research.research_process.thinker import Thinker
from main.src.research.tools import (
    process_document,
    search_and_scrape,
    search_images,
    search_local_knowledge,
    search_news,
    search_youtube,
    summarize_content,
)
from main.src.store.DBManager import researches_db_manager
from main.src.store.vector import vector_store
from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import quickLog
from main.sse.event_bus import event_bus

CURR_DIR = Path(__file__).parent
MAX_PASSES = 4


# ---------------------------------------------------------------------------
# Temp .md helpers  —  one file per research_id  (the Phase 2 knowledge source)
# ---------------------------------------------------------------------------


def _temp_path(research_id: str) -> Path:
    folder = CURR_DIR / "temp_files"
    folder.mkdir(exist_ok=True)
    return folder / f"{research_id}.md"


def _init_md(research_id: str, title: str, objective: str) -> None:
    _temp_path(research_id).write_text(
        f"# {title}\n\n**Objective:** {objective}\n\n"
        f"---\n\n"
        f"<!-- AUTO-GENERATED KNOWLEDGE SOURCE — Phase 1 output —"
        f" feed directly into Phase 2 -->\n\n"
    )


def _append_md(research_id: str, content: str) -> None:
    with _temp_path(research_id).open("a") as f:
        f.write("\n\n" + content)


def _read_md(research_id: str) -> str:
    p = _temp_path(research_id)
    if not p.exists():
        raise FileNotFoundError(f"No .md for research_id: {research_id}")
    return p.read_text()


# ---------------------------------------------------------------------------
# ResearchOrchestrator
# ---------------------------------------------------------------------------


class _PlanStep(Protocol):
    description: str
    tools_required: list[str]


class ResearchOrchestrator:
    def __init__(
        self,
        redis_client: Redis,
        processed_input: dict,
        plan: ResearchPlan,
        enhanced_prompt: str,
        research_id: str,
        ollama_url: str,
        gemini_api_key: str,
    ):
        self.redis_client = redis_client
        self.processed_input = processed_input
        self.plan = plan
        self.enhanced_prompt = enhanced_prompt
        self.research_id = research_id
        self.ollama_url = ollama_url
        self.gemini_api_key = gemini_api_key

        self.redis_key = f"dr:research:{research_id}"
        self.thinker = Thinker()

        # Token / generation counters (carried across passes)
        self.total_tokens_used: int = 0
        self.total_generations: int = 0

        # Sources list — shown to the user
        self.sources: list[dict] = []

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

    def _mark_step_done(self, pass_num: int, step_idx: int, description: str) -> None:
        state = self._get_state()
        done = state.get("completed_steps", [])
        done.append({"pass": pass_num, "index": step_idx, "description": description})
        self._set_state(
            {
                "completed_steps": done,
                "current_step_index": step_idx,
                "current_step_description": description,
                "tokens_used": self.total_tokens_used,
                "generations": self.total_generations,
            }
        )

    def _is_step_done(self, pass_num: int, step_idx: int) -> bool:
        done = self._get_state().get("completed_steps", [])
        return any(s["pass"] == pass_num and s["index"] == step_idx for s in done)

    # -------------------------------------------------------------------------
    # DB (fire-and-forget)
    # -------------------------------------------------------------------------

    async def _create_db_record(self) -> None:
        await scheduler.schedule(
            researches_db_manager.insert,
            params={
                "table_name": "researches",
                "data": {
                    "research_id": self.research_id,
                    "title": self.plan.title,
                    "objective": self.plan.objective,
                    "status": "in_progress",
                    "current_step": None,
                    "total_steps": len(self.plan.steps),
                    "content": "",
                    "tokens_used": 0,
                    "generations": 0,
                },
            },
        )

    async def _update_db(self, **fields) -> None:
        await scheduler.schedule(
            researches_db_manager.update,
            params={
                "table_name": "researches",
                "where": {"research_id": self.research_id},
                "data": {
                    **fields,
                    "tokens_used": self.total_tokens_used,
                    "generations": self.total_generations,
                },
            },
        )

    async def _save_final_to_db(self, markdown: str) -> None:
        await scheduler.schedule(
            researches_db_manager.update,
            params={
                "table_name": "researches",
                "where": {"research_id": self.research_id},
                "data": {
                    "status": "complete",
                    "content": markdown,
                    "sources": json.dumps(self.sources),
                    "tokens_used": self.total_tokens_used,
                    "generations": self.total_generations,
                },
            },
        )

    # -------------------------------------------------------------------------
    # SSE broadcast helper
    # -------------------------------------------------------------------------

    async def _broadcast(self, event_type: str, **payload) -> None:
        await event_bus.broadcast(
            message={
                "type": event_type,
                "research": self.research_id,
                "tokens_used": self.total_tokens_used,
                "generations": self.total_generations,
                **payload,
            }
        )

    async def _collect_stream_text(self, stream) -> str:
        parts: list[str] = []
        async for event in stream:
            if isinstance(event, dict):
                if event.get("content"):
                    parts.append(str(event["content"]))
                elif event.get("summary"):
                    parts.append(str(event["summary"]))
                elif event.get("message"):
                    continue
                else:
                    parts.append(str(event))
            else:
                parts.append(str(event))
        return "\n\n".join(p for p in parts if p).strip()

    # -------------------------------------------------------------------------
    # Vector store helpers
    # -------------------------------------------------------------------------

    async def _store_text_in_vector(
        self,
        text: str,
        source_uri: str,
        step_description: str,
        tool_name: str,
        pass_num: int,
        extra_metadata: dict | None = None,
    ) -> list[str]:
        """Store text content in the 'research' vector collection."""
        metadata = {
            "research_id": self.research_id,
            "step": step_description,
            "tool": tool_name,
            "pass": str(pass_num),
            "title": self.plan.title,
            **(extra_metadata or {}),
        }
        try:
            ids = await vector_store.add_text(
                text=text,
                collection="research",
                source_uri=source_uri,
                metadata=metadata,
            )
            return ids
        except Exception as e:
            quickLog(
                level="error",
                message=f"Vector text store failed: {e}",
                module=["RESEARCH"],
            )
            return []

    async def _store_image_in_vector(
        self,
        image_path: str,
        step_description: str,
        source_uri: str,
        pass_num: int,
        extra_metadata: dict | None = None,
    ) -> str | None:
        """Store an image in the 'images' vector collection."""
        metadata = {
            "research_id": self.research_id,
            "step": step_description,
            "tool": "image_search",
            "pass": str(pass_num),
            "title": self.plan.title,
            **(extra_metadata or {}),
        }
        try:
            img_id = await vector_store.add_image(
                image_path=image_path,
                collection="images",
                metadata=metadata,
            )
            return img_id
        except Exception as e:
            quickLog(
                level="error",
                message=f"Vector image store failed: {e}",
                module=["RESEARCH"],
            )
            return None

    # -------------------------------------------------------------------------
    # Task Orchestrator 1 — 4 parallel search agents
    # -------------------------------------------------------------------------

    async def _agent_web_search(self, query: str, pass_num: int) -> dict:
        """Web search agent — scrapes and returns raw content."""
        try:
            stream = search_and_scrape(
                query=query,
                max_urls=5,
                research_id=self.research_id,
            )
            content = await self._collect_stream_text(stream)
            ids = await self._store_text_in_vector(
                text=content,
                source_uri=f"web_search:{query}",
                step_description=query,
                tool_name="web_search",
                pass_num=pass_num,
                extra_metadata={"query": query},
            )
            self.sources.append(
                {"tool": "web_search", "query": query, "vector_ids": ids}
            )
            self.total_generations += 1
            return {"agent": "web_search", "content": content, "ok": True}
        except Exception as e:
            quickLog(
                level="error", message=f"Web agent failed: {e}", module=["RESEARCH"]
            )
            return {"agent": "web_search", "content": "", "ok": False, "error": str(e)}

    async def _agent_local_kb(self, query: str, pass_num: int) -> dict:
        """Local knowledge base agent — queries the local KB tool + cross-searches the vector store."""
        try:
            # Primary: search_local_knowledge is the actual local KB tool
            tool_stream = search_local_knowledge(
                context=query,
                top_k=10,
                research_id=self.research_id,
            )
            tool_result = await self._collect_stream_text(tool_stream)
            # Secondary: also pull from what we've already stored in the vector store
            # for this research session (good for gap-filling passes)
            vector_results = await vector_store.search(
                query=query,
                collection="research",
                n_results=5,
                where={"research_id": self.research_id},
            )
            combined = (
                f"{tool_result}\n\n### From session vector store:\n{vector_results}"
            )
            self.sources.append({"tool": "local_kb", "query": query})
            self.total_generations += 1
            return {"agent": "local_kb", "content": combined, "ok": True}
        except Exception as e:
            quickLog(
                level="error",
                message=f"Local KB agent failed: {e}",
                module=["RESEARCH"],
            )
            return {"agent": "local_kb", "content": "", "ok": False, "error": str(e)}

    async def _agent_image_search(self, query: str, pass_num: int) -> dict:
        """Image search agent — searches images and stores them in vector."""
        try:
            result = await search_images(query=query, num_results=5)
            images = []
            if isinstance(result, dict):
                images = result.get("results", [])
            elif isinstance(result, list):
                images = result
            else:
                images = [result]
            stored_ids = []
            descriptions = []

            for img in images:
                if isinstance(img, str):
                    img = {"url": img}
                # img is expected to be a dict with at least a path or url
                img_path = (
                    img.get("path")
                    or img.get("local_path", "")
                    or img.get("img_src", "")
                )
                img_url = img.get("url") or img.get("img_src") or query
                description = img.get("description", str(img))
                descriptions.append(description)

                if img_path:
                    img_id = await self._store_image_in_vector(
                        image_path=img_path,
                        step_description=query,
                        source_uri=img_url,
                        pass_num=pass_num,
                        extra_metadata={"query": query, "url": img_url},
                    )
                    if img_id:
                        stored_ids.append(img_id)

                # Also store the description as text so it's searchable
                if description:
                    await self._store_text_in_vector(
                        text=f"Image description: {description}",
                        source_uri=img_url,
                        step_description=query,
                        tool_name="image_search",
                        pass_num=pass_num,
                        extra_metadata={"query": query, "image_url": img_url},
                    )

            content = "\n".join(descriptions)
            self.sources.append(
                {"tool": "image_search", "query": query, "vector_ids": stored_ids}
            )
            self.total_generations += 1
            return {"agent": "image_search", "content": content, "ok": True}
        except Exception as e:
            quickLog(
                level="error", message=f"Image agent failed: {e}", module=["RESEARCH"]
            )
            return {
                "agent": "image_search",
                "content": "",
                "ok": False,
                "error": str(e),
            }

    async def _agent_youtube(self, query: str, pass_num: int) -> dict:
        """YouTube agent — searches videos and summarises content."""
        try:
            result = await search_youtube(
                query=query,
                max_videos=3,
                summarize=True,
                ollama_url=self.ollama_url,
            )
            content = str(result)
            ids = await self._store_text_in_vector(
                text=content,
                source_uri=f"youtube:{query}",
                step_description=query,
                tool_name="youtube_search",
                pass_num=pass_num,
                extra_metadata={"query": query, "platform": "youtube"},
            )
            self.sources.append(
                {"tool": "youtube_search", "query": query, "vector_ids": ids}
            )
            self.total_generations += 1
            return {"agent": "youtube_search", "content": content, "ok": True}
        except Exception as e:
            quickLog(
                level="error", message=f"YouTube agent failed: {e}", module=["RESEARCH"]
            )
            return {
                "agent": "youtube_search",
                "content": "",
                "ok": False,
                "error": str(e),
            }

    async def _agent_document(self, query: str, pass_num: int) -> dict:
        """Document search agent — processes uploaded documents via process_document."""
        doc_urls = self.processed_input.get("document_urls", [])
        if not doc_urls:
            quickLog(
                level="info",
                message=f"No document_urls in processed_input for: {query}",
                module=["RESEARCH"],
            )
            return {
                "agent": "document_search",
                "content": "",
                "ok": False,
                "error": "no documents",
            }
        try:
            stream = process_document(
                urls=doc_urls,
                summarize=True,
                ollama_url=self.ollama_url,
            )
            content = await self._collect_stream_text(stream)
            ids = await self._store_text_in_vector(
                text=content,
                source_uri=f"document:{','.join(doc_urls[:2])}",
                step_description=query,
                tool_name="document_search",
                pass_num=pass_num,
                extra_metadata={"query": query, "doc_count": str(len(doc_urls))},
            )
            self.sources.append(
                {
                    "tool": "document_search",
                    "query": query,
                    "urls": doc_urls,
                    "vector_ids": ids,
                }
            )
            self.total_generations += 1
            return {"agent": "document_search", "content": content, "ok": True}
        except Exception as e:
            quickLog(
                level="error",
                message=f"Document agent failed: {e}",
                module=["RESEARCH"],
            )
            return {
                "agent": "document_search",
                "content": "",
                "ok": False,
                "error": str(e),
            }

    async def _agent_image_understanding(self, query: str, pass_num: int) -> dict:
        """Image understanding agent — processes uploaded images via process_document."""
        image_urls = self.processed_input.get("image_urls", [])
        if not image_urls:
            quickLog(
                level="info",
                message=f"No image_urls in processed_input for: {query}",
                module=["RESEARCH"],
            )
            return {
                "agent": "image_understanding",
                "content": "",
                "ok": False,
                "error": "no images",
            }
        try:
            stream = process_document(
                urls=image_urls,
                summarize=True,
                ollama_url=self.ollama_url,
            )
            content = await self._collect_stream_text(stream)
            # Store the understanding result as text
            ids = await self._store_text_in_vector(
                text=content,
                source_uri=f"image_understanding:{','.join(image_urls[:2])}",
                step_description=query,
                tool_name="image_understanding",
                pass_num=pass_num,
                extra_metadata={
                    "query": query,
                    "image_count": str(len(image_urls)),
                    "type": "image_understanding",
                },
            )
            # Also store raw images in the image vector collection
            for img_url in image_urls:
                await self._store_image_in_vector(
                    image_path=img_url,
                    step_description=query,
                    source_uri=img_url,
                    pass_num=pass_num,
                    extra_metadata={"query": query, "type": "uploaded_image"},
                )
            self.sources.append(
                {
                    "tool": "image_understanding",
                    "query": query,
                    "urls": image_urls,
                    "vector_ids": ids,
                }
            )
            self.total_generations += 1
            return {"agent": "image_understanding", "content": content, "ok": True}
        except Exception as e:
            quickLog(
                level="error",
                message=f"Image understanding agent failed: {e}",
                module=["RESEARCH"],
            )
            return {
                "agent": "image_understanding",
                "content": "",
                "ok": False,
                "error": str(e),
            }

    async def _agent_news(self, query: str, pass_num: int) -> dict:
        """News search agent — fetches recent news articles."""
        try:
            result = await search_news(
                query=query,
                num_results=5,
            )
            content = str(result)
            ids = await self._store_text_in_vector(
                text=content,
                source_uri=f"news:{query}",
                step_description=query,
                tool_name="news_search",
                pass_num=pass_num,
                extra_metadata={"query": query, "platform": "news"},
            )
            self.sources.append(
                {"tool": "news_search", "query": query, "vector_ids": ids}
            )
            self.total_generations += 1
            return {"agent": "news_search", "content": content, "ok": True}
        except Exception as e:
            quickLog(
                level="error", message=f"News agent failed: {e}", module=["RESEARCH"]
            )
            return {"agent": "news_search", "content": "", "ok": False, "error": str(e)}

    async def _run_parallel_agents(
        self,
        step_description: str,
        tools_required: list[str],
        pass_num: int,
    ) -> list[dict]:
        """
        Runs the relevant agents for this step in parallel.
        Only runs agents whose tool is listed in tools_required.
        """
        TOOL_TO_AGENT = {
            "web_search": self._agent_web_search,
            "semantic_search": self._agent_local_kb,
            "get_current_knowledge_on_the_topic": self._agent_local_kb,
            "image_search": self._agent_image_search,
            "image_understanding": self._agent_image_understanding,
            "document_search": self._agent_document,
            "youtube_search": self._agent_youtube,
            "news_search": self._agent_news,
            "summarizer": None,  # runs in pipeline step 5, not as a parallel agent
        }

        # Deduplicate — multiple tools may map to the same agent; skip None (pipeline-only tools)
        agents_to_run: dict[str, Any] = {}
        for tool in tools_required:
            agent_fn = TOOL_TO_AGENT.get(tool)
            if agent_fn is not None and agent_fn.__name__ not in agents_to_run:
                agents_to_run[agent_fn.__name__] = agent_fn

        if not agents_to_run:
            quickLog(
                level="info",
                message=f"No agents for tools: {tools_required}",
                module=["RESEARCH"],
            )
            return []

        tasks = [fn(step_description, pass_num) for fn in agents_to_run.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for r in results:
            if isinstance(r, Exception):
                quickLog(
                    level="error", message=f"Agent exception: {r}", module=["RESEARCH"]
                )
            elif isinstance(r, dict):
                output.append(r)
        return output

    # -------------------------------------------------------------------------
    # Processing Pipeline (right side of diagram)
    # -------------------------------------------------------------------------

    async def _pipeline_source_credibility(
        self, raw_results: list[dict], step_description: str
    ) -> list[dict]:
        """
        Step 1: Source credibility check.
        Uses the Thinker to score and filter each agent result.
        Low-quality results get flagged but not dropped (we keep everything for Phase 2).
        """
        self.total_generations += 1
        scored = []
        for result in raw_results:
            if not result.get("ok") or not result.get("content"):
                continue
            content_preview = result["content"][:500]
            topic = (
                f"Rate the credibility of this source for the query: {step_description}"
            )
            context = (
                f"Source type: {result['agent']}\n"
                f"Content preview:\n{content_preview}\n\n"
                "Reply in this format:\n"
                "SCORE: 1-10\n"
                "REASON: <one sentence>\n"
                "KEEP: yes/no"
            )
            try:
                response = await self.thinker.think(
                    topic=topic, context=context, thinking_intensity=0.3
                )
                response_text = str(response)
                score = 5
                keep = True
                for line in response_text.splitlines():
                    lne = line.strip()
                    if lne.lower().startswith("score:"):
                        try:
                            score = int(lne.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                    elif lne.lower().startswith("keep:"):
                        keep = lne.split(":", 1)[1].strip().lower() == "yes"
                result["credibility_score"] = score
                result["keep"] = keep
            except Exception:
                result["credibility_score"] = 5
                result["keep"] = True

            scored.append(result)

        await self._broadcast(
            "pipeline_credibility_done",
            step=step_description,
            results_count=len(scored),
        )
        return scored

    async def _pipeline_session_kb_builder(
        self,
        credible_results: list[dict],
        step_description: str,
        pass_num: int,
        step_idx: int,
    ) -> str:
        """
        Step 2: Session knowledge builder.
        Merges all agent results into a well-structured .md section and appends it.
        This is the main write to the Phase 2 knowledge source.
        """
        parts = [
            f"## [Pass {pass_num} | Step {step_idx + 1}] {step_description}\n",
            f"*Credible sources: {sum(1 for r in credible_results if r.get('keep'))} / {len(credible_results)}*\n",
        ]

        for result in credible_results:
            if not result.get("content"):
                continue
            agent = result["agent"]
            score = result.get("credibility_score", "?")
            kept = "✓" if result.get("keep") else "⚠"
            parts.append(f"\n### {kept} [{agent}] (credibility: {score}/10)\n")
            parts.append(result["content"])

        section = "\n".join(parts)
        _append_md(self.research_id, section)

        await self._broadcast(
            "pipeline_kb_updated", step=step_description, pass_num=pass_num
        )
        return section

    async def _pipeline_entity_extraction(
        self, combined_content: str, step_description: str
    ) -> dict:
        """
        Step 3: Entity and relationship extraction.
        Extracts key entities and their relationships — stored back into vector and .md.
        """
        self.total_generations += 1
        topic = f"Extract entities and relationships from this content about: {step_description}"
        context = (
            f"Content:\n{combined_content[:3000]}\n\n"
            "Reply in this format:\n"
            "ENTITIES: <comma-separated list of key entities>\n"
            "RELATIONSHIPS: <one per line: EntityA -> relationship -> EntityB>\n"
            "KEY_FACTS: <bullet points of the most important facts>"
        )
        try:
            response = await self.thinker.think(
                topic=topic, context=context, thinking_intensity=0.5
            )
            response_text = str(response)

            extraction_md = (
                f"\n#### Entities & Relationships\n```\n{response_text}\n```\n"
            )
            _append_md(self.research_id, extraction_md)

            # Store entities in vector for future semantic lookups
            await self._store_text_in_vector(
                text=response_text,
                source_uri=f"entity_extraction:{self.research_id}:{step_description[:40]}",
                step_description=step_description,
                tool_name="entity_extraction",
                pass_num=0,
                extra_metadata={"type": "entity_extraction"},
            )

            await self._broadcast("pipeline_entities_extracted", step=step_description)
            return {"entities_text": response_text, "ok": True}
        except Exception as e:
            quickLog(
                level="error",
                message=f"Entity extraction failed: {e}",
                module=["RESEARCH"],
            )
            return {"entities_text": "", "ok": False}

    async def _pipeline_contradiction_detector(
        self, combined_content: str, step_description: str
    ) -> str:
        """
        Step 4: Contradiction and consensus detector.
        Flags conflicting info and notes what sources agree on.
        Adds a note section to the .md so Phase 2 knows what to treat carefully.
        """
        self.total_generations += 1
        topic = f"Detect contradictions and consensus in these sources about: {step_description}"
        context = (
            f"Content from multiple sources:\n{combined_content[:3000]}\n\n"
            "Reply in this format:\n"
            "CONSENSUS: <what all/most sources agree on>\n"
            "CONTRADICTIONS: <conflicting claims, one per line>\n"
            "CONFIDENCE: high/medium/low"
        )
        try:
            response = await self.thinker.think(
                topic=topic, context=context, thinking_intensity=0.4
            )
            response_text = str(response)

            note_md = f"\n#### Contradictions & Consensus\n```\n{response_text}\n```\n"
            _append_md(self.research_id, note_md)

            await self._broadcast(
                "pipeline_contradictions_checked", step=step_description
            )
            return response_text
        except Exception as e:
            quickLog(
                level="error",
                message=f"Contradiction check failed: {e}",
                module=["RESEARCH"],
            )
            return ""

    async def _pipeline_summarize(
        self,
        combined_content: str,
        step_description: str,
        pass_num: int,
        step_idx: int,
    ) -> str:
        """
        Step 5: Summarize all.
        Produces a clean, dense summary of everything gathered for this step.
        This summary is what Phase 2 will primarily read.
        """
        self.total_generations += 1
        try:
            stream = summarize_content(
                query=step_description,
                content=combined_content,
                api_key=self.gemini_api_key,
                research_id=self.research_id,
            )
            summary_text = await self._collect_stream_text(stream)
            if not summary_text:
                summary_text = combined_content[:500]

            summary_md = (
                f"\n---\n"
                f"### SUMMARY — Step {step_idx + 1} (Pass {pass_num})\n"
                f"> {step_description}\n\n"
                f"{summary_text}\n"
                f"---\n"
            )
            _append_md(self.research_id, summary_md)

            # Store the final summary in vector — this is the highest-quality signal
            await self._store_text_in_vector(
                text=summary_text,
                source_uri=f"summary:{self.research_id}:pass{pass_num}:step{step_idx}",
                step_description=step_description,
                tool_name="summarizer",
                pass_num=pass_num,
                extra_metadata={
                    "type": "summary",
                    "step_index": str(step_idx),
                    "pass": str(pass_num),
                },
            )

            await self._broadcast(
                "pipeline_summarized", step=step_description, pass_num=pass_num
            )
            return summary_text
        except Exception as e:
            quickLog(
                level="error", message=f"Summarize failed: {e}", module=["RESEARCH"]
            )
            return combined_content[:500]

    async def _run_pipeline(
        self,
        raw_agent_results: list[dict],
        step_description: str,
        tools_required: list[str],
        pass_num: int,
        step_idx: int,
    ) -> str:
        """
        Runs the 5-stage processing pipeline on the raw agent results.
        Returns the final summary for this step.
        """
        # 1. Source credibility check
        await self._broadcast(
            "pipeline_stage", stage="source_credibility", step=step_description
        )
        credible_results = await self._pipeline_source_credibility(
            raw_agent_results, step_description
        )

        # 2. Session knowledge builder — writes to .md
        await self._broadcast(
            "pipeline_stage", stage="session_kb_builder", step=step_description
        )
        combined_section = await self._pipeline_session_kb_builder(
            credible_results, step_description, pass_num, step_idx
        )

        # Combine all text content for the downstream pipeline stages
        combined_text = "\n\n".join(
            r["content"] for r in credible_results if r.get("content") and r.get("keep")
        )

        # 3. Entity & relationship extraction
        await self._broadcast(
            "pipeline_stage", stage="entity_extraction", step=step_description
        )
        await self._pipeline_entity_extraction(combined_text, step_description)

        # 4. Contradiction & consensus detector
        await self._broadcast(
            "pipeline_stage", stage="contradiction_detector", step=step_description
        )
        await self._pipeline_contradiction_detector(combined_text, step_description)

        # 5. Summarize all
        await self._broadcast(
            "pipeline_stage", stage="summarize", step=step_description
        )
        summary = await self._pipeline_summarize(
            combined_text, step_description, pass_num, step_idx
        )

        return summary

    # -------------------------------------------------------------------------
    # Execute one full plan step  (agents → pipeline)
    # -------------------------------------------------------------------------

    async def _execute_step(
        self, pass_num: int, step_idx: int, step: _PlanStep
    ) -> None:
        step_description = step.description
        tools_required = step.tools_required

        self._set_state(
            {
                "phase": "knowledge_gathering",
                "pass_number": pass_num,
                "current_step_index": step_idx,
                "current_step_description": step_description,
                "status": "running",
            }
        )

        await self._broadcast(
            "step_start",
            pass_num=pass_num,
            step_index=step_idx,
            step=step_description,
            tools=tools_required,
        )
        await self._update_db(status="in_progress", current_step=step_description)

        # --- Task Orchestrator 1: run agents in parallel ---
        await self._broadcast(
            "agents_start", step=step_description, tools=tools_required
        )
        raw_results = await self._run_parallel_agents(
            step_description, tools_required, pass_num
        )
        await self._broadcast(
            "agents_done", step=step_description, results_count=len(raw_results)
        )

        # --- Processing pipeline ---
        await self._run_pipeline(
            raw_results, step_description, tools_required, pass_num, step_idx
        )

        self._mark_step_done(pass_num, step_idx, step_description)

        await self._broadcast(
            "step_complete",
            pass_num=pass_num,
            step_index=step_idx,
            step=step_description,
        )
        quickLog(
            level="success",
            message=f"[Pass {pass_num}] Step {step_idx + 1} done: {step_description} | tokens={self.total_tokens_used} gens={self.total_generations}",
            module=["RESEARCH"],
        )

    # -------------------------------------------------------------------------
    # Thinker diamond: "Need more context?"
    # -------------------------------------------------------------------------

    async def _need_more_context(self, pass_num: int) -> tuple[bool, str]:
        """
        Asks the Thinker to review the full .md and decide if more context is needed.
        Returns (need_more: bool, gaps: str)
        """
        self.total_generations += 1
        current_md = _read_md(self.research_id)

        topic = f"Does this knowledge base fully answer: {self.plan.objective}"
        context = (
            f"Research title: {self.plan.title}\n"
            f"Objective: {self.plan.objective}\n\n"
            f"Knowledge base (pass {pass_num}):\n\n"
            f"{current_md}\n\n"
            "Reply in exactly this format:\n"
            "NEED_MORE_CONTEXT: yes/no\n"
            "REASON: <one sentence>\n"
            "GAPS: <if yes: list missing topics one per line starting with '-'. if no: none>"
        )

        await self._broadcast("thinker_evaluating", pass_num=pass_num)

        try:
            response = await self.thinker.think(
                topic=topic, context=context, thinking_intensity=0.6
            )
            response_text = str(response)

            need_more = False
            gaps = ""
            for line in response_text.splitlines():
                lne = line.strip()
                if lne.lower().startswith("need_more_context:"):
                    need_more = lne.split(":", 1)[1].strip().lower() == "yes"
                elif lne.lower().startswith("gaps:"):
                    gaps = lne.split(":", 1)[1].strip()
        except Exception as e:
            quickLog(
                level="error", message=f"Thinker check failed: {e}", module=["RESEARCH"]
            )
            need_more = False
            gaps = ""

        quickLog(
            level="info",
            message=f"Thinker: need_more={need_more}, gaps='{gaps[:80]}'",
            module=["RESEARCH"],
        )

        self._set_state(
            {
                "last_thinker_check": {
                    "pass": pass_num,
                    "need_more": need_more,
                    "gaps": gaps,
                }
            }
        )

        await self._broadcast(
            "thinker_result", pass_num=pass_num, need_more=need_more, gaps=gaps
        )
        return need_more, gaps

    # -------------------------------------------------------------------------
    # Build gap-filling steps from Thinker output
    # -------------------------------------------------------------------------

    def _gap_steps(self, gaps: str) -> list:
        class GapStep:
            def __init__(self, desc, tools):
                self.description = desc
                self.tools_required = tools

        lines = [
            lne.strip("- •").strip()
            for lne in gaps.splitlines()
            if lne.strip() and lne.strip().lower() not in ("none", "")
        ]
        if not lines and gaps.strip() and gaps.strip().lower() != "none":
            lines = [gaps.strip()]

        return [
            GapStep(
                desc=gap,
                tools=["web_search", "semantic_search"],
            )
            for gap in lines
        ]

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    async def execute(self) -> None:
        quickLog(
            level="info",
            message=f"Phase 1 ResearchOrchestrator starting — research_id={self.research_id}",
            module=["RESEARCH"],
        )

        # Fresh start vs resume
        existing_state = self._get_state()
        is_fresh = not existing_state

        if is_fresh:
            self._set_state(
                {
                    "research_id": self.research_id,
                    "title": self.plan.title,
                    "phase": "knowledge_gathering",
                    "status": "starting",
                    "completed_steps": [],
                    "total_steps": len(self.plan.steps),
                    "pass_number": 1,
                    "tokens_used": 0,
                    "generations": 0,
                }
            )
            await self._create_db_record()
            _init_md(self.research_id, self.plan.title, self.plan.objective)
        else:
            # Restore counters from Redis on resume
            self.total_tokens_used = existing_state.get("tokens_used", 0)
            self.total_generations = existing_state.get("generations", 0)
            quickLog(
                level="info",
                message=f"Resuming research {self.research_id}",
                module=["RESEARCH"],
            )

        await self._broadcast(
            "research_start",
            title=self.plan.title,
            total_steps=len(self.plan.steps),
            resumed=not is_fresh,
        )

        # ---- Knowledge gathering loop ----
        pass_num = self._get_state().get("pass_number", 1)
        current_steps = list(self.plan.steps)

        while pass_num <= MAX_PASSES:
            quickLog(
                level="info",
                message=f"Pass {pass_num} — {len(current_steps)} steps",
                module=["RESEARCH"],
            )
            self._set_state({"pass_number": pass_num})
            await self._broadcast(
                "pass_start", pass_num=pass_num, steps_count=len(current_steps)
            )

            for step_idx, step in enumerate(current_steps):
                if self._is_step_done(pass_num, step_idx):
                    await self._broadcast(
                        "step_skipped", pass_num=pass_num, step_index=step_idx
                    )
                    continue

                try:
                    await self._execute_step(pass_num, step_idx, step)
                except Exception as e:
                    quickLog(
                        level="error",
                        message=f"[Pass {pass_num}] Step {step_idx + 1} failed: {e}",
                        module=["RESEARCH"],
                        urgency="critical",
                    )
                    self._set_state(
                        {
                            "status": "step_error",
                            "error": str(e),
                            "failed_step": step_idx,
                        }
                    )
                    await self._broadcast(
                        "step_error",
                        pass_num=pass_num,
                        step_index=step_idx,
                        error=str(e),
                    )
                    continue  # keep going — don't kill the whole pass

            await self._broadcast("pass_complete", pass_num=pass_num)

            # ---- Thinker diamond: Need more context? ----
            need_more, gaps = await self._need_more_context(pass_num)

            if not need_more:
                quickLog(
                    level="success",
                    message=f"Thinker satisfied after pass {pass_num}.",
                    module=["RESEARCH"],
                )
                break

            if pass_num >= MAX_PASSES:
                quickLog(
                    level="info",
                    message=f"MAX_PASSES ({MAX_PASSES}) reached. Finalizing.",
                    module=["RESEARCH"],
                )
                await self._broadcast("max_passes_reached", pass_num=pass_num)
                break

            gap_steps = self._gap_steps(gaps)
            if not gap_steps:
                quickLog(
                    level="info",
                    message="No actionable gaps. Finalizing.",
                    module=["RESEARCH"],
                )
                break

            current_steps = gap_steps
            pass_num += 1

        # ---- Finalize ----
        final_md = _read_md(self.research_id)

        # Write a final index section to the .md so Phase 2 knows what's in it
        index_section = (
            f"\n\n---\n"
            f"## Knowledge Base Index\n"
            f"- **Total passes:** {pass_num}\n"
            f"- **Total sources:** {len(self.sources)}\n"
            f"- **Total generations:** {self.total_generations}\n"
            f"- **Tokens used:** {self.total_tokens_used}\n"
            f"- **Steps completed:** {len(self._get_state().get('completed_steps', []))}\n"
            f"\n### Sources\n"
        )
        for i, src in enumerate(self.sources):
            index_section += f"{i + 1}. [{src['tool']}] {src.get('query', '')}\n"
        index_section += "\n---\n<!-- END PHASE 1 — ready for Phase 2 -->\n"
        _append_md(self.research_id, index_section)

        final_md = _read_md(self.research_id)

        self._set_state(
            {
                "status": "complete",
                "phase": "phase1_done",
                "total_passes": pass_num,
                "sources_count": len(self.sources),
                "tokens_used": self.total_tokens_used,
                "generations": self.total_generations,
            }
        )

        await self._save_final_to_db(final_md)

        await self._broadcast(
            "research_phase1_complete",
            title=self.plan.title,
            total_passes=pass_num,
            sources_count=len(self.sources),
            total_generations=self.total_generations,
            tokens_used=self.total_tokens_used,
            md_path=str(_temp_path(self.research_id)),
        )

        quickLog(
            level="success",
            message=(
                f"Phase 1 complete — {self.research_id} | "
                f"passes={pass_num} sources={len(self.sources)} "
                f"gens={self.total_generations} tokens={self.total_tokens_used}"
            ),
            module=["RESEARCH"],
        )
