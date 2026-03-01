# 🤖 Personal Agent

Agente autónomo de IA que recopila datos de FB Marketplace, YouTube y Arxiv, los indexa en una base de datos vectorial (PostgreSQL + pgvector) y genera notas inteligentes en tu vault de Obsidian.

## Arquitectura

```
START
  │
  ├─▶ scrape_fb ──────┐
  ├─▶ scrape_youtube ─┤  (fan-out condicional)
  └─▶ collect_arxiv ──┘
                       │
                 index_vectors (pgvector)
                       │
                write_obsidian (LLM Groq)
                       │
                      END
```

**Stack:** LangGraph · Crawl4AI · Playwright · arxiv.py · PostgreSQL + pgvector · Groq (Llama 3.3) · APScheduler · Docker

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes)
- Docker & Docker Compose (para deploy en servidor)
- API key de Groq (LLM) y OpenAI (embeddings)
- Vault de Obsidian accesible por filesystem

## Instalación

```bash
# 1. Clonar y entrar al proyecto
cd personal-agent

# 2. Instalar dependencias (uv crea el venv automáticamente)
uv sync

# 3. Instalar browsers de Playwright
uv run playwright install chromium --with-deps

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys (LLM_API_KEY, EMBEDDING_API_KEY) y rutas
```

## Configuración de perfiles de navegador

Para scraping autenticado de FB Marketplace y YouTube, necesitas crear perfiles de browser persistentes **una sola vez** desde una máquina con display:

```bash
# Crear perfil de Facebook (se abre Chromium, inicia sesión manualmente)
python -m src.scrapers.browser_profiles fb

# Crear perfil de Google/YouTube
python -m src.scrapers.browser_profiles google

# Listar perfiles existentes
python -m src.scrapers.browser_profiles list
```

Los perfiles se guardan en `profiles/` y contienen cookies, localStorage, etc.

## Uso

### Ejecución única (testing)

```bash
# Ejecutar todas las tareas
python -m src.main --run-once --task all

# Solo Arxiv
python -m src.main --run-once --task arxiv

# Solo FB Marketplace
python -m src.main --run-once --task fb

# Solo YouTube
python -m src.main --run-once --task youtube
```

### Modo daemon (servidor 24/7)

```bash
# Directo
python -m src.main

# Con Docker
docker compose up -d
docker compose logs -f
```

### Horarios por defecto

| Tarea                    | Frecuencia           | Configurable en |
| ------------------------ | -------------------- | --------------- |
| FB Marketplace + YouTube | 2x/día (8:00, 20:00) | `SCRAPE_HOURS`  |
| Arxiv papers             | 1x/día (07:00)       | `ARXIV_HOUR`    |

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

## Docker (producción)

```bash
# Construir y levantar
docker compose up -d --build

# Ver logs
docker compose logs -f agent

# Detener
docker compose down
```

**Importante:** Los perfiles de browser deben crearse **antes** de desplegar en Docker. Copiar la carpeta `profiles/` al servidor.

Para sincronizar el vault de Obsidian con OneDrive en el servidor Linux:

```bash
# Opción: montar OneDrive con rclone
rclone mount onedrive: /mnt/onedrive --vfs-cache-mode writes &
```

## Tests

```bash
uv run pytest tests/ -v
```

## Variables de entorno

Ver [.env.example](.env.example) para todas las opciones configurables.

## ⚠️ Notas importantes

- **ToS de Facebook/YouTube:** El scraping autenticado de estas plataformas puede violar sus términos de servicio. Este proyecto es para **uso personal** únicamente.
- **Rate limiting:** El agente incluye delays entre requests (5-10s) para evitar bloqueos.
- **Perfiles de browser:** Contienen tus cookies de sesión. **No los compartas ni los subas a Git.**
- **pgvector:** Extensión de PostgreSQL para búsqueda vectorial. Se ejecuta como servicio Docker independiente con persistencia en volumen `pgdata`.
