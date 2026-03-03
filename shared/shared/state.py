"""Data models shared across all microservices."""

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
    price_numeric: float = 0.0
    currency: str = "PEN"
    is_deal: bool = False
    deal_reason: str = ""
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
    subtitles: str = ""
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
