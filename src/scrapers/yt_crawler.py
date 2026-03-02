"""YouTube crawler: browser-based feed scraping + yt-dlp metadata extraction.

Strategy:
    1. Crawl4AI + Google profile → scrape personalised feeds (subscriptions,
       recommendations, home) to discover video URLs.
    2. yt-dlp → for each discovered video, extract rich metadata: title,
       description, tags, upload date, duration, view count.
    3. yt-dlp → download auto-generated subtitles (es/en) so the LLM can
       "read" the video content without watching it.

The result is a list of YouTubeVideo dicts ready for embedding + Obsidian notes.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from dataclasses import asdict
from typing import Any

from loguru import logger

from src.config import Settings
from src.graph.state import YouTubeVideo


# ── JS helpers ───────────────────────────────────────────────────────────────

SCROLL_JS = """
(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    for (let i = 0; i < 8; i++) {
        window.scrollBy(0, window.innerHeight);
        await delay(2000);
    }
})();
"""

# ── Feed URLs ────────────────────────────────────────────────────────────────

# Auth-required (personalised)
YOUTUBE_AUTH_URLS = [
    "https://www.youtube.com/",                          # Home / recommendations
    "https://www.youtube.com/feed/subscriptions",        # Subscriptions
]

# Fallback public URLs (no auth needed)
YOUTUBE_PUBLIC_URLS = [
    "https://www.youtube.com/results?search_query=AI+agents+2026",
    "https://www.youtube.com/results?search_query=LLM+evaluation+benchmark",
    "https://www.youtube.com/results?search_query=multi+agent+systems+LLM",
]

# Max videos to enrich with yt-dlp (each takes ~2-3s)
_MAX_VIDEOS_TO_ENRICH = 30

# Max subtitle chars to keep (saves tokens)
_SUBTITLE_LIMIT = 3000


# ── Main entry point ─────────────────────────────────────────────────────────


async def crawl_youtube(settings: Settings) -> list[dict[str, Any]]:
    """Discover videos from YouTube feeds and enrich them via yt-dlp.

    Returns a list of YouTubeVideo dicts with title, description, tags,
    upload_date, subtitles (truncated transcript), etc.
    """
    # Phase 1: discover video URLs from feeds
    video_urls = await _discover_video_urls(settings)

    if not video_urls:
        logger.warning("No YouTube video URLs discovered from feeds")
        return []

    logger.info("Discovered {} unique video URLs from feeds", len(video_urls))

    # Phase 2: enrich with yt-dlp (metadata + subtitles)
    videos = await _enrich_videos(video_urls[:_MAX_VIDEOS_TO_ENRICH])

    logger.info("Enriched {}/{} videos with metadata + subtitles", len(videos), len(video_urls))
    return videos


# ── Phase 1: Feed discovery via Crawl4AI ─────────────────────────────────────


async def _discover_video_urls(settings: Settings) -> list[str]:
    """Use Crawl4AI with Google profile to scrape feed pages and extract
    /watch?v= URLs."""
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
    )

    profile_path = settings.google_profile_path
    has_profile = profile_path.exists() and any(profile_path.iterdir())

    if not has_profile:
        logger.warning(
            "Google profile not found at {}. "
            "Personalised feeds unavailable. "
            "Create profile: uv run python -m src.scrapers.browser_profiles google",
            profile_path,
        )

    browser_config = BrowserConfig(
        headless=True,
        use_managed_browser=True,
        user_data_dir=str(profile_path) if has_profile else None,
        browser_type="chromium",
    )

    crawl_config = CrawlerRunConfig(
        js_code=SCROLL_JS,
        wait_for="css:ytd-rich-item-renderer, ytd-video-renderer, ytd-compact-video-renderer, a[href*='watch']",
        page_timeout=45000,
        magic=True,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        locale="es-PE",
    )

    # Use auth URLs if profile exists, always add public search
    urls: list[str] = []
    if has_profile:
        urls.extend(YOUTUBE_AUTH_URLS)
        logger.info("Google profile found — using personalised feeds + search")
    urls.extend(YOUTUBE_PUBLIC_URLS)

    all_video_urls: list[str] = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            logger.info("Scraping YouTube feed: {}", url)
            try:
                result = await crawler.arun(url=url, config=crawl_config)

                if not result.success:
                    logger.warning("YT feed scrape failed for {}: {}", url, result.error_message)
                    continue

                # Extract /watch?v= URLs from the HTML/links
                found = _extract_video_urls(result.html or result.markdown or "")
                all_video_urls.extend(found)
                logger.info("Found {} video URLs from {}", len(found), url)

                await asyncio.sleep(3)

            except Exception as exc:
                logger.error("Error scraping YT feed {}: {}", url, exc)

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for u in all_video_urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return unique


def _extract_video_urls(html_or_md: str) -> list[str]:
    """Extract unique YouTube video URLs from HTML or markdown content."""
    pattern = r'/watch\?v=([\w-]{11})'
    ids = re.findall(pattern, html_or_md)

    seen: set[str] = set()
    urls: list[str] = []
    for vid in ids:
        if vid not in seen:
            seen.add(vid)
            urls.append(f"https://www.youtube.com/watch?v={vid}")

    return urls


# ── Phase 2: yt-dlp metadata + subtitles ────────────────────────────────────


async def _enrich_videos(urls: list[str]) -> list[dict[str, Any]]:
    """Use yt-dlp to extract metadata and subtitles for each video."""
    videos: list[dict[str, Any]] = []

    for i, url in enumerate(urls):
        try:
            info = await _ytdlp_extract(url)
            if info:
                videos.append(info)
                logger.debug("Enriched ({}/{}): {}", i + 1, len(urls), info.get("title", "")[:60])
        except Exception as exc:
            logger.warning("yt-dlp failed for {}: {}", url, exc)

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    return videos


async def _ytdlp_extract(url: str) -> dict[str, Any] | None:
    """Run yt-dlp to extract metadata, then fetch subtitles separately."""
    # Step 1: metadata
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--dump-json",
        "--no-warnings",
        "--no-playlist",
        url,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        if "Private video" in err or "Sign in" in err:
            logger.debug("Skipping private/auth-required video: {}", url)
            return None
        logger.warning("yt-dlp metadata error for {}: {}", url, err[:200])
        return None

    try:
        data = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError:
        return None

    # Step 2: subtitles
    subtitles = await _fetch_subtitles(url)

    video = YouTubeVideo(
        title=data.get("title", ""),
        channel=data.get("channel", data.get("uploader", "")),
        url=data.get("webpage_url", url),
        video_id=data.get("id", ""),
        views=str(data.get("view_count", "")),
        duration=_format_duration(data.get("duration", 0)),
        upload_date=_format_date(data.get("upload_date", "")),
        description=(data.get("description", "") or "")[:1000],
        tags=(data.get("tags") or [])[:15],  # limit tags
        subtitles=subtitles,
        thumbnail_url=data.get("thumbnail", ""),
    )

    return asdict(video)


async def _fetch_subtitles(url: str) -> str:
    """Download subtitles via yt-dlp and extract plain text."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--no-warnings",
            "--no-playlist",
            "--write-sub",
            "--write-auto-sub",
            "--sub-lang", "es,en",
            "--sub-format", "vtt",
            "--output", os.path.join(tmpdir, "%(id)s.%(ext)s"),
            url,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return ""

        # Find subtitle files — prefer Spanish over English
        vtt_files = sorted(
            [f for f in os.listdir(tmpdir) if f.endswith(".vtt")],
            key=lambda f: (0 if ".es." in f else 1),
        )

        for f in vtt_files:
            vtt_path = os.path.join(tmpdir, f)
            text = _parse_vtt(vtt_path)
            if text:
                return text[:_SUBTITLE_LIMIT]

    return ""


def _parse_vtt(path: str) -> str:
    """Parse a VTT subtitle file into clean plain text."""
    lines: list[str] = []
    seen: set[str] = set()

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            # Skip timestamps, headers, empty lines
            if (not line or line.startswith("WEBVTT") or line.startswith("Kind:")
                    or line.startswith("Language:") or "-->" in line
                    or (len(line) < 12 and ":" in line and line[0].isdigit())):
                continue
            # Remove HTML tags (<c>, </c>, etc.)
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean and clean not in seen:
                seen.add(clean)
                lines.append(clean)

    return " ".join(lines)


def _format_duration(seconds: int | float | None) -> str:
    """Convert seconds to H:MM:SS or MM:SS format."""
    if not seconds:
        return ""
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_date(date_str: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str
