"""YouTube worker — search, API feeds, enrich, index, write notes.

Usage:
    uv run python -m yt_worker.main --run-once
    uv run python -m yt_worker.main              # daemon mode
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
        "/app/logs/yt-worker_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=level,
    )


async def run_pipeline() -> None:
    """Full YouTube pipeline: discover → enrich → index → notes → ideas."""
    settings = get_settings()
    logger.info("▶ Starting YouTube pipeline")

    # 1. Crawl: search + API feeds + yt-dlp enrichment
    from yt_worker.crawler import crawl_youtube

    videos = await crawl_youtube(settings)
    logger.info("Discovered & enriched {} videos", len(videos))

    if not videos:
        logger.info("No videos found — skipping")
        return

    # 2. Filter against pgvector knowledge base and index only new videos
    from shared.storage.zvec_store import (
        get_existing_ids,
        make_document_id,
        upsert_documents,
    )

    existing = get_existing_ids("youtube_feed", settings)
    new_videos = [
        v
        for v in videos
        if v.get("url") and make_document_id(v, "youtube_feed") not in existing
    ]

    if not new_videos:
        logger.info("No new videos after pgvector dedup — skipping notes and ideas")
        return

    indexed = upsert_documents("youtube_feed", new_videos, "title", settings)
    logger.info(
        "Indexed {} new videos (skipped {})", indexed, len(videos) - len(new_videos)
    )

    # 3. Write Obsidian notes
    from shared.storage.obsidian import write_youtube_summary

    write_youtube_summary(new_videos, settings)

    # 4. Extract ideas with LLM
    from shared.writer import extract_and_write_ideas

    summary = _build_summary(new_videos)
    await extract_and_write_ideas(summary, settings, reasoning_effort="medium")

    logger.info(
        "✓ YouTube pipeline complete | videos={} | new={} | indexed={}",
        len(videos),
        len(new_videos),
        indexed,
    )


def _build_summary(videos: list[dict]) -> str:
    """Build a text summary of videos for LLM idea extraction."""
    items = "\n".join(
        f"- [{v.get('title', '')}]({v.get('url', '')}) by {v.get('channel', '')} "
        f"({v.get('views', '?')} views, {v.get('duration', '')})"
        for v in videos[:20]
    )
    return f"## YouTube Videos ({len(videos)} discovered)\n{items}"


def main() -> None:
    settings = get_settings()
    _setup_logging(settings.log_level)

    if "--run-once" in sys.argv:
        logger.info("One-shot mode: YouTube")
        asyncio.run(run_pipeline())
        return

    logger.info(
        "Starting YouTube worker daemon (hours: {})", settings.yt_scrape_hours_list
    )
    scheduler = AsyncIOScheduler()

    hours_str = ",".join(str(h) for h in settings.yt_scrape_hours_list)
    scheduler.add_job(
        run_pipeline,
        CronTrigger(hour=hours_str),
        id="youtube_feed",
        name="YouTube video discovery",
        replace_existing=True,
    )

    async def _run() -> None:
        scheduler.start()
        logger.info("YouTube scheduler started.")
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
        logger.info("Shutting down YouTube worker …")


if __name__ == "__main__":
    main()
