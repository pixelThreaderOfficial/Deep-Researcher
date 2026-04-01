import asyncio
import uuid
from typing import Any
from urllib.parse import urlencode

from main.secrets.DRSecrets import Secrets
from main.src.store.DBManager import (
    buckets_db_manager,
    chats_db_manager,
    history_db_manager,
    main_db_manager,
    researches_db_manager,
)
from main.src.store.vector import vector_store
from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import quickLog
from main.src.utils.llms.ollama.DROllamaWrapper import asyncGenerateContent
from main.src.utils.llms.ollama.DROllamaWrapper import getAsyncClient as ollama_client
from main.src.utils.utilities import (
    checkStringIsEmpty,
    convertExplicitToString,
    utcnow_iso,
)
from main.sse.event_bus import event_bus

OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_SEARCH_SUMMARIZER_SYSTEM_PROMPT = """
You are an advanced `search summarization` agent.
Your task is to analyze structured search results from multiple sources and generate a concise, highly useful summary.

STRICT RULES:

1. OUTPUT FORMAT (MANDATORY)
You must ALWAYS return valid JSON in the exact schema below:
{
    "ai_summary": "",
    "sources": [],
    "highlight_answer": ""
}

2. LENGTH CONSTRAINT
* Keep the total response VERY SHORT.
* ai_summary must be under 80 words.
* highlight_answer must be a single precise sentence (preferably under 20 words).

3. GOAL
* Extract the most useful, relevant, and factual information.
* Do NOT explain everything.
* Do NOT repeat the same idea.
* Focus on clarity and usefulness.

4. HIGHLIGHT ANSWER (CRITICAL)
* This is the most important part.
* It must directly answer the user query.
* It should be specific, factual, and extracted or derived from the results.
* Prefer numerical values, dates, or exact facts when available.

5. AI SUMMARY
* Provide a short markdown-formatted summary.
* Include only key insights (no fluff).
* Use bullet points ONLY if necessary.
* Avoid long explanations.

6. SOURCES
* Extract and return relevant source identifiers exactly as provided in input.
* Include only sources that contributed to the answer.
* Do NOT hallucinate sources.

7. INPUT HANDLING
* You will receive structured search results containing:
  * title
  * snippet/content
  * source/url
* Parse them intelligently.
* Ignore irrelevant or duplicate information.

8. NO HALLUCINATION
* Do NOT invent facts.
* If data is unclear, base output only on available information.

9. STYLE
* Neutral, precise, factual.
* No conversational tone.
* No unnecessary words.

10. PRIORITY ORDER
1) highlight_answer (most important)
2) ai_summary
3) sources

Remember:
* Be fast.
* Be precise.
* Be minimal.
* Be useful.

"""


def urlize(query: str) -> str:
    return f"https://localhost:8000/search?{urlencode({'query': query})}"


class Search:
    def __init__(self, query: str, page: int, offset: int, search_user: str) -> None:
        self.query = query
        self.page = page
        self.offset = offset
        self.search_user = search_user
        self.normalized_query: str | None = None
        self.current_search_id: str | None = None
        self.results: list[dict[Any, Any]] | None = None
        self.total_results: int = 0

    @classmethod
    async def create(
        cls, query: str, page: int, offset: int, search_user: str
    ) -> "Search":
        """
        Async factory to create and initialize the Search instance.
        """
        self = cls(query, page, offset, search_user)
        # await the async normalization and assign the returned string
        self.normalized_query = await self._normalize_query()
        self.current_search_id = await self._create_search_record()
        return self

    async def _normalize_query(self) -> str:
        """
        Normalize query and return normalized string.
        Raises ValueError if query is empty (or handle as you prefer).
        """
        if checkStringIsEmpty(self.query):
            await event_bus.broadcast(
                message={
                    "type": "search_error",
                    "message": "Query is empty",
                    "user_query": str(self.query),
                    "user_name": self.search_user,
                }
            )
            raise ValueError("Query is empty")
        return convertExplicitToString(self.query.strip())

    async def _create_search_record(self) -> str | None:
        if self.normalized_query is None:
            return
        search_id = uuid.uuid4()
        await scheduler.schedule(
            history_db_manager.insert,
            params={
                "table_name": "search_history",
                "data": {
                    "id": search_id,
                    "query": self.normalized_query,
                    "user_id": self.search_user,
                    "results": "",
                    "ai_summary": "",
                    "ai_citations": "",
                    "created_at": utcnow_iso(),
                    "updated_at": utcnow_iso(),
                },
            },
        )
        await scheduler.schedule(
            history_db_manager.insert,
            params={
                "table_name": "user_usage_history",
                "data": {
                    "id": search_id,
                    "workspace_id": "",
                    "user_id": self.search_user,
                    "activity": "search",
                    "type": "search",
                    "actions": "delete",
                    "created_at": utcnow_iso(),
                    "last_seen": utcnow_iso(),
                    "url": urlize(self.normalized_query),
                },
            },
        )
        await event_bus.broadcast(
            message={
                "type": "search_record",
                "query": self.normalized_query,
                "user_id": self.search_user,
                "timestamp": utcnow_iso(),
            }
        )
        return str(search_id)

    async def _search_workspaces(self) -> dict[Any, Any]:
        results = {}

        raw_res = main_db_manager.fetch_all(
            table_name="workspaces", where={"name": self.normalized_query}
        )
        self.total_results += len(raw_res["data"])
        for item in raw_res["data"]:
            results[item["name"]] = item["name"]

        self.total_results = len(results)

        return results

    async def _search_reserches(self) -> dict[Any, Any]:
        return {"": ""}

    async def _search_chats(self) -> dict[Any, Any]:
        return {"": ""}

    async def _search_assets(self) -> dict[Any, Any]:
        return {"": ""}

    async def find(self, ai_summary: bool = False) -> dict[Any, Any]:
        results = await asyncio.gather(
            self._search_workspaces(),
            self._search_reserches(),
            self._search_chats(),
            self._search_assets(),
        )
        self.results = list(results)
        if self.results is not None:
            await event_bus.broadcast(
                message={
                    "type": "search_record",
                    "results": results,
                }
            )
        else:
            await event_bus.broadcast(
                message={
                    "type": "search_record",
                    "results": None,
                }
            )

        await scheduler.schedule(
            history_db_manager.update,
            params={
                "table_name": "searches",
                "data": {
                    "total_results": self.total_results,
                    "results": self.results,
                    "updated_at": utcnow_iso(),
                },
                "where": {"id": self.current_search_id},
            },
        )

        if ai_summary:
            await self.get_ai_summary()

        return {
            "workspaces": results[0],
            "researches": results[1],
            "chats": results[2],
            "assets": results[3],
        }

    async def get_ai_summary(self) -> None:
        if self.current_search_id is None or self.normalized_query is None:
            await event_bus.broadcast(
                message={
                    "type": "search_record",
                    "ai_summary": None,
                }
            )
            return
        response = await asyncGenerateContent(
            model=OLLAMA_MODEL,
            prompt=f"Provide a concise summary of the following search query: {self.normalized_query}",
            aclient=ollama_client(),
            system=OLLAMA_SEARCH_SUMMARIZER_SYSTEM_PROMPT,
            image=None,
            options={"think": False},
            json_schema={"ai_summary": "", "sources": [], "highlight_answer": ""},
        )
        await event_bus.broadcast(
            message={
                "type": "search_record",
                "ai_summary": response,
            },
        )
        await scheduler.schedule(
            history_db_manager.update,
            params={
                "table_name": "searches",
                "data": {
                    "ai_summary": response,
                    "ai_citations": response,
                    "updated_at": utcnow_iso(),
                },
                "where": {"id": self.current_search_id},
            },
        )
