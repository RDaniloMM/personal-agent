# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies with uv (cached between builds)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Install Playwright browsers (cached between builds)
RUN --mount=type=cache,target=/root/.cache/ms-playwright \
    uv run playwright install chromium --with-deps

# Copy tests
COPY tests/ ./tests/

# Create required directories
RUN mkdir -p /app/profiles /app/logs

# Environment variables (override via .env or docker-compose)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV UV_SYSTEM_PYTHON=1

# Default command: start the scheduler daemon
CMD ["uv", "run", "python", "-m", "src.main"]
