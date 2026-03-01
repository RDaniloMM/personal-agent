"""LangGraph node: write Obsidian notes + LLM-generated key ideas.

Uses *Pragmatic Tool Calling*: the LLM decides which ideas to extract
and how to annotate them based on the collected data, rather than
mechanically writing everything.  Uses Groq API for fast inference.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState
from src.prompts.obsidian_skill import OBSIDIAN_FORMATTING_SKILL


# ── LLM tool definitions for pragmatic tool calling ──────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_idea_note",
            "description": (
                "Write an insight / key idea note to the Obsidian vault. "
                "Use this when you identify a non-obvious insight, trend, or "
                "connection across the data collected today."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the idea (max 80 chars)",
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Markdown body of the idea note. Include reasoning, "
                            "cross-references ([[links]]), and actionable takeaways."
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Relevant tags (without #): e.g. ['agent', 'evaluation']",
                    },
                },
                "required": ["title", "content", "tags"],
            },
        },
    }
]

# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM = f"""You are a research analyst assistant. You've just received today's
data collection from three sources: Facebook Marketplace listings (gadgets,
electronics, books), YouTube videos, and Arxiv AI research papers.

Your task:
1. Review ALL the data provided.
2. For Arxiv papers: identify the 3-5 most important findings, emerging trends,
   or connections between papers. Focus on AI agents & evaluation.
3. For marketplace/YouTube: only note truly interesting anomalies or trends
   (e.g. unusually cheap laptops, viral AI videos).
4. Call the `write_idea_note` tool for each insight worth recording.
5. If nothing is noteworthy, call the tool once with a brief "nothing notable today" note.

Write notes in Spanish. Be concise but insightful.

{OBSIDIAN_FORMATTING_SKILL}

IMPORTANTE: En el contenido de cada nota, usa formato Obsidian completo:
- Incluye [[wiki-links]] para conceptos, autores y frameworks
- Usa callouts (> [!tip], > [!note]) para resaltar hallazgos
- Usa **negrita** y ==resaltado== para info clave
- Añade tags inline relevantes (#ia/agentes, #tendencia, etc.)"""


async def write_obsidian_node(state: AgentState) -> dict:
    """Node that writes Obsidian notes:

    1. Deterministic notes: paper notes, marketplace/YT daily summaries.
    2. LLM-driven notes: key ideas via pragmatic tool calling.
    """
    logger.info("═══ Node: write_obsidian ═══")
    settings = get_settings()
    notes: list[str] = []

    # ── 1. Deterministic writes ──────────────────────────────────────────

    from src.storage.obsidian import (
        write_arxiv_paper,
        write_idea_note,
        write_marketplace_summary,
        write_youtube_summary,
    )

    # Paper notes — first analyze with LLM, then write only relevant ones
    papers_to_write = state.arxiv_papers
    if state.arxiv_papers:
        try:
            from src.research.paper_analyzer import analyze_papers

            analyzed = await analyze_papers(state.arxiv_papers, settings)
            logger.info(
                "LLM classified {}/{} papers as relevant",
                len(analyzed), len(state.arxiv_papers),
            )
            papers_to_write = analyzed
        except Exception as exc:
            logger.warning("Paper analysis failed, writing all papers raw: {}", exc)

    for paper in papers_to_write:
        try:
            path = write_arxiv_paper(paper, settings)
            notes.append(path)
        except Exception as exc:
            logger.warning("Failed to write paper note: {}", exc)

    # Daily summaries
    if state.marketplace_listings:
        try:
            path = write_marketplace_summary(state.marketplace_listings, settings)
            notes.append(path)
        except Exception as exc:
            logger.warning("Failed to write marketplace summary: {}", exc)

    if state.youtube_videos:
        try:
            path = write_youtube_summary(state.youtube_videos, settings)
            notes.append(path)
        except Exception as exc:
            logger.warning("Failed to write YT summary: {}", exc)

    # ── 2. LLM-driven idea extraction (Pragmatic Tool Calling) ───────────

    try:
        idea_notes = await _extract_ideas_with_llm(state, settings)
        for idea in idea_notes:
            path = write_idea_note(
                title=idea["title"],
                content=idea["content"],
                tags=idea["tags"],
                settings=settings,
            )
            notes.append(path)
    except Exception as exc:
        logger.warning("LLM idea extraction failed: {}", exc)

    logger.info("Obsidian node wrote {} notes total", len(notes))
    return {"notes_written": notes}


async def _extract_ideas_with_llm(
    state: AgentState, settings: "Settings"
) -> list[dict[str, Any]]:
    """Use LLM with tool calling to extract key ideas from today's data."""
    import openai

    client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    # Build a concise data summary for the LLM
    data_summary = _build_data_summary(state)

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    "Here is today's collected data:\n\n"
                    f"{data_summary}\n\n"
                    "Analyze it and call `write_idea_note` for each key insight."
                ),
            },
        ],
        tools=_TOOLS,
        tool_choice="auto",
        max_tokens=4096,
    )

    # Parse tool calls from the response
    ideas: list[dict[str, Any]] = []
    message = response.choices[0].message

    if message.tool_calls:
        for call in message.tool_calls:
            if call.function.name == "write_idea_note":
                try:
                    args = json.loads(call.function.arguments)
                    ideas.append(args)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse tool call args")

    logger.info("LLM extracted {} idea notes", len(ideas))
    return ideas


def _build_data_summary(state: AgentState) -> str:
    """Create a concise text summary of all collected data for the LLM."""
    sections: list[str] = []

    if state.arxiv_papers:
        papers_text = "\n".join(
            f"- **{p.get('title', '')}** ({p.get('arxiv_id', '')}): "
            f"{p.get('abstract', '')[:200]}…"
            for p in state.arxiv_papers[:15]
        )
        sections.append(f"## Arxiv Papers ({len(state.arxiv_papers)} total)\n{papers_text}")

    if state.marketplace_listings:
        listings_text = "\n".join(
            f"- {l.get('title', '')} – {l.get('price', '')} en {l.get('location', '')}"
            for l in state.marketplace_listings[:20]
        )
        sections.append(
            f"## FB Marketplace ({len(state.marketplace_listings)} listings)\n{listings_text}"
        )

    if state.youtube_videos:
        videos_text = "\n".join(
            f"- {v.get('title', '')} ({v.get('channel', '')})"
            for v in state.youtube_videos[:15]
        )
        sections.append(f"## YouTube ({len(state.youtube_videos)} videos)\n{videos_text}")

    if not sections:
        return "No data was collected in this run."

    return "\n\n".join(sections)
