import asyncio
import logging
import openai
from arxiv_worker.paper_analyzer import _triage_batch
from arxiv_worker.client import collect_arxiv_papers
from shared.config import Settings

logging.basicConfig(level=logging.INFO)

async def main():
    settings = Settings()
    groq_client = openai.AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    print("Collecting some test papers...")
    papers = await collect_arxiv_papers(settings)
    batch = papers[:5]
    print(f"Testing triage on {len(batch)} papers...")
    results = await _triage_batch(batch, groq_client, settings)
    print("\n--- FINAL RESULTS ---")
    for r in results:
        print(r)

if __name__ == "__main__":
    asyncio.run(main())