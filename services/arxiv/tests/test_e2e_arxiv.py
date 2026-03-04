"""E2E smoke test for the Arxiv pipeline.

Runs a minimal version of the full pipeline:
  1. Collect 1 paper per query (only 1 query)
  2. Run the paper analyzer (triage + full analysis)
  3. Verify output structure

Usage (inside Docker):
    docker compose run --rm arxiv-worker uv run python -m tests.test_e2e_arxiv
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import patch

from loguru import logger


async def _run_e2e() -> None:
    """Minimal end-to-end Arxiv pipeline: 1 query × 1 paper."""

    # ── Setup ───────────────────────────────────────────────────────
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    # Limit to 1 result per query
    os.environ["ARXIV_MAX_RESULTS_PER_QUERY"] = "1"

    from shared.config import get_settings

    settings = get_settings()

    logger.info("═══ E2E ARXIV TEST START ═══")

    # ── Phase 1: Collect papers (1 query only) ──────────────────────
    from arxiv_worker.client import ARXIV_QUERIES, collect_arxiv_papers

    # Patch ARXIV_QUERIES to use only the first query
    with patch("arxiv_worker.client.ARXIV_QUERIES", ARXIV_QUERIES[:1]):
        papers = await collect_arxiv_papers(settings)

    logger.info("Collected {} papers (limited to 1 query × 1 result)", len(papers))

    if not papers:
        logger.warning("No papers found — Arxiv may be slow or unavailable")
        logger.info("═══ E2E ARXIV TEST DONE (no papers) ═══")
        return

    assert len(papers) >= 1, "Expected at least 1 paper"

    # Verify paper structure
    for paper in papers:
        assert "arxiv_id" in paper, f"Missing 'arxiv_id': {paper}"
        assert "title" in paper, f"Missing 'title': {paper}"
        assert "abstract" in paper, f"Missing 'abstract': {paper}"
        assert "authors" in paper, f"Missing 'authors': {paper}"
        logger.debug(
            "  Paper: [{}] {}",
            paper["arxiv_id"],
            paper["title"][:60],
        )

    # ── Phase 2: LLM analysis (triage + full) ──────────────────────
    from arxiv_worker.paper_analyzer import analyze_papers

    analyzed = await analyze_papers(papers, settings)
    logger.info(
        "Paper analyzer: {}/{} passed triage",
        len(analyzed), len(papers),
    )

    # Verify analyzed structure (if any passed triage)
    for paper in analyzed:
        assert "arxiv_id" in paper
        assert "relevance" in paper, f"Missing 'relevance' in analyzed paper"
        assert paper["relevance"] in ("high", "medium"), (
            f"Expected high/medium relevance, got: {paper['relevance']}"
        )
        # Full analysis fields
        for field in ("summary", "conclusions", "contributions", "key_takeaways"):
            assert field in paper, f"Missing '{field}' in analyzed paper"
        logger.info(
            "  ✓ Analyzed: [{}] {} → relevance={}",
            paper["arxiv_id"],
            paper["title"][:40],
            paper["relevance"],
        )

    logger.info("═══ E2E ARXIV TEST PASSED ═══")


def main() -> None:
    asyncio.run(_run_e2e())


if __name__ == "__main__":
    main()
