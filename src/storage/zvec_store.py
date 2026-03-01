"""PostgreSQL + pgvector store for embedding and querying collected data."""

from __future__ import annotations

import hashlib
from typing import Any

import openai
import psycopg
from loguru import logger
from pgvector.psycopg import register_vector

from src.config import Settings

# ── Table names per collection ───────────────────────────────────────────────
_COLLECTIONS = {"fb_marketplace", "youtube_feed", "arxiv_papers"}


def _ensure_schema(conn: psycopg.Connection, dim: int) -> None:
    """Create the pgvector collection tables if they don't exist."""
    for name in _COLLECTIONS:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {name} (
                id   TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding vector({dim}),
                metadata JSONB NOT NULL DEFAULT '{{}}'
            )
            """
        )
    conn.commit()
    logger.debug("pgvector schema ensured (dim={})", dim)


def _get_connection(settings: Settings) -> psycopg.Connection:
    """Open a psycopg3 connection, ensure pgvector extension, and register vector type."""
    conn = psycopg.connect(settings.database_url, autocommit=False)
    # Create extension first (before registering the type)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)
    _ensure_schema(conn, settings.embedding_dim)
    return conn


# ── Embedding helper ─────────────────────────────────────────────────────────


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    """Generate embeddings using OpenAI's text-embedding-3-small API."""
    client = openai.OpenAI(api_key=settings.embedding_api_key)
    all_embeddings: list[list[float]] = []
    batch_size = 512

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        all_embeddings.extend([d.embedding for d in response.data])

    return all_embeddings

# ── Lookup helpers ────────────────────────────────────────────────────────────

def get_existing_ids(
    collection_name: str,
    settings: Settings,
) -> set[str]:
    """Return the set of document IDs already stored in a collection."""
    if collection_name not in _COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")

    conn = _get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {collection_name}")
            return {row[0] for row in cur.fetchall()}
    except Exception as exc:
        logger.warning("Could not fetch existing IDs from '{}': {}", collection_name, exc)
        return set()
    finally:
        conn.close()

# ── CRUD operations ──────────────────────────────────────────────────────────


def upsert_documents(
    collection_name: str,
    documents: list[dict[str, Any]],
    text_field: str,
    settings: Settings,
) -> int:
    """Embed and upsert documents into a pgvector table.

    Args:
        collection_name: "fb_marketplace", "youtube_feed", or "arxiv_papers".
        documents: list of dicts to store.
        text_field: key in each dict whose value will be embedded.
        settings: app settings.

    Returns:
        Number of documents upserted.
    """
    if not documents:
        return 0

    if collection_name not in _COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")

    texts = [
        doc.get(text_field, "") or doc.get("title", "No text")
        for doc in documents
    ]
    embeddings = embed_texts(texts, settings)

    conn = _get_connection(settings)
    try:
        import json
        from numpy import array as np_array

        with conn.cursor() as cur:
            for doc, text, emb in zip(documents, texts, embeddings):
                doc_id = _make_id(doc, collection_name)
                cur.execute(
                    f"""
                    INSERT INTO {collection_name} (id, text, embedding, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                        SET text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                    """,
                    (doc_id, text, np_array(emb), json.dumps(doc, default=str)),
                )
        conn.commit()
        logger.info("Upserted {} docs into '{}'", len(documents), collection_name)
        return len(documents)
    except Exception as exc:
        conn.rollback()
        logger.error("pgvector upsert failed for '{}': {}", collection_name, exc)
        return 0
    finally:
        conn.close()


def query_similar(
    collection_name: str,
    query_text: str,
    settings: Settings,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Query a collection by cosine similarity to a text string."""
    if collection_name not in _COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")

    query_embedding = embed_texts([query_text], settings)[0]

    conn = _get_connection(settings)
    try:
        from numpy import array as np_array

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, text, metadata, 1 - (embedding <=> %s) AS similarity
                FROM {collection_name}
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (np_array(query_embedding), np_array(query_embedding), top_k),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "text": r[1], "metadata": r[2], "similarity": float(r[3])}
            for r in rows
        ]
    except Exception as exc:
        logger.error("pgvector query failed for '{}': {}", collection_name, exc)
        return []
    finally:
        conn.close()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_id(doc: dict[str, Any], collection: str) -> str:
    """Generate a deterministic ID for deduplication."""
    if "arxiv_id" in doc:
        return doc["arxiv_id"]
    if "url" in doc and doc["url"]:
        return hashlib.sha256(doc["url"].encode()).hexdigest()[:16]
    title = doc.get("title", "")
    return hashlib.sha256(f"{collection}:{title}".encode()).hexdigest()[:16]
