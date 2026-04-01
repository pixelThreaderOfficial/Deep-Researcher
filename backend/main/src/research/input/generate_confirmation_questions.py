import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from main.src.utils.llms.gemini.DRGeminiWrapper import (
    getAsyncClient as GeminiClient,
    asyncGenerateContent,
)


GEMINI_MODEL = "gemini-2.5-flash-lite"

# ---------------------------
# UTILS
# ---------------------------
def _safe_json_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        try:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
        except Exception:
            pass

        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
        except Exception:
            pass

    return None


def _normalize_question_type(value: Any) -> str:
    allowed = {"input", "bool", "option"}
    if not isinstance(value, str):
        return "input"
    value = value.strip().lower()
    return value if value in allowed else "input"


def _normalize_questions(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        return []

    questions = []

    for item in data:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        qtype = _normalize_question_type(item.get("question_type", "input"))
        options = item.get("options", [])

        if not question:
            continue

        # normalize options
        if qtype == "bool":
            options = ["yes", "no"]

        elif qtype == "option":
            if not isinstance(options, list) or not options:
                options = ["Option 1", "Option 2"]

        else:
            options = []

        questions.append(
            {
                "question": question,
                "question_type": qtype,
                "options": options,
            }
        )

    return questions


def _format_answers_block(answers: Dict[str, Any]) -> str:
    if not answers:
        return "No answers provided."

    lines = []
    for key, value in answers.items():
        if isinstance(value, (dict, list)):
            value_text = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            value_text = str(value)
        lines.append(f"- {key}: {value_text}")
    return "\n".join(lines)


# ---------------------------
# DATA CLASSES
# ---------------------------
@dataclass
class ConfirmationResult:
    topic: str
    context: str
    questions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "context": self.context,
            "questions": self.questions,
        }


@dataclass
class EnhancedPromptResult:
    topic: str
    context: str
    answers: Dict[str, Any]
    enhanced_prompt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "context": self.context,
            "answers": self.answers,
            "enhanced_prompt": self.enhanced_prompt,
        }


# ---------------------------
# MAIN AGENT
# ---------------------------
class ConfirmationAgent:
    def __init__(self, model: str = GEMINI_MODEL) -> None:

        self.client = GeminiClient()
        self.model = model

    # ---------------------------
    # SYSTEM PROMPTS
    # ---------------------------
    def _question_system_prompt(self) -> str:
        return """
You are a clarification engine.

STRICT RULES:
- Output ONLY valid JSON
- No markdown
- No explanations

Question types:
- input → free text
- bool → MUST include options ["yes", "no"]
- option → MUST include 3-6 options

CRITICAL:
- option questions MUST include "options"
- bool MUST include ["yes", "no"]
- Do NOT leave options empty

Return:
[
  {
    "question": "...",
    "question_type": "input|bool|option",
    "options": []
  }
]
""".strip()

    def _enhance_system_prompt(self) -> str:
        return """
You are a prompt enhancement engine.

Your job:
Transform user intent + context + answers into a HIGH-QUALITY LLM prompt.

STRICT RULES:
- Output ONLY plain text
- No JSON
- No markdown
- No explanation

GOALS:
- Make prompt detailed, structured, and unambiguous
- Preserve all constraints
- Add clarity and flow
- Include assumptions ONLY if necessary
- Remove vagueness

OUTPUT:
A single clean prompt ready for an advanced planning/research agent.
""".strip()

    # ---------------------------
    # PROMPT BUILDERS
    # ---------------------------
    def _build_question_prompt(self, topic: str, context: str) -> str:
        return f"""
TOPIC:
{topic}

CONTEXT:
{context}

Generate high-value clarification questions.
""".strip()

    def _build_enhancement_prompt(
        self,
        topic: str,
        context: str,
        answers: Dict[str, Any],
    ) -> str:
        answers_block = _format_answers_block(answers)

        return f"""
TOPIC:
{topic}

CONTEXT:
{context}

USER ANSWERS:
{answers_block}

TASK:
Create a refined, detailed, and high-quality prompt for a planning/research agent.
""".strip()

    # ---------------------------
    # PUBLIC METHODS
    # ---------------------------
    async def generate_questions(
        self,
        topic: str,
        context: str = "",
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        raw = await asyncGenerateContent(
            aclient=self.client,
            prompt=self._build_question_prompt(topic, context),
            system=self._question_system_prompt(),
            model=model or self.model,
            image=None,
            json_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "question_type": {
                            "type": "string",
                            "enum": ["input", "bool", "option"],
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["question", "question_type"],
                },
            },
        )

        parsed = _safe_json_loads(raw)
        return _normalize_questions(parsed)

    async def generate_enhanced_prompt(
        self,
        topic: str,
        context: str,
        answers: Dict[str, Any],
        model: Optional[str] = None,
    ) -> str:

        result = await asyncGenerateContent(
            aclient=self.client,
            prompt=self._build_enhancement_prompt(topic, context, answers),
            system=self._enhance_system_prompt(),
            model=model or self.model,
            image=None,
        )

        if not isinstance(result, str) or not result.strip():
            raise ValueError("Invalid enhanced prompt output")

        return result.strip()



async def generateQuestionsForResearch(topic: str, context: str) -> List[Dict[str, Any]]:
    agent = ConfirmationAgent()
    return await agent.generate_questions(topic, context)

async def generateEnhancedPrompt(topic: str, context: str, answers: Dict[str, Any]) -> str:
    agent = ConfirmationAgent()
    return await agent.generate_enhanced_prompt(topic, context, answers)