# Deep Researcher v2 — Research API Documentation

> **Version**: 2.0.0  
> **Base URL**: `http://localhost:8000`  
> **Protocol**: REST + SSE (Server-Sent Events)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Research CRUD Endpoints](#research-crud-endpoints)
3. [Research Execution Pipeline](#research-execution-pipeline)
4. [ReAct Reasoning Engine](#react-reasoning-engine)
5. [Available Tools](#available-tools)
6. [SSE Event Protocol](#sse-event-protocol)
7. [Vector Store Integration](#vector-store-integration)
8. [Background Workers](#background-workers)
9. [Data Models](#data-models)
10. [Error Handling](#error-handling)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT APPLICATION                        │
│                  (Frontend / Agent)                          │
└──────────┬───────────────────────────────────┬──────────────┘
           │  REST API                         │  SSE Stream
           ▼                                   ▼
┌──────────────────────┐         ┌─────────────────────────┐
│   research_urls.py   │         │   event_bus / SSE        │
│   (FastAPI Router)   │         │   /events/{client_id}    │
└──────────┬───────────┘         └─────────────────────────┘
           │                               ▲
           ▼                               │ broadcasts
┌──────────────────────┐         ┌─────────┴───────────────┐
│  research_api_        │         │  ResearchOrchestrator    │
│  orchestrator.py      │         │  (Pipeline Controller)   │
│  (CRUD Operations)    │         └──────────┬──────────────┘
└──────────┬───────────┘                     │
           │                    ┌────────────┼────────────┐
           │                    ▼            ▼            ▼
           │           ┌────────────┐ ┌──────────┐ ┌──────────┐
           │           │ ReAct      │ │ Planner  │ │ Artifact │
           │           │ Engine     │ │          │ │ Generator│
           │           └──────┬─────┘ └──────────┘ └──────────┘
           │                  │
           │        ┌─────────┼─────────────────────┐
           │        ▼         ▼         ▼           ▼
           │   ┌─────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
           │   │WebSearch│ │Summar- │ │Semantic │ │YouTube   │
           │   │Tool     │ │izer   │ │Search   │ │Search    │
           │   └────┬────┘ └───┬────┘ └────┬────┘ └─────┬────┘
           │        │          │           │             │
           │        ▼          ▼           ▼             ▼
           │   ┌─────────────────────┐ ┌─────────────────────┐
           │   │  ExternalServices   │ │  ChromaDB + Ollama   │
           │   │  (SearXNG+crawl4ai) │ │  (Vector Store)      │
           │   └─────────────────────┘ └─────────────────────┘
           │
           ▼
┌──────────────────────┐     ┌───────────────────────┐
│  researches_db_mgr   │     │  Task Scheduler       │
│  (SQLite CRUD)       │     │  (BG Workers × 4)     │
└──────────────────────┘     └───────────────────────┘
```

### Key Components

| Component | Module | Purpose |
|-----------|--------|---------|
| **Research CRUD** | `research_api_orchestrator.py` | REST CRUD for research records & sources |
| **Pipeline Orchestrator** | `orchestrator.py` | Full research execution pipeline |
| **ReAct Engine** | `react_engine.py` | Iterative Reasoning + Acting loop |
| **Tool Registry** | `tools.py` | Tool handlers for web search, summarize, etc. |
| **External Services** | `external_services.py` | HTTP client for SearXNG, crawl4ai, Gemini |
| **Gemini Client** | `gemini_client.py` | Google Generative AI API wrapper |
| **Planner** | `planner.py` | Research plan generation via LLM |
| **Artifact Generator** | `artifact_generator.py` | Final report/document generation |
| **Vector Store** | `IngestionService.py` + `SearchEngine.py` | ChromaDB ingestion & search |
| **Background Tasks** | `task_schedular/` + `db_queue.py` | Non-blocking DB saves & ingestion |

---

## Research CRUD Endpoints

### GET `/research/`

List all research records with pagination and filtering.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | `int` | `1` | Page number (≥ 1) |
| `size` | `int` | `20` | Items per page (1–200) |
| `workspaceId` | `string` | `null` | Filter by workspace |
| `titleContains` | `string` | `null` | Title substring filter |
| `descContains` | `string` | `null` | Description substring filter |
| `promptContains` | `string` | `null` | Prompt substring filter |
| `chatAccess` | `boolean` | `null` | Filter by chat access flag |
| `backgroundProcessing` | `boolean` | `null` | Filter by BG processing flag |
| `sortBy` | `string` | `"id"` | Sort column: `id`, `title`, `workspace_id` |
| `sortOrder` | `string` | `"desc"` | Sort direction: `asc` or `desc` |

**Response: `200 OK`**

```json
{
    "items": [
        {
            "id": "uuid-string",
            "title": "Quantum Computing Research",
            "desc": "Description text",
            "prompt": "Research query",
            "sources": "serialized sources",
            "workspace_id": "uuid-string",
            "artifacts": "serialized artifact JSON",
            "chat_access": true,
            "background_processing": true,
            "research_template_id": null,
            "custom_instructions": null,
            "prompt_order": null
        }
    ],
    "page": 1,
    "size": 20,
    "total_items": 42,
    "total_pages": 3,
    "offset": 0
}
```

---

### GET `/research/{research_id}`

Retrieve a single research record.

**Response: `200 OK`** — `ResearchRecord` object.

**Error: `404 Not Found`** — Research not found.

---

### POST `/research/`

Create a new research record.

**Request Body:**

```json
{
    "title": "My Research",
    "desc": "Description",
    "prompt": "Research prompt",
    "workspace_id": "uuid-string",
    "chat_access": true,
    "background_processing": true
}
```

**Response: `201 Created`** — `ResearchRecord` with generated `id`.

---

### PUT `/research/{research_id}`

Full replacement of a research record.

**Request Body:** Same as POST.

**Response: `200 OK`** — Updated `ResearchRecord`.

---

### PATCH `/research/{research_id}`

Partial update of specific fields.

**Request Body:** Any subset of `ResearchRecord` fields.

**Response: `200 OK`** — Patched `ResearchRecord`.

---

### DELETE `/research/{research_id}`

Delete a research record.

**Response: `204 No Content`**

---

### Research Sources Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/research/urls` | List research source URLs (paginated, filterable) |
| `GET` | `/research/sources/{source_id}` | Get a single source |
| `POST` | `/research/sources` | Create a source |
| `PATCH` | `/research/sources/{source_id}` | Update a source |
| `DELETE` | `/research/sources/{source_id}` | Delete a source |

---

## Research Execution Pipeline

The full research pipeline is executed asynchronously by the `ResearchOrchestrator`:

### Pipeline Stages

| Stage | Enum Value | Description |
|-------|------------|-------------|
| 1. Validate | `validating_query` | Check query safety via Gemini |
| 2. Plan | `generating_research_plan` | Generate multi-step research plan |
| 3. Think | `thinking` | ReAct reasoning step |
| 4. Act | `acting` | ReAct tool execution |
| 5. Search | `searching_sources` | Web search via SearXNG |
| 6. Scrape | `scraping_content` | Content scraping via crawl4ai |
| 7. Summarize | `summarizing_findings` | Content summarization via Gemini |
| 8. Analyze | `analyzing_data` | Data analysis |
| 9. Semantic Search | `semantic_search` | Vector store query |
| 10. Document Search | `document_search` | PDF collection query |
| 11. YouTube Search | `youtube_search` | Video search via SearXNG |
| 12. Image Analysis | `image_analysis` | Image search & understanding |
| 13. Generate Artifact | `generating_artifact` | Final report generation |
| 14. Ingest | `ingesting_vectors` | Background vector ingestion |
| 15. Save | `saving_data` | Background DB persistence |
| 16. Finalize | `finalizing_output` | Complete pipeline |

### Execution Flow

```python
# 1. POST request triggers execution
job_id = uuid4()
input_data = {
    "prompt": "What are the latest breakthroughs in quantum computing?",
    "context": "Focus on error correction",
    "research_id": "existing-research-uuid",
    "workspace_id": "workspace-uuid",
    "api_key": "gemini-api-key"
}

# 2. Orchestrator runs the pipeline
artifact = await orchestrator.execute(job_id, input_data)

# 3. Client receives real-time updates via SSE
# GET /events/{client_id}
```

---

## ReAct Reasoning Engine

The ReAct (Reasoning + Acting) engine drives autonomous research decisions:

### How It Works

```
Step 1: THINK  →  "I need to search for quantum computing breakthroughs"
Step 1: ACT    →  web_search(query="quantum computing breakthroughs 2026")
Step 1: OBSERVE → Found 8 pages about quantum error correction, topological qubits...

Step 2: THINK  →  "Good results. Let me summarize the most relevant findings"
Step 2: ACT    →  summarizer(query="quantum breakthroughs", content="...")
Step 2: OBSERVE → Summary: "Key breakthroughs include..."

Step 3: THINK  →  "Let me check for related videos"
Step 3: ACT    →  youtube_search(query="quantum computing 2026 explained")
Step 3: OBSERVE → Found 5 videos about quantum computing

Step 4: THINK  →  "I have enough information. Final answer time."
Step 4: FINAL  →  { summary: "Comprehensive research findings..." }
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_REACT_STEPS` | `8` | Maximum reasoning iterations |
| `GEMINI_MODEL` | `gemini-2.5-flash-preview-05-20` | Model for reasoning |
| Temperature | `0.2` | Low temperature for focused reasoning |

### ThinkingStep Model

```json
{
    "step": 1,
    "thought": "I need to search for recent quantum computing breakthroughs...",
    "action": {
        "tool": "web_search",
        "parameters": {"query": "quantum computing breakthroughs 2026"},
        "reasoning": "Starting with broad web search"
    },
    "observation": "Found 8 pages about quantum error correction..."
}
```

---

## Available Tools

### 1. WebSearch (`web_search`)

Searches the web using SearXNG and scrapes results with crawl4ai.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | ✅ | Search query |
| `max_urls` | `int` | ❌ | Max results (default: 10) |
| `origin_research_id` | `string` | ❌ | Traceability ID |

### 2. WebScrape (`web_scrape`)

Scrapes specific URLs using crawl4ai.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | `string[]` | ✅ | URLs to scrape |
| `origin_research_id` | `string` | ❌ | Traceability ID |

### 3. Summarizer (`summarizer`)

Summarizes content relative to a query using Gemini.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | ❌ | Context query |
| `content` | `string` | ✅ | Text to summarize |
| `origin_research_id` | `string` | ❌ | Traceability ID |

### 4. DocumentSearch (`document_search`)

Searches ingested PDFs in the ChromaDB `pdfs` collection.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | ✅ | Search query |
| `n_results` | `int` | ❌ | Max results (default: 10) |

### 5. SemanticSearch (`semantic_search`)

Searches ALL vector store collections (websites, PDFs, images, custom).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | ✅ | Search query |
| `collections` | `string[]` | ❌ | Target collections |
| `n_results` | `int` | ❌ | Max per collection (default: 10) |

### 6. YouTubeSearch (`youtube_search`)

Searches YouTube for relevant videos via SearXNG.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | ✅ | Video search query |
| `max_results` | `int` | ❌ | Max videos (default: 5) |

### 7. ImageUnderstanding (`image_understanding`)

Searches for and collects relevant images via SearXNG.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | ✅ | Image search query |
| `max_results` | `int` | ❌ | Max images (default: 5) |

---

## SSE Event Protocol

### Connecting

```
GET /events/{client_id}
Accept: text/event-stream
```

### Event Format

```
data: {
    "job_id": "uuid-string",
    "stage": "thinking",
    "status": "running",
    "message": "Step 2: Analyzing search results...",
    "data": {
        "step": 2,
        "thought": "The search results show...",
        "tool": "summarizer",
        "parameters": {"query": "...", "content": "..."}
    }
}
```

### Job Status Values

| Status | Description |
|--------|-------------|
| `pending` | Job queued, not yet started |
| `running` | Pipeline actively executing |
| `thinking` | ReAct engine reasoning phase |
| `acting` | ReAct engine tool execution phase |
| `completed` | Pipeline finished successfully |
| `failed` | Pipeline encountered an error |
| `cancelled` | Job was cancelled |

### Final Event

```json
{
    "job_id": "uuid-string",
    "stage": "finalizing_output",
    "status": "completed",
    "message": "Research complete.",
    "data": {
        "artifact": { "title": "...", "summary": "...", "markdown_content": "..." },
        "total_sources": 15,
        "total_steps": 6,
        "total_videos": 3,
        "total_images": 5
    }
}
```

---

## Vector Store Integration

### Ingestion Pipeline

Scraped content is automatically ingested into ChromaDB via background workers:

```
Scraped Page → MarkdownChunker → Ollama Embedding → ChromaDB (websites collection)
```

### Collections

| Collection | Content Type | Embedding Model |
|------------|-------------|----------------|
| `websites` | Scraped web pages | Ollama (`embeddinggemma:latest`) |
| `pdfs` | Uploaded PDF documents | Ollama (`embeddinggemma:latest`) |
| `images` | Image descriptions | SigLIP (visual embeddings) |
| `custom` | User-provided text | Ollama (`embeddinggemma:latest`) |

### Search

```python
from main.src.store.vector import search_engine

# Search all collections
results = await search_engine.search("quantum computing", n_results=10)

# Search specific collections
results = await search_engine.search(
    "quantum computing",
    collections=["websites", "pdfs"],
    n_results=5,
)
```

---

## Background Workers

Non-critical tasks are offloaded to the background task scheduler (4 workers):

### Task Types

| Task | Priority | Description |
|------|----------|-------------|
| Vector Ingestion | `LOW` | Ingest scraped content into ChromaDB |
| Source Saving | `LOW` | Save source URLs to `research_sources` table |
| Artifact Saving | `LOW` | Save artifact JSON to `researches` table |
| Event Logging | `LOW` | Persist SSE events for replay |

### Usage Pattern

```python
from main.src.utils.core.task_schedular import scheduler

# Schedule a background task
await scheduler.schedule(
    save_research_source,
    params={
        "research_id": "uuid-string",
        "source_url": "https://example.com",
        "source_type": "website",
        "source_content": "Page content...",
    },
)
```

---

## Data Models

### Artifact (Final Output)

```json
{
    "title": "Research Report: Quantum Computing Breakthroughs",
    "type": "research_report",
    "summary": "Executive summary of findings...",
    "key_insights": [
        "Insight 1: ...",
        "Insight 2: ..."
    ],
    "detailed_sections": [
        {
            "heading": "Section Title",
            "content": "Markdown content for this section..."
        }
    ],
    "actionable_steps": ["Step 1", "Step 2"],
    "sources": ["https://source1.com", "https://source2.com"],
    "videos": [{"title": "Video Title", "url": "https://youtube.com/..."}],
    "images": [{"alt": "Image description", "url": "https://..."}],
    "highlights": ["Notable finding or quote"],
    "markdown_content": "# Full Markdown Document\n\n...",
    "confidence_score": "high",
    "thinking_trace": [
        {
            "step": 1,
            "thought": "...",
            "action": {"tool": "web_search", "parameters": {}, "reasoning": "..."},
            "observation": "..."
        }
    ]
}
```

### ResearchSession (Internal State)

```json
{
    "job_id": "uuid-string",
    "prompt": "Original user query",
    "refined_query": "Validated/sanitized query",
    "context": "Additional context",
    "research_id": "linked research record UUID",
    "workspace_id": "parent workspace UUID",
    "plan": { "title": "...", "steps": [...] },
    "thinking_steps": [...],
    "findings": [...],
    "sources": ["url1", "url2"],
    "videos": [...],
    "images": [...],
    "summaries": [...],
    "vector_ids": [...],
    "artifact": { ... },
    "status": "completed",
    "created_at": "2026-03-20T12:00:00Z"
}
```

---

## Error Handling

### HTTP Error Codes

| Code | Meaning | When |
|------|---------|------|
| `400` | Bad Request | Invalid payload or parameters |
| `404` | Not Found | Research or source record not found |
| `500` | Internal Error | Pipeline or database failure |

### Pipeline Errors

Pipeline failures emit a final SSE event with `status: "failed"`:

```json
{
    "job_id": "uuid-string",
    "stage": "finalizing_output",
    "status": "failed",
    "message": "Research failed: Gemini API rate limit exceeded"
}
```

### Environment Requirements

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | ✅ | — | Google Generative AI API key |
| `REDIS_URL` | ❌ | `redis://localhost:6379` | Redis connection URL |
| `SERVICES_BASE_URL` | ❌ | `http://localhost:8000` | Internal API base URL |
| `SEARXNG_URL` | ❌ | `http://localhost:8080` | SearXNG instance URL |
| `SERVICES_TIMEOUT` | ❌ | `120` | HTTP timeout in seconds |
