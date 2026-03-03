# Arxiv Worker

Lightweight microservice for Arxiv paper collection and LLM analysis.

## Pipeline

1. **arxiv.py** – query recent papers by topic
2. **LLM triage** – classify relevance (high/medium/low)
3. **LLM analysis** – summarize relevant papers in Spanish
4. **pgvector index** – deduplicate and store embeddings
5. **Obsidian notes** – write formatted paper notes
6. **LLM ideas** – extract actionable ideas

## Build & Run

```bash
docker compose build arxiv-worker
docker compose up arxiv-worker
```

Lightest service — no Playwright, no yt-dlp. Build takes ~1 min.
