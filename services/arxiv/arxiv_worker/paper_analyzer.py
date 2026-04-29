"""LLM-powered paper analysis: relevance classification & key-point extraction.

Phase 1 (Triage): Groq (fast, cheap) — classifies relevance from abstract only.
Phase 2 (Analysis): OpenRouter + DeepSeek (deep, large context) — analyzes the full paper
converted locally to Markdown via PyMuPDF4LLM.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Literal

import openai
import pymupdf
import pymupdf4llm
from loguru import logger
from pydantic import BaseModel, Field

from shared.config import Settings
from shared.llm_json import extract_json_payload


class TriageItem(BaseModel):
    arxiv_id: str
    relevance: Literal["high", "medium", "low"]


class TriageResponse(BaseModel):
    papers: list[TriageItem]


class AnalysisItem(BaseModel):
    arxiv_id: str
    summary: str = Field(default="", description="3-5 sentence summary in Spanish")
    conclusions: str = Field(
        default="", description="Bullet points separated by newlines"
    )
    contributions: str = Field(
        default="", description="Bullet points separated by newlines"
    )
    key_takeaways: str = Field(default="", description="3-5 actionable bullet points")
    thesis_paragraph: str = Field(
        default="", description="APA 7 thesis background paragraph in Spanish"
    )


class AnalysisResponse(BaseModel):
    papers: list[AnalysisItem]


RESEARCH_INTERESTS = """\
- AI agents / agentic systems / autonomous architectures
- LLM evaluation, benchmarks, agent evaluation frameworks
- Function/tool calling in LLMs
- Multi-agent systems
- RAG + Reasoning and Evaluation frameworks
- AI agents in industry/production environments
"""


_TRIAGE_SYSTEM = f"""Score each paper's relevance to these interests:
{RESEARCH_INTERESTS}

Return exactly one line per paper using this format:
arxiv_id|high
arxiv_id|medium
arxiv_id|low

Rules:
- keep the same arxiv_id from the input
- use only high, medium, or low
- output one line per paper and nothing else
- no JSON, no markdown, no explanations"""

_TRIAGE_JSON_SYSTEM = f"""Score each paper's relevance to these interests:
{RESEARCH_INTERESTS}

Return a JSON object with a "papers" key containing an array.
Each element: {{"arxiv_id":"...","relevance":"high"|"medium"|"low"}}
Example: {{"papers": [{{"arxiv_id": "2503.00001", "relevance": "high"}}]}}
No incluyas texto fuera del JSON ni bloques markdown."""


_ANALYSIS_SYSTEM = f"""Eres un investigador experto en IA y un académico riguroso. Analiza cada paper EN PROFUNDIDAD basándote en su contenido completo en markdown extraído del PDF.

Devuelve un JSON con clave "papers" conteniendo un array. Cada elemento debe tener:

1. **arxiv_id**: string (el ID del paper)
2. **summary**: 3-5 oraciones cubriendo la contribución central, metodología y resultados principales (en español)
3. **conclusions**: bullet points de los hallazgos y resultados principales (en español, separados por \n)
4. **contributions**: bullet points de las contribuciones novedosas al campo (en español, separados por \n)
5. **key_takeaways**: 3-5 insights accionables o implicaciones prácticas (en español, separados por \n)
6. **thesis_paragraph**: Un párrafo académico completo para usar como ANTECEDENTE en una tesis, en formato APA 7. Este párrafo DEBE seguir EXACTAMENTE esta estructura:

   a) CITACIÓN Y PRESENTACIÓN: "[Apellido(s)] et al. (año) presentan [NOMBRE DEL FRAMEWORK/HERRAMIENTA/MÉTODO], [descripción breve], su objetivo es [objetivo principal del estudio]."
   b) METODOLOGÍA: "Metodológicamente, el estudio corresponde a una investigación de tipo [aplicada/básica/mixta], con un diseño [experimental/pre-experimental/cuasi-experimental/no experimental], de nivel [descriptivo/explicativo/correlacional/descriptivo-comparativo], la técnica de recolección de datos empleada es [técnica], realizada mediante [descripción del método]; como instrumentos de medición, se utilizan [instrumentos específicos que registran métricas como X, Y, Z]."
   c) RESULTADOS: "Los resultados muestran que [resumen de hallazgos principales con datos específicos cuando estén disponibles]."
   d) CONCLUSIÓN: "En conclusión, los autores sostienen que [conclusiones principales]."
   e) APRECIACIÓN CRÍTICA: "Como apreciación crítica, el principal aporte del estudio es [evaluación del aporte, validez, limitaciones o implicaciones]."

   IMPORTANTE para thesis_paragraph:
   - Debe ser UN SOLO PÁRRAFO largo y continuo (no usar bullets ni saltos de línea)
   - Usar citación APA 7: si hay 1-2 autores usar apellidos, si hay 3+ usar "et al."
   - Inferir el tipo de investigación, diseño y nivel metodológico del contenido del paper
   - Incluir métricas y datos numéricos específicos cuando el paper los reporte
   - Escribir en español académico formal
   - El año debe extraerse de la fecha de publicación del paper

Usa texto plano dentro de los campos string.
Ejemplo de formato JSON:
{{"papers": [{{"arxiv_id": "2503.00001", "summary": "...", "conclusions": "...", "contributions": "...", "key_takeaways": "...", "thesis_paragraph": "..."}}]}}

Escribe TODO en español. No incluyas texto fuera del JSON ni bloques markdown."""


_ANALYSIS_JSON_SCHEMA_HINT = (
    '{"papers":[{"arxiv_id":"","summary":"","conclusions":"",'
    '"contributions":"","key_takeaways":"","thesis_paragraph":""}]}'
)

_ABSTRACT_LIMIT = 300
_TRIAGE_BATCH = 20
_ANALYSIS_BATCH = 1
_ANALYSIS_RETRIES = 2
_ANALYSIS_REQUEST_TIMEOUT = 600
_JSON_ONLY_SYSTEM = "Responde solo con JSON valido. No incluyas explicaciones, markdown ni bloques de codigo."
_TRIAGE_LINE_RE = re.compile(
    r"(?P<arxiv_id>\d{4}\.\d{4,5}(?:v\d+)?)\s*[:|,;-]\s*(?P<relevance>high|medium|low)",
    re.IGNORECASE,
)


async def analyze_papers(
    papers: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Two-phase analysis: Groq triage (fast) → OpenRouter deep analysis."""
    if not papers:
        return []

    groq_client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    analysis_client: openai.AsyncOpenAI | None = None
    if settings.openrouter_api_key:
        analysis_client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        logger.info(
            "Using OpenRouter model {} with provider {} for deep paper analysis",
            settings.openrouter_model,
            settings.openrouter_provider,
        )
    else:
        logger.warning(
            "No OPENROUTER_API_KEY set — falling back to Groq for analysis"
        )

    relevance_map: dict[str, str] = {}
    for i in range(0, len(papers), _TRIAGE_BATCH):
        batch = papers[i : i + _TRIAGE_BATCH]
        triage = await _triage_batch(batch, groq_client, settings)
        for t in triage:
            relevance_map[t["arxiv_id"]] = t.get("relevance", "low")

    relevant_papers = [
        p
        for p in papers
        if relevance_map.get(p.get("arxiv_id", ""), "low") in ("high", "medium")
    ]

    high_count = sum(1 for v in relevance_map.values() if v == "high")
    medium_count = sum(1 for v in relevance_map.values() if v == "medium")
    low_count = sum(1 for v in relevance_map.values() if v == "low")
    logger.info(
        "Triage: {} high, {} medium, {} low → {} to analyze",
        high_count,
        medium_count,
        low_count,
        len(relevant_papers),
    )

    if not relevant_papers:
        return []

    all_analyses: dict[str, dict[str, Any]] = {}
    for i in range(0, len(relevant_papers), _ANALYSIS_BATCH):
        batch = relevant_papers[i : i + _ANALYSIS_BATCH]
        if analysis_client:
            analyses = await _analysis_batch_openrouter(
                batch, analysis_client, groq_client, settings
            )
        else:
            analyses = await _analysis_batch_groq(batch, groq_client, settings)
        for a in analyses:
            all_analyses[a["arxiv_id"]] = a

    enriched: list[dict[str, Any]] = []
    for paper in relevant_papers:
        aid = paper.get("arxiv_id", "")
        analysis = all_analyses.get(aid, {})
        enriched.append(
            {
                **paper,
                **analysis,
                "relevance": relevance_map.get(aid, "medium"),
            }
        )

    logger.info(
        "Paper analysis complete: {} high, {} medium, {} low → {} enriched",
        high_count,
        medium_count,
        low_count,
        len(enriched),
    )
    return enriched


def _paper_snippet(p: dict[str, Any], abstract_limit: int = _ABSTRACT_LIMIT) -> str:
    abstract = (p.get("abstract", "") or "")[:abstract_limit]
    cats = ",".join(p.get("categories", []))
    return f"{p.get('arxiv_id', '')}: [{cats}] {p.get('title', '')}. {abstract}"


def _paper_metadata_header(p: dict[str, Any]) -> str:
    """Build a metadata header for a paper (used in prompts)."""
    cats = ",".join(p.get("categories", []))
    return (
        f"arxiv_id: {p.get('arxiv_id', '')}\n"
        f"title: {p.get('title', '')}\n"
        f"categories: {cats}\n"
        f"published: {p.get('published', '')}"
    )


def _parse_triage(content: str) -> list[TriageItem]:
    data = extract_json_payload(content)
    if isinstance(data, list):
        data = {"papers": data}
    return TriageResponse.model_validate(data).papers


def _parse_triage_lines(
    content: str,
    expected_ids: set[str],
) -> list[TriageItem]:
    items: list[TriageItem] = []
    seen_ids: set[str] = set()

    for raw_line in content.splitlines():
        line = raw_line.strip().strip("`")
        if not line:
            continue

        match = _TRIAGE_LINE_RE.search(line)
        if not match:
            continue

        arxiv_id = match.group("arxiv_id")
        relevance = match.group("relevance").lower()
        if arxiv_id not in expected_ids or arxiv_id in seen_ids:
            continue

        items.append(TriageItem(arxiv_id=arxiv_id, relevance=relevance))
        seen_ids.add(arxiv_id)

    if not items:
        raise ValueError("No triage lines were parsed")

    return items


def _normalize_triage_items(
    papers: list[dict[str, Any]],
    items: list[TriageItem],
) -> list[dict[str, Any]]:
    by_id = {item.arxiv_id: item.relevance for item in items}
    normalized: list[dict[str, Any]] = []
    missing_ids: list[str] = []

    for paper in papers:
        arxiv_id = paper.get("arxiv_id", "")
        relevance = by_id.get(arxiv_id)
        if relevance is None:
            relevance = "medium"
            missing_ids.append(arxiv_id)
        normalized.append({"arxiv_id": arxiv_id, "relevance": relevance})

    if missing_ids:
        logger.warning(
            "Triage omitted {} paper(s); defaulting them to medium: {}",
            len(missing_ids),
            ", ".join(missing_ids[:5]),
        )

    return normalized


def _parse_triage_response(
    content: str,
    papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected_ids = {paper.get("arxiv_id", "") for paper in papers if paper.get("arxiv_id")}

    try:
        items = _parse_triage(content)
    except (json.JSONDecodeError, ValueError):
        items = _parse_triage_lines(content, expected_ids)

    return _normalize_triage_items(papers, items)


def _parse_analysis(content: str) -> list[AnalysisItem]:
    data = extract_json_payload(content)
    if isinstance(data, list):
        data = {"papers": data}
    return AnalysisResponse.model_validate(data).papers


async def _request_json_reply(
    client: openai.AsyncOpenAI,
    settings: Settings,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
) -> Any:
    request_messages: Any = [
        {"role": "system", "content": _JSON_ONLY_SYSTEM},
        *messages,
    ]
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=request_messages,
        max_tokens=max_tokens,
    )
    return extract_json_payload(response.choices[0].message.content or "{}")


async def _triage_batch(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _retries: int = 2,
) -> list[dict[str, Any]]:
    papers_text = "\n".join(_paper_snippet(p) for p in papers)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _TRIAGE_SYSTEM},
        {"role": "user", "content": papers_text},
    ]
    json_fallback_messages: list[dict[str, Any]] = [
        {"role": "system", "content": _TRIAGE_JSON_SYSTEM},
        {"role": "user", "content": papers_text},
    ]

    for attempt in range(_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                max_tokens=512,
            )
            return _parse_triage_response(
                response.choices[0].message.content or "",
                papers,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Triage parse/validation failed (attempt {}): {}", attempt + 1, exc
            )
        except openai.RateLimitError as exc:
            wait = 15 * (attempt + 1)
            logger.warning(
                "Groq rate limit hit (attempt {}), waiting {}s: {}",
                attempt + 1,
                wait,
                exc,
            )
            if attempt < _retries:
                await asyncio.sleep(wait)
            continue
        except openai.BadRequestError as exc:
            logger.warning(
                "Triage request failed (attempt {}), retrying with JSON-only fallback: {}",
                attempt + 1,
                exc,
            )
            try:
                data = await _request_json_reply(
                    client, settings, json_fallback_messages, max_tokens=1024
                )
                if isinstance(data, list):
                    data = {"papers": data}
                items = TriageResponse.model_validate(data).papers
                return _normalize_triage_items(papers, items)
            except (json.JSONDecodeError, ValueError) as fallback_exc:
                logger.warning(
                    "Triage fallback parse failed (attempt {}): {}",
                    attempt + 1,
                    fallback_exc,
                )
        except Exception as exc:
            logger.error("Triage LLM call failed: {}", exc)
            return [
                {"arxiv_id": p.get("arxiv_id", ""), "relevance": "low"} for p in papers
            ]

        if attempt < _retries:
            await asyncio.sleep(2**attempt)

    logger.warning("Triage exhausted {} retries, falling back to medium", _retries + 1)
    return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "medium"} for p in papers]


def _extract_pdf_markdown(pdf_bytes: bytes, arxiv_id: str) -> str:
    """Extract full Markdown from a PDF using PyMuPDF4LLM."""
    if not pdf_bytes:
        return ""

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.warning("PDF open failed for {}: {}", arxiv_id, exc)
        return ""

    page_count = doc.page_count
    try:
        markdown = (pymupdf4llm.to_markdown(doc) or "").strip()
    except Exception as exc:
        logger.warning("PyMuPDF4LLM extraction failed for {}: {}", arxiv_id, exc)
        return ""
    finally:
        doc.close()

    if not markdown:
        return ""

    logger.info(
        "PDF markdown extracted for {}: {} pages, {:.0f}K chars",
        arxiv_id,
        page_count,
        len(markdown) / 1000,
    )
    return markdown


def _analysis_input_text(paper: dict[str, Any]) -> tuple[str, str, str]:
    """Build full analysis input from PDF markdown when available."""
    arxiv_id = paper.get("arxiv_id", "")
    pdf_bytes: bytes = paper.get("pdf_bytes", b"") or b""
    markdown = _extract_pdf_markdown(pdf_bytes, arxiv_id)
    abstract = paper.get("abstract", "") or ""

    if markdown:
        text = (
            "Abstract del paper:\n"
            f"{abstract}\n\n"
            "Markdown completo extraido desde el PDF:\n"
            f"{markdown}"
        )
        return (
            text,
            f"PDF markdown completo ({len(markdown) / 1000:.0f}K chars)",
            abstract,
        )

    if abstract:
        return abstract, "abstract only", abstract
    return "", "no text available", abstract


def _message_text(content: Any) -> str:
    """Normalize OpenAI-compatible message content into a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
                continue
            item_type = getattr(item, "type", None)
            item_text = getattr(item, "text", None)
            if item_type == "text" and item_text is not None:
                parts.append(str(item_text))
        return "".join(parts)
    return ""


def _estimate_tokens(text: str) -> int:
    """Cheap token estimate for debug progress logs."""
    if not text:
        return 0
    return max(1, len(text) // 4)


async def _repair_json_with_groq(
    client: openai.AsyncOpenAI,
    settings: Settings,
    raw_content: str,
    schema_hint: str,
    *,
    max_tokens: int,
) -> Any:
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "Convierte la siguiente salida a JSON valido sin inventar informacion. "
                "Si falta algun campo, usa string vacia o lista vacia. "
                f"Debes respetar este esquema: {schema_hint}"
            ),
        },
        {"role": "user", "content": raw_content},
    ]
    return await _request_json_reply(client, settings, messages, max_tokens=max_tokens)


def _analysis_provider_extra_body(settings: Settings) -> dict[str, Any]:
    return {
        "provider": {
            "only": [settings.openrouter_provider],
            "allow_fallbacks": False,
            "data_collection": "allow",
        }
    }


async def _analysis_json_completion(
    client: openai.AsyncOpenAI,
    groq_client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout: int,
    schema_hint: str,
    label: str,
) -> Any:
    last_error: Exception | None = None

    for attempt in range(_ANALYSIS_RETRIES + 1):
        try:
            request_messages: Any = [
                {
                    "role": "system",
                    "content": f"{_JSON_ONLY_SYSTEM}\n\n{system_prompt}",
                },
                {"role": "user", "content": user_prompt},
            ]
            prompt_estimate = sum(
                _estimate_tokens(message.get("content", ""))
                for message in request_messages
                if isinstance(message.get("content", ""), str)
            )
            logger.info(
                "{} started | prompt_est~{} tok | max_tokens={} | provider={}",
                label,
                prompt_estimate,
                max_tokens,
                settings.openrouter_provider,
            )

            async def _collect_stream() -> tuple[str, Any]:
                stream = await client.chat.completions.create(
                    model=settings.openrouter_model,
                    messages=request_messages,
                    temperature=0.3,
                    top_p=1,
                    max_tokens=max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                    extra_body=_analysis_provider_extra_body(settings),
                )

                content_parts: list[str] = []
                usage: Any = None
                started_at = time.monotonic()
                last_log_at = started_at

                async for chunk in stream:
                    if getattr(chunk, "usage", None) is not None:
                        usage = chunk.usage

                    choice = chunk.choices[0] if chunk.choices else None
                    delta = getattr(choice, "delta", None)
                    delta_text = _message_text(delta.content if delta else "")
                    if delta_text:
                        content_parts.append(delta_text)

                    now = time.monotonic()
                    if now - last_log_at >= 5:
                        generated_text = "".join(content_parts)
                        logger.info(
                            "{} streaming | output_est~{} tok | elapsed={}s",
                            label,
                            _estimate_tokens(generated_text),
                            int(now - started_at),
                        )
                        last_log_at = now

                return "".join(content_parts), usage

            raw_content, usage = await asyncio.wait_for(_collect_stream(), timeout=timeout)
            if not raw_content:
                raise json.JSONDecodeError("Empty content", "", 0)

            if usage is not None:
                reasoning_tokens = getattr(
                    getattr(usage, "completion_tokens_details", None),
                    "reasoning_tokens",
                    0,
                ) or 0
                logger.info(
                    "{} usage | prompt={} | completion={} | reasoning={} | total={}",
                    label,
                    getattr(usage, "prompt_tokens", 0),
                    getattr(usage, "completion_tokens", 0),
                    reasoning_tokens,
                    getattr(usage, "total_tokens", 0),
                )
            else:
                logger.info(
                    "{} finished without usage block | output_est~{} tok",
                    label,
                    _estimate_tokens(raw_content),
                )

            try:
                return extract_json_payload(raw_content)
            except json.JSONDecodeError as exc:
                last_error = exc
                repaired = await _repair_json_with_groq(
                    groq_client,
                    settings,
                    raw_content,
                    schema_hint,
                    max_tokens=min(4096, max_tokens),
                )
                logger.info("{} JSON repaired with Groq", label)
                return repaired
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "{} parse failed (attempt {}/{}): {}",
                label,
                attempt + 1,
                _ANALYSIS_RETRIES + 1,
                exc,
            )
            if attempt < _ANALYSIS_RETRIES:
                await asyncio.sleep(3 * (attempt + 1))
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning(
                "{} timed out after {}s (attempt {}/{})",
                label,
                timeout,
                attempt + 1,
                _ANALYSIS_RETRIES + 1,
            )
            if attempt < _ANALYSIS_RETRIES:
                await asyncio.sleep(3 * (attempt + 1))
        except openai.RateLimitError as exc:
            last_error = exc
            wait = 15 * (attempt + 1)
            logger.warning(
                "{} hit OpenRouter rate limit (attempt {}/{}), waiting {}s: {}",
                label,
                attempt + 1,
                _ANALYSIS_RETRIES + 1,
                wait,
                exc,
            )
            if attempt < _ANALYSIS_RETRIES:
                await asyncio.sleep(wait)
        except openai.BadRequestError as exc:
            last_error = exc
            logger.error("{} request failed: {}", label, exc)
            break
        except Exception as exc:
            last_error = exc
            logger.error("{} failed: {}", label, exc)
            break

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{label} failed without a specific exception")


async def _analysis_batch_openrouter(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    groq_client: openai.AsyncOpenAI,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Analyze papers using OpenRouter's OpenAI-compatible chat API."""
    results: list[dict[str, Any]] = []

    for paper in papers:
        header = _paper_metadata_header(paper)
        arxiv_id = paper.get("arxiv_id", "")
        analysis_text, source, abstract = _analysis_input_text(paper)

        if not analysis_text:
            results.append(_empty_analysis(paper))
            continue

        user_prompt = (
            f"Metadatos del paper:\n{header}\n\n"
            f"Fuente analizada: {source}\n\n"
            f"Abstract original:\n{abstract}\n\n"
            "Analiza este paper en profundidad usando TODO el contenido proporcionado. "
            "El markdown proviene del PDF completo extraido localmente; preserva la estructura del paper, "
            "incluyendo titulos, listas, tablas serializadas y cualquier pie de figura que aparezca en el markdown. "
            "No inventes informacion faltante.\n\n"
            f"Contenido completo del paper:\n{analysis_text}"
        )

        try:
            logger.info(
                "Analyzing [{}] with OpenRouter/{} using {}",
                arxiv_id,
                settings.openrouter_provider,
                source,
            )
            analysis_data = await _analysis_json_completion(
                client,
                groq_client,
                settings,
                system_prompt=_ANALYSIS_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=8192,
                timeout=_ANALYSIS_REQUEST_TIMEOUT,
                schema_hint=_ANALYSIS_JSON_SCHEMA_HINT,
                label=f"OpenRouter final analysis for {arxiv_id}",
            )
            if isinstance(analysis_data, list):
                analysis_data = {"papers": analysis_data}

            items = AnalysisResponse.model_validate(analysis_data).papers
            result = next(
                (item.model_dump() for item in items if item.arxiv_id == arxiv_id),
                items[0].model_dump() if items else _empty_analysis(paper),
            )
            results.append(result)
        except Exception as exc:
            logger.error("OpenRouter analysis failed for {}: {}", arxiv_id, exc)
            fallback = await _analysis_batch_groq([paper], groq_client, settings)
            results.append(fallback[0] if fallback else _empty_analysis(paper))

    return results


async def _analysis_batch_groq(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Fallback: analyze papers using Groq with abstract text only."""
    papers_text = "\n\n".join(
        f"---\n{_paper_metadata_header(p)}\n\n{p.get('abstract', '')}\n---"
        for p in papers
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _ANALYSIS_SYSTEM},
        {"role": "user", "content": f"Analiza estos papers:\n{papers_text}"},
    ]
    try:
        prompt_estimate = sum(
            _estimate_tokens(message.get("content", ""))
            for message in messages
            if isinstance(message.get("content", ""), str)
        )
        logger.info(
            "Analyzing {} paper(s) with Groq fallback ({:.0f}K chars, prompt_est~{} tok)",
            len(papers),
            len(papers_text) / 1000,
            prompt_estimate,
        )
        try:
            request_messages: Any = messages
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=request_messages,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            if getattr(response, "usage", None) is not None:
                logger.info(
                    "Groq fallback usage | prompt={} | completion={} | total={}",
                    getattr(response.usage, "prompt_tokens", 0),
                    getattr(response.usage, "completion_tokens", 0),
                    getattr(response.usage, "total_tokens", 0),
                )
            items = _parse_analysis(
                response.choices[0].message.content or '{"papers":[]}'
            )
        except openai.BadRequestError as exc:
            logger.warning("Groq analysis JSON fallback triggered: {}", exc)
            data = await _request_json_reply(
                client, settings, messages, max_tokens=4096
            )
            if isinstance(data, list):
                data = {"papers": data}
            items = AnalysisResponse.model_validate(data).papers
        return [item.model_dump() for item in items]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Analysis parse/validation failed: {}", exc)
        return [_empty_analysis(p) for p in papers]
    except Exception as exc:
        logger.error("Analysis LLM call failed: {}", exc)
        return [_empty_analysis(p) for p in papers]


def _empty_analysis(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "arxiv_id": p.get("arxiv_id", ""),
        "relevance": "low",
        "summary": "",
        "conclusions": "",
        "contributions": "",
        "key_takeaways": "",
        "thesis_paragraph": "",
    }
