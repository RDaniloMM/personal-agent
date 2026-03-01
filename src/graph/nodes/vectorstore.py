"""LangGraph node: index collected data into PostgreSQL + pgvector."""

from __future__ import annotations

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState


async def index_vectors_node(state: AgentState) -> dict:
    """Node that embeds and upserts all collected data into pgvector."""
    logger.info("═══ Node: index_vectors ═══")
    settings = get_settings()
    total_indexed = 0

    try:
        from src.storage.zvec_store import upsert_documents

        # Index FB Marketplace listings
        if state.marketplace_listings:
            count = upsert_documents(
                collection_name="fb_marketplace",
                documents=state.marketplace_listings,
                text_field="title",
                settings=settings,
            )
            total_indexed += count
            logger.info("Indexed {} FB listings", count)

        # Index YouTube videos
        if state.youtube_videos:
            count = upsert_documents(
                collection_name="youtube_feed",
                documents=state.youtube_videos,
                text_field="title",
                settings=settings,
            )
            total_indexed += count
            logger.info("Indexed {} YouTube videos", count)

        # Index Arxiv papers (embed the abstract for richer semantics)
        if state.arxiv_papers:
            count = upsert_documents(
                collection_name="arxiv_papers",
                documents=state.arxiv_papers,
                text_field="abstract",
                settings=settings,
            )
            total_indexed += count
            logger.info("Indexed {} Arxiv papers", count)

        return {"vectors_indexed": total_indexed}

    except Exception as exc:
        error_msg = f"Vector indexing failed: {exc}"
        logger.error(error_msg)
        return {"errors": [error_msg]}
