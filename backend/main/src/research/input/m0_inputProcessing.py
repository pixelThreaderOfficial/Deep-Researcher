import uuid
import json
import asyncio
from redis import Redis
from main.secrets.DRSecrets import Secrets
import main.src.utils.llms.ollama.DROllamaWrapper as ollama
from main.src.utils.core.task_schedular import scheduler
from main.src.utils.DRLogger import quickLog
from main.src.store.DBManager import (
    main_db_manager,
    researches_db_manager,
    buckets_db_manager,
)
from main.src.research.tools import validate_query
from main.src.research.input.generate_confirmation_questions import (
    generateQuestionsForResearch,
    generateEnhancedPrompt,
)
from main.src.research.input.createPlan import ResearchPlan, generatePlan
from main.sse.event_bus import event_bus
from main.sse.wss import wss

oAsCli = ollama.getAsyncClient()
OLLAMA_LLM_OPTIONS = {"num_ctx": 4096}
OLLAMA_MODEL = "qwen3.5:9b"
secret_keys = Secrets()

# ─────────────────────────────────────────────────────────────────────────────
# Redis key helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_redis_research_key(research_id: str) -> str:
    """Returns the canonical Redis key for a given research ID."""
    return f"dr:research:{research_id}"


def _serialize_redis_research_state(state: dict) -> str:
    """Serializes the research state dict to a JSON string for Redis storage."""
    return json.dumps(state, default=str)


def _sync_research_state_to_redis(
    redis_client: Redis, research_id: str, state: dict
) -> None:
    """
    Synchronously writes the full research pipeline state to Redis.
    This is intended to be offloaded via scheduler.schedule so it runs
    in the background without blocking the async pipeline.

    The key is: dr:research:{research_id}
    TTL is set to 86400 seconds (24 hours) as a safety expiry.
    """
    redis_key = _build_redis_research_key(research_id)
    serialized_state = _serialize_redis_research_state(state)
    redis_client.set(redis_key, serialized_state, ex=86400)


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────


class InputProcessing:
    """
    ## Description

    Class to handle the initial processing of research inputs, including
    record creation, query validation, metadata generation, user confirmation
    questions, and execution plan creation with user approval.

    All critical state is mirrored to Redis after every pipeline step so that
    if the application crashes and restarts, the pipeline can resume from the
    last known good state using the WebSocket session that is still alive on
    the server.

    ## Redis State Schema

    Key: `dr:research:{research_id}`

    ```json
    {
        "research_id": "string",
        "workspace_id": "string",
        "pipeline_stage": "string",
        "is_query_good": "no | yes | processing",
        "title": "string",
        "desc": "string",
        "enhanced_prompt": "string | null",
        "bucket_id": "string | null",
        "sources_context": "string | null",
        "plan": "string | null",
        "plan_approved": "boolean | null",
        "error": "string | null"
    }
    ```
    """

    def __init__(
        self,
        r: Redis,
        title: str,
        desc: str,
        prompt: str,
        sources: list[str],
        workspaceId: str,
        system_prompt: str,
        custom_prompt: str,
        research_template: str,
        ai_personality: str,
        username: str,
        chat_access: bool = True,
        background_processing: bool = True,
    ):
        self.redis_client = r
        self.is_query_good = "no"  # "no" | "yes" | "processing"
        self.title = title
        self.desc = desc
        self.prompt = prompt
        self.sources = sources  # list of source ids
        self.workspaceId = workspaceId
        self.system_prompt = system_prompt
        self.custom_prompt = custom_prompt
        self.research_template = research_template
        self.ai_personality = ai_personality
        self.username = username
        self.chat_access = chat_access
        self.background_processing = background_processing

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Redis helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _push_pipeline_state_to_redis(
        self,
        research_id: str,
        pipeline_stage: str,
        extra_fields: dict | None = None,
    ) -> None:
        """
        Builds the current pipeline state snapshot and offloads a Redis write
        to the background scheduler.

        ## Parameters

        - `research_id` (`str`): The research record ID.
        - `pipeline_stage` (`str`): Human-readable label of the current stage,
          e.g. `"query_validation"`, `"confirmation_questions"`, `"plan_approval"`.
        - `extra_fields` (`dict | None`): Any additional fields to merge into
          the base state snapshot before writing to Redis.
        """
        base_state = {
            "research_id": research_id,
            "workspace_id": self.workspaceId,
            "pipeline_stage": pipeline_stage,
            "is_query_good": self.is_query_good,
            "title": self.title,
            "desc": self.desc,
            "prompt": self.prompt,
            "custom_prompt": self.custom_prompt,
            "sources": self.sources,
            "error": None,
        }

        if extra_fields:
            base_state.update(extra_fields)

        asyncio.run(
            scheduler.schedule(
                _sync_research_state_to_redis,
                params={
                    "redis_client": self.redis_client,
                    "research_id": research_id,
                    "state": base_state,
                },
            )
        )

    def _push_error_state_to_redis(
        self,
        research_id: str,
        pipeline_stage: str,
        error_message: str,
    ) -> None:
        """
        Writes a failed pipeline state snapshot to Redis so the crash point
        is visible for debugging and resumption logic.

        ## Parameters

        - `research_id` (`str`): The research record ID.
        - `pipeline_stage` (`str`): The stage at which the error occurred.
        - `error_message` (`str`): The string representation of the exception.
        """
        self._push_pipeline_state_to_redis(
            research_id=research_id,
            pipeline_stage=pipeline_stage,
            extra_fields={
                "error": error_message,
                "pipeline_stage": f"{pipeline_stage}:FAILED",
            },
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline steps
    # ─────────────────────────────────────────────────────────────────────────

    async def craeteResearchRecord(self) -> dict:
        """
        ## Description

        Creates a base research record in the database for tracking.

        ## Returns

        `dict`

        The full inserted record including the `id` field:

        ```json
        {
            "id": "uuid",
            "title": "string",
            "desc": "string",
            "...": "other record fields"
        }
        ```

        ## Side Effects

        - Inserts record into `researches` table.
        - Broadcasts "I'm on it!" event with the real research ID.
        - Seeds the initial Redis state for this research.
        """
        try:
            research_id = str(uuid.uuid4())
            research_record = {
                "id": research_id,
                "title": self.title or "Untitled Research",
                "desc": self.desc or "No description provided.",
                "prompt": self.prompt,
                "sources": str(self.sources),
                "workspace_id": self.workspaceId,
                "artifacts": None,
                "chat_access": self.chat_access,
                "background_processing": self.background_processing,
                "research_template_id": (
                    self.research_template
                    if isinstance(self.research_template, str)
                    else ""
                ),
                "custom_instructions": self.custom_prompt,
                "prompt_order": None,
            }

            insert_result = researches_db_manager.insert("researches", research_record)
            if not insert_result.get("success"):
                raise RuntimeError(
                    insert_result.get("message") or "Failed to insert research record"
                )

            # Normalize the object returned to the pipeline so downstream logic
            # can always access a stable research id.
            research_instance = dict(research_record)

            # Seed the initial Redis state so the key exists from the very start
            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="record_created",
            )

            await event_bus.broadcast(
                message={"msg": "I'm on it!", "research": research_id}
            )

            return research_instance

        except Exception as exc:
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Error creating research record: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )
            raise

    async def process_input(self, research_id: str) -> None:
        """
        ## Description

        Validates the user prompt and custom instructions using the Agent Server API.
        Updates the internal state `is_query_good` which gates subsequent pipeline steps.

        ## Parameters

        - `research_id` (`str`): The unique identifier for the current research instance.

        ## Returns

        `None`

        ## Side Effects

        - Updates `self.is_query_good` ("processing" → "yes" | "no").
        - Pushes validation stage state to Redis.
        - Broadcasts terminal messages via `event_bus`.
        - Logs errors via `quickLog` through scheduler.
        """
        self.is_query_good = "processing"

        self._push_pipeline_state_to_redis(
            research_id=research_id,
            pipeline_stage="query_validation:in_progress",
        )

        final_validation_result = None

        try:
            async for validation_event in validate_query(
                query=self.prompt,
                api_key=secret_keys.get_gemini_api_key() or "",
                research_id=research_id,
            ):
                event_type = validation_event.get("type")

                if event_type == "result":
                    final_validation_result = validation_event
                elif event_type == "error":
                    self.is_query_good = "no"
                    raise RuntimeError(
                        validation_event.get(
                            "message", "Validation failed with unknown error"
                        )
                    )
                elif event_type == "done":
                    break

        except Exception as exc:
            self.is_query_good = "no"

            self._push_error_state_to_redis(
                research_id=research_id,
                pipeline_stage="query_validation",
                error_message=str(exc),
            )

            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Error during query validation for research {research_id}: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )

            await event_bus.broadcast(
                message={
                    "msg": "Validation failed due to a technical error.",
                    "research": research_id,
                }
            )
            raise

        if final_validation_result and final_validation_result.get("success"):
            self.is_query_good = "yes"

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="query_validation:passed",
            )

            await event_bus.broadcast(
                message={
                    "msg": "Validation successful! Starting research...",
                    "research": research_id,
                }
            )
        else:
            self.is_query_good = "no"

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="query_validation:failed",
            )

            await event_bus.broadcast(
                message={
                    "msg": "Validation failed. Please check your prompt or custom instructions and try again.",
                    "research": research_id,
                }
            )

    async def getBucket(self, workspaceId: str, research_id: str) -> str | None:
        """
        ## Description

        Retrieves the connected bucket ID for a specific workspace.

        ## Parameters

        - `workspaceId` (`str`): The ID of the workspace to query.
        - `research_id` (`str`): Current research context for broadcasting and Redis.

        ## Returns

        `str | None`

        - Returns `bucket_id` string if found, `None` if workspace has no connected bucket.

        ## Side Effects

        - Broadcasts "Getting bucket ready!" event.
        - Pushes bucket retrieval stage state to Redis.
        """
        try:
            workspace_result = main_db_manager.fetch_one(
                "workspaces", where={"id": workspaceId}
            )

            await event_bus.broadcast(
                message={"msg": "Getting bucket ready!", "research": research_id}
            )

            if not workspace_result or len(workspace_result.get("data", {})) == 0:
                self._push_pipeline_state_to_redis(
                    research_id=research_id,
                    pipeline_stage="bucket_retrieval:not_found",
                    extra_fields={"bucket_id": None},
                )
                return None

            bucket_id = workspace_result["data"]["connected_bucket_id"]

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="bucket_retrieval:complete",
                extra_fields={"bucket_id": bucket_id},
            )

            return bucket_id

        except Exception as exc:
            self._push_error_state_to_redis(
                research_id=research_id,
                pipeline_stage="bucket_retrieval",
                error_message=str(exc),
            )
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Error fetching bucket for workspace {workspaceId} on research {research_id}: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )
            raise

    async def getSourcesContent(self, sources: list[str], research_id: str) -> dict:
        """
        ## Description

        Fetches and summarizes content from a list of source IDs.

        ## Parameters

        - `sources` (`list[str]`): List of bucket item IDs.
        - `research_id` (`str`): Current research context.

        ## Returns

        `dict`

        Schema: `{ "filename": "summary", ... }`

        ## Side Effects

        - Reads from bucket database.
        - Broadcasts "Reading your sources!" message.
        - Pushes sources stage state to Redis.
        """
        sources_content = {}

        try:
            for source_id in sources:
                source_record = buckets_db_manager.fetch_one(
                    "bucket_items",
                    where={"id": source_id},
                )
                sources_content[source_record["data"]["file_name"]] = source_record[
                    "data"
                ]["summary"]

            await event_bus.broadcast(
                message={"msg": "Reading your sources!", "research": research_id}
            )

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="sources_content:loaded",
                extra_fields={"sources_loaded_count": len(sources_content)},
            )

            return sources_content

        except Exception as exc:
            self._push_error_state_to_redis(
                research_id=research_id,
                pipeline_stage="sources_content",
                error_message=str(exc),
            )
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Error fetching sources content for research {research_id}: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS", "DB"],
                    "urgency": "critical",
                },
            )
            raise

    async def generate_title_desc(self, context: str, research_id: str) -> None:
        """
        ## Description

        Generates a concise title and description based on research context using Ollama.
        Updates both the database record and the internal instance state.

        ## Parameters

        - `context` (`str`): Research prompt or source summary used as generation context.
        - `research_id` (`str`): The research record ID.

        ## Returns

        `None`

        ## Side Effects

        - Triggers Ollama LLM inference.
        - Updates `self.title` and `self.desc`.
        - Schedules `researches` table update in background.
        - Broadcasts metadata update to `event_bus`.
        - Pushes title/desc stage state to Redis.
        """
        try:
            raw_title_desc_response = await ollama.asyncGenerateContent(
                prompt=(
                    f"Generate a concise and descriptive title & description for a research project "
                    f"based on the following context: {context}\n\n"
                    f"The title should be no more than 10 words and description should not be more than "
                    f"20 words and should capture the essence of the research project. "
                    f'Schema {{"title": "string", "desc": "string"}}'
                ),
                aclient=oAsCli,
                system=(
                    "You are a helpful research assistant that generates titles and descriptions "
                    "for research projects based on the provided context. You analyze the context "
                    "to create a concise and descriptive title that captures the essence of the "
                    "research project. The title should be no more than 10 words, and the "
                    "description should be no more than 20 words."
                ),
                model=OLLAMA_MODEL,
                image=None,
                options=OLLAMA_LLM_OPTIONS,
                json_schema={"title": "string", "desc": "string"},
            )

            parsed_title_desc = (
                json.loads(raw_title_desc_response)
                if isinstance(raw_title_desc_response, str)
                else {}
            )

            generated_title = parsed_title_desc.get("title", "Untitled Research")
            generated_desc = parsed_title_desc.get("desc", "No description provided.")

            # Update instance state so downstream steps and Redis snapshots see the real values
            self.title = generated_title
            self.desc = generated_desc

            await event_bus.broadcast(
                message={
                    "msg": "Got title and description!",
                    "research": research_id,
                    "title": generated_title,
                    "desc": generated_desc,
                }
            )

            await scheduler.schedule(
                researches_db_manager.update,
                params={
                    "table_name": "researches",
                    "where": {"id": research_id},
                    "data": {"title": generated_title, "desc": generated_desc},
                },
            )

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="title_desc:generated",
            )

        except Exception as exc:
            self._push_error_state_to_redis(
                research_id=research_id,
                pipeline_stage="title_desc",
                error_message=str(exc),
            )
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Error generating title and description for research {research_id}: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )
            raise

    async def draft_confirmation_queries(self, research_id: str) -> str:
        """
        ## Description

        Generates confirmation questions from the research prompt and custom instructions,
        sends them to the user over WebSocket, waits for answers, then uses those answers
        to produce an enhanced version of the original prompt.

        The WebSocket session is expected to be alive for the lifetime of the server,
        so even if the app process restarted, the Redis state snapshot allows the
        orchestrator to know exactly where to resume.

        ## Parameters

        - `research_id` (`str`): The research record ID.

        ## Returns

        `str`

        - The enhanced prompt after user answers are incorporated.

        ## Raises

        - `ValueError`: If `is_query_good` is not "yes".

        ## Side Effects

        - Triggers Ollama LLM inference via `generateQuestionsForResearch`.
        - Sends questions to client via WebSocket.
        - Waits up to 1200 seconds for answers.
        - Schedules DB insert for confirmation Q&A record.
        - Schedules DB update with enhanced prompt.
        - Pushes confirmation stage state to Redis at every sub-step.
        """
        if self.is_query_good != "yes":
            self._push_error_state_to_redis(
                research_id=research_id,
                pipeline_stage="confirmation_questions",
                error_message="Query did not pass validation, cannot draft confirmation questions.",
            )
            await event_bus.broadcast(
                message={
                    "msg": "Query did not pass validation, cannot draft confirmation questions.",
                    "research": research_id,
                }
            )
            raise ValueError(
                "Query did not pass validation, cannot draft confirmation questions."
            )

        try:
            confirmation_context = (
                f"Prompt: {self.prompt}\n\nCustom Instructions: {self.custom_prompt}"
            )

            await event_bus.broadcast(
                message={
                    "msg": "Drafting confirmation questions!",
                    "research": research_id,
                }
            )

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="confirmation_questions:generating",
            )

            generated_questions = await generateQuestionsForResearch(
                self.title, confirmation_context
            )

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="confirmation_questions:awaiting_user_answers",
                extra_fields={"confirmation_questions": str(generated_questions)},
            )

            websocket_question_handle = await wss.sendQuestions(
                {
                    "client_id": uuid.uuid4(),
                    "msg": "Please confirm some questions to make sure I understand your research correctly!",
                    "data": generated_questions,
                }
            )

            user_answer_data = await websocket_question_handle.getAnswers(1200)
            user_answers = user_answer_data.get("answers")

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="confirmation_questions:answers_received",
                extra_fields={
                    "confirmation_questions": str(generated_questions),
                    "confirmation_answers": str(user_answers),
                },
            )

            await scheduler.schedule(
                researches_db_manager.insert,
                params={
                    "table_name": "research_confirmation_questions",
                    "data": {
                        "id": uuid.uuid4(),
                        "research_id": str(research_id),
                        "questions": str(user_answers),
                    },
                },
            )

            enhanced_prompt = await generateEnhancedPrompt(
                self.title,
                confirmation_context,
                {"questions": generated_questions, "answers": user_answers},
            )

            # Update instance prompt so all subsequent steps and Redis snapshots use enhanced version
            self.prompt = enhanced_prompt

            await scheduler.schedule(
                researches_db_manager.update,
                params={
                    "table_name": "researches",
                    "where": {"id": research_id},
                    "data": {"prompt": enhanced_prompt},
                },
            )

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="confirmation_questions:enhanced_prompt_ready",
                extra_fields={"enhanced_prompt": enhanced_prompt},
            )

            return enhanced_prompt

        except Exception as exc:
            self._push_error_state_to_redis(
                research_id=research_id,
                pipeline_stage="confirmation_questions",
                error_message=str(exc),
            )
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Error during confirmation questions for research {research_id}: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )
            raise

    async def create_execution_plan(self, research_id: str) -> ResearchPlan:
        """
        ## Description

        Generates an execution plan using the (enhanced) prompt, sends it to the user
        over WebSocket for approval, and loops indefinitely — regenerating the plan on
        each rejection — until the user explicitly approves it.

        This loop is fully Redis-backed: every attempt and every approval/rejection is
        written to Redis so that if the server restarts between a plan send and the
        user's response, the state is recoverable.

        ## Parameters

        - `research_id` (`str`): The research record ID.

        ## Returns

        `ResearchPlan`

        - The approved plan object passed back to the master orchestrator.

        ## Side Effects

        - Calls `generatePlan` (LLM inference) on every loop iteration.
        - Sends plan to client via WebSocket and waits up to 1200 seconds per attempt.
        - Schedules DB insert for each generated plan.
        - Pushes plan stage state to Redis after every sub-step.
        - Broadcasts plan status events to `event_bus`.
        """
        plan_attempt_number = 0

        while True:
            plan_attempt_number += 1

            try:
                await event_bus.broadcast(
                    message={
                        "msg": f"Generating execution plan (attempt {plan_attempt_number})...",
                        "research": research_id,
                    }
                )

                self._push_pipeline_state_to_redis(
                    research_id=research_id,
                    pipeline_stage=f"execution_plan:generating:attempt_{plan_attempt_number}",
                    extra_fields={"plan_attempt_number": plan_attempt_number},
                )

                generated_plan = await generatePlan(self.prompt)

                self._push_pipeline_state_to_redis(
                    research_id=research_id,
                    pipeline_stage=f"execution_plan:awaiting_user_approval:attempt_{plan_attempt_number}",
                    extra_fields={
                        "plan_attempt_number": plan_attempt_number,
                        "current_plan": str(generated_plan),
                    },
                )

                await scheduler.schedule(
                    researches_db_manager.insert,
                    params={
                        "table_name": "research_plans",
                        "data": {
                            "id": uuid.uuid4(),
                            "research_id": str(research_id),
                            "plan": str(generated_plan),
                        },
                        "workspace_id": self.workspaceId,
                    },
                )

                await event_bus.broadcast(
                    message={
                        "msg": "Execution plan ready! Waiting for your approval...",
                        "research": research_id,
                    }
                )

                websocket_plan_approval_handle = await wss.sendQuestions(
                    {
                        "client_id": uuid.uuid4(),
                        "msg": (
                            "Here's the execution plan I've created based on your prompt and answers. "
                            "Do you approve this plan?"
                        ),
                        "data": str(generated_plan),
                    }
                )

                plan_approval_answer_data = (
                    await websocket_plan_approval_handle.getAnswers(1200)
                )
                user_approval_response = (
                    plan_approval_answer_data.get("answers", [{}])[0]
                    .get("answer", "no")
                    .lower()
                    .strip()
                )

                if user_approval_response == "yes":
                    self._push_pipeline_state_to_redis(
                        research_id=research_id,
                        pipeline_stage="execution_plan:approved",
                        extra_fields={
                            "plan_attempt_number": plan_attempt_number,
                            "approved_plan": str(generated_plan),
                        },
                    )

                    await event_bus.broadcast(
                        message={
                            "msg": "Plan approved! Starting the research execution...",
                            "research": research_id,
                        }
                    )

                    return generated_plan

                else:
                    # User rejected the plan — log, update Redis, and loop to regenerate
                    self._push_pipeline_state_to_redis(
                        research_id=research_id,
                        pipeline_stage=f"execution_plan:rejected:attempt_{plan_attempt_number}",
                        extra_fields={
                            "plan_attempt_number": plan_attempt_number,
                            "rejected_plan": str(generated_plan),
                        },
                    )

                    await scheduler.schedule(
                        quickLog,
                        params={
                            "level": "info",
                            "message": (
                                f"Execution plan attempt {plan_attempt_number} rejected by user "
                                f"for research {research_id}. Regenerating..."
                            ),
                            "module": ["API", "RESEARCH", "AGENTS"],
                            "urgency": "low",
                        },
                    )

                    await event_bus.broadcast(
                        message={
                            "msg": f"Got it! Let me regenerate the plan for you (attempt {plan_attempt_number + 1})...",
                            "research": research_id,
                        }
                    )

                    # Loop continues → generatePlan will be called again at top of while

            except Exception as exc:
                self._push_error_state_to_redis(
                    research_id=research_id,
                    pipeline_stage=f"execution_plan:attempt_{plan_attempt_number}",
                    error_message=str(exc),
                )
                await scheduler.schedule(
                    quickLog,
                    params={
                        "level": "error",
                        "message": (
                            f"Error during execution plan attempt {plan_attempt_number} "
                            f"for research {research_id}: {exc}"
                        ),
                        "module": ["API", "RESEARCH", "AGENTS"],
                        "urgency": "critical",
                    },
                )
                raise

    # ─────────────────────────────────────────────────────────────────────────
    # Main orchestration entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def process(self) -> tuple[dict, ResearchPlan, str, str]:
        """
        ## Description

        Main method that orchestrates all input processing steps in sequence:

        1. Create research DB record → extract `research_id` from returned instance.
        2. Validate the query → gate `is_query_good`.
        3. Fetch workspace bucket ID.
        4. Fetch and build sources context string.
        5. Generate title and description via Ollama (awaited, updates self.title / self.desc).
        6. Run confirmation questions over WebSocket → produces `enhanced_prompt`.
        7. Create and seek approval for execution plan over WebSocket (loops until approved).

        Every step updates Redis state in the background via scheduler so the pipeline
        is fully resumable if the application crashes between steps.

        ## Returns

        `tuple[dict, ResearchPlan, str, str]`

        - `research_instance` (`dict`): The full DB record dict for the created research.
        - `approved_plan` (`ResearchPlan`): The user-approved execution plan.
        - `enhanced_prompt` (`str`): The confirmation-questions-enhanced research prompt.
        - `research_id` (`str`): The canonical research id used across pipeline phases.

        ## Raises

        - Re-raises any exception from sub-steps after logging and Redis error state write.
        """
        research_instance = None

        try:
            # ── Step 1: Create the research DB record ────────────────────────
            research_instance = await self.craeteResearchRecord()
            research_id = str(research_instance["id"])

            # ── Step 2: Validate the query ───────────────────────────────────
            await self.process_input(research_id)

            # ── Step 3: Fetch the workspace bucket ───────────────────────────
            bucket_id = await self.getBucket(self.workspaceId, research_id)

            # ── Step 4: Load sources content and build context string ────────
            sources_content = await self.getSourcesContent(self.sources, research_id)

            sources_context_string = ""
            for source_filename, source_summary in sources_content.items():
                sources_context_string += f"{source_filename}: {source_summary}\n\n"

            full_generation_context = (
                f"Prompt: {self.prompt}\n\n"
                f"Custom Instructions: {self.custom_prompt}\n\n"
                f"Sources:\n{sources_context_string}"
            )

            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="sources_context:built",
                extra_fields={
                    "bucket_id": bucket_id,
                    "sources_context": full_generation_context,
                },
            )

            # ── Step 5: Generate title and description (awaited) ─────────────
            # Must be awaited here because self.title is used downstream by
            # generateQuestionsForResearch and generateEnhancedPrompt.
            await self.generate_title_desc(full_generation_context, research_id)

            # ── Step 6: Confirmation questions → enhanced prompt ─────────────
            enhanced_prompt = await self.draft_confirmation_queries(research_id)

            # ── Step 7: Execution plan creation + user approval loop ─────────
            approved_plan = await self.create_execution_plan(research_id)

            # ── Final: Mark pipeline as fully complete in Redis ──────────────
            self._push_pipeline_state_to_redis(
                research_id=research_id,
                pipeline_stage="input_processing:complete",
                extra_fields={
                    "enhanced_prompt": enhanced_prompt,
                    "approved_plan": str(approved_plan),
                },
            )

            await event_bus.broadcast(
                message={
                    "msg": "Input processing complete! Handing off to research executor...",
                    "research": research_id,
                }
            )

            return research_instance, approved_plan, enhanced_prompt, research_id

        except Exception as exc:
            if research_instance is not None:
                research_id = str(research_instance.get("id", ""))
                self._push_error_state_to_redis(
                    research_id=research_id,
                    pipeline_stage="input_processing:pipeline_fatal_error",
                    error_message=str(exc),
                )

            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Fatal error in input processing pipeline: {exc}",
                    "module": ["API", "RESEARCH", "AGENTS"],
                    "urgency": "critical",
                },
            )
            raise
