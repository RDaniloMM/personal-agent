"""Entry point: scheduler that runs the agent graph on a cron schedule."""

from __future__ import annotations

import asyncio
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.config import get_settings
from src.graph.builder import build_graph
from src.graph.state import AgentState


# ── Configure logging ────────────────────────────────────────────────────────


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
        "logs/agent_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=level,
    )


# ── Graph runner ─────────────────────────────────────────────────────────────


async def run_graph(task_type: str = "all") -> None:
    """Invoke the agent graph for a given task type."""
    logger.info("▶ Starting agent run (task={})", task_type)
    graph = build_graph()

    initial_state = AgentState(task_type=task_type)  # type: ignore[arg-type]

    try:
        result = await graph.ainvoke(initial_state)
        logger.info(
            "✓ Agent run complete | vectors={} | notes={} | errors={}",
            result.get("vectors_indexed", 0),
            len(result.get("notes_written", [])),
            len(result.get("errors", [])),
        )
        if result.get("errors"):
            for err in result["errors"]:
                logger.warning("  ⚠ {}", err)
    except Exception as exc:
        logger.exception("✗ Agent run failed: {}", exc)


# ── Scheduled jobs ───────────────────────────────────────────────────────────


async def job_scrape_fb_yt() -> None:
    """Scheduled job: scrape FB Marketplace + YouTube."""
    await run_graph("fb")
    await run_graph("youtube")


async def job_collect_arxiv() -> None:
    """Scheduled job: collect Arxiv papers."""
    await run_graph("arxiv")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Launch the scheduler or run a one-shot task via CLI."""
    settings = get_settings()
    _setup_logging(settings.log_level)

    # CLI mode: --run-once --task <type>
    if "--run-once" in sys.argv:
        task = "all"
        if "--task" in sys.argv:
            idx = sys.argv.index("--task")
            task = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "all"
        logger.info("One-shot mode: task={}", task)
        asyncio.run(run_graph(task))
        return

    # Daemon mode: start the async scheduler
    logger.info("Starting personal-agent scheduler daemon …")
    logger.info(
        "  FB+YT scraping at hours: {}",
        settings.scrape_hours_list,
    )
    logger.info(
        "  Arxiv collection at hour {}",
        settings.arxiv_hour,
    )

    scheduler = AsyncIOScheduler()

    # FB + YouTube: 2x/day at configured hours
    hours_str = ",".join(str(h) for h in settings.scrape_hours_list)
    scheduler.add_job(
        job_scrape_fb_yt,
        CronTrigger(hour=hours_str),
        id="scrape_fb_yt",
        name="FB Marketplace + YouTube scraping",
        replace_existing=True,
    )

    # Arxiv: once per day at configured hour
    scheduler.add_job(
        job_collect_arxiv,
        CronTrigger(hour=settings.arxiv_hour),
        id="collect_arxiv",
        name="Arxiv paper collection",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to stop.")

    # Keep the event loop running
    loop = asyncio.new_event_loop()
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler …")
        scheduler.shutdown(wait=False)
        loop.close()


if __name__ == "__main__":
    main()
