"""Arxiv paper collector using the arxiv.py library (free, no API key)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import arxiv
from loguru import logger

from shared.config import Settings
from shared.state import ArxivPaper

# ── Pre-defined queries ─────────────────────────────────────────────────────

ARXIV_QUERIES: list[str] = [
    # AI agents & agentic systems
    'cat:cs.AI AND (ti:"AI agent" OR ti:"agentic" OR ti:"autonomous agent")',
    # LLM evaluation & benchmarks
    'cat:cs.CL AND (ti:"evaluation" OR ti:"benchmark") AND (ti:"LLM" OR ti:"language model")',
    # Agent evaluation frameworks
    '(cat:cs.AI OR cat:cs.CL) AND ti:"agent" AND (ti:"evaluation" OR ti:"assessment")',
    # Tool use & function calling
    'cat:cs.CL AND (ti:"tool use" OR ti:"tool-use" OR ti:"function calling" OR ti:"tool calling")',
]


async def collect_arxiv_papers(settings: Settings) -> list[dict[str, Any]]:
    """Fetch recent papers from Arxiv matching pre-defined AI research queries.

    Returns a deduplicated list of paper dicts.
    """
    client = arxiv.Client(
        page_size=50,
        delay_seconds=3.0,
        num_retries=3,
    )

    all_papers: dict[str, dict[str, Any]] = {}  # keyed by arxiv_id for dedup

    for query in ARXIV_QUERIES:
        logger.info("Querying Arxiv: {}", query[:80])

        search = arxiv.Search(
            query=query,
            max_results=settings.arxiv_max_results_per_query,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        try:
            for result in client.results(search):
                paper = ArxivPaper(
                    arxiv_id=result.entry_id.split("/")[-1],
                    title=result.title.strip(),
                    authors=[a.name for a in result.authors[:10]],
                    abstract=result.summary.strip(),
                    categories=[c for c in result.categories],
                    pdf_url=result.pdf_url or "",
                    published=result.published.isoformat() if result.published else "",
                )
                if paper.arxiv_id not in all_papers:
                    all_papers[paper.arxiv_id] = asdict(paper)

        except Exception as exc:
            logger.error("Arxiv query failed for '{}': {}", query[:40], exc)

    papers_list = list(all_papers.values())
    logger.info(
        "Arxiv collection complete: {} unique papers from {} queries",
        len(papers_list),
        len(ARXIV_QUERIES),
    )
    return papers_list
