"""FB Marketplace worker — scrape, detect deals, index, write notes.

Usage:
    uv run python -m fb_worker.main --run-once
    uv run python -m fb_worker.main              # daemon mode
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
        "/app/logs/fb-worker_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=level,
    )


async def run_pipeline() -> None:
    """Full FB Marketplace pipeline: scrape → deals → index → notes."""
    settings = get_settings()
    logger.info("▶ Starting FB Marketplace pipeline")

    # 1. Scrape listings (price=0 already filtered)
    from fb_worker.crawler import crawl_fb_marketplace

    all_listings = await crawl_fb_marketplace(settings)
    logger.info("Scraped {} listings (price > 0)", len(all_listings))

    if not all_listings:
        logger.info("No listings found — skipping")
        return

    # 2. Detect deals via LLM
    from fb_worker.deal_analyzer import analyze_deals

    deals = await analyze_deals(all_listings, settings)
    logger.info("Deal analyzer: {}/{} are deals", len(deals), len(all_listings))

    # 2b. Enrich deals with seller descriptions
    if deals:
        from fb_worker.crawler import enrich_with_descriptions
        deals = await enrich_with_descriptions(deals, max_items=20)

    # 3. Index in pgvector (deduplicated)
    from shared.storage.zvec_store import get_existing_ids, upsert_documents

    existing = get_existing_ids("fb_marketplace", settings)
    new_listings = [d for d in deals if d.get("url") and d["url"] not in existing]

    indexed = 0
    if new_listings:
        indexed = upsert_documents("fb_marketplace", new_listings, "title", settings)
    logger.info("Indexed {} new listings (skipped {})", indexed, len(deals) - len(new_listings))

    # 4. Write Obsidian notes
    from shared.storage.obsidian import write_marketplace_summary

    write_marketplace_summary(deals, settings)

    # 5. Extract ideas with LLM
    from shared.writer import extract_and_write_ideas

    if deals:
        summary = _build_summary(deals)
        await extract_and_write_ideas(summary, settings, reasoning_effort="medium")

    logger.info("✓ FB pipeline complete | deals={} | indexed={}", len(deals), indexed)


def _build_summary(listings: list[dict]) -> str:
    """Build a text summary of deals for LLM idea extraction."""
    items = "\n".join(
        f"- {l.get('title', '')} – {l.get('price', '')} en {l.get('location', '')}. "
        f"{l.get('deal_reason', '')}"
        for l in listings[:20]
    )
    return f"## FB Marketplace Deals ({len(listings)} gangas encontradas)\n{items}"


def main() -> None:
    settings = get_settings()
    _setup_logging(settings.log_level)

    if "--run-once" in sys.argv:
        logger.info("One-shot mode: FB Marketplace")
        asyncio.run(run_pipeline())
        return

    logger.info("Starting FB worker daemon (hours: {})", settings.scrape_hours_list)
    scheduler = AsyncIOScheduler()

    hours_str = ",".join(str(h) for h in settings.scrape_hours_list)
    scheduler.add_job(
        run_pipeline,
        CronTrigger(hour=hours_str),
        id="fb_marketplace",
        name="FB Marketplace scraping",
        replace_existing=True,
    )

    async def _run() -> None:
        scheduler.start()
        logger.info("FB scheduler started.")
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
        logger.info("Shutting down FB worker …")


if __name__ == "__main__":
    main()
