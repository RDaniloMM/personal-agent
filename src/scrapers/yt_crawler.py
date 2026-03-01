"""YouTube crawler using Crawl4AI with identity-based browsing."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from loguru import logger

from src.config import Settings
from src.graph.state import YouTubeVideo


# ── JS helpers ───────────────────────────────────────────────────────────────

SCROLL_JS = """
(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    for (let i = 0; i < 5; i++) {
        window.scrollBy(0, window.innerHeight);
        await delay(2000);
    }
})();
"""

# ── Target URLs ──────────────────────────────────────────────────────────────

YOUTUBE_FEED_URLS = [
    "https://www.youtube.com/feed/subscriptions",
    "https://www.youtube.com/feed/trending",
    "https://www.youtube.com/results?search_query=AI+agents+2026",
    "https://www.youtube.com/results?search_query=LLM+evaluation+benchmark",
]


async def crawl_youtube(settings: Settings) -> list[dict[str, Any]]:
    """Scrape YouTube feeds and search results using a persistent Google profile.

    The authenticated session lets us access the subscriptions feed and
    personalised recommendations.
    """
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
    )

    browser_config = BrowserConfig(
        headless=True,
        use_managed_browser=True,
        user_data_dir=str(settings.google_profile_path),
        browser_type="chromium",
    )

    crawl_config = CrawlerRunConfig(
        js_code=SCROLL_JS,
        wait_for="css:ytd-rich-item-renderer, ytd-video-renderer",
        page_timeout=60000,
        magic=True,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        locale="es-PE",
    )

    all_videos: list[dict[str, Any]] = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in YOUTUBE_FEED_URLS:
            logger.info("Crawling YouTube: {}", url)

            try:
                result = await crawler.arun(url=url, config=crawl_config)

                if not result.success:
                    logger.warning("YT crawl failed for {}: {}", url, result.error_message)
                    continue

                videos = _parse_videos(result.markdown, url)
                all_videos.extend(videos)
                logger.info("Found {} videos from {}", len(videos), url)

                await asyncio.sleep(4)

            except Exception as exc:
                logger.error("Error crawling YT {}: {}", url, exc)

    # Deduplicate by title (rough)
    seen_titles: set[str] = set()
    unique: list[dict[str, Any]] = []
    for v in all_videos:
        t = v.get("title", "").lower().strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            unique.append(v)

    logger.info("Total unique YouTube videos scraped: {}", len(unique))
    return unique


def _parse_videos(markdown: str, source_url: str) -> list[dict[str, Any]]:
    """Parse YouTube video entries from crawled markdown.

    YouTube markdown typically contains lines like:
        ## Video Title
        Channel Name · 123K views · 2 hours ago
        Description snippet …
    """
    videos: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    lines = markdown.strip().splitlines()

    for line in lines:
        stripped = line.strip()

        # Heading-like line → new video title
        if stripped.startswith("#"):
            # Flush previous
            if current.get("title"):
                videos.append(current)
            current = {"title": stripped.lstrip("# ").strip()}
            continue

        # Metadata line (channel · views · time)
        if "·" in stripped and current.get("title") and "channel" not in current:
            parts = [p.strip() for p in stripped.split("·")]
            current["channel"] = parts[0] if parts else ""
            current["views"] = parts[1] if len(parts) > 1 else ""
            current["duration"] = parts[2] if len(parts) > 2 else ""
            continue

        # Link to video
        if "/watch?v=" in stripped or "youtu.be/" in stripped:
            # Extract URL from markdown link syntax [text](url)
            if "(" in stripped and ")" in stripped:
                url = stripped.split("(")[-1].rstrip(")")
                current["url"] = url
            elif stripped.startswith("http"):
                current["url"] = stripped
            continue

        # Description (first non-empty line after metadata)
        if current.get("channel") and "description" not in current and stripped:
            current["description"] = stripped[:300]
            continue

    # Flush last
    if current.get("title"):
        videos.append(current)

    # Normalize
    normalized: list[dict[str, Any]] = []
    for item in videos:
        video = YouTubeVideo(
            title=item.get("title", ""),
            channel=item.get("channel", ""),
            url=item.get("url", ""),
            views=item.get("views", ""),
            duration=item.get("duration", ""),
            description=item.get("description", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
        )
        normalized.append(asdict(video))

    return normalized
