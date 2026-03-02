"""Browser profile management for identity-based crawling.

Creates Chromium user-data-dir profiles via Playwright so that the exact
same directory format used by ``BrowserConfig(user_data_dir=...)`` in
Crawl4AI is what gets saved.  This avoids the mismatch between
``BrowserProfiler`` managed profiles and the ``user_data_dir`` path.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from loguru import logger

from src.config import Settings


async def create_profile_interactive(profile_name: str, settings: Settings) -> Path:
    """Open a headed Chromium window so the user can log in.

    The browser profile is saved directly to
    ``settings.browser_profiles_dir / profile_name`` — the exact same path
    referenced by the crawlers at runtime.

    This **must** run on a machine with a display (not headless/Docker).
    After the user finishes logging in, they close the browser window or
    press Enter in the terminal to save.

    Returns the path to the saved profile directory.
    """
    from playwright.async_api import async_playwright

    profile_path = settings.browser_profiles_dir / profile_name
    profile_path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Opening Chromium with profile '{}' at {} — log in and then close the browser",
        profile_name,
        profile_path,
    )

    async with async_playwright() as p:
        # Launch a *headed* browser with persistent context (user_data_dir)
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,
            channel="chromium",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            locale="es-PE",
            viewport={"width": 1280, "height": 900},
        )

        # Navigate to the appropriate login page
        page = context.pages[0] if context.pages else await context.new_page()

        if "fb" in profile_name.lower():
            await page.goto("https://www.facebook.com/marketplace/")
            logger.info("Navigate to Facebook Marketplace and log in. Close the browser when done.")
        elif "google" in profile_name.lower():
            await page.goto("https://accounts.google.com/")
            logger.info("Log in to Google. Then visit YouTube. Close the browser when done.")
        else:
            await page.goto("https://google.com/")
            logger.info("Navigate where needed. Close the browser when done.")

        # Wait until the user closes the browser
        try:
            await context.pages[0].wait_for_event("close", timeout=0)
        except Exception:
            pass

        # Closing the context flushes cookies/localStorage to user_data_dir
        await context.close()

    logger.info("Profile '{}' saved at {}", profile_name, profile_path)
    return profile_path


async def ensure_profiles_exist(settings: Settings) -> dict[str, Path]:
    """Return paths for FB and Google profiles.

    If a profile directory doesn't exist, log a warning with instructions.
    Profile creation must happen on a desktop machine, then copied via SCP.
    """
    profiles: dict[str, Path] = {}

    for name in (settings.fb_profile_name, settings.google_profile_name):
        profile_path = settings.browser_profiles_dir / name
        if profile_path.exists() and any(profile_path.iterdir()):
            logger.info("Browser profile '{}' found at {}", name, profile_path)
            profiles[name] = profile_path
        else:
            logger.warning(
                "Profile '{}' not found at {}. "
                "Create it on a desktop machine with:\n"
                "  uv run python -m src.scrapers.browser_profiles {}\n"
                "Then copy to server:\n"
                "  scp -r profiles/{} danilo@server:~/personal-agent/profiles/{}",
                name, profile_path,
                name.split("-")[0],  # fb or google
                name, name,
            )

    return profiles


# ── Standalone CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    """Run directly to create profiles:

        uv run python -m src.scrapers.browser_profiles fb
        uv run python -m src.scrapers.browser_profiles google
        uv run python -m src.scrapers.browser_profiles list
    """
    from src.config import get_settings

    settings = get_settings()
    arg = sys.argv[1] if len(sys.argv) > 1 else "list"

    if arg == "list":
        profiles_dir = settings.browser_profiles_dir
        if profiles_dir.exists():
            for p in sorted(profiles_dir.iterdir()):
                if p.is_dir():
                    n_files = sum(1 for _ in p.rglob("*") if _.is_file())
                    print(f"  {p.name:30s}  ({n_files} files)")
        else:
            print("  No profiles directory found")
    elif arg == "fb":
        asyncio.run(create_profile_interactive(settings.fb_profile_name, settings))
    elif arg == "google":
        asyncio.run(create_profile_interactive(settings.google_profile_name, settings))
    else:
        print("Usage: uv run python -m src.scrapers.browser_profiles [fb|google|list]")
