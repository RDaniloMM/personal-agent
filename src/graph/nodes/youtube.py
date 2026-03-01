"""LangGraph node: scrape YouTube."""

from __future__ import annotations

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState


async def scrape_youtube_node(state: AgentState) -> dict:
    """Node that scrapes YouTube feeds and appends results to state."""
    logger.info("═══ Node: scrape_youtube ═══")
    settings = get_settings()

    try:
        from src.scrapers.yt_crawler import crawl_youtube

        videos = await crawl_youtube(settings)
        logger.info("YouTube node collected {} videos", len(videos))
        return {"youtube_videos": videos}

    except Exception as exc:
        error_msg = f"YouTube scraping failed: {exc}"
        logger.error(error_msg)
        return {"errors": [error_msg]}
