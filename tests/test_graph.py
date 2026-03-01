"""Tests for the LangGraph agent graph."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.graph.state import AgentState


class TestGraphRouting:
    """Test the conditional routing logic."""

    def test_route_fb_only(self):
        from src.graph.builder import route_by_task

        state = AgentState(task_type="fb")
        assert route_by_task(state) == ["scrape_fb"]

    def test_route_youtube_only(self):
        from src.graph.builder import route_by_task

        state = AgentState(task_type="youtube")
        assert route_by_task(state) == ["scrape_youtube"]

    def test_route_arxiv_only(self):
        from src.graph.builder import route_by_task

        state = AgentState(task_type="arxiv")
        assert route_by_task(state) == ["collect_arxiv"]

    def test_route_all(self):
        from src.graph.builder import route_by_task

        state = AgentState(task_type="all")
        result = route_by_task(state)
        assert "scrape_fb" in result
        assert "scrape_youtube" in result
        assert "collect_arxiv" in result


class TestAgentState:
    """Test the AgentState dataclass."""

    def test_default_state(self):
        state = AgentState()
        assert state.task_type == "all"
        assert state.marketplace_listings == []
        assert state.youtube_videos == []
        assert state.arxiv_papers == []
        assert state.vectors_indexed == 0
        assert state.notes_written == []
        assert state.errors == []
        assert state.retry_count == 0

    def test_state_with_task(self):
        state = AgentState(task_type="arxiv")
        assert state.task_type == "arxiv"

    def test_state_preserves_data(self):
        state = AgentState()
        state.marketplace_listings.append({"title": "Test", "price": "100"})
        assert len(state.marketplace_listings) == 1


class TestGraphBuild:
    """Test that the graph compiles without errors."""

    def test_build_graph_compiles(self):
        from src.graph.builder import build_graph

        graph = build_graph()
        assert graph is not None
