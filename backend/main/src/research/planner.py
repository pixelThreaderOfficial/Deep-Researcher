"""
planner.py — Deep Researcher v2
=================================
Generates structured research plans using Gemini LLM.

## Description

Takes a user query and optional context, asks Gemini to decompose it
into a multi-step research plan with tool requirements, and returns
the plan as a ``ResearchPlan`` Pydantic model.

## Side Effects

- Calls the Gemini API for plan generation.

## Customization

Modify the system instruction to change planning behavior.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from main.src.utils.llms.gemini.DRGeminiWrapper import asyncGenerateContent, _safe_json_loads
from main.src.research.models import ResearchPlan, ResearchStep

_log = logging.getLogger(__name__)

PLANNING_MODEL = "gemini-2.5-flash-preview-05-20"


class ResearchPlanner:
    """
    ## Description

    Generates multi-step research plans by prompting Gemini with the
    user query and context. Each step specifies what to investigate
    and which tools to use.

    ## Parameters

    - `gemini` (`Any`) — Async Gemini API client.

    ## Returns

    `ResearchPlanner` instance.

    ## Customization

    Adjust the system instruction or model to change plan granularity.
    """

    def __init__(self, gemini: Any) -> None:
        self.gemini = gemini

    async def create_plan(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> ResearchPlan:
        """
        ## Description

        Generates a structured research plan by decomposing the user query
        into actionable steps with associated tool requirements.

        ## Parameters

        - `query` (`str`)
          - Description: The refined research query.
          - Constraints: Must be non-empty.
          - Example: ``"What are the latest breakthroughs in quantum computing?"``

        - `context` (`Optional[str]`)
          - Description: Additional context or constraints.
          - Constraints: Can be None.

        ## Returns

        `ResearchPlan`

        Structure:

        ```json
        {
            "title": "Research Plan: Quantum Computing Breakthroughs",
            "objective": "...",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Search for recent papers on quantum error correction",
                    "tools_required": ["web_search", "summarizer"]
                }
            ],
            "expected_tools": ["web_search", "summarizer", "youtube_search"]
        }
        ```

        ## Side Effects

        - Makes an async Gemini API call.

        ## Customization

        Modify the system instruction below to change the plan structure.
        """
        system_instruction = """You are a Research Planner. Your job is to break down a research query into a logical, multi-step execution plan.

Each step should:
- Be specific and actionable
- Reference the tools it would need (web_search, summarizer, document_search, semantic_search, youtube_search, image_understanding)
- Build upon previous steps logically

Return a JSON object with this structure:
{
    "title": "Plan title",
    "objective": "Overall research objective",
    "steps": [
        {
            "description": "What to do in this step",
            "tools_required": ["tool_name_1", "tool_name_2"]
        }
    ],
    "expected_tools": ["list", "of", "all", "tools", "needed"]
}

Generate 3-6 focused steps. Be thorough but efficient."""

        prompt = f"""User Query: {query}
Context: {context or 'None provided'}

Generate a multi-step research plan."""

        try:
            plan_text = await asyncGenerateContent(
                prompt=prompt,
                system=system_instruction,
                model=PLANNING_MODEL,
                image=None,
                aclient=self.gemini,
                json_schema={"type": "object"}
            )
            plan_data = _safe_json_loads(plan_text) or {}

            steps = []
            for idx, s in enumerate(plan_data.get("steps", [])):
                if isinstance(s, dict):
                    desc = s.get("description", "")
                    tools = s.get("tools_required", [])
                else:
                    desc = str(s)
                    tools = []

                steps.append(
                    ResearchStep(
                        id=f"step_{idx + 1}",
                        description=desc,
                        tools_required=tools,
                        status="pending",
                    )
                )

            return ResearchPlan(
                title=plan_data.get("title", "Research Plan"),
                objective=plan_data.get("objective", query),
                steps=steps,
                expected_tools=plan_data.get("expected_tools", []),
            )

        except Exception as exc:
            _log.error("[Planner] Plan generation failed: %s", exc)
            # Fallback: single-step plan
            return ResearchPlan(
                title="Research Plan",
                objective=query,
                steps=[
                    ResearchStep(
                        id="step_1",
                        description=f"Research: {query}",
                        tools_required=["web_search", "summarizer"],
                        status="pending",
                    )
                ],
                expected_tools=["web_search", "summarizer"],
            )
