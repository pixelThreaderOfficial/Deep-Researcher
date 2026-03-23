"""
react_engine.py — Deep Researcher v2 ReAct Engine
===================================================
Implements the ReAct (Reasoning + Acting) loop that drives the
research pipeline's autonomous decision-making process.

Architecture
------------
::

    Prompt → Gemini Think → ToolCall Decision
                │
                ▼
            Tool Execution → Observation
                │
                ▼
            Gemini Think (with observation) → Next Action or Finalize
                │
                ▼
            ... (iterates until max_steps or final_answer)

## Description

The ReAct engine takes a user query, reasons about what tools to use,
executes them, observes results, and iteratively refines until it has
enough information to produce a comprehensive research answer.

## Side Effects

- Calls Gemini API for reasoning steps.
- Executes tools that make HTTP requests and vector DB queries.
- Emits SSE events through the provided callback.

## Customization

Adjust ``MAX_REACT_STEPS`` to control research depth, or modify
the system prompt to change reasoning behavior.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

from main.src.utils.llms.gemini.DRGeminiWrapper import asyncGenerateContent, _safe_json_loads
from main.src.research.models import (
    ThinkingStep,
    ToolCall,
    ToolName,
    ToolResult,
)
from main.src.research.tools import ToolRegistry

_log = logging.getLogger(__name__)

MAX_REACT_STEPS = 8
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"


def _build_system_prompt(tool_descriptions: str) -> str:
    """
    ## Description

    Constructs the system instruction for the Gemini model that powers
    the ReAct reasoning loop. Includes tool descriptions and output format.

    ## Parameters

    - `tool_descriptions` (`str`)
      - Description: Formatted tool name + description listing.
      - Constraints: Must be non-empty.

    ## Returns

    `str` — The full system prompt.
    """
    return f"""You are a Deep Research Agent using the ReAct (Reasoning + Acting) framework.

Your job is to conduct thorough, multi-step research on a given query by reasoning about what information you need and selecting appropriate tools to gather it.

## Available Tools

{tool_descriptions}

## Response Format

You MUST respond with a valid JSON object for EVERY response. No markdown, no explanation outside JSON.

When you need to USE A TOOL, respond with:
```json
{{
    "thought": "Your reasoning about what to do next and why",
    "action": {{
        "tool": "tool_name_from_list_above",
        "parameters": {{"param1": "value1"}}
    }}
}}
```

When you have ENOUGH INFORMATION to provide a final answer, respond with:
```json
{{
    "thought": "I now have sufficient information to answer comprehensively.",
    "final_answer": true,
    "summary": "Comprehensive research summary based on all gathered information"
}}
```

## Rules

1. ALWAYS think before acting. Explain your reasoning in the "thought" field.
2. Use MULTIPLE tools across multiple steps to gather comprehensive information.
3. Start with web_search to find primary sources, then summarize the most relevant ones.
4. Use semantic_search or document_search to find related information from local knowledge.
5. Use youtube_search and image_understanding to enrich findings with multimedia.
6. After gathering enough data (usually 3-6 steps), provide your final answer.
7. Be thorough but efficient — don't repeat the same searches.
8. Each tool call should serve a distinct research purpose.
"""


class ReActEngine:
    """
    ## Description

    Drives the iterative ReAct (Reason + Act) loop for autonomous
    research. In each step, the Gemini model reasons about the current
    state, selects a tool, the tool is executed, and the observation
    feeds back into the next reasoning step.

    ## Parameters

    - `gemini` (`Any`) — Async Gemini API client.
    - `tool_registry` (`ToolRegistry`) — Registry of available tools.
    - `max_steps` (`int`) — Maximum ReAct iterations. Default: 8.

    ## Returns

    `ReActEngine` instance.

    ## Side Effects

    - Calls Gemini API for each reasoning step.
    - Executes tools which may involve HTTP requests, vector queries, etc.
    - Invokes the optional ``on_step`` callback after each step.

    ## Customization

    Adjust ``max_steps`` or modify ``_build_system_prompt`` to change
    the agent's behavior and depth of research.
    """

    def __init__(
        self,
        gemini: Any,
        tool_registry: ToolRegistry,
        max_steps: int = MAX_REACT_STEPS,
    ) -> None:
        self.gemini = gemini
        self.tools = tool_registry
        self.max_steps = max_steps

    async def run(
        self,
        query: str,
        context: str = "",
        on_step: Optional[
            Callable[[ThinkingStep], Coroutine[Any, Any, None]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        ## Description

        Executes the full ReAct loop for a given query. Iteratively
        reasons, selects tools, executes them, and collects observations
        until the agent decides it has enough information or hits the
        step limit.

        ## Parameters

        - `query` (`str`)
          - Description: The research query to investigate.
          - Constraints: Must be non-empty.
          - Example: ``"What are the latest breakthroughs in quantum computing?"``

        - `context` (`str`)
          - Description: Additional context or constraints for the research.
          - Constraints: Can be empty.

        - `on_step` (`Optional[Callable[[ThinkingStep], Coroutine]]`)
          - Description: Async callback invoked after each ReAct step with
            the ``ThinkingStep`` data. Used for SSE event emission.
          - Constraints: Must be an async callable or None.

        ## Returns

        `Dict[str, Any]`

        Structure:

        ```json
        {
            "thinking_steps": [ThinkingStep, ...],
            "tool_results": [ToolResult, ...],
            "final_summary": "string or None",
            "sources": ["url1", "url2", ...],
            "videos": [{"title": "...", "url": "..."}],
            "images": [{"alt": "...", "url": "..."}],
            "scraped_content": [{"url": "...", "content": "..."}]
        }
        ```

        ## Raises

        - `Exception` — Propagated from tool execution failures.

        ## Side Effects

        - Multiple Gemini API calls (one per reasoning step).
        - Tool executions with external side effects.
        - ``on_step`` callback invocations.
        """
        system_prompt = _build_system_prompt(self.tools.get_tool_descriptions())

        thinking_steps: List[ThinkingStep] = []
        tool_results: List[ToolResult] = []
        all_sources: List[str] = []
        all_videos: List[Dict[str, str]] = []
        all_images: List[Dict[str, str]] = []
        all_scraped: List[Dict[str, Any]] = []
        final_summary: Optional[str] = None

        # Build the ongoing conversation for context accumulation
        conversation_history = f"Research Query: {query}\n"
        if context:
            conversation_history += f"Additional Context: {context}\n"
        conversation_history += "\nBegin your research. Respond with JSON.\n"

        for step_num in range(1, self.max_steps + 1):
            _log.info("[ReAct] Step %d/%d", step_num, self.max_steps)

            # --- THINK ---
            try:
                raw_response_text = await asyncGenerateContent(
                    prompt=conversation_history,
                    system=system_prompt,
                    model=GEMINI_MODEL,
                    image=None,
                    aclient=self.gemini,
                    json_schema={"type": "object"}
                )
                raw_response = _safe_json_loads(raw_response_text) or {}
            except Exception as exc:
                _log.error("[ReAct] Gemini call failed at step %d: %s", step_num, exc)
                # Try to get a text response as fallback
                try:
                    text_resp = await asyncGenerateContent(
                        prompt=conversation_history,
                        system=system_prompt,
                        model=GEMINI_MODEL,
                        image=None,
                        aclient=self.gemini
                    )
                    raw_response = _extract_json_from_text(text_resp)
                except Exception:
                    break

            if not raw_response:
                _log.warning("[ReAct] Empty response at step %d, breaking.", step_num)
                break

            thought = raw_response.get("thought", "")

            # --- Check for FINAL ANSWER ---
            if raw_response.get("final_answer"):
                step = ThinkingStep(
                    step=step_num,
                    thought=thought,
                    observation=raw_response.get("summary", ""),
                )
                thinking_steps.append(step)
                final_summary = raw_response.get("summary", thought)

                if on_step:
                    await on_step(step)

                _log.info("[ReAct] Final answer reached at step %d", step_num)
                break

            # --- ACT ---
            action_data = raw_response.get("action")
            if not action_data:
                _log.warning("[ReAct] No action in response at step %d", step_num)
                step = ThinkingStep(step=step_num, thought=thought)
                thinking_steps.append(step)
                if on_step:
                    await on_step(step)
                conversation_history += f"\nThought: {thought}\nYou did not specify an action. Please specify a tool to use or provide your final_answer.\n"
                continue

            # Parse tool call
            tool_name_str = action_data.get("tool", "")
            tool_params = action_data.get("parameters", {})

            try:
                tool_name = ToolName(tool_name_str)
            except ValueError:
                observation = f"Unknown tool '{tool_name_str}'. Available: {self.tools.available_tools}"
                step = ThinkingStep(
                    step=step_num,
                    thought=thought,
                    action=ToolCall(
                        tool=ToolName.WEB_SEARCH,
                        parameters=tool_params,
                        reasoning=thought,
                    ),
                    observation=observation,
                )
                thinking_steps.append(step)
                if on_step:
                    await on_step(step)
                conversation_history += f"\nThought: {thought}\nAction: {tool_name_str}\nObservation: {observation}\n"
                continue

            tool_call = ToolCall(
                tool=tool_name,
                parameters=tool_params,
                reasoning=thought,
            )

            # Execute tool
            tool_handler = self.tools.get(tool_name)
            if tool_handler is None:
                observation = f"Tool '{tool_name_str}' is registered but has no handler."
                step = ThinkingStep(
                    step=step_num,
                    thought=thought,
                    action=tool_call,
                    observation=observation,
                )
                thinking_steps.append(step)
                if on_step:
                    await on_step(step)
                conversation_history += f"\nThought: {thought}\nAction: {tool_name_str}({tool_params})\nObservation: {observation}\n"
                continue

            _log.info("[ReAct] Executing tool: %s", tool_name_str)
            result = await tool_handler.execute(tool_params)
            tool_results.append(result)

            # Process observations and accumulate data
            observation = _format_observation(result, tool_name)

            # Collect sources/media from results
            if result.success and result.data:
                if tool_name in (ToolName.WEB_SEARCH, ToolName.WEB_SCRAPE):
                    if isinstance(result.data, list):
                        for item in result.data:
                            if isinstance(item, dict):
                                url = item.get("url", "")
                                if url:
                                    all_sources.append(url)
                                all_scraped.append(item)

                elif tool_name == ToolName.YOUTUBE_SEARCH:
                    if isinstance(result.data, list):
                        all_videos.extend(result.data)

                elif tool_name == ToolName.IMAGE_UNDERSTANDING:
                    if isinstance(result.data, list):
                        all_images.extend(result.data)

                elif tool_name in (ToolName.SEMANTIC_SEARCH, ToolName.DOCUMENT_SEARCH):
                    if isinstance(result.data, dict):
                        sources = result.data.get("sources", [])
                        all_sources.extend(sources)

            step = ThinkingStep(
                step=step_num,
                thought=thought,
                action=tool_call,
                observation=observation[:2000],
            )
            thinking_steps.append(step)

            if on_step:
                await on_step(step)

            # Append to conversation for next iteration
            conversation_history += (
                f"\nThought: {thought}\n"
                f"Action: {tool_name_str}({json.dumps(tool_params)})\n"
                f"Observation: {observation[:3000]}\n"
            )

        # If we exhausted steps without a final answer, summarize what we have
        if not final_summary and thinking_steps:
            final_summary = thinking_steps[-1].thought

        return {
            "thinking_steps": thinking_steps,
            "tool_results": tool_results,
            "final_summary": final_summary,
            "sources": list(set(all_sources)),
            "videos": all_videos,
            "images": all_images,
            "scraped_content": all_scraped,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_observation(result: ToolResult, tool_name: ToolName) -> str:
    """
    ## Description

    Formats a ``ToolResult`` into a human-readable observation string
    for injection into the ReAct conversation context.

    ## Parameters

    - `result` (`ToolResult`) — The tool execution result.
    - `tool_name` (`ToolName`) — The tool that produced the result.

    ## Returns

    `str` — Formatted observation text.
    """
    if not result.success:
        return f"Tool '{tool_name.value}' FAILED: {result.error}"

    data = result.data
    if data is None:
        return f"Tool '{tool_name.value}' returned no data."

    if tool_name in (ToolName.WEB_SEARCH, ToolName.WEB_SCRAPE):
        if isinstance(data, list):
            parts = []
            for i, item in enumerate(data[:5]):
                title = item.get("title", "No Title")
                url = item.get("url", "")
                content_preview = (item.get("content", ""))[:300]
                parts.append(f"[{i+1}] {title} ({url})\n{content_preview}...")
            return f"Found {len(data)} pages:\n" + "\n\n".join(parts)
        return str(data)

    if tool_name == ToolName.SUMMARIZER:
        return f"Summary:\n{data}"

    if tool_name in (ToolName.SEMANTIC_SEARCH, ToolName.DOCUMENT_SEARCH):
        if isinstance(data, dict):
            total = data.get("total", 0)
            results = data.get("results", [])
            parts = []
            for r in results[:5]:
                doc_preview = (r.get("document", ""))[:200]
                source = r.get("metadata", {}).get("source", "unknown")
                parts.append(f"- [{source}] {doc_preview}...")
            return f"Found {total} results in vector store:\n" + "\n".join(parts)
        return str(data)

    if tool_name == ToolName.YOUTUBE_SEARCH:
        if isinstance(data, list):
            parts = [f"- {v.get('title', '?')} → {v.get('url', '?')}" for v in data[:5]]
            return f"Found {len(data)} videos:\n" + "\n".join(parts)
        return str(data)

    if tool_name == ToolName.IMAGE_UNDERSTANDING:
        if isinstance(data, list):
            parts = [f"- {img.get('alt', '?')} → {img.get('url', '?')}" for img in data[:5]]
            return f"Found {len(data)} images:\n" + "\n".join(parts)
        return str(data)

    return json.dumps(data, default=str)[:2000]


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    ## Description

    Attempts to extract a JSON object from a text response that may
    contain markdown code fences or other non-JSON content.

    ## Parameters

    - `text` (`str`) — Raw text that may contain embedded JSON.

    ## Returns

    `Dict[str, Any]` — Parsed JSON, or empty dict on failure.
    """
    if not text:
        return {}

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from code fences
    import re

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON object
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    return {}
