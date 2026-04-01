import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from main.src.utils.llms.gemini.DRGeminiWrapper import (
    getAsyncClient as GeminiClient,
    asyncGenerateContent,
)
from research.input.generate_confirmation_questions import GEMINI_MODEL

_log = logging.getLogger(__name__)

# ---------------------------
# DATA STRUCTURES
# ---------------------------
#

_log.info("initilizing the Gemini client")

VALID_TOOLS = {
    "web_search",
    "summarizer",
    "document_search",
    "semantic_search",
    "youtube_search",
    "image_understanding",
    "image_search",
    "get_current_knowledge_on_the_topic",
}


@dataclass
class ResearchStep:
    id: str
    description: str
    tools_required: List[str]
    status: str = "pending"
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    title: str
    objective: str
    steps: List[ResearchStep]
    expected_tools: List[str]

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "objective": self.objective,
            "steps": [asdict(step) for step in self.steps],
            "expected_tools": self.expected_tools,
        }


# ---------------------------
# SAFE JSON PARSER
# ---------------------------


def _safe_json_loads(text: str) -> Optional[Dict]:
    try:
        return json.loads(text)
    except Exception:
        try:
            # fallback: extract JSON block
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


# ---------------------------
# VALIDATION LAYER
# ---------------------------


def _validate_tools(tools: List[str]) -> List[str]:
    return [t for t in tools if t in VALID_TOOLS]


def _validate_plan_structure(plan: Dict) -> bool:
    if not isinstance(plan, dict):
        return False
    if "steps" not in plan or not isinstance(plan["steps"], list):
        return False
    return True


def _deduplicate_steps(steps: List[ResearchStep]) -> List[ResearchStep]:
    seen = set()
    unique = []
    for step in steps:
        if step.description not in seen:
            seen.add(step.description)
            unique.append(step)
    return unique


# ---------------------------
# CORE PLANNER
# ---------------------------


class ResearchPlanner:
    def __init__(self) -> None:
        self.client = GeminiClient()

    async def create_plan(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> ResearchPlan:

        system_instruction = """
        You are an elite Research Planning Engine designed for deep, multi-modal, tool-augmented research.

        Your task is to decompose a given query into a highly detailed, exhaustive, and execution-ready research plan.

        STRICT RULES:
        - Output ONLY valid JSON
        - No explanations
        - No markdown
        - No extra text

        PLANNING PRINCIPLES:
        - Generate MANY steps (minimum 10, maximum 30)
        - Maximize research depth and coverage
        - Each step must contribute meaningful progress toward the objective
        - Avoid redundancy, but DO NOT under-explore
        - Prefer over-completeness over minimalism

        STEP DESIGN REQUIREMENTS:
        Each step MUST:
        - Be highly specific and actionable
        - Combine MULTIPLE tools whenever possible
        - Clearly indicate what is being searched, extracted, analyzed, or synthesized
        - Be structured so an execution agent can directly perform it
        - Build logically on previous steps
        - Include intelligent dependencies

        TOOL USAGE STRATEGY:
        - web_search → for broad discovery and fresh information
        - document_search → for structured or known-source retrieval
        - semantic_search → for deep contextual linking and similarity discovery
        - youtube_search → for visual, experiential, or tutorial-based insights
        - image_search → for discovering visual references
        - image_understanding → for extracting insights from images (clothing, places, artifacts, etc.)
        - summarizer → MUST be used frequently to compress and refine outputs
        - get_current_knowledge_on_the_topic → ALWAYS use early to establish baseline understanding

        MULTI-TOOL REQUIREMENT:
        - Each step should use 2–4 tools where meaningful
        - Avoid single-tool steps unless absolutely necessary
        - Prefer pipelines like:
          ["web_search", "summarizer"]
          ["youtube_search", "summarizer"]
          ["image_search", "image_understanding", "summarizer"]
          ["document_search", "semantic_search", "summarizer"]

        DEPENDENCY RULES:
        - Steps must form a DAG (Directed Acyclic Graph)
        - Later steps must depend on logically relevant earlier steps
        - Final steps must aggregate and synthesize all prior findings

        FINAL STEPS (MANDATORY):
        Include steps that:
        - Cross-validate findings across multiple sources
        - Identify gaps or inconsistencies
        - Optimize results (budget, efficiency, relevance, etc.)
        - Produce a final structured synthesis

        OUTPUT FORMAT:
        {
            "title": "string",
            "objective": "string",
            "steps": [
                {
                    "id": "step_x",
                    "description": "string",
                    "tools_required": ["tool1", "tool2", "tool3"],
                    "status": "pending",
                    "depends_on": ["step_y"]
                }
            ],
            "expected_tools": ["tool1", "tool2", ...]
        }

        IMPORTANT:
        - Use ALL relevant tools across the plan
        - Ensure tool diversity
        - Ensure deep coverage of the topic
        - Think like a senior research analyst, not a basic planner
        - The plan should be executable, scalable, and production-grade
"""

        prompt = f"""
User Query:
{query}

Context:
{context or "None"}

Constraints:
- Be efficient but thorough
- Avoid unnecessary steps
- Use a variety of tools where appropriate to gather comprehensive information (e.g., web_search for general info, youtube_search for videos, image_understanding for visuals, summarizer for condensing data)
"""

        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "objective": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "tools_required": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                "expected_tools": {"type": "array", "items": {"type": "string"}},
            },
        }

        try:
            plan_text = await asyncGenerateContent(
                prompt=prompt,
                json_schema=schema,
                system=system_instruction,
                model=GEMINI_MODEL,
                image=None,
                aclient=self.client,
            )

            plan_data = _safe_json_loads(plan_text)

            if not plan_data or not _validate_plan_structure(plan_data):
                raise ValueError("Invalid plan structure")

            steps: List[ResearchStep] = []

            for idx, s in enumerate(plan_data.get("steps", [])):
                if not isinstance(s, dict):
                    continue

                desc = s.get("description", "").strip()
                tools = _validate_tools(s.get("tools_required", []))
                depends_on = s.get("depends_on", [])

                if not desc:
                    continue

                steps.append(
                    ResearchStep(
                        id=f"step_{idx + 1}",
                        description=desc,
                        tools_required=tools,
                        depends_on=depends_on if isinstance(depends_on, list) else [],
                    )
                )

            # Remove duplicates
            steps = _deduplicate_steps(steps)

            if not steps:
                raise ValueError("No valid steps generated")

            expected_tools = list(
                {tool for step in steps for tool in step.tools_required}
            )

            return ResearchPlan(
                title=plan_data.get("title", "Research Plan"),
                objective=plan_data.get("objective", query),
                steps=steps,
                expected_tools=expected_tools,
            )

        except Exception as exc:
            _log.error("[Planner] Failure: %s", exc)

            # 🔥 Smart fallback (not dumb anymore)
            return ResearchPlan(
                title="Fallback Research Plan",
                objective=query,
                steps=[
                    ResearchStep(
                        id="step_1",
                        description=f"Perform broad search on: {query}",
                        tools_required=["web_search"],
                    ),
                    ResearchStep(
                        id="step_2",
                        description="Summarize key findings",
                        tools_required=["summarizer"],
                        depends_on=["step_1"],
                    ),
                ],
                expected_tools=["web_search", "summarizer"],
            )



async def generatePlan(query: str, context: Optional[str] = None) -> ResearchPlan:
    planner = ResearchPlanner()
    return await planner.create_plan(query, context)