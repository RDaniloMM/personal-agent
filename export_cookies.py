"""Export YouTube cookies from the local Google profile for server use.

Run on Windows: uv run python export_cookies.py
This produces cookies.txt (Netscape format) for yt-dlp on the server.
"""
import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = Path("profiles/google-profile")
OUTPUT_JSON = Path("cookies.json")
OUTPUT_TXT = Path("cookies.txt")


def cookies_to_netscape(cookies: list[dict]) -> str:
    """Convert Playwright cookies list to Netscape cookies.txt format."""
    lines = ["# Netscape HTTP Cookie File", "# https://curl.se/docs/http-cookies.html", ""]
    for c in cookies:
        domain = c.get("domain", "")
        # Netscape format: domain, include_subdomains, path, secure, expires, name, value
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        expires = str(int(c.get("expires", 0)))
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append(f"{domain}\t{include_sub}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    return "\n".join(lines) + "\n"


async def main():
    print("Opening YouTube with your Google profile...")
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,  # Visible so you can verify login
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=30000)
        
        # Wait for page to settle
        await asyncio.sleep(5)
        
        # Check if signed in
        body = await page.inner_text("body")
        if "Acceder" in body[:500] or "Sign in" in body[:500]:
            print("⚠ NOT signed in. Opening login page...")
            await page.goto("https://accounts.google.com/", wait_until="networkidle", timeout=30000)
            print("✓ Login page opened. Please sign in manually.")
            print("  Then close the browser when done.")
            # Wait for browser to close
            try:
                await page.wait_for_event("close", timeout=300000)
            except Exception:
                pass
            # Re-open YouTube to grab cookies after login
            page2 = await ctx.new_page()
            await page2.goto("https://www.youtube.com/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
        else:
            print("✓ Already signed in!")
        
        # Get all cookies for youtube and google domains
        cookies = await ctx.cookies(["https://www.youtube.com", "https://accounts.google.com", "https://www.google.com"])
        
        # Save as JSON (for Playwright use)
        OUTPUT_JSON.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        print(f"✓ Saved {len(cookies)} cookies to {OUTPUT_JSON}")
        
        # Save as Netscape format (for yt-dlp use)
        netscape = cookies_to_netscape(cookies)
        OUTPUT_TXT.write_text(netscape, encoding="utf-8")
        print(f"✓ Saved Netscape cookies to {OUTPUT_TXT}")
        
        await ctx.close()
    
    print(f"\nNext steps:")
    print(f"  scp {OUTPUT_TXT} danilo@192.168.100.18:~/personal-agent/profiles/")
    print(f"  scp {OUTPUT_JSON} danilo@192.168.100.18:~/personal-agent/profiles/")


asyncio.run(main())
