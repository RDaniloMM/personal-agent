"""Tests for the Obsidian writer and scrapers (unit-level)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_vault(tmp_path: Path):
    """Create a temporary Obsidian vault directory."""
    vault = tmp_path / "test-vault"
    vault.mkdir()
    return vault


@pytest.fixture
def settings(tmp_vault: Path):
    """Return a mock Settings pointing to the temp vault."""
    s = MagicMock()
    s.obsidian_vault_path = tmp_vault

    def obsidian_subfolder(*parts):
        p = tmp_vault / "Agent-Research" / Path(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    s.obsidian_subfolder = obsidian_subfolder
    return s


class TestObsidianWriter:
    """Test the obsidian.py module."""

    def test_write_arxiv_paper(self, settings):
        from src.storage.obsidian import write_arxiv_paper

        paper = {
            "arxiv_id": "2601.12345v1",
            "title": "Test Paper on AI Agents",
            "authors": ["Alice", "Bob"],
            "abstract": "This paper explores autonomous AI agents.",
            "categories": ["cs.AI", "cs.CL"],
            "pdf_url": "https://arxiv.org/pdf/2601.12345v1",
            "published": "2026-01-15T00:00:00",
        }

        path = write_arxiv_paper(paper, settings)

        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "Test Paper on AI Agents" in content
        assert "2601.12345v1" in content
        assert "paper" in content  # tag in frontmatter (without #)

    def test_write_arxiv_paper_idempotent(self, settings):
        """Writing the same paper twice should not create a duplicate."""
        from src.storage.obsidian import write_arxiv_paper

        paper = {
            "arxiv_id": "2601.99999v1",
            "title": "Idempotent Paper",
            "authors": ["Test"],
            "abstract": "Test abstract.",
            "categories": ["cs.AI"],
            "pdf_url": "",
            "published": "2026-01-01T00:00:00",
        }

        path1 = write_arxiv_paper(paper, settings)
        path2 = write_arxiv_paper(paper, settings)
        assert path1 == path2

    def test_write_marketplace_summary(self, settings):
        from src.storage.obsidian import write_marketplace_summary

        listings = [
            {
                "title": "Laptop HP",
                "price": "S/ 1500",
                "location": "Tacna",
                "url": "https://fb.com/item/1",
            },
            {
                "title": "Kindle Paperwhite",
                "price": "S/ 300",
                "location": "Moquegua",
                "url": "https://fb.com/item/2",
            },
        ]

        path = write_marketplace_summary(listings, settings)

        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "Laptop HP" in content
        assert "S/ 1500" in content
        assert "marketplace" in content  # tag in frontmatter (without #)

    def test_write_youtube_summary(self, settings):
        from src.storage.obsidian import write_youtube_summary

        videos = [
            {
                "title": "AI Agents in 2026",
                "channel": "TechChannel",
                "url": "https://youtube.com/watch?v=abc",
                "views": "50K",
            },
        ]

        path = write_youtube_summary(videos, settings)

        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "AI Agents in 2026" in content
        assert "youtube" in content  # tag in frontmatter (without #)

    def test_write_idea_note(self, settings):
        from src.storage.obsidian import write_idea_note

        path = write_idea_note(
            title="Tendencia: evaluación de agentes",
            content="Se observa un crecimiento en papers sobre [[evaluación de agentes]].",
            tags=["agent", "evaluation", "trend"],
            settings=settings,
        )

        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "evaluación de agentes" in content
        assert "idea" in content  # tag in frontmatter (without #)


class TestFBCrawlerParser:
    """Test the FB listing parser (no network calls)."""

    def test_parse_listings_extracts_items(self):
        from src.scrapers.fb_crawler import _parse_listings

        markdown = """
S/ 1,200
Laptop Lenovo ThinkPad
Tacna

S/ 350
Libro Python Crash Course
Moquegua
"""
        listings = _parse_listings(markdown, "laptop", "tacna")
        assert len(listings) >= 2
        assert listings[0]["title"] == "Laptop Lenovo ThinkPad"
        assert listings[0]["price"] == "S/ 1,200"

    def test_parse_listings_empty_markdown(self):
        from src.scrapers.fb_crawler import _parse_listings

        listings = _parse_listings("", "query", "location")
        assert listings == []


class TestYTCrawlerParser:
    """Test the YouTube URL extraction and helpers (no network calls)."""

    def test_extract_video_urls(self):
        from src.scrapers.yt_crawler import _extract_video_urls

        html = """
        <a href="/watch?v=abc12345678">Video 1</a>
        <a href="/watch?v=xyz98765432">Video 2</a>
        <a href="/watch?v=abc12345678">Duplicate</a>
        <a href="/shorts/not-a-watch">Short</a>
        """
        urls = _extract_video_urls(html)
        assert len(urls) == 2
        assert "https://www.youtube.com/watch?v=abc12345678" in urls
        assert "https://www.youtube.com/watch?v=xyz98765432" in urls

    def test_format_duration(self):
        from src.scrapers.yt_crawler import _format_duration

        assert _format_duration(0) == ""
        assert _format_duration(None) == ""
        assert _format_duration(65) == "1:05"
        assert _format_duration(3661) == "1:01:01"

    def test_format_date(self):
        from src.scrapers.yt_crawler import _format_date

        assert _format_date("20260301") == "2026-03-01"
        assert _format_date("invalid") == "invalid"
        assert _format_date("") == ""

    def test_parse_vtt(self):
        import tempfile
        import os
        from src.scrapers.yt_crawler import _parse_vtt

        vtt_content = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
Hello world

00:00:02.000 --> 00:00:04.000
This is a test

00:00:04.000 --> 00:00:06.000
Hello world
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".vtt", delete=False, encoding="utf-8") as f:
            f.write(vtt_content)
            f.flush()
            result = _parse_vtt(f.name)
        os.unlink(f.name)
        assert "Hello world" in result
        assert "This is a test" in result
