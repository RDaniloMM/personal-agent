# 🤖 Personal Agent

Agente autónomo de IA que recopila datos de **FB Marketplace**, **YouTube** y **Arxiv**, los analiza con LLM (Groq), los indexa en PostgreSQL + pgvector, y genera notas inteligentes en tu vault de **Obsidian**. Desplegado como microservicios Docker en un servidor casero.

## Arquitectura

```
personal-agent/
├── shared/              # Librería compartida (Settings, storage, writer)
├── services/
│   ├── fb/              # FB Marketplace worker (Crawl4AI + Playwright)
│   ├── arxiv/           # Arxiv paper worker (arxiv.py)
│   └── youtube/         # YouTube worker (yt-dlp + API v3)
├── scripts/             # Deploy, sync, status
├── docker-compose.yml   # 4 servicios: db, fb-worker, arxiv-worker, yt-worker
└── AGENTS.md            # Documentación técnica detallada
```

Cada worker es un contenedor independiente con su propio pipeline lineal:

```
Crawl / Collect → Triage (LLM) → Analyze (LLM) → Index (pgvector) → Notes (Obsidian)
```

**Stack:** Python 3.12 · uv · Groq (GPT-OSS-120b) · Crawl4AI · Playwright · yt-dlp · arxiv.py · PostgreSQL + pgvector · APScheduler · Docker Compose

## Requisitos

- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes, usado dentro de los containers)
- API key de [Groq](https://console.groq.com/) (LLM)
- API key de [OpenAI](https://platform.openai.com/) (embeddings)
- Servidor Linux con acceso SSH (para deploy)

## Instalación y deploy

```bash
# 1. Clonar el repositorio
git clone <repo> && cd personal-agent

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys y rutas

# 3. Construir y levantar todos los servicios
docker compose up -d --build

# 4. Ver estado
docker compose ps
docker compose logs -f fb-worker
```

## Configuración

Ver [.env.example](.env.example) para todas las variables. Las principales:

| Variable              | Descripción                                               |
| --------------------- | --------------------------------------------------------- |
| `LLM_API_KEY`         | API key de Groq                                           |
| `EMBEDDING_API_KEY`   | API key de OpenAI (embeddings)                            |
| `FB_LOCATIONS`        | `nombre:fb_location_id,...` (ej: `tacna:111957248821463`) |
| `FB_SEARCH_QUERIES`   | Queries separadas por coma                                |
| `OBSIDIAN_VAULT_PATH` | Ruta al vault (dentro del container: `/app/vault`)        |

## Uso

### Ejecución programada (producción)

Los workers corren como daemons con APScheduler. Horarios por defecto:

| Worker       | Horario              | Configurable en   |
| ------------ | -------------------- | ----------------- |
| fb-worker    | 2x/día (8:00, 20:00) | `SCRAPE_HOURS`    |
| yt-worker    | 1x/día (9:00)        | `YT_SCRAPE_HOURS` |
| arxiv-worker | 1x/día (07:00)       | `ARXIV_HOUR`      |

### Ejecución manual (testing)

```bash
# Run-once de un worker específico
docker compose run --rm fb-worker uv run python -m fb_worker.main --run-once
docker compose run --rm arxiv-worker uv run python -m arxiv_worker.main --run-once
docker compose run --rm yt-worker uv run python -m yt_worker.main --run-once
```

### Tests E2E

Cada worker incluye un smoke test que ejecuta el pipeline real con datos mínimos:

```bash
docker compose run --rm arxiv-worker uv run python -m tests.test_e2e_arxiv   # ~30s
docker compose run --rm yt-worker uv run python -m tests.test_e2e_yt         # ~20s
docker compose run --rm fb-worker uv run python -m tests.test_e2e_fb         # ~2 min
```

## Estructura del vault de Obsidian

Las notas se crean automáticamente en:

```
Segundo cerebro/
└── Agent-Research/
    ├── Papers/          # Un .md por paper de Arxiv
    ├── FB-Marketplace/  # Resúmenes diarios de listings
    ├── YouTube/         # Resúmenes diarios de videos
    └── Ideas/           # Ideas clave generadas por el LLM
```

Cada nota incluye frontmatter YAML con tags para fácil búsqueda en Obsidian.

## Scripts de administración

```powershell
# Desplegar cambios al servidor
.\scripts\deploy-to-server.ps1

# Sincronizar vault y logs del servidor a local
.\scripts\sync-from-server.ps1

# Ver estado de contenedores
.\scripts\server-status.ps1
```

## Operaciones en servidor

```bash
# Reconstruir un worker específico
ssh danilo@192.168.100.18 'cd ~/personal-agent && docker compose build --no-cache fb-worker'

# Reiniciar workers
ssh danilo@192.168.100.18 'cd ~/personal-agent && docker compose up -d fb-worker arxiv-worker yt-worker'

# Ver logs en tiempo real
ssh danilo@192.168.100.18 'cd ~/personal-agent && docker compose logs -f fb-worker'
```

## ⚠️ Notas importantes

- **ToS de Facebook/YouTube:** El scraping de estas plataformas puede violar sus términos de servicio. Este proyecto es para **uso personal** únicamente.
- **Rate limiting:** El agente incluye delays entre requests para evitar bloqueos.
- **MercadoLibre API:** La API pública de búsqueda puede retornar 403 — el pipeline FB degrada gracefully sin precios de referencia.
- **pgvector:** Extensión de PostgreSQL para búsqueda vectorial. Se ejecuta como servicio Docker con persistencia en volumen `pgdata`.

## Documentación técnica

Ver [AGENTS.md](AGENTS.md) para detalles completos de arquitectura, pipelines, notas de integración LLM, y guía de deploy.
