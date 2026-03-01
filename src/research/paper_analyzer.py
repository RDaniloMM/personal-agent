"""LLM-powered paper analysis: relevance classification & key-point extraction.

Given a batch of Arxiv papers, GPT-5-mini evaluates relevance against the
user's research interests and extracts structured key points for relevant ones.
"""

from __future__ import annotations

import json
from typing import Any

import openai
from loguru import logger

from src.config import Settings

# ── Research interests (used to judge relevance) ─────────────────────────────

RESEARCH_INTERESTS = """
- AI agents and agentic systems
- Autonomous agent architectures (planning, tool-use, memory)
- LLM evaluation and benchmarks
- Agent evaluation frameworks and metrics
- Function calling / tool calling in LLMs
- Multi-agent systems
- Retrieval-augmented generation (RAG)
- Prompt engineering and reasoning strategies
"""

# ── System prompt for relevance + extraction ─────────────────────────────────

_SYSTEM = f"""You are a research paper analyst. The user's research interests are:

{RESEARCH_INTERESTS}

For each paper provided, you MUST:
1. Evaluate how relevant it is to the user's interests above.
2. Assign a relevance score: "high", "medium", or "low".
3. For papers scored "high" or "medium", extract:
   - summary: A concise 2-3 sentence summary in Spanish
   - conclusions: The main conclusions / findings (in Spanish, bullet points)
   - contributions: What's novel or the key contributions (in Spanish, bullet points)
   - key_takeaways: 2-3 actionable takeaways for the user (in Spanish)
4. For "low" relevance papers, still provide a 1-sentence summary.

Respond with ONLY valid JSON (no markdown fences). Return an array of objects, one per paper.
Each object has:
- arxiv_id: string
- relevance: "high" | "medium" | "low"
- summary: string
- conclusions: string (bullet points with \\n)
- contributions: string (bullet points with \\n)
- key_takeaways: string (bullet points with \\n)

Write ALL analysis text in Spanish."""

# ── Batch size for LLM calls (avoid context overflow) ────────────────────────
_BATCH_SIZE = 10


async def analyze_papers(
    papers: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Analyze a list of papers for relevance and extract key points.

    Returns a list of analysis dicts keyed by arxiv_id, merged with original
    paper data. Only papers with "high" or "medium" relevance are returned.
    """
    if not papers:
        return []

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    all_analyses: dict[str, dict[str, Any]] = {}

    # Process in batches
    for i in range(0, len(papers), _BATCH_SIZE):
        batch = papers[i : i + _BATCH_SIZE]
        batch_analyses = await _analyze_batch(batch, client, settings)
        for analysis in batch_analyses:
            all_analyses[analysis["arxiv_id"]] = analysis

    # Merge analysis into original paper data, filter by relevance
    enriched: list[dict[str, Any]] = []
    high_count = 0
    medium_count = 0
    low_count = 0

    for paper in papers:
        aid = paper.get("arxiv_id", "")
        analysis = all_analyses.get(aid, {})
        relevance = analysis.get("relevance", "low")

        if relevance == "high":
            high_count += 1
        elif relevance == "medium":
            medium_count += 1
        else:
            low_count += 1

        if relevance in ("high", "medium"):
            enriched_paper = {**paper, **analysis}
            enriched.append(enriched_paper)

    logger.info(
        "Paper analysis: {} high, {} medium, {} low → {} relevant",
        high_count, medium_count, low_count, len(enriched),
    )
    return enriched


async def _analyze_batch(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Send a batch of papers to the LLM for analysis."""
    papers_text = "\n\n".join(
        f"---\narxiv_id: {p.get('arxiv_id', '')}\n"
        f"title: {p.get('title', '')}\n"
        f"categories: {', '.join(p.get('categories', []))}\n"
        f"abstract: {p.get('abstract', '')}\n---"
        for p in papers
    )

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Analyze these {len(papers)} papers:\n\n{papers_text}"
                    ),
                },
            ],
            max_completion_tokens=8192,
        )

        content = response.choices[0].message.content or "[]"

        # Strip markdown fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        analyses = json.loads(content)
        if not isinstance(analyses, list):
            analyses = [analyses]

        return analyses

    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM analysis JSON: {}", exc)
        # Return minimal analysis for all papers
        return [
            {"arxiv_id": p.get("arxiv_id", ""), "relevance": "medium",
             "summary": "Análisis no disponible", "conclusions": "",
             "contributions": "", "key_takeaways": ""}
            for p in papers
        ]
    except Exception as exc:
        logger.error("LLM paper analysis failed: {}", exc)
        return [
            {"arxiv_id": p.get("arxiv_id", ""), "relevance": "medium",
             "summary": "Error en análisis", "conclusions": "",
             "contributions": "", "key_takeaways": ""}
            for p in papers
        ]
