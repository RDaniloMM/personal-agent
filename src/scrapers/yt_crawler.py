"""YouTube crawler: yt-dlp search + YouTube Data API feeds + yt-dlp enrichment.

Strategy:
    1. yt-dlp ``ytsearch`` → discover videos for each research interest
       (fast, no browser needed).
    2. YouTube Data API v3 (OAuth2) → fetch latest uploads from
       subscribed channels for personalised discovery.
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

    # Phase 1b: personalised feeds via YouTube Data API (OAuth2)
    token_path = settings.youtube_token_path
    if token_path.exists():
        logger.info("YouTube OAuth token found — fetching subscription feeds")
        api_urls = await _discover_from_api(token_path, settings.youtube_client_secret_path)
        all_urls.extend(api_urls)
    else:
        logger.warning(
            "YouTube OAuth token not found at {}. "
            "Personalised feeds unavailable. "
            "Run: uv run python -m src.scrapers.youtube_auth",
            token_path,
        )

    # Deduplicate, preserve order
    video_urls = _deduplicate(all_urls)

    if not video_urls:
        logger.warning("No YouTube video URLs discovered")
        return []

    logger.info("Discovered {} unique video URLs", len(video_urls))

    # Phase 2: enrich with yt-dlp (metadata + subtitles)
    videos = await _enrich_videos(video_urls[:_MAX_VIDEOS_TO_ENRICH])

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


# ── Phase 1b: Personalised feed discovery via YouTube Data API ───────────

# Max recent videos to pull per subscribed channel
_VIDEOS_PER_CHANNEL = 3
# Max subscriptions to scan (API quota: 1 unit per sub page)
_MAX_SUBSCRIPTIONS = 50


async def _discover_from_api(token_path: Path, client_secret_path: Path) -> list[str]:
    """Use YouTube Data API v3 to list subscriptions and fetch recent uploads."""
    urls: list[str] = []

    try:
        from src.scrapers.youtube_auth import build_youtube_service

        youtube = build_youtube_service(token_path, client_secret_path)

        # Step 1: get subscribed channel IDs
        channel_ids: list[str] = []
        request = youtube.subscriptions().list(
            part="snippet",
            mine=True,
            maxResults=50,
            order="relevance",
        )
        while request and len(channel_ids) < _MAX_SUBSCRIPTIONS:
            response = request.execute()
            for item in response.get("items", []):
                ch_id = item["snippet"]["resourceId"]["channelId"]
                channel_ids.append(ch_id)
            request = youtube.subscriptions().list_next(request, response)

        logger.info("YouTube API: found {} subscriptions", len(channel_ids))

        # Step 2: get recent videos from each channel
        # Use search.list (costs 100 units per call) — batch channels
        # to stay under quota.  Alternative: channels.list → uploads
        # playlist → playlistItems.list (3 units per channel, cheaper).
        for ch_id in channel_ids:
            try:
                # Get uploads playlist ID (costs 1 unit)
                ch_resp = youtube.channels().list(
                    part="contentDetails",
                    id=ch_id,
                ).execute()
                items = ch_resp.get("items", [])
                if not items:
                    continue
                uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

                # Get latest videos from uploads playlist (costs 1 unit)
                pl_resp = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=uploads_id,
                    maxResults=_VIDEOS_PER_CHANNEL,
                ).execute()
                for vid in pl_resp.get("items", []):
                    vid_id = vid["snippet"]["resourceId"].get("videoId", "")
                    if vid_id:
                        urls.append(f"https://www.youtube.com/watch?v={vid_id}")
            except Exception as exc:
                logger.debug("API error for channel {}: {}", ch_id, exc)

        logger.info("YouTube API: discovered {} videos from subscriptions", len(urls))

    except Exception as exc:
        logger.error("YouTube Data API discovery failed: {}", exc)

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
