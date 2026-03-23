import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchRecord(BaseModel):
    """Represents `researches` table rows."""

    id: str = Field(default_factory=_new_id)
    title: str | None = None
    desc: str | None = None
    prompt: str | None = None
    sources: str | None = None
    workspace_id: str | None = None
    artifacts: str | None = None
    chat_access: bool = True
    background_processing: bool = True
    research_template_id: str | None = None
    custom_instructions: str | None = None
    prompt_order: str | None = None


class ResearchCreate(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str | None = None
    desc: str | None = None
    prompt: str | None = None
    sources: str | None = None
    workspace_id: str | None = None
    artifacts: str | None = None
    chat_access: bool = True
    background_processing: bool = True
    research_template_id: str | None = None
    custom_instructions: str | None = None
    prompt_order: str | None = None


class ResearchPatch(BaseModel):
    title: str | None = None
    desc: str | None = None
    prompt: str | None = None
    sources: str | None = None
    workspace_id: str | None = None
    artifacts: str | None = None
    chat_access: bool | None = None
    background_processing: bool | None = None
    research_template_id: str | None = None
    custom_instructions: str | None = None
    prompt_order: str | None = None


class ResearchTemplateRecord(BaseModel):
    """Represents `research_templates` table rows."""

    id: str = Field(default_factory=_new_id)
    title: str | None = None
    desc: str | None = None
    template: str | None = None
    total_researches: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ResearchTemplateCreate(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str | None = None
    desc: str | None = None
    template: str | None = None
    total_researches: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ResearchTemplatePatch(BaseModel):
    title: str | None = None
    desc: str | None = None
    template: str | None = None
    total_researches: int | None = None
    updated_at: datetime | None = None


class ResearchPlanRecord(BaseModel):
    """Represents `research_plans` table rows."""

    id: str = Field(default_factory=_new_id)
    title: str | None = None
    desc: str | None = None
    plan: str | None = None
    workflow: str | None = None
    workspace_id: str | None = None
    research_template_id: str | None = None
    prompt_order: str | None = None


class ResearchPlanCreate(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str | None = None
    desc: str | None = None
    plan: str | None = None
    workflow: str | None = None
    workspace_id: str | None = None
    research_template_id: str | None = None
    prompt_order: str | None = None


class ResearchPlanPatch(BaseModel):
    title: str | None = None
    desc: str | None = None
    plan: str | None = None
    workflow: str | None = None
    workspace_id: str | None = None
    research_template_id: str | None = None
    prompt_order: str | None = None


class ResearchWorkflowRecord(BaseModel):
    """Represents `research_workflow` table rows."""

    id: str = Field(default_factory=_new_id)
    workspace_id: str | None = None
    research_id: str | None = None
    workflow: str | None = None
    steps: int | None = None
    tokens_used: int | None = None
    resources_used: int | None = None
    time_taken_sec: int | None = None
    success: bool | None = None
    updated_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)


class ResearchWorkflowCreate(BaseModel):
    id: str = Field(default_factory=_new_id)
    workspace_id: str | None = None
    research_id: str | None = None
    workflow: str | None = None
    steps: int | None = None
    tokens_used: int | None = None
    resources_used: int | None = None
    time_taken_sec: int | None = None
    success: bool | None = None
    updated_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)


class ResearchWorkflowPatch(BaseModel):
    workspace_id: str | None = None
    research_id: str | None = None
    workflow: str | None = None
    steps: int | None = None
    tokens_used: int | None = None
    resources_used: int | None = None
    time_taken_sec: int | None = None
    success: bool | None = None
    updated_at: datetime | None = None


class ResearchMetadataRecord(BaseModel):
    """Represents `research_metadata` table rows."""

    id: str = Field(default_factory=_new_id)
    models: str | None = None
    workspace_id: str | None = None
    research_id: str | None = None
    connected_bucket: str | None = None
    time_taken_sec: int | None = None
    token_count: int | None = None
    source_count: int | None = None
    websites_count: int | None = None
    file_count: int | None = None
    citations: str | None = None
    exported: str | None = None
    status: bool | None = None
    chats_referenced: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ResearchMetadataCreate(BaseModel):
    id: str = Field(default_factory=_new_id)
    models: str | None = None
    workspace_id: str | None = None
    research_id: str | None = None
    connected_bucket: str | None = None
    time_taken_sec: int | None = None
    token_count: int | None = None
    source_count: int | None = None
    websites_count: int | None = None
    file_count: int | None = None
    citations: str | None = None
    exported: str | None = None
    status: bool | None = None
    chats_referenced: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ResearchMetadataPatch(BaseModel):
    models: str | None = None
    workspace_id: str | None = None
    research_id: str | None = None
    connected_bucket: str | None = None
    time_taken_sec: int | None = None
    token_count: int | None = None
    source_count: int | None = None
    websites_count: int | None = None
    file_count: int | None = None
    citations: str | None = None
    exported: str | None = None
    status: bool | None = None
    chats_referenced: str | None = None
    updated_at: datetime | None = None


class ResearchSourceRecord(BaseModel):
    """Represents `research_sources` table rows."""

    id: str = Field(default_factory=_new_id)
    research_id: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_content: str | None = None
    source_citations: str | None = None
    source_vector_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ResearchSourceCreate(BaseModel):
    id: str = Field(default_factory=_new_id)
    research_id: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_content: str | None = None
    source_citations: str | None = None
    source_vector_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ResearchSourcePatch(BaseModel):
    research_id: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_content: str | None = None
    source_citations: str | None = None
    source_vector_id: str | None = None
    updated_at: datetime | None = None


class ResearchListResponse(BaseModel):
    items: list[ResearchRecord]
    page: int
    size: int
    total_items: int
    total_pages: int
    offset: int


class ResearchTemplateListResponse(BaseModel):
    items: list[ResearchTemplateRecord]
    page: int
    size: int
    total_items: int
    total_pages: int
    offset: int


class ResearchPlanListResponse(BaseModel):
    items: list[ResearchPlanRecord]
    page: int
    size: int
    total_items: int
    total_pages: int
    offset: int


class ResearchWorkflowListResponse(BaseModel):
    items: list[ResearchWorkflowRecord]
    page: int
    size: int
    total_items: int
    total_pages: int
    offset: int


class ResearchMetadataListResponse(BaseModel):
    items: list[ResearchMetadataRecord]
    page: int
    size: int
    total_items: int
    total_pages: int
    offset: int


class ResearchSourceListResponse(BaseModel):
    items: list[ResearchSourceRecord]
    page: int
    size: int
    total_items: int
    total_pages: int
    offset: int


# Optional compatibility aliases
Research = ResearchRecord
ResearchTemplate = ResearchTemplateRecord
ResearchPlan = ResearchPlanRecord


class ResearchRunRequest(BaseModel):
    """Payload for triggering the research execution pipeline."""

    prompt: str
    context: str | None = None
    research_id: str | None = None
    workspace_id: str | None = None
    api_key: str | None = None
