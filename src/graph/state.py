"""LangGraph agent state definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class MarketplaceListing:
    """A single FB Marketplace product listing."""

    title: str
    price: str
    location: str
    url: str
    image_url: str = ""
    description: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "fb_marketplace"


@dataclass
class YouTubeVideo:
    """A single YouTube video entry with rich metadata."""

    title: str
    channel: str
    url: str
    video_id: str = ""
    views: str = ""
    duration: str = ""
    upload_date: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    subtitles: str = ""  # truncated transcript text
    thumbnail_url: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "youtube"


@dataclass
class ArxivPaper:
    """A single Arxiv paper."""

    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    pdf_url: str
    published: str
    source: str = "arxiv"


# ── Agent state ──────────────────────────────────────────────────────────────

TaskType = Literal["fb", "youtube", "arxiv", "all"]


@dataclass
class AgentState:
    """State that flows through the LangGraph graph.

    Using a dataclass rather than TypedDict so we get default values
    and methods.  LangGraph ≥ 0.4 supports dataclass states natively.
    """

    task_type: TaskType = "all"

    # Collected raw data (each node appends to the relevant list)
    marketplace_listings: list[dict[str, Any]] = field(default_factory=list)
    youtube_videos: list[dict[str, Any]] = field(default_factory=list)
    arxiv_papers: list[dict[str, Any]] = field(default_factory=list)

    # Vectors indexed in this run
    vectors_indexed: int = 0

    # Obsidian notes written in this run
    notes_written: list[str] = field(default_factory=list)

    # Error tracking
    errors: list[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2

    # Metadata
    run_started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
