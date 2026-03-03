# YouTube Worker

Lightweight microservice for YouTube video discovery and enrichment.

## Pipeline

1. **yt-dlp search** – discover videos via `ytsearchN:query`
2. **YouTube Data API** – fetch latest uploads from subscriptions (OAuth2)
3. **yt-dlp enrich** – extract metadata + subtitles for each video
4. **pgvector index** – deduplicate and store embeddings
5. **Obsidian notes** – write rich video summaries
6. **LLM ideas** – extract actionable ideas

## Build & Run

```bash
docker compose build yt-worker
docker compose up yt-worker
```

No Playwright/Chromium needed — very fast build (~1-2 min).
