"""LangGraph node: index collected data into PostgreSQL + pgvector."""

from __future__ import annotations

from loguru import logger

from src.config import get_settings
from src.graph.state import AgentState


async def index_vectors_node(state: AgentState) -> dict:
    """Node that embeds and upserts *new* data into pgvector.

    Papers/listings already present (by ID) are skipped to save
    embedding API calls and downstream LLM tokens.
    """
    logger.info("═══ Node: index_vectors ═══")
    settings = get_settings()
    total_indexed = 0

    try:
        from src.storage.zvec_store import get_existing_ids, upsert_documents

        # ── Filter out already-indexed documents ───────────────────────

        new_fb = state.marketplace_listings
        new_yt = state.youtube_videos
        new_arxiv = state.arxiv_papers

        if state.marketplace_listings:
            existing = get_existing_ids("fb_marketplace", settings)
            new_fb = [d for d in state.marketplace_listings
                      if d.get("url", "") and d["url"] not in existing]
            logger.info("FB: {} new / {} total (skipped {})",
                        len(new_fb), len(state.marketplace_listings),
                        len(state.marketplace_listings) - len(new_fb))

        if state.youtube_videos:
            existing = get_existing_ids("youtube_feed", settings)
            new_yt = [d for d in state.youtube_videos
                      if d.get("url", "") and d["url"] not in existing]
            logger.info("YT: {} new / {} total (skipped {})",
                        len(new_yt), len(state.youtube_videos),
                        len(state.youtube_videos) - len(new_yt))

        if state.arxiv_papers:
            existing = get_existing_ids("arxiv_papers", settings)
            new_arxiv = [p for p in state.arxiv_papers
                         if p.get("arxiv_id", "") not in existing]
            logger.info("Arxiv: {} new / {} total (skipped {})",
                        len(new_arxiv), len(state.arxiv_papers),
                        len(state.arxiv_papers) - len(new_arxiv))

        # ── Embed & upsert only new documents ────────────────────────

        if new_fb:
            count = upsert_documents("fb_marketplace", new_fb, "title", settings)
            total_indexed += count
            logger.info("Indexed {} FB listings", count)

        if new_yt:
            count = upsert_documents("youtube_feed", new_yt, "title", settings)
            total_indexed += count
            logger.info("Indexed {} YouTube videos", count)

        if new_arxiv:
            count = upsert_documents("arxiv_papers", new_arxiv, "abstract", settings)
            total_indexed += count
            logger.info("Indexed {} Arxiv papers", count)

        # Propagate only NEW papers to downstream nodes (write_obsidian)
        # so the LLM doesn’t re-analyze papers it already processed.
        result: dict = {"vectors_indexed": total_indexed}
        if state.arxiv_papers and len(new_arxiv) < len(state.arxiv_papers):
            result["arxiv_papers"] = new_arxiv
        return result

    except Exception as exc:
        error_msg = f"Vector indexing failed: {exc}"
        logger.error(error_msg)
        return {"errors": [error_msg]}
