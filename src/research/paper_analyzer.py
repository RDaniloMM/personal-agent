"""LLM-powered paper analysis: relevance classification & key-point extraction.

Given a batch of Arxiv papers, the LLM evaluates relevance against the
user's research interests and extracts structured key points for relevant ones.
Uses Groq API (OpenAI-compatible) for fast inference.
"""

from __future__ import annotations

import json
from typing import Any, Literal

import openai
from loguru import logger
from pydantic import BaseModel, Field

from src.config import Settings
from src.prompts.obsidian_skill import OBSIDIAN_FORMATTING_SKILL


# ── Pydantic models for structured LLM output ────────────────────────────────

class TriageItem(BaseModel):
    """Relevance classification for a single paper."""

    arxiv_id: str
    relevance: Literal["high", "medium", "low"]


class TriageResponse(BaseModel):
    """Wrapper for the triage response array."""

    papers: list[TriageItem]


class AnalysisItem(BaseModel):
    """Full analysis of a single paper."""

    arxiv_id: str
    summary: str = Field(default="", description="2-3 sentence summary in Spanish")
    conclusions: str = Field(default="", description="Bullet points separated by newlines")
    contributions: str = Field(default="", description="Bullet points separated by newlines")
    key_takeaways: str = Field(default="", description="2-3 actionable bullet points")


class AnalysisResponse(BaseModel):
    """Wrapper for the analysis response array."""

    papers: list[AnalysisItem]

# ── Research interests (used to judge relevance) ─────────────────────────

RESEARCH_INTERESTS = """\
- AI agents / agentic systems / autonomous architectures
- LLM evaluation, benchmarks, agent evaluation
- Function/tool calling in LLMs
- Multi-agent systems"""

# ── Phase 1: quick relevance triage (cheap – small output) ────────────────────

_TRIAGE_SYSTEM = f"""Score each paper's relevance to these interests:
{RESEARCH_INTERESTS}

Return a JSON object with a "papers" key containing an array.
Each element: {{"arxiv_id":"...","relevance":"high"|"medium"|"low"}}
Example: {{"papers": [{{"arxiv_id": "2503.00001", "relevance": "high"}}]}}"""

# ── Phase 2: full analysis (only for relevant papers) ─────────────────────────

_ANALYSIS_SYSTEM = f"""Analyze each paper. Return a JSON object with a "papers" key containing an array.
Each element must have:
- arxiv_id: string
- summary: 2-3 sentences (Spanish)
- conclusions: bullet points (Spanish, separated by \\n)
- contributions: bullet points (Spanish, separated by \\n)
- key_takeaways: 2-3 actionable bullet points (Spanish, separated by \\n)

Use [[wiki-links]] for key concepts, **bold** for important terms.
Example: {{"papers": [{{"arxiv_id": "...", "summary": "...", "conclusions": "...", "contributions": "...", "key_takeaways": "..."}}]}}
Write in Spanish.

{OBSIDIAN_FORMATTING_SKILL}"""

# Max abstract chars sent to the LLM per paper
_ABSTRACT_LIMIT = 300

# ── Batch sizes ──────────────────────────────────────────────────────────────
_TRIAGE_BATCH = 20   # triage is cheap – bigger batches
_ANALYSIS_BATCH = 8  # full analysis – smaller batches


async def analyze_papers(
    papers: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Two-phase analysis: cheap triage → full analysis on relevant only.

    Phase 1 (triage): classify all papers as high/medium/low with a small prompt.
    Phase 2 (analysis): generate full summaries only for high+medium papers.
    This saves ~60-80% of output tokens compared to the single-pass approach.
    """
    if not papers:
        return []

    client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    # ── Phase 1: Triage (cheap) ───────────────────────────────────
    relevance_map: dict[str, str] = {}
    for i in range(0, len(papers), _TRIAGE_BATCH):
        batch = papers[i : i + _TRIAGE_BATCH]
        triage = await _triage_batch(batch, client, settings)
        for t in triage:
            relevance_map[t["arxiv_id"]] = t.get("relevance", "low")

    relevant_papers = [
        p for p in papers
        if relevance_map.get(p.get("arxiv_id", ""), "low") in ("high", "medium")
    ]

    high_count = sum(1 for v in relevance_map.values() if v == "high")
    medium_count = sum(1 for v in relevance_map.values() if v == "medium")
    low_count = sum(1 for v in relevance_map.values() if v == "low")
    logger.info(
        "Triage: {} high, {} medium, {} low → {} to analyze",
        high_count, medium_count, low_count, len(relevant_papers),
    )

    if not relevant_papers:
        return []

    # ── Phase 2: Full analysis (only relevant) ────────────────────
    all_analyses: dict[str, dict[str, Any]] = {}
    for i in range(0, len(relevant_papers), _ANALYSIS_BATCH):
        batch = relevant_papers[i : i + _ANALYSIS_BATCH]
        analyses = await _analysis_batch(batch, client, settings)
        for a in analyses:
            all_analyses[a["arxiv_id"]] = a

    # Merge analysis + relevance back into original paper data
    enriched: list[dict[str, Any]] = []
    for paper in relevant_papers:
        aid = paper.get("arxiv_id", "")
        analysis = all_analyses.get(aid, {})
        enriched.append({
            **paper,
            **analysis,
            "relevance": relevance_map.get(aid, "medium"),
        })

    logger.info(
        "Paper analysis complete: {} high, {} medium, {} low → {} enriched",
        high_count, medium_count, low_count, len(enriched),
    )
    return enriched


# ── Phase helpers ────────────────────────────────────────────────────────────


def _paper_snippet(p: dict[str, Any], abstract_limit: int = _ABSTRACT_LIMIT) -> str:
    """Compact text repr of a paper for the LLM."""
    abstract = (p.get("abstract", "") or "")[:abstract_limit]
    cats = ",".join(p.get("categories", []))
    return f"{p.get('arxiv_id','')}: [{cats}] {p.get('title','')}. {abstract}"


def _parse_triage(content: str) -> list[TriageItem]:
    """Parse & validate triage JSON via Pydantic."""
    data = json.loads(content)
    # Handle both {"papers": [...]} and bare [...]
    if isinstance(data, list):
        data = {"papers": data}
    return TriageResponse.model_validate(data).papers


def _parse_analysis(content: str) -> list[AnalysisItem]:
    """Parse & validate analysis JSON via Pydantic."""
    data = json.loads(content)
    if isinstance(data, list):
        data = {"papers": data}
    return AnalysisResponse.model_validate(data).papers


async def _triage_batch(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _retries: int = 2,
) -> list[dict[str, Any]]:
    """Phase 1: quick relevance classification. Minimal tokens."""
    import asyncio

    papers_text = "\n".join(_paper_snippet(p) for p in papers)
    last_exc: Exception | None = None

    for attempt in range(_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": _TRIAGE_SYSTEM},
                    {"role": "user", "content": papers_text},
                ],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            items = _parse_triage(response.choices[0].message.content or '{"papers":[]}')
            return [item.model_dump() for item in items]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Triage parse/validation failed (attempt {}): {}", attempt + 1, exc)
            last_exc = exc
        except openai.BadRequestError as exc:
            # Groq returns 400 when json_object mode produces empty output
            logger.warning("Triage JSON generation failed (attempt {}): {}", attempt + 1, exc)
            last_exc = exc
        except Exception as exc:
            logger.error("Triage LLM call failed: {}", exc)
            return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "low"} for p in papers]

        if attempt < _retries:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s backoff

    # All retries exhausted – safe fallback: classify as medium so they still get analyzed
    logger.warning("Triage exhausted {} retries, falling back to medium", _retries + 1)
    return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "medium"} for p in papers]


async def _analysis_batch(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Phase 2: full analysis of already-triaged relevant papers."""
    papers_text = "\n\n".join(
        f"---\narxiv_id: {p.get('arxiv_id', '')}\n"
        f"title: {p.get('title', '')}\n"
        f"abstract: {(p.get('abstract', '') or '')[:500]}\n---"
        for p in papers
    )
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {"role": "user", "content": f"Analyze:\n{papers_text}"},
            ],
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        items = _parse_analysis(response.choices[0].message.content or '{"papers":[]}')
        return [item.model_dump() for item in items]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Analysis parse/validation failed: {}", exc)
        return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "low",
                 "summary": "", "conclusions": "",
                 "contributions": "", "key_takeaways": ""} for p in papers]
    except Exception as exc:
        logger.error("Analysis LLM call failed: {}", exc)
        return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "low",
                 "summary": "", "conclusions": "",
                 "contributions": "", "key_takeaways": ""} for p in papers]
