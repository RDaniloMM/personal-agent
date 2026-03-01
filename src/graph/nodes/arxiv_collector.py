"""LangGraph node: collect Arxiv papers."""

from __future__ import annotations

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState


async def collect_arxiv_node(state: AgentState) -> dict:
    """Node that queries Arxiv and appends papers to state."""
    logger.info("═══ Node: collect_arxiv ═══")
    settings = get_settings()

    try:
        from src.research.arxiv_client import collect_arxiv_papers

        papers = await collect_arxiv_papers(settings)
        logger.info("Arxiv node collected {} papers", len(papers))
        return {"arxiv_papers": papers}

    except Exception as exc:
        error_msg = f"Arxiv collection failed: {exc}"
        logger.error(error_msg)
        return {"errors": [error_msg]}
