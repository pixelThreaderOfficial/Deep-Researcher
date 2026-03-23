"""
research — Deep Researcher v2 Research Package
================================================
Entry point for the research subsystem. Exposes the key orchestrators,
engines, and services for use by the API layer and background workers.

## Description

Provides importable references to:
- ``research_api_orchestrator`` — CRUD orchestrator for REST endpoints.
- ``ResearchOrchestrator`` (from ``orchestrator``) — Full pipeline controller.
- ``ReActEngine`` — ReAct reasoning loop.
- ``ToolRegistry`` — Available tool handlers.
- ``ExternalServices`` — HTTP client for external APIs.
- All models and enums.

## Usage

```python
from main.src.research import research_api_orchestrator
from main.src.research.orchestrator import ResearchOrchestrator
```
"""

from main.src.research import research_api_orchestrator  # noqa: F401
from main.src.research.orchestrator import ResearchOrchestrator  # noqa: F401

__all__ = [
    "research_api_orchestrator",
    "ResearchOrchestrator",
]
