"""LLM-powered deal analyzer for FB Marketplace listings.

Three-phase approach:
  Phase 1 – cheap triage: classify each listing as deal / maybe / skip.
  Phase 2 – price research: search MercadoLibre for real market prices.
  Phase 3 – full analysis: LLM compares listing vs market prices with calculator.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
from typing import Any

import httpx
import openai
from loguru import logger
from pydantic import BaseModel, Field

from shared.config import Settings


# ── Pydantic models ──────────────────────────────────────────────────────────


class DealTriageItem(BaseModel):
    index: int = Field(description="0-based index of the listing in the batch")
    verdict: str = Field(description="deal | maybe | skip")


class DealTriageResponse(BaseModel):
    listings: list[DealTriageItem]


class DealAnalysisItem(BaseModel):
    index: int = Field(description="0-based index of the listing in the batch")
    estimated_market_price: str = Field(default="")
    discount_pct: int = Field(default=0)
    reason: str = Field(default="")


class DealAnalysisResponse(BaseModel):
    listings: list[DealAnalysisItem]


_TRIAGE_BATCH = 25
_ANALYSIS_BATCH = 10


# ── MercadoLibre price lookup ────────────────────────────────────────────────

_ML_SEARCH_URL = "https://api.mercadolibre.com/sites/MPE/search"
_ML_TIMEOUT = 10  # seconds


async def _search_mercadolibre(
    query: str,
    *,
    limit: int = 5,
    condition: str | None = None,
) -> list[dict[str, Any]]:
    """Search MercadoLibre Peru for product prices.

    Returns a list of {title, price, currency, condition, permalink}.
    """
    params: dict[str, Any] = {"q": query, "limit": limit}
    if condition:
        params["ITEM_CONDITION"] = condition  # "new" or "used"
    try:
        headers = {"User-Agent": "PersonalAgent/1.0 (deal-analyzer)"}
        async with httpx.AsyncClient(timeout=_ML_TIMEOUT, headers=headers) as client:
            resp = await client.get(_ML_SEARCH_URL, params=params)
            if resp.status_code != 200:
                logger.warning("MercadoLibre search failed ({}): {}", resp.status_code, query)
                return []
            data = resp.json()
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "price": item.get("price", 0),
                    "currency": item.get("currency_id", "PEN"),
                    "condition": item.get("condition", ""),
                    "permalink": item.get("permalink", ""),
                })
            return results
    except Exception as exc:
        logger.warning("MercadoLibre search error for '{}': {}", query, exc)
        return []


def _format_market_context(market_data: dict[int, list[dict]]) -> str:
    """Format ML search results into text context for the LLM."""
    if not market_data:
        return ""
    lines = ["\n--- PRECIOS DE REFERENCIA EN MERCADO LIBRE (Perú) ---"]
    for idx, results in sorted(market_data.items()):
        if not results:
            continue
        prices = [r["price"] for r in results if r.get("price")]
        if not prices:
            continue
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        sample_titles = "; ".join(r["title"][:50] for r in results[:3])
        lines.append(
            f"[{idx}] MercadoLibre: S/ {min_price:.0f} – S/ {max_price:.0f} "
            f"(promedio S/ {avg_price:.0f}, {len(prices)} resultados). "
            f"Ej: {sample_titles}"
        )
    return "\n".join(lines) if len(lines) > 1 else ""


# ── Calculator tool ──────────────────────────────────────────────────────────

_CALC_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Evalúa una expresión matemática. Útil para calcular descuentos, "
            "porcentajes y comparar precios. Ejemplo: '(2500 - 800) / 2500 * 100'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expresión matemática a evaluar",
                }
            },
            "required": ["expression"],
        },
    },
}


def _safe_eval(expression: str) -> str:
    """Safely evaluate a math expression (no exec/eval of arbitrary code)."""
    sanitized = re.sub(r'[^0-9+\-*/().,%\s]', '', expression)
    sanitized = sanitized.replace('%', '/100')
    try:
        code = compile(sanitized, "<calc>", "eval")
        allowed_names = {"abs": abs, "round": round, "min": min, "max": max, "math": math}
        result = eval(code, {"__builtins__": {}}, allowed_names)  # noqa: S307
        return str(round(result, 2))
    except Exception:
        return "Error: expresión inválida"


# ── LLM Prompts ──────────────────────────────────────────────────────────────

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
Si el precio está en MX$ (pesos mexicanos) o USD y es sospechosamente bajo, \
marca como "skip" — probablemente es un error de moneda.

Return a JSON object: {"listings": [{"index": 0, "verdict": "deal"}, ...]}"""


_ANALYSIS_SYSTEM = """\
Eres un experto en precios de segunda mano en Perú. \
Te proporciono artículos de Facebook Marketplace marcados como posibles gangas \
junto con **precios reales de Mercado Libre Perú** para comparar.

Para cada artículo:
1. Compara el precio del artículo con los precios de Mercado Libre
2. Usa la tool `calculate` si necesitas calcular descuentos o promedios
3. Determina el precio estimado de mercado (basado en ML y tu conocimiento)
4. Calcula el porcentaje real de descuento
5. Explica por qué es buena compra (1-2 oraciones en español)

Criterios de una ganga REAL:
- El descuento debe ser ≥30% respecto a precios de Mercado Libre usados
- Si no hay datos de ML, usa tu conocimiento del mercado peruano
- Considera el estado del producto (usado vs nuevo)
- Precios en MX$ o USD sospechosamente bajos → probablemente error de moneda, NO es ganga

Return a JSON object:
{"listings": [{"index": 0, "estimated_market_price": "S/ 2,500", \
"discount_pct": 60, "reason": "Laptop gamer a menos de la mitad del precio de ML..."}]}"""


# ── Main entry point ─────────────────────────────────────────────────────────


async def analyze_deals(
    listings: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    """Three-phase deal detection: triage → price research → analysis."""
    if not listings:
        return []

    client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    # ── Phase 1: Triage ──────────────────────────────────────────────
    verdicts: dict[int, str] = {}
    for i in range(0, len(listings), _TRIAGE_BATCH):
        batch = listings[i : i + _TRIAGE_BATCH]
        triage = await _triage_batch(batch, i, client, settings)
        for t in triage:
            verdicts[t["index"]] = t.get("verdict", "skip")

    deal_indices = [idx for idx, v in verdicts.items() if v == "deal"]
    maybe_indices = [idx for idx, v in verdicts.items() if v == "maybe"]
    skip_count = sum(1 for v in verdicts.values() if v == "skip")

    logger.info(
        "Deal triage: {} deals, {} maybe, {} skip (of {} total)",
        len(deal_indices), len(maybe_indices), skip_count, len(listings),
    )

    if not deal_indices:
        return []

    # ── Phase 2: Price research on MercadoLibre ──────────────────────
    deal_listings = [(idx, listings[idx]) for idx in deal_indices if idx < len(listings)]
    logger.info("Searching MercadoLibre for {} deal candidates…", len(deal_listings))

    market_data: dict[int, list[dict]] = {}
    for _local_i, (global_idx, listing) in enumerate(deal_listings):
        title = listing.get("title", "")
        query = re.sub(r'\b\d{4,}\b', '', title).strip()[:80]
        if query:
            results = await _search_mercadolibre(query, limit=5, condition="used")
            if not results:
                results = await _search_mercadolibre(query, limit=5)
            if results:
                market_data[global_idx] = results
                logger.debug(
                    "ML prices for [{}] '{}': {} results, avg S/ {:.0f}",
                    global_idx,
                    title[:40],
                    len(results),
                    sum(r["price"] for r in results) / len(results),
                )
            await asyncio.sleep(0.3)

    logger.info(
        "MercadoLibre: found prices for {}/{} listings",
        len(market_data), len(deal_listings),
    )

    # ── Phase 3: Full analysis with market context + calculator ──────
    analyses: dict[int, dict[str, Any]] = {}
    for i in range(0, len(deal_listings), _ANALYSIS_BATCH):
        batch = deal_listings[i : i + _ANALYSIS_BATCH]
        batch_market = {idx: market_data.get(idx, []) for idx, _ in batch}
        results = await _analysis_batch(batch, batch_market, client, settings)
        for r in results:
            analyses[r["index"]] = r

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

    logger.info("Deal analysis complete: {} deals enriched", len(enriched))
    return enriched


# ── Helpers ──────────────────────────────────────────────────────────────────


def _listing_snippet(listing: dict[str, Any], index: int) -> str:
    title = listing.get("title", "")
    price = listing.get("price", "")
    price_num = listing.get("price_numeric", 0)
    location = listing.get("location", "")
    desc = (listing.get("description", "") or "")[:100]
    return f"[{index}] {title} — {price} (S/ {price_num:.0f}) — {location}. {desc}"


# ── Phase 1: Triage ─────────────────────────────────────────────────────────


async def _triage_batch(
    batch: list[dict[str, Any]],
    offset: int,
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _retries: int = 2,
) -> list[dict[str, Any]]:
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
            logger.warning("Deal triage parse failed (attempt {}): {}", attempt + 1, exc)
            last_exc = exc
        except openai.BadRequestError as exc:
            logger.warning("Deal triage JSON failed (attempt {}): {}", attempt + 1, exc)
            last_exc = exc
        except Exception as exc:
            logger.error("Deal triage LLM call failed: {}", exc)
            return [{"index": offset + i, "verdict": "skip"} for i in range(len(batch))]

        if attempt < _retries:
            await asyncio.sleep(2 ** attempt)

    logger.warning("Deal triage exhausted retries, fallback to skip")
    return [{"index": offset + i, "verdict": "skip"} for i in range(len(batch))]


# ── Phase 3: Analysis with ML prices + calculator ───────────────────────────


async def _analysis_batch(
    batch: list[tuple[int, dict[str, Any]]],
    market_data: dict[int, list[dict]],
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _max_tool_rounds: int = 3,
) -> list[dict[str, Any]]:
    items_text = "\n".join(
        _listing_snippet(listing, idx) for idx, listing in batch
    )
    market_context = _format_market_context(market_data)

    user_content = f"Analiza estas gangas:\n{items_text}"
    if market_context:
        user_content += f"\n{market_context}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _ANALYSIS_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    try:
        # Agentic loop: let LLM call calculator if needed
        for _round in range(_max_tool_rounds):
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                max_tokens=2048,
                tools=[_CALC_TOOL],
                tool_choice="auto",
            )
            msg = response.choices[0].message

            # If model returned tool calls, execute them and continue
            if msg.tool_calls:
                # Build a clean assistant message — Groq rejects extra
                # SDK-added fields like 'annotations', 'audio', etc.
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                messages.append(assistant_msg)
                for tc in msg.tool_calls:
                    if tc.function.name == "calculate":
                        args = json.loads(tc.function.arguments)
                        result = _safe_eval(args.get("expression", "0"))
                        logger.debug("Calculator: {} = {}", args.get("expression"), result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })
                continue

            # Final answer — parse JSON
            if msg.content:
                data = json.loads(msg.content)
                if isinstance(data, list):
                    data = {"listings": data}
                items = DealAnalysisResponse.model_validate(data).listings
                return [item.model_dump() for item in items]
            break

        # Fallback: force a final JSON response without tools
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
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
