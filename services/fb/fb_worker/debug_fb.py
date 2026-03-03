"""Quick debug: see what markdown Facebook returns for Marketplace."""
import asyncio

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

DISMISS_JS = r"""
(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const dismiss = () => {
        document.querySelectorAll('[aria-label="Close"], [aria-label="Cerrar"]')
            .forEach(b => { try { b.click(); } catch(e){} });
        document.querySelectorAll('[role="dialog"]').forEach(el => el.remove());
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
        document.body.style.position = 'static';
    };
    dismiss();
    await delay(3000);
    dismiss();
    for (let i = 0; i < 4; i++) {
        window.scrollBy(0, window.innerHeight);
        await delay(1500);
        dismiss();
    }
})();
"""


async def test():
    bc = BrowserConfig(
        headless=True,
        use_managed_browser=True,
        browser_type="chromium",
        extra_args=["--disable-blink-features=AutomationControlled", "--lang=es-PE"],
    )
    cc = CrawlerRunConfig(
        js_code=DISMISS_JS,
        wait_for='css:div[role="main"]',
        page_timeout=45000,
        magic=True,
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
    )
    async with AsyncWebCrawler(config=bc) as c:
        r = await c.arun(
            url="https://www.facebook.com/marketplace/108444959180261/search?query=laptop&radius_in_km=40",
            config=cc,
        )
        print("SUCCESS:", r.success)
        print("STATUS:", r.status_code)
        md = r.markdown or ""
        print("MD_LEN:", len(md))
        print("=== FULL MARKDOWN ===")
        print(md[:5000])
        print("=== END ===")

        # Test parser
        from fb_worker.crawler import _parse_listings
        listings = _parse_listings(md, "laptop", "moquegua")
        print(f"\n=== PARSED {len(listings)} LISTINGS ===")
        for i, lst in enumerate(listings[:10]):
            print(f"  [{i}] {lst.get('price')} | {lst.get('title', '')[:60]} | {lst.get('location', '')}")


asyncio.run(test())
