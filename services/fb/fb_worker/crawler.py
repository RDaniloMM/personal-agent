"""Facebook Marketplace crawler — no login required.

Bypasses the login modal via JS injection and scrapes as a guest.
No browser profile or cookies needed.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict
from typing import Any

from loguru import logger

from shared.config import Settings
from shared.state import MarketplaceListing


# ── JS: dismiss login modal + scroll ────────────────────────────────────────

DISMISS_AND_SCROLL_JS = """
(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));

    const dismiss = () => {
        // 1. Click any "Close" / "Cerrar" buttons
        document.querySelectorAll(
            '[aria-label="Close"], [aria-label="Cerrar"], ' +
            '[aria-label="Decline optional cookies"], ' +
            '[aria-label="Rechazar cookies opcionales"]'
        ).forEach(b => { try { b.click(); } catch(e){} });

        // 2. Remove dialog overlays
        document.querySelectorAll(
            '[role="dialog"], [data-nosnippet="true"]'
        ).forEach(el => el.remove());

        // 3. Remove fixed-position overlays / backdrops
        document.querySelectorAll('div[class*="x1n2onr6"]').forEach(el => {
            const s = getComputedStyle(el);
            if (s.position === 'fixed' && s.zIndex > 100) el.remove();
        });

        // 4. Re-enable scrolling
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
        document.body.style.position = 'static';

        // 5. Remove any remaining overlays via class patterns
        document.querySelectorAll('[class*="uiLayer"], [class*="GenericModal"]')
            .forEach(el => el.remove());
    };

    // First pass – immediate
    dismiss();
    await delay(2000);
    dismiss();

    // Scroll + dismiss on each iteration (FB re-shows the modal)
    for (let i = 0; i < 6; i++) {
        window.scrollBy(0, window.innerHeight);
        await delay(1500);
        dismiss();
    }
})();
"""

# ── Price parsing ────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(
    r"""
    (?:S/\.?\s*|PEN\s*|US?\$\s*|MX\$\s*|R\$\s*|\$\s*)   # currency prefix
    ([\d,.\s]+)                                             # digits with separators
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _parse_price(text: str) -> tuple[float, str]:
    """Extract numeric price and currency from a price string."""
    if not text:
        return 0.0, ""

    text_lower = text.lower().strip()
    if text_lower in ("gratis", "free", "regalo"):
        return 0.0, "PEN"

    # Detect currency only from explicit prefixes
    currency = "PEN"
    if "s/." in text_lower or "s/" in text_lower or "pen" in text_lower:
        currency = "PEN"
    elif "us$" in text_lower:
        currency = "USD"
    elif "mx$" in text_lower:
        currency = "MXN"
    elif "r$" in text_lower:
        currency = "BRL"
    # Bare "$" is ambiguous — keep as PEN when searching in PEN regions

    m = _PRICE_RE.search(text)
    if not m:
        bare = re.search(r"([\d,.\s]+)", text)
        if bare:
            num_str = bare.group(1).replace(",", "").replace(" ", "").strip()
            try:
                return float(num_str), currency
            except ValueError:
                return 0.0, ""
        return 0.0, ""

    num_str = m.group(1).replace(",", "").replace(" ", "").strip()
    try:
        return float(num_str), currency
    except ValueError:
        return 0.0, ""


async def crawl_fb_marketplace(settings: Settings) -> list[dict[str, Any]]:
    """Scrape FB Marketplace as guest — no login/profile needed."""
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
    )

    browser_config = BrowserConfig(
        headless=True,
        use_managed_browser=True,
        browser_type="chromium",
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--lang=es-PE",
        ],
        headers={
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.5",
        },
        init_scripts=[
            # Hide automation indicators before any page script runs
            "Object.defineProperty(navigator, 'webdriver', {get: () => false})",
        ],
    )

    wait_selectors = [
        "css:div[aria-label='Collection of Marketplace items']",
        "css:div[role='main'] a[href*='/marketplace/item/']",
        "css:div[data-pagelet*='Marketplace']",
        "css:div[role='main']",
    ]

    crawl_config = CrawlerRunConfig(
        js_code=DISMISS_AND_SCROLL_JS,
        wait_for=wait_selectors[0],
        page_timeout=45000,
        magic=True,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        locale="es-PE",
    )

    all_listings: list[dict[str, Any]] = []
    locations = settings.fb_locations_map  # {name: fb_location_id}
    radius = settings.fb_radius_km

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for loc_name, loc_id in locations.items():
            for query in settings.fb_search_queries_list:
                url = (
                    f"https://www.facebook.com/marketplace/{loc_id}/search"
                    f"?query={query.replace(' ', '%20')}"
                    f"&radius={radius}"
                )
                logger.info("Crawling FB Marketplace [{}]: {}", loc_name, query)

                result = None
                for selector in wait_selectors:
                    crawl_config.wait_for = selector
                    try:
                        result = await crawler.arun(url=url, config=crawl_config)
                        if result.success and result.markdown and len(result.markdown.strip()) > 100:
                            md_lower = result.markdown.lower()
                            if "marketplace" in md_lower or "s/" in md_lower or "$" in md_lower:
                                break
                    except Exception:
                        continue

                if result is None or not result.success:
                    msg = result.error_message if result else "all selectors failed"
                    logger.warning("FB crawl failed for '{}' [{}]: {}", query, loc_name, msg)
                    continue

                listings = _parse_listings(result.markdown, query, loc_name)

                # Filter out listings not in the target country
                if listings:
                    listings = _filter_by_location(listings, loc_name)

                all_listings.extend(listings)
                logger.info("Found {} listings for '{}' [{}]", len(listings), query, loc_name)

                await asyncio.sleep(5)

    logger.info("Total FB Marketplace listings scraped: {}", len(all_listings))
    return all_listings


# ── Location filter ───────────────────────────────────────────────────────────

# Known Peruvian departments + capital cities (lowercased for matching).
# FB returns US results for guest sessions, so we whitelist Peruvian locations.
# Matching is done per comma-separated segment (exact match) to avoid false
# positives like "South Gate, CA" matching "ate".
_PERU_LOCATIONS: set[str] = {
    # Country
    "perú", "peru",
    # Departments
    "amazonas", "ancash", "áncash", "apurímac", "apurimac", "arequipa",
    "ayacucho", "cajamarca", "callao", "cusco", "cuzco",
    "huancavelica", "huánuco", "huanuco", "ica", "junín", "junin",
    "la libertad", "lambayeque", "lima", "loreto",
    "madre de dios", "moquegua", "pasco", "piura", "puno",
    "san martín", "san martin", "tacna", "tumbes", "ucayali",
    # Capital cities / major cities
    "chachapoyas", "huaraz", "abancay", "huamanga", "trujillo",
    "chiclayo", "huancayo", "iquitos", "puerto maldonado",
    "cerro de pasco", "moyobamba", "tarapoto", "pucallpa",
    "sullana", "juliaca", "chimbote", "ilo",
    "chincha", "nazca", "huacho", "barranca", "cañete",
    "san juan de lurigancho", "los olivos", "surco",
    "miraflores", "san isidro", "chorrillos", "villa el salvador",
    "san miguel", "breña", "pueblo libre", "jesús maría",
    "la molina", "magdalena", "lince", "independencia",
    "comas", "carabayllo", "puente piedra", "lurín", "ate",
    "arica",  # border region
}


def _filter_by_location(
    listings: list[dict[str, Any]],
    target_location: str,
) -> list[dict[str, Any]]:
    """Keep only listings from Peruvian locations (whitelist approach).

    FB Marketplace ignores lat/lng for guest (non-authenticated) sessions and
    often returns US-based listings.  We keep a listing only when its location
    field matches a known Peruvian city/department, or when the location is
    empty (benefit of the doubt).

    Matching is done per comma-separated segment (exact, case-insensitive)
    to avoid false positives like "South Gate" matching "ate".
    """
    before = len(listings)
    filtered: list[dict[str, Any]] = []
    for listing in listings:
        loc = (listing.get("location") or "").strip()
        if not loc:
            filtered.append(listing)  # no location → keep
            continue
        # Split "City, State/Country" into segments and check each
        segments = [s.strip().lower() for s in loc.split(",")]
        if any(seg in _PERU_LOCATIONS for seg in segments):
            filtered.append(listing)
            continue
        # Otherwise skip (likely US or other country)

    removed = before - len(filtered)
    if removed:
        logger.info(
            "Location filter [{}]: kept {}/{} (removed {} non-local listings)",
            target_location, len(filtered), before, removed,
        )
    return filtered


# ── JS for item detail page ─────────────────────────────────────────────────

DISMISS_ITEM_JS = """
(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const dismiss = () => {
        document.querySelectorAll(
            '[aria-label="Close"], [aria-label="Cerrar"]'
        ).forEach(b => { try { b.click(); } catch(e){} });
        document.querySelectorAll('[role="dialog"]').forEach(el => el.remove());
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
        document.body.style.position = 'static';
    };
    dismiss();
    await delay(2000);
    dismiss();
    window.scrollBy(0, 400);
    await delay(1000);
})();
"""


async def enrich_with_descriptions(
    listings: list[dict[str, Any]], *, max_items: int = 20
) -> list[dict[str, Any]]:
    """Visit each listing's URL to scrape the seller's description.

    Only processes up to max_items to avoid excessive scraping.
    """
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
    )

    urls = [l for l in listings if l.get("url") and not l.get("description")]
    if not urls:
        return listings

    urls = urls[:max_items]
    logger.info("Enriching {} listings with descriptions…", len(urls))

    browser_config = BrowserConfig(
        headless=True,
        use_managed_browser=True,
        browser_type="chromium",
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--lang=es-PE",
        ],
        headers={"Accept-Language": "es-PE,es;q=0.9,en;q=0.5"},
    )

    crawl_config = CrawlerRunConfig(
        js_code=DISMISS_ITEM_JS,
        wait_for='css:div[role="main"]',
        page_timeout=30000,
        magic=True,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
    )

    enriched_count = 0

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for listing in urls:
            try:
                result = await crawler.arun(url=listing["url"], config=crawl_config)
                if not result.success or not result.markdown:
                    continue

                desc = _extract_description(result.markdown)
                if desc:
                    listing["description"] = desc
                    enriched_count += 1
                    logger.debug(
                        "Description for '{}': {}…",
                        listing.get("title", "")[:40],
                        desc[:80],
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to get description for {}: {}",
                    listing.get("url", ""), exc,
                )
            await asyncio.sleep(3)

    logger.info("Enriched {}/{} listings with descriptions", enriched_count, len(urls))
    return listings


def _extract_description(markdown: str) -> str:
    """Extract the seller's item description from a FB item page markdown."""
    lines = markdown.splitlines()
    desc_lines: list[str] = []
    capture = False

    for line in lines:
        stripped = line.strip()

        # Skip navigation / boilerplate
        if any(kw in stripped.lower() for kw in (
            "log in", "create new account", "email or phone",
            "forgot password", "see more on facebook",
            "loading more", "marketplace",
        )):
            continue

        # Start capturing after "Seller's description" / "Descripción del vendedor"
        if re.search(r"(?:seller.s description|descripci[oó]n del vendedor)", stripped, re.I):
            capture = True
            continue

        if capture:
            # Stop at next section header or empty zone
            if stripped.startswith("#") or stripped.startswith("---"):
                break
            if not stripped:
                if desc_lines:
                    break
                continue
            desc_lines.append(stripped)

    if desc_lines:
        return " ".join(desc_lines)[:500]

    # Fallback: look for any substantial text block (>50 chars) after the title
    # that's not boilerplate
    for i, line in enumerate(lines):
        stripped = line.strip()
        if len(stripped) > 50 and not any(kw in stripped.lower() for kw in (
            "log in", "create new", "email or phone", "forgot password",
            "see more", "loading", "marketplace", "http",
        )):
            return stripped[:500]

    return ""


def _parse_listings(
    markdown: str, query: str, location_name: str = ""
) -> list[dict[str, Any]]:
    """Parse marketplace listings from crawled markdown.

    Facebook returns listings as markdown links:
      [ $500 Acer Nitro Gaming Laptop Berkeley, CA ](https://…/marketplace/item/123…)
    """
    # Pattern: markdown link whose URL points to a marketplace item
    link_re = re.compile(
        r'\[\s*(.+?)\s*\]\((https://www\.facebook\.com/marketplace/item/\d+[^)]*)\)',
        re.DOTALL,
    )

    # Price at the start of text
    price_start_re = re.compile(
        r'^((?:S/\.?\s*|PEN\s*|US?\$\s*|MX\$\s*|R\$\s*|\$\s*)[\d,.\s]+)',
        re.IGNORECASE,
    )

    normalized: list[dict[str, Any]] = []

    for m in link_re.finditer(markdown):
        text = m.group(1).replace("\n", " ").strip()
        item_url = m.group(2).strip()

        # Strip embedded markdown images  ![alt](url)
        text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text).strip()

        # Extract price from the beginning of the text
        pm = price_start_re.match(text)
        if not pm:
            continue
        price_str = pm.group(1).strip()
        remainder = text[pm.end():].strip()

        # Try to split remainder into title + location
        # FB format: "Title City Name, ST" — e.g. "Laptop Intel i5 San Francisco, CA"
        # Strategy: find ", XX" at end (state code), then use known city
        # patterns for multi-word cities, otherwise take last word as city.
        loc_state_match = re.search(r',\s*([A-Z]{2})\s*$', remainder)
        if loc_state_match:
            state = loc_state_match.group(1)
            before_comma = remainder[:loc_state_match.start()].rstrip()
            words = before_comma.split()

            # Try to detect multi-word city names at the end
            # Common patterns: "San X", "Los X", "Las X", "New X", "El X",
            #                  "La X", "Santa X", "Fort X", "Saint X"
            city_words = 1
            if len(words) >= 2:
                second_last = words[-2].lower()
                if second_last in (
                    "san", "los", "las", "new", "el", "la", "santa",
                    "fort", "saint", "mount", "port", "south", "north",
                    "east", "west", "del", "de",
                ):
                    city_words = 2
                # Also try 3-word cities: "San Luis Obispo", etc.
                if len(words) >= 3 and words[-3].lower() in (
                    "san", "santa", "new", "south", "north",
                ):
                    city_words = 3

            if len(words) > city_words:
                title = " ".join(words[:-city_words])
                location = " ".join(words[-city_words:]) + ", " + state
            elif len(words) >= 1:
                title = " ".join(words)
                location = location_name or state
            else:
                title = before_comma
                location = location_name or state
        else:
            title = remainder
            location = ""

        if not title:
            continue

        price_num, currency = _parse_price(price_str)
        if price_num <= 5:
            continue  # skip spam listings (Free, PEN1, etc.)

        listing = MarketplaceListing(
            title=title,
            price=price_str,
            location=location or location_name or query,
            url=item_url,
            image_url="",
            description="",
            price_numeric=price_num,
            currency=currency,
        )
        normalized.append(asdict(listing))

    # Fallback: try line-by-line parsing if no markdown links found
    if not normalized:
        normalized = _parse_listings_lines(markdown, query)

    logger.debug(
        "Parsed {} listings from markdown ({} chars)",
        len(normalized), len(markdown),
    )
    return normalized


def _parse_listings_lines(
    markdown: str, query: str
) -> list[dict[str, Any]]:
    """Fallback line-by-line parser for older FB format."""
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

        if any(
            stripped.startswith(sym) for sym in ("S/", "$", "US$", "PEN")
        ) or (len(stripped) < 20 and any(c.isdigit() for c in stripped)):
            if "price" not in current:
                current["price"] = stripped
                continue

        if "price" in current and "title" not in current:
            current["title"] = stripped
            continue

        if "title" in current and "location" not in current:
            current["location"] = stripped
            continue

    if current.get("title"):
        listings.append(current)

    normalized: list[dict[str, Any]] = []
    for item in listings:
        price_str = item.get("price", "")
        price_num, currency = _parse_price(price_str)

        if price_num <= 0:
            continue

        listing = MarketplaceListing(
            title=item.get("title", ""),
            price=price_str,
            location=item.get("location", query),
            url=item.get("url", ""),
            image_url=item.get("image_url", ""),
            description=item.get("description", ""),
            price_numeric=price_num,
            currency=currency,
        )
        normalized.append(asdict(listing))

    return normalized
