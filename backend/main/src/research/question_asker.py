"""
question_asker.py — Deep Researcher v2
========================================
Generates targeted clarifying questions to keep research on track.

## Description

Analyzes the current research state (query, context, findings)
and produces 2-3 targeted questions that would help refine the
research direction and uncover gaps.

## Side Effects

- Calls the Gemini API for question generation.

## Customization

Adjust the system instruction to change question quantity or focus.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from main.src.utils.llms.gemini.DRGeminiWrapper import asyncGenerateContent, _safe_json_loads

_log = logging.getLogger(__name__)

QA_MODEL = "gemini-2.5-flash-preview-05-20"


class QuestionAsker:
    """
    ## Description

    Generates clarifying questions based on the current research state
    to ensure the pipeline stays on track and covers all relevant angles.

    ## Parameters

    - `gemini` (`Any`) — Async Gemini API client.

    ## Returns

    `QuestionAsker` instance.

    ## Customization

    Modify the system instruction to change question characteristics.
    """

    def __init__(self, gemini: Any) -> None:
        self.gemini = gemini

    async def ask_clarifying_questions(
        self,
        query: str,
        context: Optional[str] = None,
        findings: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        ## Description

        Analyzes the current research state and generates targeted
        clarifying questions that would help refine the direction.

        ## Parameters

        - `query` (`str`)
          - Description: The research query being investigated.
          - Constraints: Must be non-empty.
          - Example: ``"What are the latest breakthroughs in quantum computing?"``

        - `context` (`Optional[str]`)
          - Description: Additional user context.
          - Constraints: Can be None.

        - `findings` (`Optional[List[Dict[str, Any]]]`)
          - Description: Findings accumulated so far.
          - Constraints: Can be None or empty.

        ## Returns

        `List[str]` — List of 2-3 clarifying question strings.

        ## Raises

        - Returns empty list on Gemini API failures.

        ## Side Effects

        - Makes an async Gemini API call.
        """
        system_instruction = """You are a Research Quality Controller.
Your job is to identify ambiguities, missing perspectives, or gaps in the current research.
Generate 2-3 targeted clarifying questions that would help refine the research direction.
Return a JSON object with a 'questions' key containing a list of strings.

Example: {"questions": ["What specific aspect of X are you most interested in?", "Should the research focus on theoretical or practical applications?"]}"""

        prompt = f"""Original Query: {query}
Current Context: {context or 'None'}
Findings so far: {findings or 'None'}

What questions should we ask to ensure the research stays on track and deepens correctly?"""

        try:
            text_resp = await asyncGenerateContent(
                prompt=prompt,
                system=system_instruction,
                model=QA_MODEL,
                image=None,
                aclient=self.gemini,
                json_schema={"type": "object"}
            )
            data = _safe_json_loads(text_resp) or {}
            return data.get("questions", [])
        except Exception as exc:
            _log.warning("[QuestionAsker] Failed to generate questions: %s", exc)
            return []
