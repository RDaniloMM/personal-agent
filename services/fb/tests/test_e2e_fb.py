"""E2E smoke test for the FB Marketplace pipeline.

Runs a minimal version of the full pipeline:
  1. Crawl 1 listing per query (1 location, 1 query)
  2. Run the deal analyzer (triage + MercadoLibre search + analysis)
  3. Verify output structure

Usage (inside Docker):
    docker compose run --rm fb-worker uv run python -m pytest tests/ -v -s
    docker compose run --rm fb-worker uv run python -m tests.test_e2e_fb
"""

from __future__ import annotations

import asyncio
import os
import sys

from loguru import logger


async def _run_e2e() -> None:
    """Minimal end-to-end FB pipeline: 1 location × 1 query × 1 listing."""

    # ── Setup ───────────────────────────────────────────────────────
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    # Override settings for a fast test (force override, not setdefault)
    os.environ["FB_SEARCH_QUERIES"] = "laptop"
    os.environ["FB_LOCATIONS"] = "tacna:111957248821463"

    from shared.config import get_settings

    settings = get_settings()

    logger.info("═══ E2E FB TEST START ═══")
    logger.info(
        "Config: queries={}, locations={}",
        settings.fb_search_queries_list,
        list(settings.fb_locations_map.keys()),
    )

    # ── Phase 1: Crawl (limited) ────────────────────────────────────
    from fb_worker.crawler import crawl_fb_marketplace

    all_listings = await crawl_fb_marketplace(settings)
    logger.info("Crawled {} listings", len(all_listings))

    # Limit to at most 3 listings for fast analysis
    test_listings = all_listings[:3]

    if not test_listings:
        logger.warning("No listings found — skipping LLM phases (FB may be blocking)")
        logger.info("═══ E2E FB TEST DONE (no listings) ═══")
        return

    # Verify listing structure
    for listing in test_listings:
        assert "title" in listing, f"Missing 'title' in listing: {listing}"
        assert "price" in listing, f"Missing 'price' in listing: {listing}"
        logger.debug("  Listing: {} — {}", listing.get("title", "?")[:50], listing.get("price"))

    # ── Phase 2: Deal analysis (triage + MercadoLibre + calculator) ─
    from fb_worker.deal_analyzer import analyze_deals

    deals = await analyze_deals(test_listings, settings)
    logger.info("Deal analyzer returned {} deals from {} listings", len(deals), len(test_listings))

    # Verify deal structure (if any)
    for deal in deals:
        assert "title" in deal, f"Missing 'title' in deal"
        assert "is_deal" in deal, f"Missing 'is_deal' in deal"
        assert deal["is_deal"] is True
        assert "deal_reason" in deal, f"Missing 'deal_reason' in deal"
        assert "estimated_market_price" in deal
        assert "discount_pct" in deal
        logger.info(
            "  ✓ Deal: {} — {} ({}% off, ML: {})",
            deal.get("title", "?")[:40],
            deal.get("price"),
            deal.get("discount_pct"),
            deal.get("estimated_market_price"),
        )

    # ── Phase 3: MercadoLibre search standalone test ────────────────
    from fb_worker.deal_analyzer import _search_mercadolibre

    ml_results = await _search_mercadolibre("laptop", limit=3)
    logger.info("MercadoLibre search test: {} results", len(ml_results))
    for r in ml_results:
        assert "title" in r
        assert "price" in r
        assert "currency" in r
        logger.debug("  ML: {} — {} {}", r["title"][:40], r["currency"], r["price"])

    logger.info("═══ E2E FB TEST PASSED ═══")


def main() -> None:
    asyncio.run(_run_e2e())


if __name__ == "__main__":
    main()
