"""YouTube crawler: yt-dlp search + yt-dlp cookie-based feeds + yt-dlp enrichment.

Strategy:
    1. yt-dlp ``ytsearch`` → discover videos for each research interest
       (fast, no browser needed).
    2. yt-dlp + cookies.txt → fetch personalised feeds (home,
       subscriptions) using exported browser cookies — no Playwright needed.
    3. yt-dlp → for each discovered video, extract rich metadata: title,
       description, tags, upload date, duration, view count.
    4. yt-dlp → download auto-generated subtitles (es/en) so the LLM can
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
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import Settings
from src.graph.state import YouTubeVideo


# ── yt-dlp search queries (no browser needed) ───────────────────────────────

SEARCH_QUERIES = [
    "AI agent evaluation framework",
    "LLM evaluation benchmark",
    "multi agent systems LLM",
]

# How many results per search query
_SEARCH_RESULTS_PER_QUERY = 10

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
    all_urls: list[str] = []

    # Phase 1a: search discovery via yt-dlp (fast, no browser)
    search_urls = await _discover_via_search()
    all_urls.extend(search_urls)

    # Phase 1b: personalised feeds via yt-dlp + cookies
    cookies_file = settings.cookies_path
    if cookies_file.exists():
        logger.info("cookies.txt found — fetching personalised feeds via yt-dlp")
        feed_urls = await _discover_from_feeds(cookies_file)
        all_urls.extend(feed_urls)
    else:
        logger.warning(
            "cookies.txt not found at {}. "
            "Personalised feeds unavailable. "
            "Export cookies from Chrome and place at {}",
            cookies_file,
            cookies_file,
        )

    # Deduplicate, preserve order
    video_urls = _deduplicate(all_urls)

    if not video_urls:
        logger.warning("No YouTube video URLs discovered")
        return []

    logger.info("Discovered {} unique video URLs", len(video_urls))

    # Phase 2: enrich with yt-dlp (metadata + subtitles)
    cookies_arg = str(cookies_file) if cookies_file.exists() else None
    videos = await _enrich_videos(video_urls[:_MAX_VIDEOS_TO_ENRICH], cookies_arg)

    logger.info(
        "Enriched {}/{} videos with metadata + subtitles",
        len(videos),
        len(video_urls),
    )
    return videos


# ── Phase 1a: Search discovery via yt-dlp ────────────────────────────────────


async def _discover_via_search() -> list[str]:
    """Use ``yt-dlp --flat-playlist ytsearchN:query`` to discover video URLs.

    This is fast and reliable — no browser needed.
    """
    urls: list[str] = []

    for query in SEARCH_QUERIES:
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                f"ytsearch{_SEARCH_RESULTS_PER_QUERY}:{query}",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=30,
            )

            if proc.returncode != 0:
                logger.warning(
                    "yt-dlp search failed for '{}': {}",
                    query,
                    stderr.decode(errors="replace")[:200],
                )
                continue

            # Each line is a JSON object
            for line in stdout.decode(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    vid_url = data.get("url") or data.get("webpage_url", "")
                    vid_id = data.get("id", "")
                    if vid_id:
                        urls.append(f"https://www.youtube.com/watch?v={vid_id}")
                    elif "/watch?v=" in vid_url:
                        urls.append(vid_url)
                except json.JSONDecodeError:
                    continue

            logger.info("yt-dlp search '{}': found {} videos", query, len(urls))

        except asyncio.TimeoutError:
            logger.warning("yt-dlp search timed out for '{}'", query)
        except Exception as exc:
            logger.error("yt-dlp search error for '{}': {}", query, exc)

    return urls


# ── Phase 1b: Personalised feed discovery via yt-dlp + cookies ───────────────

_FEED_PLAYLIST_URLS = [
    # yt-dlp can extract the YouTube home feed and subscriptions as playlists
    ":ythome",                               # Home / recommendations
    ":ytsubs",                               # Subscriptions feed
    "https://www.youtube.com/feed/trending",  # Trending (fallback, no auth needed)
]


async def _discover_from_feeds(cookies_file: Path) -> list[str]:
    """Use yt-dlp with cookies.txt to fetch personalised feed URLs."""
    urls: list[str] = []

    for feed in _FEED_PLAYLIST_URLS:
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                "--cookies", str(cookies_file),
                "--playlist-end", "15",  # limit to 15 per feed
                feed,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=45,
            )

            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                logger.warning("yt-dlp feed '{}' failed: {}", feed, err[:200])
                continue

            count = 0
            for line in stdout.decode(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    vid_id = data.get("id", "")
                    if vid_id and len(vid_id) == 11:
                        urls.append(f"https://www.youtube.com/watch?v={vid_id}")
                        count += 1
                except json.JSONDecodeError:
                    continue

            logger.info("yt-dlp feed '{}': found {} videos", feed, count)

        except asyncio.TimeoutError:
            logger.warning("yt-dlp feed '{}' timed out", feed)
        except Exception as exc:
            logger.error("yt-dlp feed '{}' error: {}", feed, exc)

    return urls


def _deduplicate(urls: list[str]) -> list[str]:
    """Remove duplicate URLs preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for u in urls:
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


async def _enrich_videos(urls: list[str], cookies: str | None = None) -> list[dict[str, Any]]:
    """Use yt-dlp to extract metadata and subtitles for each video."""
    videos: list[dict[str, Any]] = []

    for i, url in enumerate(urls):
        try:
            info = await _ytdlp_extract(url, cookies)
            if info:
                videos.append(info)
                logger.debug("Enriched ({}/{}): {}", i + 1, len(urls), info.get("title", "")[:60])
        except Exception as exc:
            logger.warning("yt-dlp failed for {}: {}", url, exc)

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    return videos


async def _ytdlp_extract(url: str, cookies: str | None = None) -> dict[str, Any] | None:
    """Run yt-dlp to extract metadata, then fetch subtitles separately."""
    # Step 1: metadata
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--dump-json",
        "--no-warnings",
        "--no-playlist",
    ]
    if cookies:
        cmd.extend(["--cookies", cookies])
    cmd.append(url)

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
    subtitles = await _fetch_subtitles(url, cookies)

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


async def _fetch_subtitles(url: str, cookies: str | None = None) -> str:
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
        ]
        if cookies:
            cmd.extend(["--cookies", cookies])
        cmd.append(url)

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
