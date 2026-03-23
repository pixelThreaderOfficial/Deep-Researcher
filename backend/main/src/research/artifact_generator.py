"""
artifact_generator.py — Deep Researcher v2
============================================
Generates the final structured research artifact (markdown report)
from accumulated findings, media, and reasoning traces.

## Description

Takes research findings, YouTube videos, images, and the original
query, then produces a comprehensive ``Artifact`` with structured
sections, key insights, and a full markdown document.

## Side Effects

- Calls the Gemini API for artifact generation.

## Customization

Modify the system instruction to change artifact format and structure.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from main.src.utils.llms.gemini.DRGeminiWrapper import asyncGenerateContent, _safe_json_loads
from main.src.research.models import Artifact, ArtifactSection

_log = logging.getLogger(__name__)

ARTIFACT_MODEL = "gemini-2.5-flash-preview-05-20"


class ArtifactGenerator:
    """
    ## Description

    Generates the final research artifact by feeding accumulated
    findings, media, and context to Gemini with a structured output
    requirement.

    ## Parameters

    - `gemini` (`Any`) — Async Gemini API client.

    ## Returns

    `ArtifactGenerator` instance.

    ## Customization

    Modify the system instruction or model to change artifact format.
    """

    def __init__(self, gemini: Any) -> None:
        self.gemini = gemini

    async def generate(
        self,
        query: str,
        findings: List[Dict[str, Any]],
        videos: List[Dict[str, str]],
        images: List[Dict[str, str]],
    ) -> Artifact:
        """
        ## Description

        Produces a comprehensive, structured research artifact from
        accumulated findings, videos, and images.

        ## Parameters

        - `query` (`str`)
          - Description: The original or refined research query.
          - Constraints: Must be non-empty.

        - `findings` (`List[Dict[str, Any]]`)
          - Description: List of research findings, each with ``source`` and ``summary``.
          - Constraints: Can be empty (will produce minimal artifact).

        - `videos` (`List[Dict[str, str]]`)
          - Description: YouTube video references with ``title`` and ``url``.

        - `images` (`List[Dict[str, str]]`)
          - Description: Image references with ``alt`` and ``url``.

        ## Returns

        `Artifact` — The structured research deliverable.

        ## Raises

        - `Exception` — On Gemini API failures (falls back to minimal artifact).

        ## Side Effects

        - Makes an async Gemini API call.
        """
        system_instruction = """You are a Research Artifact Generator.
Your goal is to produce a HIGH-VALUE, structured research deliverable.

CRITICAL: You must also generate a 'markdown_content' field which is a PURE MARKDOWN FILE.
The markdown MUST include:
- A clear title and summary
- Key insights as a bulleted list
- Detailed sections with headings (## Heading)
- Embedded YouTube videos (using markdown links: [Video Title](url))
- Multiple images (using markdown image syntax: ![alt](url))
- Highlighted content (using > blockquotes or **bolding**)
- A sources section with linked references
- Confidence assessment

Return a JSON object with this EXACT structure:
{
    "title": "Research Report Title",
    "type": "research_report",
    "summary": "Executive summary paragraph",
    "key_insights": ["insight 1", "insight 2", "insight 3"],
    "detailed_sections": [
        {"heading": "Section Title", "content": "Section markdown content"}
    ],
    "actionable_steps": ["step 1", "step 2"],
    "sources": ["url1", "url2"],
    "highlights": ["notable quote or finding"],
    "confidence_score": "high | medium | low",
    "markdown_content": "# Full Markdown Document\\n\\n..."
}"""

        prompt = f"""Original Query: {query}

Research Findings:
{_format_findings(findings)}

Relevant Videos:
{_format_videos(videos)}

Relevant Images:
{_format_images(images)}

Generate the artifact. Ensure the 'markdown_content' is comprehensive, well-structured, and ready-to-use as a standalone document."""

        try:
            artifact_text = await asyncGenerateContent(
                prompt=prompt,
                system=system_instruction,
                model=ARTIFACT_MODEL,
                image=None,
                aclient=self.gemini,
                json_schema={"type": "object"}
            )
            artifact_data = _safe_json_loads(artifact_text) or {}

            # Parse sections
            sections = []
            for s in artifact_data.get("detailed_sections", []):
                if isinstance(s, dict):
                    sections.append(
                        ArtifactSection(
                            heading=s.get("heading", ""),
                            content=s.get("content", ""),
                        )
                    )

            return Artifact(
                title=artifact_data.get("title", f"Research: {query[:50]}"),
                type=artifact_data.get("type", "research_report"),
                summary=artifact_data.get("summary", ""),
                key_insights=artifact_data.get("key_insights", []),
                detailed_sections=sections,
                actionable_steps=artifact_data.get("actionable_steps", []),
                sources=artifact_data.get("sources", []),
                videos=[{"title": v.get("title", ""), "url": v.get("url", "")} for v in videos],
                images=[{"alt": i.get("alt", ""), "url": i.get("url", "")} for i in images],
                highlights=artifact_data.get("highlights", []),
                markdown_content=artifact_data.get("markdown_content"),
                confidence_score=artifact_data.get("confidence_score", "medium"),
            )

        except Exception as exc:
            _log.error("[ArtifactGenerator] Generation failed: %s", exc)
            # Fallback: minimal artifact from findings
            return Artifact(
                title=f"Research: {query[:80]}",
                summary=f"Research on: {query}. {len(findings)} sources analyzed.",
                key_insights=[f"Analyzed {len(findings)} sources"],
                sources=[f.get("source", "") for f in findings if f.get("source")],
                videos=[{"title": v.get("title", ""), "url": v.get("url", "")} for v in videos],
                images=[{"alt": i.get("alt", ""), "url": i.get("url", "")} for i in images],
                confidence_score="low",
            )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_findings(findings: List[Dict[str, Any]]) -> str:
    """
    ## Description

    Formats a list of finding dicts into a readable string for
    the artifact prompt.

    ## Parameters

    - `findings` (`List[Dict[str, Any]]`) — Research findings.

    ## Returns

    `str` — Formatted findings text.
    """
    if not findings:
        return "No findings collected."

    parts = []
    for i, f in enumerate(findings[:15], 1):
        source = f.get("source", "Unknown")
        summary = f.get("summary", "")[:500]
        parts.append(f"[{i}] Source: {source}\n{summary}")
    return "\n\n".join(parts)


def _format_videos(videos: List[Dict[str, str]]) -> str:
    """
    ## Description

    Formats video references for the artifact prompt.

    ## Parameters

    - `videos` (`List[Dict[str, str]]`) — Video metadata list.

    ## Returns

    `str`
    """
    if not videos:
        return "No videos found."
    return "\n".join(
        f"- {v.get('title', '?')} → {v.get('url', '?')}" for v in videos[:10]
    )


def _format_images(images: List[Dict[str, str]]) -> str:
    """
    ## Description

    Formats image references for the artifact prompt.

    ## Parameters

    - `images` (`List[Dict[str, str]]`) — Image metadata list.

    ## Returns

    `str`
    """
    if not images:
        return "No images found."
    return "\n".join(
        f"- {i.get('alt', '?')} → {i.get('url', '?')}" for i in images[:10]
    )
