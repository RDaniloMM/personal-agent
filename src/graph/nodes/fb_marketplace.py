"""LangGraph node: scrape Facebook Marketplace and detect deals."""

from __future__ import annotations

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState


async def scrape_fb_node(state: AgentState) -> dict:
    """Node that scrapes Facebook Marketplace, then uses the LLM to
    identify listings with genuinely attractive prices.

    Only listings flagged as deals (price well below market value)
    are passed downstream.  Listings with price=0 are excluded.
    """
    logger.info("═══ Node: scrape_fb_marketplace ═══")
    settings = get_settings()

    try:
        from src.scrapers.fb_crawler import crawl_fb_marketplace

        all_listings = await crawl_fb_marketplace(settings)
        logger.info("FB scraper returned {} listings (price>0)", len(all_listings))

        if not all_listings:
            return {"marketplace_listings": []}

        # ── Deal detection via LLM ───────────────────────────────────
        from src.research.deal_analyzer import analyze_deals

        deals = await analyze_deals(all_listings, settings)
        logger.info(
            "Deal analyzer: {}/{} listings are deals",
            len(deals), len(all_listings),
        )
        return {"marketplace_listings": deals}

    except Exception as exc:
        error_msg = f"FB Marketplace scraping failed: {exc}"
        logger.error(error_msg)
        return {"errors": [error_msg]}
