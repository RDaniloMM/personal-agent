"""Arxiv worker — collect papers, analyze, index, write notes.

Usage:
    uv run python -m arxiv_worker.main --run-once
    uv run python -m arxiv_worker.main              # daemon mode
"""

from __future__ import annotations

import asyncio
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from shared.config import get_settings


def _setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        "/app/logs/arxiv-worker_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=level,
    )


async def run_pipeline() -> None:
    """Full Arxiv pipeline: collect → analyze → index → notes → ideas."""
    settings = get_settings()
    logger.info("▶ Starting Arxiv pipeline")

    # 1. Collect papers from Arxiv
    from arxiv_worker.client import collect_arxiv_papers

    papers = await collect_arxiv_papers(settings)
    logger.info("Collected {} papers from Arxiv", len(papers))

    if not papers:
        logger.info("No papers found — skipping")
        return

    # 2. LLM analysis: triage + full analysis on relevant papers
    from arxiv_worker.paper_analyzer import analyze_papers

    analyzed = await analyze_papers(papers, settings)
    logger.info("Analyzed {} relevant papers", len(analyzed))

    # 3. Index in pgvector (deduplicated)
    from shared.storage.zvec_store import get_existing_ids, upsert_documents

    existing = get_existing_ids("arxiv_papers", settings)
    new_papers = [
        p for p in analyzed
        if p.get("arxiv_id") and p["arxiv_id"] not in existing
    ]

    indexed = 0
    if new_papers:
        indexed = upsert_documents("arxiv_papers", new_papers, "title", settings)
    logger.info("Indexed {} new papers (skipped {})", indexed, len(analyzed) - len(new_papers))

    # 4. Write Obsidian notes
    from shared.storage.obsidian import write_arxiv_paper

    for paper in analyzed:
        write_arxiv_paper(paper, settings)

    # 5. Extract ideas with LLM
    from shared.writer import extract_and_write_ideas

    if analyzed:
        summary = _build_summary(analyzed)
        await extract_and_write_ideas(summary, settings, reasoning_effort="high")

    logger.info(
        "✓ Arxiv pipeline complete | papers={} | analyzed={} | indexed={}",
        len(papers), len(analyzed), indexed,
    )


def _build_summary(papers: list[dict]) -> str:
    """Build a text summary of papers for LLM idea extraction."""
    items = "\n".join(
        f"- {p.get('title', '')} [{p.get('relevance', '')}]: "
        f"{(p.get('summary', '') or p.get('abstract', ''))[:200]}"
        for p in papers[:20]
    )
    return f"## Arxiv Papers ({len(papers)} analyzed)\n{items}"


def main() -> None:
    settings = get_settings()
    _setup_logging(settings.log_level)

    if "--run-once" in sys.argv:
        logger.info("One-shot mode: Arxiv")
        asyncio.run(run_pipeline())
        return

    logger.info("Starting Arxiv worker daemon (hours: {})", settings.scrape_hours_list)
    scheduler = AsyncIOScheduler()

    hours_str = ",".join(str(h) for h in settings.scrape_hours_list)
    scheduler.add_job(
        run_pipeline,
        CronTrigger(hour=hours_str),
        id="arxiv_papers",
        name="Arxiv paper collection",
        replace_existing=True,
    )

    async def _run() -> None:
        scheduler.start()
        logger.info("Arxiv scheduler started.")
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            scheduler.shutdown(wait=False)

    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down Arxiv worker …")


if __name__ == "__main__":
    main()
