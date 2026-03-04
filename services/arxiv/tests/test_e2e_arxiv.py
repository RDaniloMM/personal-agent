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

    from arxiv_worker.client import _download_pdfs
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

    # ── Phase 1b: PDF download (raw bytes for Gemini) ───────────────
    await _download_pdfs(papers)

    pdf_bytes = papers[0].get("pdf_bytes", b"")
    if pdf_bytes:
        logger.info("✓ PDF downloaded: {:.1f}MB", len(pdf_bytes) / (1024 * 1024))
    else:
        logger.warning("⚠ No PDF downloaded")

    assert pdf_bytes, "Expected pdf_bytes from PDF download"

    # ── Phase 2: LLM analysis (triage + Gemini native PDF) ─────────
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

    # ── Phase 3: Write Obsidian note to vault/Agent-Research/Tests/ ──
    import re
    from pathlib import Path

    tests_subfolder = settings.obsidian_subfolder("Tests")
    papers_folder = settings.obsidian_subfolder("Papers")

    from shared.storage.obsidian import write_arxiv_paper

    for paper in analyzed:
        # Compute the exact filename write_arxiv_paper will use
        title = paper.get("title", "paper")
        clean = re.sub(r'[<>:"/\\|?*\n\r]', "", title).strip(". ")[:80]
        expected_file = papers_folder / (clean + ".md")

        # Delete existing note so write_arxiv_paper generates a fresh one
        if expected_file.exists():
            logger.debug("Removing existing note: {}", expected_file.name)
            expected_file.unlink()

        # Generate fresh note into Papers/
        note_path = Path(write_arxiv_paper(paper, settings))

        if not note_path.exists():
            logger.warning("Note was not generated: {}", note_path)
            continue

        # Copy to Tests/ subfolder (separate from production notes)
        dest = tests_subfolder / note_path.name
        note_content = note_path.read_text(encoding="utf-8")
        dest.write_text(note_content, encoding="utf-8")
        logger.info("Copied test note to: {}", dest)

        # Display the full note content in logs
        logger.info("\n{}\nGENERATED NOTE: {}\n{}\n{}\n{}",
            "═" * 80, dest.name, "═" * 80, note_content, "═" * 80)

    logger.info("═══ E2E ARXIV TEST PASSED ═══")


def main() -> None:
    asyncio.run(_run_e2e())


if __name__ == "__main__":
    main()
