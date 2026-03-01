"""Tests for the Arxiv collector."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from src.graph.state import ArxivPaper


class FakeResult:
    """Mimics an arxiv.Result object."""

    def __init__(self, entry_id: str, title: str, summary: str):
        self.entry_id = entry_id
        self.title = title
        self.summary = summary
        self.authors = [MagicMock(name="Author A"), MagicMock(name="Author B")]
        for i, a in enumerate(self.authors):
            a.name = f"Author {chr(65 + i)}"
        self.categories = ["cs.AI"]
        self.pdf_url = f"https://arxiv.org/pdf/{entry_id}"
        self.published = MagicMock()
        self.published.isoformat.return_value = "2026-02-28T00:00:00"


@pytest.fixture
def settings():
    """Return a mock Settings object."""
    s = MagicMock()
    s.arxiv_max_results_per_query = 5
    return s


@pytest.mark.asyncio
async def test_collect_arxiv_papers_returns_deduped(settings):
    """Papers with the same arxiv_id should be deduplicated."""
    from src.research.arxiv_client import collect_arxiv_papers

    fake_results = [
        FakeResult("2601.00001v1", "Paper A", "Abstract A"),
        FakeResult("2601.00001v1", "Paper A Duplicate", "Abstract A dup"),
        FakeResult("2601.00002v1", "Paper B", "Abstract B"),
    ]

    with patch("src.research.arxiv_client.arxiv") as mock_arxiv:
        mock_client = MagicMock()
        mock_arxiv.Client.return_value = mock_client
        mock_client.results.return_value = iter(fake_results)
        mock_arxiv.Search = MagicMock()
        mock_arxiv.SortCriterion.SubmittedDate = "submittedDate"
        mock_arxiv.SortOrder.Descending = "descending"

        papers = await collect_arxiv_papers(settings)

    # Should have 2 unique papers, not 3
    ids = [p["arxiv_id"] for p in papers]
    assert len(set(ids)) == len(ids)


@pytest.mark.asyncio
async def test_collect_arxiv_handles_errors_gracefully(settings):
    """If a query fails, the collector should continue with other queries."""
    from src.research.arxiv_client import collect_arxiv_papers

    with patch("src.research.arxiv_client.arxiv") as mock_arxiv:
        mock_client = MagicMock()
        mock_arxiv.Client.return_value = mock_client
        # First call raises, subsequent calls return empty
        mock_client.results.side_effect = [
            Exception("Network error"),
            iter([FakeResult("2601.00003v1", "Paper C", "Abstract C")]),
            iter([]),
            iter([]),
        ]
        mock_arxiv.Search = MagicMock()
        mock_arxiv.SortCriterion.SubmittedDate = "submittedDate"
        mock_arxiv.SortOrder.Descending = "descending"

        papers = await collect_arxiv_papers(settings)

    # Should have at least 1 paper from the successful query
    assert len(papers) >= 1
