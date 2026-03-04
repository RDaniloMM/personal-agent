# AGENTS.md — Personal Agent

## Project Overview

Autonomous AI agent system that scrapes **FB Marketplace**, **YouTube**, and **Arxiv**, analyzes content via LLM (Groq), and writes structured notes to an **Obsidian vault**. Deployed as Docker microservices on a home server (`danilo@192.168.100.18`, Moquegua, Perú).

## Architecture

```
personal-agent/
├── shared/                  # Shared library (pydantic Settings, storage, writer)
│   └── shared/
│       ├── config.py        # Settings (pydantic-settings, loaded from .env)
│       ├── state.py         # Dataclasses: MarketplaceListing, YouTubeVideo, ArxivPaper
│       ├── writer.py        # LLM idea extraction → Obsidian notes
│       └── storage/
│           ├── obsidian.py  # Write .md summaries to vault
│           └── zvec_store.py # pgvector indexing & dedup
├── services/
│   ├── fb/                  # FB Marketplace worker
│   │   ├── fb_worker/
│   │   │   ├── main.py      # Pipeline: crawl → deals → index → notes
│   │   │   ├── crawler.py   # Crawl4AI + Playwright, location filter
│   │   │   └── deal_analyzer.py  # 3-phase: triage → MercadoLibre search → LLM analysis + calculator tool
│   │   └── tests/
│   │       └── test_e2e_fb.py
│   ├── arxiv/               # Arxiv paper worker
│   │   ├── arxiv_worker/
│   │   │   ├── main.py      # Pipeline: collect → analyze → index → notes
│   │   │   ├── client.py    # arxiv.py queries (4 predefined AI research queries)
│   │   │   └── paper_analyzer.py  # 2-phase: triage → full analysis
│   │   └── tests/
│   │       └── test_e2e_arxiv.py
│   └── youtube/             # YouTube worker
│       ├── yt_worker/
│       │   ├── main.py      # Pipeline: discover → enrich → index → notes
│       │   ├── crawler.py   # yt-dlp search + YouTube Data API + subtitle extraction
│       │   └── auth.py      # YouTube OAuth2 token management
│       └── tests/
│           └── test_e2e_yt.py
├── scripts/
│   ├── deploy-to-server.ps1 # SCP deploy + docker compose build/restart
│   ├── sync-from-server.ps1 # Sync vault notes + logs from server to local
│   └── server-status.ps1    # Check container status
├── docker-compose.yml       # 4 services: db, fb-worker, arxiv-worker, yt-worker
├── .env                     # Secrets & config (LLM_API_KEY, EMBEDDING_API_KEY, etc.)
└── AGENTS.md                # This file
```

## Key Technologies

| Component    | Tech                                        |
| ------------ | ------------------------------------------- |
| LLM          | Groq API (`openai/gpt-oss-120b`)            |
| Embeddings   | OpenAI `text-embedding-3-small`             |
| Vector DB    | PostgreSQL + pgvector                       |
| FB Scraping  | Crawl4AI 0.8 + Playwright Chromium          |
| YT Discovery | yt-dlp + YouTube Data API v3                |
| Arxiv        | arxiv.py library (no API key needed)        |
| Config       | pydantic-settings (`Settings` in config.py) |
| Packaging    | uv + hatchling                              |
| Container    | Docker Compose, Python 3.12-slim            |
| Notes        | Obsidian vault (markdown + wiki-links)      |

## Configuration (`.env`)

Required variables:

- `LLM_API_KEY` — Groq API key
- `EMBEDDING_API_KEY` — OpenAI API key
- `OBSIDIAN_VAULT_PATH` — Path to the Obsidian vault (inside container: `/app/vault`)
- `DATABASE_URL` — PostgreSQL connection string
- `FB_LOCATIONS` — Format: `name:fb_location_id,name:fb_location_id` (e.g. `tacna:111957248821463,moquegua:108444959180261`)
- `FB_SEARCH_QUERIES` — Comma-separated (e.g. `laptop,gadgets,libros`)

## Worker Pipelines

### FB Marketplace (`fb-worker`)

1. **Crawl** — Iterates `locations × queries`, scrapes listings via Crawl4AI
2. **Location filter** — Whitelist of ~60 Peruvian cities, exact segment matching
3. **Deal triage** — LLM classifies each listing as `deal`/`maybe`/`skip` (JSON mode)
4. **Price research** — Searches MercadoLibre Peru API for real market prices (⚠️ ML API may require auth token — returns 403 without it; pipeline degrades gracefully)
5. **Deal analysis** — LLM compares listing vs ML prices, uses `calculate` tool
6. **Index** — pgvector dedup by URL
7. **Notes** — Obsidian summary + LLM idea extraction

### Arxiv (`arxiv-worker`)

1. **Collect** — 4 hardcoded queries via `arxiv.py`, configurable `max_results`
2. **Triage** — LLM classifies relevance as `high`/`medium`/`low` (JSON mode)
3. **Full analysis** — LLM generates summary, conclusions, contributions, key takeaways
4. **Index** — pgvector dedup by `arxiv_id`
5. **Notes** — Obsidian per-paper notes + LLM idea extraction

### YouTube (`yt-worker`)

1. **Search discovery** — yt-dlp `ytsearch` with 3 hardcoded queries
2. **API feeds** — YouTube Data API v3 (OAuth2, subscription feeds)
3. **Enrich** — yt-dlp metadata + subtitle extraction (es/en)
4. **Index** — pgvector dedup by URL
5. **Notes** — Obsidian summary + LLM idea extraction

## LLM Integration Notes

- **Model**: `openai/gpt-oss-120b` via Groq (`https://api.groq.com/openai/v1`)
- **JSON mode** (`response_format={"type": "json_object"}`): Used for triage and analysis in deal_analyzer and paper_analyzer. **Incompatible with `reasoning_effort` on this model** — do not add `extra_body` with reasoning params when using JSON mode.
- **Tool use**: Used in `writer.py` (`write_idea_note` tool) and `deal_analyzer.py` (`calculate` tool). `reasoning_effort` works with tool use via `extra_body`.
- **reasoning_effort**: Applied to `writer.py` calls only (`"medium"` for FB/YT, `"high"` for Arxiv).
- **Groq tool call messages**: When re-sending assistant messages with tool calls back to Groq, you **must** construct a clean dict with only `role`, `content`, and `tool_calls` fields. The OpenAI SDK's `msg.model_dump()` includes extra fields (`annotations`, `audio`, etc.) that Groq rejects with 400 errors.

## Deployment

```bash
# Deploy from local to server
scp <file> danilo@192.168.100.18:~/personal-agent/<path>

# Rebuild a worker
ssh danilo@192.168.100.18 'cd ~/personal-agent && docker compose build --no-cache fb-worker'

# Restart workers
ssh danilo@192.168.100.18 'cd ~/personal-agent && docker compose up -d fb-worker arxiv-worker yt-worker'

# One-shot test run
ssh danilo@192.168.100.18 'cd ~/personal-agent && docker compose run --rm fb-worker uv run python -m fb_worker.main --run-once'
```

Server timezone: `America/Lima` (set in docker-compose.yml via `TZ=America/Lima`).

## E2E Tests

Each worker has a smoke test that runs the real pipeline with minimal data (no mocks for external APIs — these hit real services).

### Running E2E Tests

Tests run **inside Docker containers** since each worker has its own dependencies:

```bash
# FB Marketplace E2E (~2-3 min, crawls 1 query × 1 location, calls Groq + MercadoLibre)
docker compose run --rm fb-worker uv run python -m tests.test_e2e_fb

# Arxiv E2E (~30s, fetches 1 paper, calls Groq for analysis)
docker compose run --rm arxiv-worker uv run python -m tests.test_e2e_arxiv

# YouTube E2E (~30s, searches 1 video via yt-dlp, enriches metadata)
docker compose run --rm yt-worker uv run python -m tests.test_e2e_yt
```

### What They Test

| Test             | Crawl                                 | LLM Analysis           | External API      | Assertions                                  |
| ---------------- | ------------------------------------- | ---------------------- | ----------------- | ------------------------------------------- |
| `test_e2e_fb`    | 1 location × 1 query (3 listings max) | Deal triage + analysis | MercadoLibre Peru | Listing structure, deal fields, ML search   |
| `test_e2e_arxiv` | 1 query × 1 paper                     | Triage + full analysis | Arxiv API         | Paper structure, relevance, analysis fields |
| `test_e2e_yt`    | 1 search query × 1 result             | —                      | yt-dlp            | Video structure, enrichment fields          |

### Test Design Principles

- **Real external calls** — no mocks for Groq, MercadoLibre, Arxiv, yt-dlp
- **Minimal data** — monkey-patches constants/settings to fetch 1 item per category
- **Graceful degradation** — tests pass with a warning if external services are down
- **No DB writes** — tests only run crawl + analysis, skip indexing and note writing
- **Fast** — each test completes in under 3 minutes
