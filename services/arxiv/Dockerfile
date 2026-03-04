FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Layer 1: shared package (rarely changes)
COPY shared/ /app/shared/

# Layer 2: service dependencies (changes when pyproject.toml changes)
COPY services/arxiv/pyproject.toml /app/services/arxiv/
WORKDIR /app/services/arxiv
RUN uv sync --no-dev --no-install-project

# Layer 3: service source (changes frequently)
COPY services/arxiv/arxiv_worker/ /app/services/arxiv/arxiv_worker/
COPY services/arxiv/tests/ /app/services/arxiv/tests/
RUN uv sync --no-dev

CMD ["uv", "run", "python", "-m", "arxiv_worker.main"]
