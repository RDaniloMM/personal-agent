"""Facebook Marketplace crawler using Crawl4AI with identity-based browsing."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from loguru import logger

from src.config import Settings
from src.graph.state import MarketplaceListing


# ── JS helpers ───────────────────────────────────────────────────────────────

SCROLL_JS = """
(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    for (let i = 0; i < 5; i++) {
        window.scrollBy(0, window.innerHeight);
        await delay(1500);
    }
})();
"""

# ── Extraction prompt for LLM-based strategy ────────────────────────────────

EXTRACTION_PROMPT = """
Extract all product listings visible on this Facebook Marketplace page.
For each listing, return a JSON object with these fields:
- title: product name/title
- price: price as shown (include currency symbol)
- location: city or area
- url: link to the listing (relative or absolute)
- image_url: URL of the product image
- description: short description if available

Return a JSON array of objects. If no listings are found, return [].
"""


async def crawl_fb_marketplace(settings: Settings) -> list[dict[str, Any]]:
    """Scrape FB Marketplace for configured queries and locations.

    Uses a persistent browser profile so Facebook sees an authenticated session.
    Falls back gracefully when selectors change or the session has expired.
    """
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
    )

    profile_path = settings.fb_profile_path
    if not profile_path.exists() or not any(profile_path.iterdir()):
        logger.warning(
            "FB profile not found at {}. "
            "Create it on your desktop with: uv run python -m src.scrapers.browser_profiles fb",
            profile_path,
        )
        return []

    browser_config = BrowserConfig(
        headless=True,
        use_managed_browser=True,
        user_data_dir=str(profile_path),
        browser_type="chromium",
    )

    # Multiple fallback selectors — Facebook changes these frequently
    wait_selectors = [
        "css:div[aria-label='Collection of Marketplace items']",
        "css:div[role='main'] a[href*='/marketplace/item/']",
        "css:div[data-pagelet*='Marketplace']",
        "css:div[role='main']",
    ]

    crawl_config = CrawlerRunConfig(
        js_code=SCROLL_JS,
        wait_for=wait_selectors[0],
        page_timeout=30000,
        magic=True,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        locale="es-PE",
    )

    all_listings: list[dict[str, Any]] = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for location in settings.fb_locations_list:
            for query in settings.fb_search_queries_list:
                url = (
                    f"https://www.facebook.com/marketplace/{location}"
                    f"/search?query={query.replace(' ', '%20')}"
                )
                logger.info("Crawling FB Marketplace: {} in {}", query, location)

                result = None
                # Try each selector until one works
                for selector in wait_selectors:
                    crawl_config.wait_for = selector
                    try:
                        result = await crawler.arun(url=url, config=crawl_config)
                        if result.success and result.markdown and len(result.markdown.strip()) > 100:
                            break
                    except Exception:
                        continue

                if result is None or not result.success:
                    msg = result.error_message if result else "all selectors failed"
                    # Check for login wall
                    if result and result.markdown and "log in" in result.markdown.lower():
                        logger.warning(
                            "FB session expired for {}/{}. Re-create profile with: "
                            "uv run python -m src.scrapers.browser_profiles fb",
                            location, query,
                        )
                    else:
                        logger.warning("FB crawl failed for {}/{}: {}", location, query, msg)
                    continue

                listings = _parse_listings(result.markdown, query, location)
                all_listings.extend(listings)
                logger.info(
                    "Found {} listings for '{}' in {}",
                    len(listings), query, location,
                )

                # Rate-limit between requests
                await asyncio.sleep(5)

    logger.info("Total FB Marketplace listings scraped: {}", len(all_listings))
    return all_listings


def _parse_listings(
    markdown: str, query: str, location: str
) -> list[dict[str, Any]]:
    """Parse marketplace listings from crawled markdown content.

    Uses a heuristic approach: each listing block typically has a price line,
    a title line, and a location line.  Falls back to raw text chunks.
    """
    listings: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    lines = markdown.strip().splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current.get("title"):
                listings.append(current)
                current = {}
            continue

        # Price detection (S/ or $ followed by digits)
        if any(
            stripped.startswith(sym) for sym in ("S/", "$", "US$", "PEN")
        ) or (len(stripped) < 20 and any(c.isdigit() for c in stripped)):
            if "price" not in current:
                current["price"] = stripped
                continue

        # If we already have a price, next meaningful line is likely the title
        if "price" in current and "title" not in current:
            current["title"] = stripped
            continue

        # After title, location
        if "title" in current and "location" not in current:
            current["location"] = stripped
            continue

    # Flush last item
    if current.get("title"):
        listings.append(current)

    # Normalize into MarketplaceListing dicts
    normalized: list[dict[str, Any]] = []
    for item in listings:
        listing = MarketplaceListing(
            title=item.get("title", ""),
            price=item.get("price", ""),
            location=item.get("location", location),
            url=item.get("url", ""),
            image_url=item.get("image_url", ""),
            description=item.get("description", ""),
        )
        normalized.append(asdict(listing))

    return normalized
