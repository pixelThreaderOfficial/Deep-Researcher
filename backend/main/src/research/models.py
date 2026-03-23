"""
models.py — Deep Researcher v2 Research Models
================================================
Pydantic models and enums defining the complete data structures
for the research pipeline, including ReAct reasoning, tool usage,
and artifact generation.
"""

from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    """
    ## Description

    Represents the lifecycle status of a research job.

    ## Parameters

    - None (Enum class)

    ## Returns

    `str`

    ## Customization

    Add new states here if extending the pipeline lifecycle.
    """

    PENDING = "pending"
    RUNNING = "running"
    THINKING = "thinking"
    ACTING = "acting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchStage(str, Enum):
    """
    ## Description

    Enumerates the discrete stages of the research pipeline.
    Maps to SSE event stages broadcast to connected clients.

    ## Parameters

    - None (Enum class)

    ## Returns

    `str`

    ## Customization

    Add new stages to extend the pipeline. Ensure matching
    SSE event handlers exist in the orchestrator.
    """

    VALIDATING = "validating_query"
    PLANNING = "generating_research_plan"
    THINKING = "thinking"
    ACTING = "acting"
    SEARCHING = "searching_sources"
    SCRAPING = "scraping_content"
    SUMMARIZING = "summarizing_findings"
    ANALYZING = "analyzing_data"
    SEMANTIC_SEARCH = "semantic_search"
    DOCUMENT_SEARCH = "document_search"
    YOUTUBE_SEARCH = "youtube_search"
    IMAGE_ANALYSIS = "image_analysis"
    ARTIFACT_GEN = "generating_artifact"
    INGESTING = "ingesting_vectors"
    SAVING = "saving_data"
    FINALIZING = "finalizing_output"


class ToolName(str, Enum):
    """
    ## Description

    Identifies each tool available to the ReAct reasoning engine
    during a research session.

    ## Parameters

    - None (Enum class)

    ## Returns

    `str`

    ## Customization

    Register new tools here and implement the handler in `tools.py`.
    """

    WEB_SEARCH = "web_search"
    SUMMARIZER = "summarizer"
    DOCUMENT_SEARCH = "document_search"
    SEMANTIC_SEARCH = "semantic_search"
    YOUTUBE_SEARCH = "youtube_search"
    IMAGE_UNDERSTANDING = "image_understanding"
    WEB_SCRAPE = "web_scrape"
    ARTIFACT_GENERATOR = "artifact_generator"


class Priority(str, Enum):
    """
    ## Description

    Priority classification for background task scheduling.

    ## Parameters

    - None (Enum class)

    ## Returns

    `str`
    """

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# ---------------------------------------------------------------------------
# Event / State models
# ---------------------------------------------------------------------------


class RedisEvent(BaseModel):
    """
    ## Description

    Represents a single event emitted during research execution.
    Used for SSE broadcasting and persistence in both Redis and
    the database via background workers.

    ## Parameters

    - `job_id` (`str`) — Unique research job identifier.
    - `stage` (`str`) — Current research stage.
    - `status` (`JobStatus`) — Job lifecycle status.
    - `message` (`str`) — Human-readable progress description.
    - `data` (`Optional[Dict[str, Any]]`) — Optional payload data.
    - `timestamp` (`str`) — UTC ISO timestamp, auto-generated.

    ## Returns

    `RedisEvent` instance.
    """

    job_id: str
    stage: str
    status: JobStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Tool invocation models
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """
    ## Description

    Represents a single tool invocation decided by the ReAct engine
    during its reasoning loop.

    ## Parameters

    - `tool` (`ToolName`) — Which tool to execute.
    - `parameters` (`Dict[str, Any]`) — Arguments for the tool.
    - `reasoning` (`str`) — Why the ReAct engine chose this tool.

    ## Returns

    `ToolCall` instance.
    """

    tool: ToolName
    parameters: Dict[str, Any] = {}
    reasoning: str = ""


class ToolResult(BaseModel):
    """
    ## Description

    Encapsulates the outcome of a single tool execution within
    the ReAct loop, including success/failure status and any
    artifacts produced.

    ## Parameters

    - `tool` (`ToolName`) — The tool that was executed.
    - `success` (`bool`) — Whether the tool execution succeeded.
    - `data` (`Any`) — Raw output from the tool.
    - `error` (`Optional[str]`) — Error message if the tool failed.
    - `duration_sec` (`float`) — Wall-clock execution time.

    ## Returns

    `ToolResult` instance.
    """

    tool: ToolName
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    duration_sec: float = 0.0


# ---------------------------------------------------------------------------
# ReAct reasoning models
# ---------------------------------------------------------------------------


class ThinkingStep(BaseModel):
    """
    ## Description

    Captures a single "Thought" turn in the ReAct loop, representing
    the model's internal reasoning before deciding on an action.

    ## Parameters

    - `step` (`int`) — Step number in the loop.
    - `thought` (`str`) — The reasoning text.
    - `action` (`Optional[ToolCall]`) — The resulting tool call, if any.
    - `observation` (`Optional[str]`) — The observation after executing the action.

    ## Returns

    `ThinkingStep` instance.
    """

    step: int
    thought: str
    action: Optional[ToolCall] = None
    observation: Optional[str] = None


# ---------------------------------------------------------------------------
# Research planning models
# ---------------------------------------------------------------------------


class ResearchStep(BaseModel):
    """
    ## Description

    Represents a single actionable step in a generated research plan.

    ## Parameters

    - `id` (`str`) — Unique step identifier (e.g. `step_1`).
    - `description` (`str`) — What this step entails.
    - `tools_required` (`List[str]`) — Tools needed for this step.
    - `status` (`str`) — Current execution status.
    - `result` (`Optional[str]`) — Output after execution.

    ## Returns

    `ResearchStep` instance.
    """

    id: str
    description: str
    tools_required: List[str] = []
    status: str = "pending"
    result: Optional[str] = None


class ResearchPlan(BaseModel):
    """
    ## Description

    A structured, multi-step research plan generated by the planner.

    ## Parameters

    - `title` (`str`) — Plan title.
    - `objective` (`str`) — Overall research objective.
    - `steps` (`List[ResearchStep]`) — Ordered execution steps.
    - `expected_tools` (`List[str]`) — Tools the plan expects to use.

    ## Returns

    `ResearchPlan` instance.
    """

    title: str
    objective: str = ""
    steps: List[ResearchStep] = []
    expected_tools: List[str] = []


# ---------------------------------------------------------------------------
# Artifact models
# ---------------------------------------------------------------------------


class ArtifactSection(BaseModel):
    """
    ## Description

    A single section within a generated research artifact document.

    ## Parameters

    - `heading` (`str`) — Section heading text.
    - `content` (`str`) — Markdown content for this section.

    ## Returns

    `ArtifactSection` instance.
    """

    heading: str
    content: str


class Artifact(BaseModel):
    """
    ## Description

    The final, structured research deliverable produced at the end
    of the pipeline. Contains the full markdown report, structured
    sections, media references, and source citations.

    ## Parameters

    - `title` (`str`) — Artifact title.
    - `type` (`str`) — Artifact type classification.
    - `summary` (`str`) — Executive summary of findings.
    - `key_insights` (`List[str]`) — Top-level takeaways.
    - `detailed_sections` (`List[ArtifactSection]`) — Rich content sections.
    - `actionable_steps` (`List[str]`) — Recommended next steps.
    - `sources` (`List[str]`) — Citation URLs.
    - `videos` (`List[Dict[str, str]]`) — YouTube video references.
    - `images` (`List[Dict[str, str]]`) — Image references.
    - `highlights` (`List[str]`) — Notable highlights.
    - `markdown_content` (`Optional[str]`) — Full markdown document.
    - `confidence_score` (`str`) — Confidence rating of the research.
    - `thinking_trace` (`List[ThinkingStep]`) — Full ReAct reasoning trace.

    ## Returns

    `Artifact` instance.
    """

    title: str
    type: str = "research_report"
    summary: str = ""
    key_insights: List[str] = []
    detailed_sections: List[ArtifactSection] = []
    actionable_steps: List[str] = []
    sources: List[str] = []
    videos: List[Dict[str, str]] = []
    images: List[Dict[str, str]] = []
    highlights: List[str] = []
    markdown_content: Optional[str] = None
    confidence_score: str = "medium"
    thinking_trace: List[ThinkingStep] = []


# ---------------------------------------------------------------------------
# Research session state
# ---------------------------------------------------------------------------


class ResearchSession(BaseModel):
    """
    ## Description

    Tracks the complete mutable state of a single research execution,
    from initial query through all ReAct cycles to final artifact.

    ## Parameters

    - `job_id` (`str`) — Unique session identifier.
    - `prompt` (`str`) — Original user query.
    - `refined_query` (`str`) — Validated/refined version of the query.
    - `context` (`Optional[str]`) — Additional user-provided context.
    - `research_id` (`Optional[str]`) — Associated research record ID.
    - `workspace_id` (`Optional[str]`) — Parent workspace ID.
    - `plan` (`Optional[ResearchPlan]`) — Generated research plan.
    - `thinking_steps` (`List[ThinkingStep]`) — Full ReAct trace.
    - `findings` (`List[Dict[str, Any]]`) — Accumulated research findings.
    - `sources` (`List[str]`) — All discovered source URLs.
    - `videos` (`List[Dict[str, str]]`) — Discovered videos.
    - `images` (`List[Dict[str, str]]`) — Discovered images.
    - `summaries` (`List[Dict[str, Any]]`) — Summarized content.
    - `vector_ids` (`List[str]`) — IDs of ingested vector chunks.
    - `artifact` (`Optional[Artifact]`) — Final generated artifact.
    - `status` (`JobStatus`) — Current lifecycle status.
    - `error` (`Optional[str]`) — Error message if failed.
    - `created_at` (`str`) — UTC ISO timestamp.

    ## Returns

    `ResearchSession` instance.
    """

    job_id: str
    prompt: str
    refined_query: str = ""
    context: Optional[str] = None
    research_id: Optional[str] = None
    workspace_id: Optional[str] = None
    plan: Optional[ResearchPlan] = None
    thinking_steps: List[ThinkingStep] = []
    findings: List[Dict[str, Any]] = []
    sources: List[str] = []
    videos: List[Dict[str, str]] = []
    images: List[Dict[str, str]] = []
    summaries: List[Dict[str, Any]] = []
    vector_ids: List[str] = []
    artifact: Optional[Artifact] = None
    status: JobStatus = JobStatus.PENDING
    error: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
