FROM python:3.12-slim

# System deps for yt-dlp (ffmpeg optional but nice to have)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Layer 1: shared package (rarely changes)
COPY shared/ /app/shared/

# Layer 2: service dependencies (changes when pyproject.toml changes)
COPY services/youtube/pyproject.toml /app/services/youtube/
WORKDIR /app/services/youtube
RUN uv sync --no-dev --no-install-project

# Layer 3: service source (changes frequently)
COPY services/youtube/yt_worker/ /app/services/youtube/yt_worker/
RUN uv sync --no-dev

CMD ["uv", "run", "python", "-m", "yt_worker.main"]
