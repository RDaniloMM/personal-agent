"""LLM-driven idea extraction — shared across all workers.

Uses the LLM to identify key insights from collected data
and calls ``write_idea_note`` for each one.
"""

from __future__ import annotations

import json
from typing import Any

import openai
from loguru import logger

from shared.config import Settings
from shared.prompts.obsidian_skill import OBSIDIAN_FORMATTING_SKILL
from shared.storage.obsidian import write_idea_note


# ── LLM tool definition ─────────────────────────────────────────────────────

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


_SYSTEM = f"""You are a research analyst assistant. You've just received today's
data collection. Your task:

1. Review ALL the data provided.
2. Identify the 2-5 most important findings, emerging trends, or connections.
3. For marketplace items: only note truly interesting anomalies or deals.
4. For YouTube: note viral or groundbreaking videos.
5. For papers: focus on AI agents & evaluation breakthroughs.
6. Call the `write_idea_note` tool for each insight worth recording.
7. If nothing is noteworthy, call the tool once with a brief "nothing notable today" note.

Write notes in Spanish. Be concise but insightful.

{OBSIDIAN_FORMATTING_SKILL}

IMPORTANTE: En el contenido de cada nota, usa formato Obsidian completo:
- Incluye [[wiki-links]] para conceptos, autores y frameworks
- Usa callouts (> [!tip], > [!note]) para resaltar hallazgos
- Usa **negrita** y ==resaltado== para info clave
- Añade tags inline relevantes (#ia/agentes, #tendencia, etc.)"""


async def extract_ideas(
    data_summary: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Use LLM with tool calling to extract key ideas from a data summary.

    Args:
        data_summary: Pre-built text describing today's collected data.
        settings: App settings with LLM credentials.

    Returns:
        List of idea dicts with title, content, tags.
    """
    client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

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


async def extract_and_write_ideas(
    data_summary: str,
    settings: Settings,
) -> list[str]:
    """Extract ideas via LLM and write them to Obsidian. Returns note paths."""
    ideas = await extract_ideas(data_summary, settings)
    paths: list[str] = []
    for idea in ideas:
        try:
            path = write_idea_note(
                title=idea["title"],
                content=idea["content"],
                tags=idea["tags"],
                settings=settings,
            )
            paths.append(path)
        except Exception as exc:
            logger.warning("Failed to write idea note: {}", exc)
    return paths
