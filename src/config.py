"""Application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the personal-agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM (Groq / OpenAI-compatible) ─────────────────
    llm_api_key: str = Field(..., description="API key for the LLM provider (Groq)")
    llm_base_url: str = Field(
        "https://api.groq.com/openai/v1",
        description="Base URL for the LLM API (OpenAI-compatible)",
    )
    llm_model: str = Field("openai/gpt-oss-120b", description="Chat model to use")

    # ── Embeddings (OpenAI API) ─────────────────────
    embedding_api_key: str = Field(..., description="OpenAI API key for embeddings")
    embedding_model: str = Field(
        "text-embedding-3-small", description="OpenAI embedding model"
    )
    embedding_dim: int = Field(1536, description="Embedding dimension")

    # ── PostgreSQL + pgvector ────────────────────────
    database_url: str = Field(
        "postgresql://agent:agent_secret@localhost:5432/agent_vectors",
        description="PostgreSQL connection string",
    )

    # ── Obsidian ─────────────────────────────────────
    obsidian_vault_path: Path = Field(
        ...,
        description="Absolute path to the Obsidian vault",
    )

    # ── Browser profiles ─────────────────────────────
    browser_profiles_dir: Path = Field(
        Path("./profiles"), description="Directory for Crawl4AI browser profiles"
    )
    fb_profile_name: str = Field("fb-profile", description="Profile name for Facebook")
    google_profile_name: str = Field("google-profile", description="Profile name for Google/YouTube")

    # ── Scheduler ────────────────────────────────────
    scrape_hours: str = Field("8,20", description="Comma-separated hours for FB+YT scraping")
    arxiv_hour: int = Field(7, description="Hour of day (0-23) to collect Arxiv papers")

    # ── FB Marketplace ───────────────────────────────
    fb_search_queries: str = Field(
        "laptop,gadgets,libros,equipos electronicos",
        description="Comma-separated search queries for FB Marketplace",
    )
    fb_locations: str = Field(
        "tacna,moquegua",
        description="Comma-separated FB Marketplace locations",
    )

    # ── Arxiv ────────────────────────────────────────
    arxiv_max_results_per_query: int = Field(20, description="Max papers per Arxiv query")

    # ── Logging ──────────────────────────────────────
    log_level: str = Field("INFO", description="Logging level")

    # ── Derived helpers ──────────────────────────────

    @property
    def scrape_hours_list(self) -> list[int]:
        return [int(h.strip()) for h in self.scrape_hours.split(",")]

    @property
    def fb_search_queries_list(self) -> list[str]:
        return [q.strip() for q in self.fb_search_queries.split(",")]

    @property
    def fb_locations_list(self) -> list[str]:
        return [loc.strip() for loc in self.fb_locations.split(",")]

    @property
    def fb_profile_path(self) -> Path:
        return self.browser_profiles_dir / self.fb_profile_name

    @property
    def google_profile_path(self) -> Path:
        return self.browser_profiles_dir / self.google_profile_name

    @property
    def cookies_path(self) -> Path:
        return self.browser_profiles_dir / "cookies.txt"

    @property
    def youtube_token_path(self) -> Path:
        return self.browser_profiles_dir / "youtube_token.json"

    @property
    def youtube_client_secret_path(self) -> Path:
        return self.browser_profiles_dir / "client_secret.json"

    def obsidian_subfolder(self, *parts: str) -> Path:
        path = self.obsidian_vault_path / "Agent-Research" / Path(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]
