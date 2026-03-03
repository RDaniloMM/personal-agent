"""LLM-powered deal analyzer for FB Marketplace listings.

Given a batch of listings with parsed prices, the LLM evaluates whether
each item's price is a genuine bargain compared to typical market values.
Follows the same two-phase pattern as ``paper_analyzer.py``:
  Phase 1 – cheap triage: classify each listing as deal / maybe / skip.
  Phase 2 – full analysis on deals: explain *why* it's a great deal.

Uses Groq API (OpenAI-compatible) for fast inference.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import openai
from loguru import logger
from pydantic import BaseModel, Field

from src.config import Settings


# ── Pydantic models for structured LLM output ────────────────────────────────


class DealTriageItem(BaseModel):
    """Quick classification for a single listing."""

    index: int = Field(description="0-based index of the listing in the batch")
    verdict: str = Field(description="deal | maybe | skip")


class DealTriageResponse(BaseModel):
    """Wrapper for triage output."""

    listings: list[DealTriageItem]


class DealAnalysisItem(BaseModel):
    """Full deal analysis for a single listing."""

    index: int = Field(description="0-based index of the listing in the batch")
    estimated_market_price: str = Field(
        default="",
        description="Estimated typical market price for this item (e.g. 'S/ 2,500')",
    )
    discount_pct: int = Field(
        default=0,
        description="Approximate discount percentage vs market price",
    )
    reason: str = Field(
        default="",
        description="1-2 sentence explanation of why this is a great deal (Spanish)",
    )


class DealAnalysisResponse(BaseModel):
    """Wrapper for analysis output."""

    listings: list[DealAnalysisItem]


# ── Batch sizes ──────────────────────────────────────────────────────────────

_TRIAGE_BATCH = 25   # triage is cheap
_ANALYSIS_BATCH = 10  # full analysis


# ── System prompts ───────────────────────────────────────────────────────────

_TRIAGE_SYSTEM = """\
Eres un experto en precios de productos de segunda mano en Perú \
(soles peruanos, S/). Te daré una lista de artículos de Facebook Marketplace \
con su precio.

Para CADA artículo, responde si el precio es:
- "deal": precio MUY por debajo del valor de mercado (≥30% descuento). \
  Una verdadera ganga que vale la pena comprar ya.
- "maybe": precio algo bajo pero no extraordinario.
- "skip": precio normal, caro, o no se puede determinar.

Contexto de mercado (Perú, 2025-2026, precios segunda mano):
- Laptop básica usada: S/ 600-1200
- Laptop gamer usada: S/ 1500-3500
- Smartphone gama media: S/ 300-800
- Tablet: S/ 200-600
- Monitor: S/ 200-500
- Libros: S/ 5-30
- Gadgets/electrónicos varios: depende del artículo

Sé estricto: solo marca "deal" si el precio es realmente excepcional.
Ignora artículos donde no puedas determinar un precio razonable de mercado.

Return a JSON object: {"listings": [{"index": 0, "verdict": "deal"}, ...]}"""


_ANALYSIS_SYSTEM = """\
Eres un experto en precios de segunda mano en Perú. \
Para cada artículo marcado como ganga, analiza:
1. El precio estimado de mercado para ese tipo de artículo (segunda mano, Perú)
2. El porcentaje de descuento aproximado
3. Por qué es una buena compra (1-2 oraciones en español)

Return a JSON object:
{"listings": [{"index": 0, "estimated_market_price": "S/ 2,500", \
"discount_pct": 60, "reason": "Laptop gamer a menos de la mitad..."}]}"""


# ── Main entry point ─────────────────────────────────────────────────────────


async def analyze_deals(
    listings: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    """Two-phase deal detection: triage → analysis on deals only.

    Returns only listings identified as genuine deals, enriched with
    ``is_deal=True``, ``deal_reason``, ``estimated_market_price``, etc.
    """
    if not listings:
        return []

    client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    # ── Phase 1: Triage ──────────────────────────────────────────
    verdicts: dict[int, str] = {}
    for i in range(0, len(listings), _TRIAGE_BATCH):
        batch = listings[i : i + _TRIAGE_BATCH]
        offset = i
        triage = await _triage_batch(batch, offset, client, settings)
        for t in triage:
            verdicts[t["index"]] = t.get("verdict", "skip")

    deal_indices = [idx for idx, v in verdicts.items() if v == "deal"]
    maybe_count = sum(1 for v in verdicts.values() if v == "maybe")
    skip_count = sum(1 for v in verdicts.values() if v == "skip")

    logger.info(
        "Deal triage: {} deals, {} maybe, {} skip (of {} total)",
        len(deal_indices), maybe_count, skip_count, len(listings),
    )

    if not deal_indices:
        return []

    # ── Phase 2: Full analysis (only deals) ──────────────────────
    deal_listings = [(idx, listings[idx]) for idx in deal_indices if idx < len(listings)]
    analyses: dict[int, dict[str, Any]] = {}

    for i in range(0, len(deal_listings), _ANALYSIS_BATCH):
        batch = deal_listings[i : i + _ANALYSIS_BATCH]
        results = await _analysis_batch(batch, client, settings)
        for r in results:
            analyses[r["index"]] = r

    # ── Merge analysis into listings ─────────────────────────────
    enriched: list[dict[str, Any]] = []
    for idx, listing in deal_listings:
        analysis = analyses.get(idx, {})
        enriched.append({
            **listing,
            "is_deal": True,
            "deal_reason": analysis.get("reason", "Precio atractivo"),
            "estimated_market_price": analysis.get("estimated_market_price", ""),
            "discount_pct": analysis.get("discount_pct", 0),
        })

    logger.info(
        "Deal analysis complete: {} deals enriched with reasoning",
        len(enriched),
    )
    return enriched


# ── Phase helpers ────────────────────────────────────────────────────────────


def _listing_snippet(listing: dict[str, Any], index: int) -> str:
    """Compact text repr of a listing for the LLM."""
    title = listing.get("title", "")
    price = listing.get("price", "")
    price_num = listing.get("price_numeric", 0)
    location = listing.get("location", "")
    desc = (listing.get("description", "") or "")[:100]
    return f"[{index}] {title} — {price} (S/ {price_num:.0f}) — {location}. {desc}"


async def _triage_batch(
    batch: list[dict[str, Any]],
    offset: int,
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _retries: int = 2,
) -> list[dict[str, Any]]:
    """Phase 1: cheap classification — deal / maybe / skip."""
    items_text = "\n".join(
        _listing_snippet(item, offset + i) for i, item in enumerate(batch)
    )
    last_exc: Exception | None = None

    for attempt in range(_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": _TRIAGE_SYSTEM},
                    {"role": "user", "content": items_text},
                ],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content or '{"listings":[]}')
            if isinstance(data, list):
                data = {"listings": data}
            items = DealTriageResponse.model_validate(data).listings
            return [item.model_dump() for item in items]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Deal triage parse failed (attempt {}): {}", attempt + 1, exc,
            )
            last_exc = exc
        except openai.BadRequestError as exc:
            logger.warning(
                "Deal triage JSON failed (attempt {}): {}", attempt + 1, exc,
            )
            last_exc = exc
        except Exception as exc:
            logger.error("Deal triage LLM call failed: {}", exc)
            return [
                {"index": offset + i, "verdict": "skip"} for i in range(len(batch))
            ]

        if attempt < _retries:
            await asyncio.sleep(2 ** attempt)

    logger.warning("Deal triage exhausted retries, fallback to skip")
    return [{"index": offset + i, "verdict": "skip"} for i in range(len(batch))]


async def _analysis_batch(
    batch: list[tuple[int, dict[str, Any]]],
    client: openai.AsyncOpenAI,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Phase 2: explain why each deal is a great buy."""
    items_text = "\n".join(
        _listing_snippet(listing, idx) for idx, listing in batch
    )
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {"role": "user", "content": f"Analiza estas gangas:\n{items_text}"},
            ],
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or '{"listings":[]}')
        if isinstance(data, list):
            data = {"listings": data}
        items = DealAnalysisResponse.model_validate(data).listings
        return [item.model_dump() for item in items]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Deal analysis parse failed: {}", exc)
        return [{"index": idx, "reason": ""} for idx, _ in batch]
    except Exception as exc:
        logger.error("Deal analysis LLM call failed: {}", exc)
        return [{"index": idx, "reason": ""} for idx, _ in batch]
