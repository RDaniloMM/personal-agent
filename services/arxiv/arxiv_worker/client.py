"""Arxiv paper collector using the arxiv.py library (free, no API key).

Downloads PDFs and extracts full text via PyMuPDF for deep analysis.
"""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import arxiv
import fitz  # PyMuPDF
import httpx
import pymupdf4llm
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

    Downloads PDFs and extracts full text for deep analysis.
    Returns a deduplicated list of paper dicts with 'full_text' field.
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

    # Download PDFs and extract full text
    await _enrich_with_full_text(papers_list)

    return papers_list


# ── PDF download & text extraction ──────────────────────────────────────────

_MAX_PDF_SIZE_MB = 15
_PDF_DOWNLOAD_TIMEOUT = 60


async def _download_pdf(url: str) -> bytes | None:
    """Download a PDF from a URL, returning bytes or None on failure."""
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=_PDF_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
            size_mb = len(content) / (1024 * 1024)
            if size_mb > _MAX_PDF_SIZE_MB:
                logger.warning("PDF too large ({:.1f}MB), skipping: {}", size_mb, url)
                return None
            return content
    except Exception as exc:
        logger.warning("PDF download failed for {}: {}", url, exc)
        return None


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes as clean Markdown using pymupdf4llm."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        md_text = pymupdf4llm.to_markdown(doc)
        doc.close()
        # Clean up excessive whitespace
        lines = [line.rstrip() for line in md_text.splitlines()]
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("PDF markdown extraction failed: {}", exc)
        return ""


async def _enrich_with_full_text(papers: list[dict[str, Any]]) -> None:
    """Download PDFs and add 'full_text' to each paper dict."""
    import asyncio

    total = len(papers)
    success = 0

    # Process in batches of 5 to avoid overwhelming the server
    batch_size = 5
    for i in range(0, total, batch_size):
        batch = papers[i : i + batch_size]
        tasks = [_download_pdf(p.get("pdf_url", "")) for p in batch]
        results = await asyncio.gather(*tasks)

        for paper, pdf_bytes in zip(batch, results):
            if pdf_bytes:
                text = _extract_text_from_pdf(pdf_bytes)
                paper["full_text"] = text
                if text:
                    success += 1
                    logger.debug(
                        "Extracted {:.0f}K chars from {}",
                        len(text) / 1000,
                        paper.get("arxiv_id", ""),
                    )
            else:
                paper["full_text"] = ""

    logger.info(
        "PDF extraction: {}/{} papers with full text",
        success, total,
    )
