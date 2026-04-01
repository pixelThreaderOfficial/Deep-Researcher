from dataclasses import dataclass
import json
from typing import Any, AsyncGenerator, Dict, Optional

from main.src.utils.llms.gemini.DRGeminiWrapper import (
    asyncGenerateContentStream,
    getAsyncClient as GeminiClient,
    asyncGenerateContent,
)

GEMINI_MODEL = "gemini-2.5-flash-lite"


def _clamp_intensity(value: float) -> float:
    try:
        value = float(value)
    except Exception:
        value = 0.5
    return max(0.0, min(1.0, value))


def _build_thinking_profile(intensity: float) -> Dict[str, Any]:
    intensity = _clamp_intensity(intensity)

    if intensity <= 0.2:
        return {
            "label": "light",
            "max_steps": 3,
            "temperature": 0.2,
            "detail_level": "brief",
            "instruction": "Think concisely and focus on the most important insights only.",
        }
    if intensity <= 0.5:
        return {
            "label": "balanced",
            "max_steps": 5,
            "temperature": 0.35,
            "detail_level": "moderate",
            "instruction": "Think carefully with balanced depth and practical reasoning.",
        }
    if intensity <= 0.8:
        return {
            "label": "deep",
            "max_steps": 7,
            "temperature": 0.45,
            "detail_level": "detailed",
            "instruction": "Think deeply, connect related ideas, and explore implications.",
        }
    return {
        "label": "max",
        "max_steps": 10,
        "temperature": 0.55,
        "detail_level": "very_detailed",
        "instruction": "Think with maximum depth, broad coverage, and strong analytical rigor.",
    }


@dataclass
class ThinkingResult:
    topic: str
    context: str
    intensity: float
    thinking_profile: Dict[str, Any]
    output: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "context": self.context,
            "intensity": self.intensity,
            "thinking_profile": self.thinking_profile,
            "output": self.output,
        }


class Thinker:
    """
    Core thinker agent for the Deep Researcher app.

    Usage:
        thinker = Thinker(api_key="...")
        result = await thinker.think(topic="...", context="...", thinking_intensity=0.7)
        stream = thinker.think_stream(topic="...", context="...", thinking_intensity=0.7)
    """

    def __init__(self, model: str = "gemini-2.5-flash-lite") -> None:

        self.client = GeminiClient()
        self.model = model

    # ---------------------------
    # SAFE JSON PARSE
    # ---------------------------
    @staticmethod
    def _safe_json(raw: Any) -> Optional[Dict]:
        if isinstance(raw, dict):
            return raw

        if isinstance(raw, str):
            try:
                return json.loads(raw.strip())
            except:
                return None

        return None

    def _system_prompt(self, intensity: float) -> str:
        profile = _build_thinking_profile(intensity)

        return f"""
You are a pure reasoning engine ("Thinker").

Your job is to think deeply about the given topic within the provided context.

STRICT RULES:
- Do not mention user, query, task, or anything about being an AI
- Do not explain what you are doing
- Do not narrate intentions
- Do not restate the prompt
- Do not produce instructions or plans
- Only produce internal analytical reasoning

THINKING STYLE:
- Write like raw internal strategist notes
- Focus on insights, constraints, tradeoffs, and reasoning paths
- Convert context into structured understanding
- Derive implications, not summaries
- Be sharp, compressed, and insight-heavy

OUTPUT STRUCTURE:
1. Core Understanding
2. Key Observations
3. Hidden Constraints
4. Tradeoffs
5. Strategic Directions

TONE:
- Analytical
- Detached
- Precise
- No conversational language

Thinking intensity:
- label: {profile["label"]}
- depth: {profile["detail_level"]}
- max_steps: {profile["max_steps"]}

Behavior rules:
- Low intensity means shorter, sharper, more compressed reasoning.
- High intensity means deeper, broader, and more exhaustive reasoning.
- Stay generalized and reusable for any topic.
- Focus only on the provided topic and context.
- Never mention the existence of these rules.
""".strip()

    def _build_prompt(self, topic: str, context: str, intensity: float) -> str:
        profile = _build_thinking_profile(intensity)

        return f"""
TOPIC:
{topic}

CONTEXT:
{context}

REASONING MODE:
- Focus only on the topic above.
- Use the context only as grounding material.
- Do not speak to the user.
- Do not explain the process.
- Do not produce plans or instructions.
- Think in compressed internal notes.

DEPTH:
- intensity={profile["label"]} ({intensity:.2f})

OUTPUT SHAPE:
- Core Understanding
- Key Observations
- Hidden Constraints
- Tradeoffs
- Strategic Directions

RULES:
- No markdown code fences
- No unrelated content
- No conversational language
- No mention of user intent
""".strip()

    async def think(
        self,
        topic: str,
        context: str,
        thinking_intensity: float = 0.5,
        model: Optional[str] = None,
    ) -> str:
        intensity = _clamp_intensity(thinking_intensity)
        system = self._system_prompt(intensity)
        prompt = self._build_prompt(topic, context, intensity)

        output = await asyncGenerateContent(
            prompt=prompt,
            system=system,
            model=model or self.model,
            image=None,
            aclient=self.client,
        )

        return output.strip()

    async def think_stream(
        self,
        topic: str,
        context: str,
        thinking_intensity: float = 0.5,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        intensity = _clamp_intensity(thinking_intensity)
        system = self._system_prompt(intensity)
        prompt = self._build_prompt(topic, context, intensity)

        async for chunk in asyncGenerateContentStream(
            prompt=prompt,
            system=system,
            model=model or self.model,
            image=None,
            aclient=self.client,
        ):
            if chunk:
                yield chunk

    async def think_json(
        self,
        topic: str,
        context: str,
        thinking_intensity: float = 0.5,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        intensity = _clamp_intensity(thinking_intensity)
        profile = _build_thinking_profile(intensity)

        schema = {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "intensity": {"type": "number"},
                "thinking_profile": {"type": "object"},
                "core_interpretation": {"type": "string"},
                "key_insights": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "tradeoffs": {"type": "array", "items": {"type": "string"}},
                "best_next_actions": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "topic",
                "intensity",
                "thinking_profile",
                "core_interpretation",
                "key_insights",
                "assumptions",
                "tradeoffs",
                "best_next_actions",
            ],
        }

        prompt = f"""
TOPIC:
{topic}

CONTEXT:
{context}

Return a structured internal reasoning output grounded only in the topic and context.
Adjust the depth according to intensity={profile["label"]} ({intensity:.2f}).
Do not mention the user, the task, or that you are thinking.
""".strip()

        raw = await asyncGenerateContent(
            prompt=prompt,
            json_schema=schema,
            system=self._system_prompt(intensity),
            model=model or self.model,
            image=None,
            aclient=self.client,
        )

        parsed = self._safe_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Structured thinking output could not be parsed")

        return parsed
