"""Debug: check what YouTube shows with the Google profile."""
import asyncio
import re
import json
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir="/app/profiles/google-profile",
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
            viewport={"width": 1280, "height": 900},
            locale="es-PE",
            ignore_https_errors=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Use networkidle for full render
        await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)

        # Scroll a few times
        for i in range(4):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(2)

        title = await page.title()
        print(f"TITLE: {title}")

        html = await page.content()

        # Check sign-in indicators
        has_signin = "Sign in" in html or "Iniciar sesión" in html
        print(f"SIGNIN_TEXT_PRESENT: {has_signin}")

        # DOM links
        links = await page.query_selector_all('a[href*="/watch?v="]')
        print(f"WATCH_LINKS_DOM: {len(links)}")

        # Regex in HTML
        watch_ids = re.findall(r'/watch\?v=([\w-]{11})', html)
        unique_ids = list(set(watch_ids))
        print(f"WATCH_IDS_REGEX: {len(unique_ids)}")

        # Try ytInitialData
        try:
            yt_data = await page.evaluate("window.ytInitialData")
            if yt_data:
                yt_str = json.dumps(yt_data)
                yt_ids = re.findall(r'"videoId":"([\w-]{11})"', yt_str)
                print(f"YT_INITIAL_DATA_IDS: {len(set(yt_ids))}")
            else:
                print("YT_INITIAL_DATA: None")
        except Exception as e:
            print(f"YT_INITIAL_DATA_ERROR: {e}")

        # Check URL bar (did it redirect?)
        print(f"CURRENT_URL: {page.url}")

        # Avatar / signed-in check
        avatar = await page.query_selector('button#avatar-btn, img#img[alt], [aria-label*="Cuenta"], [aria-label*="Account"]')
        print(f"AVATAR_FOUND: {avatar is not None}")
        
        # Check for sign-in button specifically
        signin_btn = await page.query_selector('a[href*="accounts.google.com"], tp-yt-paper-button#sign-in-button, [aria-label*="Sign in"], [aria-label*="Acceder"]')
        print(f"SIGNIN_BUTTON: {signin_btn is not None}")

        await page.screenshot(path="/tmp/yt_home.png", full_page=False)
        print("Screenshot saved to /tmp/yt_home.png")

        if unique_ids:
            print(f"SAMPLE_IDS: {unique_ids[:5]}")

        # Dump some inner text to see what user sees
        body_text = await page.inner_text("body")
        # Print first 3000 chars of visible text
        print("--- VISIBLE TEXT ---")
        print(body_text[:3000])
        print("--- END VISIBLE TEXT ---")

        # Check for consent/GDPR dialogs
        consent = await page.query_selector('form[action*="consent"], [aria-label*="consent"], [aria-label*="Accept"], button:has-text("Accept all"), button:has-text("Aceptar todo"), button:has-text("Rechazar todo")')
        print(f"CONSENT_DIALOG: {consent is not None}")

        await ctx.close()

asyncio.run(check())
