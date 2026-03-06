"""Reanalyze stored Arxiv papers from pgvector and regenerate notes."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import psycopg
from google import genai
from loguru import logger

from arxiv_worker.client import _download_pdfs
from arxiv_worker.paper_analyzer import _analysis_batch_gemini, _analysis_batch_groq
from shared.config import get_settings
from shared.storage.obsidian import write_arxiv_paper


def _fetch_stored_papers(database_url: str) -> list[dict[str, Any]]:
    conn = psycopg.connect(database_url, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT metadata
                FROM arxiv_papers
                ORDER BY COALESCE(metadata->>'published', '') DESC, id DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    papers: list[dict[str, Any]] = []
    for (metadata,) in rows:
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict):
            continue
        paper = dict(metadata)
        paper.pop("pdf_bytes", None)
        papers.append(paper)
    return papers


def _wipe_existing_notes(folder: Path) -> int:
    count = 0
    for path in folder.glob("*.md"):
        path.unlink(missing_ok=True)
        count += 1
    return count


def _update_metadata(database_url: str, papers: list[dict[str, Any]]) -> int:
    conn = psycopg.connect(database_url, autocommit=False)
    updated = 0
    try:
        with conn.cursor() as cur:
            for paper in papers:
                arxiv_id = paper.get("arxiv_id", "")
                if not arxiv_id:
                    continue
                cur.execute(
                    "UPDATE arxiv_papers SET metadata = %s::jsonb WHERE id = %s",
                    (json.dumps(paper, default=str), arxiv_id),
                )
                updated += cur.rowcount
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def _run(limit: int | None, wipe_notes: bool) -> None:
    settings = get_settings()
    papers = _fetch_stored_papers(settings.database_url)
    if limit is not None:
        papers = papers[:limit]

    logger.info("Loaded {} stored Arxiv papers from pgvector", len(papers))
    if not papers:
        return

    await _download_pdfs(papers)
    pdf_ready = sum(1 for paper in papers if paper.get("pdf_bytes"))
    logger.info("PDF ready for {}/{} stored papers", pdf_ready, len(papers))

    if settings.gemini_api_key:
        logger.info("Reanalyzing with Gemini {}", settings.gemini_model)
        analyses = await _analysis_batch_gemini(
            papers,
            genai.Client(api_key=settings.gemini_api_key),
            settings,
        )
    else:
        logger.warning("GEMINI_API_KEY missing, falling back to Groq abstract analysis")
        from openai import AsyncOpenAI

        analyses = await _analysis_batch_groq(
            papers,
            AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url),
            settings,
        )

    analysis_map = {item.get("arxiv_id", ""): item for item in analyses if item.get("arxiv_id")}
    refreshed: list[dict[str, Any]] = []
    for paper in papers:
        arxiv_id = paper.get("arxiv_id", "")
        refreshed.append(
            {
                **paper,
                **analysis_map.get(arxiv_id, {}),
                "relevance": paper.get("relevance", "high"),
            }
        )

    folder = settings.obsidian_subfolder("Papers")
    if wipe_notes:
        removed = _wipe_existing_notes(folder)
        logger.info("Removed {} existing paper notes from {}", removed, folder)

    written = 0
    for paper in refreshed:
        write_arxiv_paper(paper, settings)
        written += 1

    updated = _update_metadata(settings.database_url, refreshed)
    logger.info(
        "Reanalysis complete: refreshed={} | notes_written={} | db_rows_updated={}",
        len(refreshed), written, updated,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reanalyze stored Arxiv papers")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of papers")
    parser.add_argument(
        "--wipe-notes",
        action="store_true",
        help="Delete existing Papers/*.md before writing regenerated notes",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.limit, args.wipe_notes))


if __name__ == "__main__":
    main()
