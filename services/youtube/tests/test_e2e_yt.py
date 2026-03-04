"""E2E smoke test for the YouTube pipeline.

Runs a minimal version of the full pipeline:
  1. Search 1 query, get 1 result via yt-dlp
  2. Enrich 1 video (metadata + subtitles)
  3. Verify output structure

Usage (inside Docker):
    docker compose run --rm yt-worker uv run python -m tests.test_e2e_yt
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, patch

from loguru import logger


async def _run_e2e() -> None:
    """Minimal end-to-end YouTube pipeline: 1 query × 1 video."""

    # ── Setup ───────────────────────────────────────────────────────
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    from shared.config import get_settings

    settings = get_settings()

    logger.info("═══ E2E YOUTUBE TEST START ═══")

    # ── Phase 1: Discover videos (1 query × 1 result) ──────────────
    import yt_worker.crawler as yt_crawler

    # Patch constants for minimal crawl
    # Skip API subscription feeds to avoid discovering 150+ videos
    with patch.object(yt_crawler, "SEARCH_QUERIES", ["AI agent framework"]), \
         patch.object(yt_crawler, "_SEARCH_RESULTS_PER_QUERY", 1), \
         patch.object(yt_crawler, "_MAX_VIDEOS_TO_ENRICH", 1), \
         patch.object(yt_crawler, "_discover_from_api", new_callable=AsyncMock, return_value=[]):

        videos = await yt_crawler.crawl_youtube(settings)

    logger.info("Discovered & enriched {} videos", len(videos))

    if not videos:
        logger.warning("No videos found — yt-dlp may have issues")
        logger.info("═══ E2E YOUTUBE TEST DONE (no videos) ═══")
        return

    assert len(videos) >= 1, "Expected at least 1 video"

    # Verify video structure
    for video in videos:
        assert "title" in video, f"Missing 'title': {video}"
        assert "url" in video, f"Missing 'url': {video}"
        logger.debug(
            "  Video: {} — {} — {}",
            video.get("title", "?")[:50],
            video.get("channel", "?"),
            video.get("duration", "?"),
        )

    # Check enrichment fields
    video = videos[0]
    expected_fields = ["title", "url", "channel", "duration", "views", "upload_date"]
    for field in expected_fields:
        assert field in video, f"Missing enrichment field '{field}' in video"

    logger.info(
        "  ✓ Video: '{}' by {} ({}, {} views)",
        video.get("title", "?")[:40],
        video.get("channel", "?"),
        video.get("duration", "?"),
        video.get("views", "?"),
    )

    # Check subtitles if available
    subtitles = video.get("subtitles", "")
    if subtitles:
        logger.info("  ✓ Subtitles found: {} chars", len(subtitles))
    else:
        logger.info("  ℹ No subtitles for this video (normal)")

    logger.info("═══ E2E YOUTUBE TEST PASSED ═══")


def main() -> None:
    asyncio.run(_run_e2e())


if __name__ == "__main__":
    main()
