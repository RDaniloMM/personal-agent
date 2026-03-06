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
from typing import Any, Literal, cast

import httpx
import openai
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from shared.config import Settings
from shared.llm_json import extract_json_payload


# ── Pydantic models ──────────────────────────────────────────────────────────


class DealTriageItem(BaseModel):
    index: int = Field(description="0-based index of the listing in the batch")
    verdict: Literal["deal", "maybe", "skip"] = Field(description="deal | maybe | skip")

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, value: Any) -> str:
        verdict = _normalize_verdict(value)
        if verdict is None:
            raise ValueError(f"Unsupported verdict: {value!r}")
        return verdict


class DealTriageResponse(BaseModel):
    listings: list[DealTriageItem]


class DealAnalysisItem(BaseModel):
    index: int = Field(description="0-based index of the listing in the batch")
    estimated_market_price: str = Field(default="")
    discount_pct: int = Field(default=0)
    reason: str = Field(default="")

    @field_validator("discount_pct", mode="before")
    @classmethod
    def _normalize_discount_pct(cls, value: Any) -> int:
        if value in (None, ""):
            return 0
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:[.,]\d+)?", value)
            if not match:
                return 0
            value = match.group().replace(",", ".")
        return int(round(float(value)))


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
                logger.warning(
                    "MercadoLibre search failed ({}): {}", resp.status_code, query
                )
                return []
            data = resp.json()
            results = []
            for item in data.get("results", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "price": item.get("price", 0),
                        "currency": item.get("currency_id", "PEN"),
                        "condition": item.get("condition", ""),
                        "permalink": item.get("permalink", ""),
                    }
                )
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
    sanitized = re.sub(r"[^0-9+\-*/().,%\s]", "", expression)
    sanitized = sanitized.replace("%", "/100")
    try:
        code = compile(sanitized, "<calc>", "eval")
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "math": math,
        }
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

Return a JSON object: {"listings": [{"index": 0, "verdict": "deal"}, ...]}
No incluyas texto fuera del JSON ni bloques markdown."""


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
"discount_pct": 60, "reason": "Laptop gamer a menos de la mitad del precio de ML..."}]}
No incluyas texto fuera del JSON ni bloques markdown."""


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
        len(deal_indices),
        len(maybe_indices),
        skip_count,
        len(listings),
    )

    if not deal_indices:
        return []

    # ── Phase 2: Price research on MercadoLibre ──────────────────────
    deal_listings = [
        (idx, listings[idx]) for idx in deal_indices if idx < len(listings)
    ]
    logger.info("Searching MercadoLibre for {} deal candidates…", len(deal_listings))

    market_data: dict[int, list[dict]] = {}
    for _local_i, (global_idx, listing) in enumerate(deal_listings):
        title = listing.get("title", "")
        query = re.sub(r"\b\d{4,}\b", "", title).strip()[:80]
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
        len(market_data),
        len(deal_listings),
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
        enriched.append(
            {
                **listing,
                "is_deal": True,
                "deal_reason": analysis.get("reason", "Precio atractivo"),
                "estimated_market_price": analysis.get("estimated_market_price", ""),
                "discount_pct": analysis.get("discount_pct", 0),
            }
        )

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


_JSON_ONLY_SYSTEM = "Responde solo con JSON valido. No incluyas explicaciones, markdown ni bloques de codigo."


async def _request_json_reply(
    client: openai.AsyncOpenAI,
    settings: Settings,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
) -> Any:
    content = await _request_text_reply(
        client,
        settings,
        messages,
        max_tokens=max_tokens,
    )
    return extract_json_payload(content or "{}")


async def _request_text_reply(
    client: openai.AsyncOpenAI,
    settings: Settings,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
) -> str:
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=cast(
            Any,
            [{"role": "system", "content": _JSON_ONLY_SYSTEM}, *messages],
        ),
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


# ── Phase 1: Triage ─────────────────────────────────────────────────────────


async def _triage_batch(
    batch: list[dict[str, Any]],
    offset: int,
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _retries: int = 2,
) -> list[dict[str, Any]]:
    expected_indices = [offset + i for i in range(len(batch))]
    items_text = "\n".join(
        _listing_snippet(item, offset + i) for i, item in enumerate(batch)
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _TRIAGE_SYSTEM},
        {"role": "user", "content": items_text},
    ]

    for attempt in range(_retries + 1):
        try:
            content = await _request_text_reply(
                client,
                settings,
                messages,
                max_tokens=1024,
            )
            items = _parse_triage_items(content, expected_indices)
            return [item.model_dump() for item in items]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Deal triage parse failed (attempt {}): {}", attempt + 1, exc
            )
        except Exception as exc:
            logger.error("Deal triage LLM call failed: {}", exc)
            return _heuristic_triage_batch(batch, offset)

        if attempt < _retries:
            await asyncio.sleep(2**attempt)

    logger.warning("Deal triage exhausted retries, using heuristic fallback")
    return _heuristic_triage_batch(batch, offset)


# ── Phase 3: Analysis with ML prices + calculator ───────────────────────────


async def _analysis_batch(
    batch: list[tuple[int, dict[str, Any]]],
    market_data: dict[int, list[dict]],
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _max_tool_rounds: int = 3,
) -> list[dict[str, Any]]:
    expected_indices = [idx for idx, _ in batch]
    items_text = "\n".join(_listing_snippet(listing, idx) for idx, listing in batch)
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
                messages=cast(Any, messages),
                max_tokens=2048,
                tools=cast(Any, [_CALC_TOOL]),
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
                            "id": cast(Any, tc).id,
                            "type": "function",
                            "function": {
                                "name": cast(Any, tc).function.name,
                                "arguments": cast(Any, tc).function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                messages.append(assistant_msg)
                for tc in msg.tool_calls:
                    tool_call = cast(Any, tc)
                    if tool_call.function.name == "calculate":
                        args = json.loads(tool_call.function.arguments)
                        result = _safe_eval(args.get("expression", "0"))
                        logger.debug(
                            "Calculator: {} = {}", args.get("expression"), result
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result,
                            }
                        )
                continue

            # Final answer — parse JSON
            if msg.content:
                items = _parse_analysis_items(msg.content, expected_indices)
                return [item.model_dump() for item in items]
            break

        # Fallback: force a final JSON response without tools
        content = await _request_text_reply(client, settings, messages, max_tokens=2048)
        items = _parse_analysis_items(content, expected_indices)
        return [item.model_dump() for item in items]

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Deal analysis parse failed: {}", exc)
        return [{"index": idx, "reason": ""} for idx, _ in batch]
    except Exception as exc:
        logger.error("Deal analysis LLM call failed: {}", exc)
        return [{"index": idx, "reason": ""} for idx, _ in batch]


def _parse_triage_items(
    content: str, expected_indices: list[int]
) -> list[DealTriageItem]:
    data = extract_json_payload(content or '{"listings":[]}')
    normalized = _normalize_triage_payload(data, expected_indices)
    return DealTriageResponse.model_validate(normalized).listings


def _parse_analysis_items(
    content: str, expected_indices: list[int]
) -> list[DealAnalysisItem]:
    data = extract_json_payload(content or '{"listings":[]}')
    normalized = _normalize_analysis_payload(data, expected_indices)
    return DealAnalysisResponse.model_validate(normalized).listings


def _normalize_triage_payload(data: Any, expected_indices: list[int]) -> dict[str, Any]:
    raw_items = _extract_items(data)
    by_index: dict[int, dict[str, Any]] = {}

    for pos, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        index = _coerce_index(
            item.get("index"), fallback=expected_indices, position=pos
        )
        verdict = _normalize_verdict(
            item.get("verdict")
            or item.get("classification")
            or item.get("status")
            or item.get("label")
            or item.get("decision")
        )
        if index is None or verdict is None or index not in expected_indices:
            continue
        by_index[index] = {"index": index, "verdict": verdict}

    return {
        "listings": [
            by_index.get(index, {"index": index, "verdict": "skip"})
            for index in expected_indices
        ]
    }


def _normalize_analysis_payload(
    data: Any, expected_indices: list[int]
) -> dict[str, Any]:
    raw_items = _extract_items(data)
    by_index: dict[int, dict[str, Any]] = {}

    for pos, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        index = _coerce_index(
            item.get("index"), fallback=expected_indices, position=pos
        )
        if index is None or index not in expected_indices:
            continue
        by_index[index] = {
            "index": index,
            "estimated_market_price": str(
                item.get("estimated_market_price")
                or item.get("estimated_price")
                or item.get("market_price")
                or item.get("market_estimate")
                or item.get("precio_mercado")
                or ""
            ),
            "discount_pct": item.get("discount_pct")
            or item.get("discount_percentage")
            or item.get("discountPercent")
            or item.get("discount")
            or item.get("descuento_pct")
            or item.get("descuento")
            or 0,
            "reason": str(
                item.get("reason")
                or item.get("why")
                or item.get("justification")
                or item.get("explicacion")
                or ""
            ),
        }

    return {
        "listings": [
            by_index.get(
                index,
                {
                    "index": index,
                    "estimated_market_price": "",
                    "discount_pct": 0,
                    "reason": "",
                },
            )
            for index in expected_indices
        ]
    }


def _extract_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("listings", "items", "results", "deals"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    if "index" in data:
        return [data]
    if data and all(str(key).strip().isdigit() for key in data):
        return [
            {"index": key, **(value if isinstance(value, dict) else {"verdict": value})}
            for key, value in data.items()
        ]
    return []


def _coerce_index(value: Any, *, fallback: list[int], position: int) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    if 0 <= position < len(fallback):
        return fallback[position]
    return None


def _normalize_verdict(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    mapping = {
        "deal": "deal",
        "ganga": "deal",
        "bargain": "deal",
        "buy": "deal",
        "maybe": "maybe",
        "tal vez": "maybe",
        "quizas": "maybe",
        "revisar": "maybe",
        "consider": "maybe",
        "skip": "skip",
        "descartar": "skip",
        "pass": "skip",
        "ignore": "skip",
    }
    return mapping.get(text)


def _heuristic_triage_batch(
    batch: list[dict[str, Any]], offset: int
) -> list[dict[str, Any]]:
    return [
        {"index": offset + i, "verdict": _heuristic_verdict(item)}
        for i, item in enumerate(batch)
    ]


def _heuristic_verdict(listing: dict[str, Any]) -> str:
    title = (listing.get("title", "") or "").lower()
    price = float(listing.get("price_numeric", 0) or 0)
    if price <= 0:
        return "skip"
    if any(currency in title for currency in ("mx$", "usd", "dolar", "dólar")):
        return "skip"

    if "laptop" in title or "notebook" in title:
        return "deal" if price <= 700 else "maybe" if price <= 1000 else "skip"
    if any(
        word in title
        for word in ("iphone", "samsung", "xiaomi", "smartphone", "celular")
    ):
        return "deal" if price <= 350 else "maybe" if price <= 550 else "skip"
    if any(word in title for word in ("monitor", "pantalla")):
        return "deal" if price <= 180 else "maybe" if price <= 280 else "skip"
    if any(word in title for word in ("tablet", "ipad")):
        return "deal" if price <= 250 else "maybe" if price <= 400 else "skip"
    if any(word in title for word in ("libro", "libros", "novela")):
        return "deal" if price <= 10 else "maybe" if price <= 20 else "skip"
    if any(
        word in title
        for word in ("audifono", "audífono", "teclado", "mouse", "parlante", "gadget")
    ):
        return "deal" if price <= 60 else "maybe" if price <= 120 else "skip"
    return "maybe" if price <= 100 else "skip"
