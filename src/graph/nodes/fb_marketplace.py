"""LangGraph node: scrape Facebook Marketplace."""

from __future__ import annotations

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState


async def scrape_fb_node(state: AgentState) -> dict:
    """Node that scrapes Facebook Marketplace and appends results to state."""
    logger.info("═══ Node: scrape_fb_marketplace ═══")
    settings = get_settings()

    try:
        from src.scrapers.fb_crawler import crawl_fb_marketplace

        listings = await crawl_fb_marketplace(settings)
        logger.info("FB node collected {} listings", len(listings))
        return {"marketplace_listings": listings}

    except Exception as exc:
        error_msg = f"FB Marketplace scraping failed: {exc}"
        logger.error(error_msg)
        return {"errors": [error_msg]}
