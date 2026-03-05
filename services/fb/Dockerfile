# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Shared package (highly cacheable layer)
COPY shared/ ./shared/

# 2. Service deps
COPY services/fb/pyproject.toml services/fb/README.md ./services/fb/

# 3. Install all Python deps
WORKDIR /app/services/fb
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# 4. Playwright browsers
RUN uv run playwright install chromium --with-deps

# 5. Service source (changes most often → last layer)
COPY services/fb/fb_worker/ ./fb_worker/
COPY services/fb/tests/ ./tests/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

RUN mkdir -p /app/profiles /app/logs /app/vault

CMD ["uv", "run", "python", "-m", "fb_worker.main"]
