"""Browser profile management for identity-based crawling with Crawl4AI."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from loguru import logger

from src.config import Settings


async def create_profile_interactive(profile_name: str, settings: Settings) -> Path:
    """Open a Chromium window so the user can log in and save a persistent profile.

    This **must** run in a desktop environment (not headless).
    After the user finishes logging in they press *q* in the terminal to save.

    Returns the path to the saved profile directory.
    """
    from crawl4ai import BrowserProfiler

    profiler = BrowserProfiler()
    profile_path = await profiler.create_profile(profile_name=profile_name)
    logger.info("Profile '{}' saved at {}", profile_name, profile_path)
    return Path(profile_path)


async def ensure_profiles_exist(settings: Settings) -> dict[str, Path]:
    """Return paths for FB and Google profiles, creating them interactively if
    they don't exist yet.

    In a headless server environment the profiles must be pre-created on a
    machine with a display and then copied into ``settings.browser_profiles_dir``.
    """
    profiles: dict[str, Path] = {}

    for name in (settings.fb_profile_name, settings.google_profile_name):
        profile_path = settings.browser_profiles_dir / name
        if profile_path.exists():
            logger.info("Browser profile '{}' found at {}", name, profile_path)
            profiles[name] = profile_path
        else:
            logger.warning(
                "Profile '{}' not found. Launching interactive setup …", name
            )
            try:
                saved = await create_profile_interactive(name, settings)
                profiles[name] = saved
            except Exception as exc:
                logger.error(
                    "Cannot create profile '{}' (headless env?): {}", name, exc
                )
                raise

    return profiles


def list_profiles() -> None:
    """CLI helper: print all Crawl4AI profiles."""
    from crawl4ai import BrowserProfiler

    profiler = BrowserProfiler()
    for p in profiler.list_profiles():
        print(f"  {p['name']:30s}  {p['path']}")


# ── Standalone CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    """Run directly to create profiles:

        python -m src.scrapers.browser_profiles [fb|google|list]
    """
    from src.config import get_settings

    settings = get_settings()
    arg = sys.argv[1] if len(sys.argv) > 1 else "list"

    if arg == "list":
        list_profiles()
    elif arg == "fb":
        asyncio.run(create_profile_interactive(settings.fb_profile_name, settings))
    elif arg == "google":
        asyncio.run(create_profile_interactive(settings.google_profile_name, settings))
    else:
        print(f"Usage: python -m src.scrapers.browser_profiles [fb|google|list]")
