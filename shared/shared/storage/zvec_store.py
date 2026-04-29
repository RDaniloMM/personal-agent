"""PostgreSQL + pgvector store for embedding and querying collected data."""

from __future__ import annotations

import hashlib
from typing import Any

import openai
import psycopg
from loguru import logger
from pgvector.psycopg import register_vector

from shared.config import Settings

# ── Table names per collection ───────────────────────────────────────────────
_COLLECTIONS = {"fb_marketplace", "youtube_feed", "arxiv_papers"}
_HYBRID_RRF_K = 60
_HYBRID_CANDIDATE_MIN = 25
_HYBRID_CANDIDATE_MULTIPLIER = 5


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
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {name}_text_fts_idx
            ON {name} USING GIN (to_tsvector('simple', text))
            """
        )
    conn.commit()
    logger.debug("pgvector schema ensured (dim={})", dim)


def _get_connection(settings: Settings) -> psycopg.Connection:
    """Open a psycopg3 connection, ensure pgvector extension, and register vector type."""
    conn = psycopg.connect(settings.database_url, autocommit=False)
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


def _document_text(doc: dict[str, Any], text_field: str) -> str:
    """Build a richer document text for dense + lexical retrieval."""

    parts: list[str] = []

    def add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, list):
            text = ", ".join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        if text and text not in parts:
            parts.append(text)

    add(doc.get(text_field, ""))
    if text_field != "title":
        add(doc.get("title", ""))

    for field in (
        "abstract",
        "summary",
        "description",
        "conclusions",
        "contributions",
        "key_takeaways",
        "thesis_paragraph",
        "location",
        "channel",
        "subtitles",
    ):
        add(doc.get(field))

    for field in ("authors", "categories", "tags"):
        add(doc.get(field))

    combined = "\n\n".join(parts)
    return combined[:20000] if combined else "No text"


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
        logger.warning(
            "Could not fetch existing IDs from '{}': {}", collection_name, exc
        )
        return set()
    finally:
        conn.close()


def make_document_id(
    doc: dict[str, Any],
    collection_name: str,
) -> str:
    """Return the deterministic storage ID for a document."""
    if collection_name not in _COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")
    return _make_id(doc, collection_name)


# ── CRUD operations ──────────────────────────────────────────────────────────


def upsert_documents(
    collection_name: str,
    documents: list[dict[str, Any]],
    text_field: str,
    settings: Settings,
) -> int:
    """Embed and upsert documents into a pgvector table."""
    if not documents:
        return 0

    if collection_name not in _COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")

    texts = [_document_text(doc, text_field) for doc in documents]
    embeddings = embed_texts(texts, settings)

    conn = _get_connection(settings)
    try:
        import json
        from numpy import array as np_array

        with conn.cursor() as cur:
            for doc, text, emb in zip(documents, texts, embeddings):
                doc_id = make_document_id(doc, collection_name)
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
    """Query a collection with hybrid vector + full-text retrieval."""
    if collection_name not in _COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")
    if not query_text.strip():
        return []

    query_embedding = embed_texts([query_text], settings)[0]

    conn = _get_connection(settings)
    try:
        from numpy import array as np_array

        candidate_k = max(_HYBRID_CANDIDATE_MIN, top_k * _HYBRID_CANDIDATE_MULTIPLIER)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH vector_matches AS (
                    SELECT
                        id,
                        text,
                        metadata,
                        1 - (embedding <=> %s) AS vector_similarity,
                        ROW_NUMBER() OVER (ORDER BY embedding <=> %s, id) AS vector_rank
                    FROM {collection_name}
                    ORDER BY embedding <=> %s, id
                    LIMIT %s
                ),
                text_matches AS (
                    SELECT
                        id,
                        ts_rank_cd(
                            to_tsvector('simple', text),
                            websearch_to_tsquery('simple', %s)
                        ) AS lexical_score,
                        ROW_NUMBER() OVER (
                            ORDER BY ts_rank_cd(
                                to_tsvector('simple', text),
                                websearch_to_tsquery('simple', %s)
                            ) DESC, id
                        ) AS text_rank
                    FROM {collection_name}
                    WHERE to_tsvector('simple', text) @@ websearch_to_tsquery('simple', %s)
                    LIMIT %s
                )
                SELECT
                    base.id,
                    base.text,
                    base.metadata,
                    COALESCE(v.vector_similarity, 0) AS vector_similarity,
                    COALESCE(t.lexical_score, 0) AS lexical_score,
                    COALESCE(1.0 / (%s + v.vector_rank), 0)
                        + COALESCE(1.0 / (%s + t.text_rank), 0) AS hybrid_score
                FROM {collection_name} base
                LEFT JOIN vector_matches v ON v.id = base.id
                LEFT JOIN text_matches t ON t.id = base.id
                WHERE v.id IS NOT NULL OR t.id IS NOT NULL
                ORDER BY hybrid_score DESC, vector_similarity DESC, lexical_score DESC, base.id
                LIMIT %s
                """,
                (
                    np_array(query_embedding),
                    np_array(query_embedding),
                    np_array(query_embedding),
                    candidate_k,
                    query_text,
                    query_text,
                    query_text,
                    candidate_k,
                    _HYBRID_RRF_K,
                    _HYBRID_RRF_K,
                    top_k,
                ),
            )
            rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "text": r[1],
                "metadata": r[2],
                "similarity": float(r[5]),
                "vector_similarity": float(r[3]),
                "lexical_score": float(r[4]),
                "hybrid_score": float(r[5]),
            }
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
