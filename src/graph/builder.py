"""LangGraph graph builder – compiles the agent pipeline."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from loguru import logger

from src.graph.nodes.arxiv_collector import collect_arxiv_node
from src.graph.nodes.fb_marketplace import scrape_fb_node
from src.graph.nodes.obsidian_writer import write_obsidian_node
from src.graph.nodes.vectorstore import index_vectors_node
from src.graph.nodes.youtube import scrape_youtube_node
from src.graph.state import AgentState


# ── Router ───────────────────────────────────────────────────────────────────


def route_by_task(state: AgentState) -> list[str]:
    """Conditional edge: decide which scraper nodes to run based on task_type.

    When task_type == "all", all three scraper nodes run in parallel (fan-out).
    """
    task = state.task_type

    if task == "fb":
        return ["scrape_fb"]
    elif task == "youtube":
        return ["scrape_youtube"]
    elif task == "arxiv":
        return ["collect_arxiv"]
    else:  # "all"
        return ["scrape_fb", "scrape_youtube", "collect_arxiv"]


# ── Graph construction ───────────────────────────────────────────────────────


def build_graph() -> Any:
    """Build and compile the LangGraph StateGraph.

    Topology::

        START
          │
          ├─▶ scrape_fb ──────┐
          ├─▶ scrape_youtube ─┤  (fan-out based on task_type)
          └─▶ collect_arxiv ──┘
                              │
                        index_vectors
                              │
                       write_obsidian
                              │
                             END
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ────────────────────────────────────────────────────────
    graph.add_node("scrape_fb", scrape_fb_node)
    graph.add_node("scrape_youtube", scrape_youtube_node)
    graph.add_node("collect_arxiv", collect_arxiv_node)
    graph.add_node("index_vectors", index_vectors_node)
    graph.add_node("write_obsidian", write_obsidian_node)

    # ── Conditional fan-out from START ───────────────────────────────────
    graph.add_conditional_edges(
        START,
        route_by_task,
        {
            "scrape_fb": "scrape_fb",
            "scrape_youtube": "scrape_youtube",
            "collect_arxiv": "collect_arxiv",
        },
    )

    # ── All scraper nodes converge into index_vectors ────────────────────
    graph.add_edge("scrape_fb", "index_vectors")
    graph.add_edge("scrape_youtube", "index_vectors")
    graph.add_edge("collect_arxiv", "index_vectors")

    # ── Then write Obsidian notes ────────────────────────────────────────
    graph.add_edge("index_vectors", "write_obsidian")

    # ── Finally, end ─────────────────────────────────────────────────────
    graph.add_edge("write_obsidian", END)

    # ── Compile ──────────────────────────────────────────────────────────
    compiled = graph.compile()
    logger.info("Agent graph compiled successfully")
    return compiled
