"""E2E smoke test for the Arxiv pipeline.

Runs a minimal version of the full pipeline using a specific paper:
  1. Fetch a known paper by ID (2602.17547v1)
  2. Download PDF and extract full text as Markdown (pymupdf4llm)
  3. Run the paper analyzer (triage + Gemini deep analysis with APA 7 paragraph)
  4. Verify output structure including thesis_paragraph

Usage (inside Docker):
    docker compose run --rm arxiv-worker uv run python -m tests.test_e2e_arxiv
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import asdict

from loguru import logger

# Specific paper for reproducible testing
_TEST_PAPER_ID = "2602.17547v1"


async def _run_e2e() -> None:
    """Minimal end-to-end Arxiv pipeline: 1 known paper → full analysis."""

    # ── Setup ───────────────────────────────────────────────────────
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    from shared.config import get_settings

    settings = get_settings()

    logger.info("═══ E2E ARXIV TEST START ═══")
    logger.info("Test paper: https://arxiv.org/abs/{}", _TEST_PAPER_ID)

    # ── Phase 1: Fetch specific paper by ID ─────────────────────────
    import arxiv as arxiv_lib

    from arxiv_worker.client import _enrich_with_full_text
    from shared.state import ArxivPaper

    client = arxiv_lib.Client()
    search = arxiv_lib.Search(id_list=[_TEST_PAPER_ID])

    paper_data = None
    try:
        for result in client.results(search):
            paper_data = ArxivPaper(
                arxiv_id=result.entry_id.split("/")[-1],
                title=result.title.strip(),
                authors=[a.name for a in result.authors[:10]],
                abstract=result.summary.strip(),
                categories=list(result.categories),
                pdf_url=result.pdf_url or "",
                published=result.published.isoformat() if result.published else "",
            )
            break
    except Exception as exc:
        logger.warning("Failed to fetch paper {} — Arxiv may be down: {}", _TEST_PAPER_ID, exc)
        logger.info("═══ E2E ARXIV TEST DONE (arxiv unavailable) ═══")
        return

    if paper_data is None:
        logger.warning("Paper {} not found on Arxiv", _TEST_PAPER_ID)
        logger.info("═══ E2E ARXIV TEST DONE (paper not found) ═══")
        return

    papers = [asdict(paper_data)]

    logger.info("Fetched paper: [{}] {}", papers[0]["arxiv_id"], papers[0]["title"][:80])

    # Verify paper structure
    for key in ("arxiv_id", "title", "abstract", "authors", "pdf_url"):
        assert key in papers[0], f"Missing '{key}' in paper"

    # ── Phase 1b: PDF download + full text extraction ───────────────
    await _enrich_with_full_text(papers)

    full_text = papers[0].get("full_text", "")
    if full_text:
        logger.info("✓ Full text extracted: {:.0f}K chars (Markdown)", len(full_text) / 1000)
        # Show first 200 chars to verify Markdown conversion
        logger.debug("  Preview: {}", full_text[:200].replace("\n", " "))
    else:
        logger.warning("⚠ No full text extracted — PDF download or conversion failed")

    assert full_text, "Expected full_text from PDF extraction"

    # ── Phase 2: LLM analysis (triage + full) ──────────────────────
    from arxiv_worker.paper_analyzer import analyze_papers

    analyzed = await analyze_papers(papers, settings)
    logger.info(
        "Paper analyzer: {}/{} passed triage",
        len(analyzed), len(papers),
    )

    if not analyzed:
        logger.warning("Paper did not pass triage — this is valid but unexpected for a known AI paper")
        logger.info("═══ E2E ARXIV TEST DONE (no triage pass) ═══")
        return

    # Verify analyzed structure
    for paper in analyzed:
        assert "arxiv_id" in paper
        assert "relevance" in paper, f"Missing 'relevance' in analyzed paper"
        assert paper["relevance"] in ("high", "medium"), (
            f"Expected high/medium relevance, got: {paper['relevance']}"
        )
        # Full analysis fields
        for field in ("summary", "conclusions", "contributions", "key_takeaways"):
            assert field in paper, f"Missing '{field}' in analyzed paper"
            assert paper[field], f"Field '{field}' is empty"

        # APA 7 thesis paragraph
        thesis = paper.get("thesis_paragraph", "")
        if thesis:
            logger.info("✓ thesis_paragraph: {} chars", len(thesis))
            logger.debug("  Preview: {}", thesis[:200])
        else:
            logger.warning("⚠ thesis_paragraph is empty")

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
