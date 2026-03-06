"""LLM-powered paper analysis: relevance classification & key-point extraction.

Phase 1 (Triage): Groq (fast, cheap) — classifies relevance from abstract only.
Phase 2 (Analysis): Gemini (deep, large context) — full paper text analysis
including APA 7 thesis paragraph generation.
"""

from __future__ import annotations

import asyncio
import io
import json
import time
from typing import Any, Literal

import openai
from google import genai
from google.genai import types
from loguru import logger
from pydantic import BaseModel, Field

from shared.config import Settings
from shared.llm_json import extract_json_payload


# ── Pydantic models for structured LLM output ────────────────────────────────


class TriageItem(BaseModel):
    arxiv_id: str
    relevance: Literal["high", "medium", "low"]


class TriageResponse(BaseModel):
    papers: list[TriageItem]


class AnalysisItem(BaseModel):
    arxiv_id: str
    summary: str = Field(default="", description="3-5 sentence summary in Spanish")
    conclusions: str = Field(default="", description="Bullet points separated by newlines")
    contributions: str = Field(default="", description="Bullet points separated by newlines")
    key_takeaways: str = Field(default="", description="3-5 actionable bullet points")
    thesis_paragraph: str = Field(default="", description="APA 7 thesis background paragraph in Spanish")


class AnalysisResponse(BaseModel):
    papers: list[AnalysisItem]


# ── Research interests (used to judge relevance) ─────────────────────────

RESEARCH_INTERESTS = """\
- AI agents / agentic systems / autonomous architectures
- LLM evaluation, benchmarks, agent evaluation frameworks
- Function/tool calling in LLMs
- Multi-agent systems
- RAG + Reasoning and Evaluation frameworks
- AI agents in industry/production environments
"""

# ── Phase 1: quick relevance triage ──────────────────────────────────────────

_TRIAGE_SYSTEM = f"""Score each paper's relevance to these interests:
{RESEARCH_INTERESTS}

Return a JSON object with a "papers" key containing an array.
Each element: {{"arxiv_id":"...","relevance":"high"|"medium"|"low"}}
Example: {{"papers": [{{"arxiv_id": "2503.00001", "relevance": "high"}}]}}
No incluyas texto fuera del JSON ni bloques markdown."""

# ── Phase 2: full analysis ───────────────────────────────────────────────────

_ANALYSIS_SYSTEM = f"""Eres un investigador experto en IA y un académico riguroso. Analiza cada paper EN PROFUNDIDAD basándote en su texto completo.

Devuelve un JSON con clave "papers" conteniendo un array. Cada elemento debe tener:

1. **arxiv_id**: string (el ID del paper)
2. **summary**: 3-5 oraciones cubriendo la contribución central, metodología y resultados principales (en español)
3. **conclusions**: bullet points de los hallazgos y resultados principales (en español, separados por \\n)
4. **contributions**: bullet points de las contribuciones novedosas al campo (en español, separados por \\n)
5. **key_takeaways**: 3-5 insights accionables o implicaciones prácticas (en español, separados por \\n)
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

_ABSTRACT_LIMIT = 300
_TRIAGE_BATCH = 20
_ANALYSIS_BATCH = 1  # One paper at a time for deep Gemini analysis


async def analyze_papers(
    papers: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Two-phase analysis: Groq triage (fast) → Gemini deep analysis (full text)."""
    if not papers:
        return []

    # Groq client for fast triage
    groq_client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    # Gemini client for deep analysis (native SDK — sends PDF bytes directly)
    gemini_native: genai.Client | None = None
    if settings.gemini_api_key:
        gemini_native = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Using Gemini ({}) with native PDF vision", settings.gemini_model)
    else:
        logger.warning("No GEMINI_API_KEY set — falling back to Groq for analysis")

    # ── Phase 1: Triage (Groq — fast, abstract only) ─────────
    relevance_map: dict[str, str] = {}
    for i in range(0, len(papers), _TRIAGE_BATCH):
        batch = papers[i : i + _TRIAGE_BATCH]
        triage = await _triage_batch(batch, groq_client, settings)
        for t in triage:
            relevance_map[t["arxiv_id"]] = t.get("relevance", "low")

    relevant_papers = [
        p for p in papers
        if relevance_map.get(p.get("arxiv_id", ""), "low") in ("high", "medium")
    ]

    high_count = sum(1 for v in relevance_map.values() if v == "high")
    medium_count = sum(1 for v in relevance_map.values() if v == "medium")
    low_count = sum(1 for v in relevance_map.values() if v == "low")
    logger.info(
        "Triage: {} high, {} medium, {} low → {} to analyze",
        high_count, medium_count, low_count, len(relevant_papers),
    )

    if not relevant_papers:
        return []

    # ── Phase 2: Deep analysis (Gemini native PDF or Groq fallback) ──
    all_analyses: dict[str, dict[str, Any]] = {}
    for i in range(0, len(relevant_papers), _ANALYSIS_BATCH):
        batch = relevant_papers[i : i + _ANALYSIS_BATCH]
        if gemini_native:
            analyses = await _analysis_batch_gemini(batch, gemini_native, settings)
        else:
            analyses = await _analysis_batch_groq(batch, groq_client, settings)
        for a in analyses:
            all_analyses[a["arxiv_id"]] = a

    enriched: list[dict[str, Any]] = []
    for paper in relevant_papers:
        aid = paper.get("arxiv_id", "")
        analysis = all_analyses.get(aid, {})
        enriched.append({
            **paper,
            **analysis,
            "relevance": relevance_map.get(aid, "medium"),
        })

    logger.info(
        "Paper analysis complete: {} high, {} medium, {} low → {} enriched",
        high_count, medium_count, low_count, len(enriched),
    )
    return enriched


# ── Phase helpers ────────────────────────────────────────────────────────────


def _paper_snippet(p: dict[str, Any], abstract_limit: int = _ABSTRACT_LIMIT) -> str:
    abstract = (p.get("abstract", "") or "")[:abstract_limit]
    cats = ",".join(p.get("categories", []))
    return f"{p.get('arxiv_id','')}: [{cats}] {p.get('title','')}. {abstract}"


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


def _parse_analysis(content: str) -> list[AnalysisItem]:
    data = extract_json_payload(content)
    if isinstance(data, list):
        data = {"papers": data}
    return AnalysisResponse.model_validate(data).papers


_JSON_ONLY_SYSTEM = (
    "Responde solo con JSON valido. No incluyas explicaciones, markdown ni bloques de codigo."
)


async def _request_json_reply(
    client: openai.AsyncOpenAI,
    settings: Settings,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
) -> Any:
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "system", "content": _JSON_ONLY_SYSTEM}, *messages],
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

    for attempt in range(_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            items = _parse_triage(response.choices[0].message.content or '{"papers":[]}')
            return [item.model_dump() for item in items]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Triage parse/validation failed (attempt {}): {}", attempt + 1, exc)
        except openai.RateLimitError as exc:
            wait = 15 * (attempt + 1)  # 15s, 30s ... deja pasar la ventana TPM
            logger.warning(
                "Groq rate limit hit (attempt {}), waiting {}s: {}",
                attempt + 1, wait, exc,
            )
            if attempt < _retries:
                await asyncio.sleep(wait)
            continue
        except openai.BadRequestError as exc:
            logger.warning(
                "Triage JSON generation failed (attempt {}), retrying without response_format: {}",
                attempt + 1, exc,
            )
            try:
                data = await _request_json_reply(client, settings, messages, max_tokens=1024)
                if isinstance(data, list):
                    data = {"papers": data}
                items = TriageResponse.model_validate(data).papers
                return [item.model_dump() for item in items]
            except (json.JSONDecodeError, ValueError) as fallback_exc:
                logger.warning(
                    "Triage fallback parse failed (attempt {}): {}",
                    attempt + 1, fallback_exc,
                )
        except Exception as exc:
            logger.error("Triage LLM call failed: {}", exc)
            return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "low"} for p in papers]

        if attempt < _retries:
            await asyncio.sleep(2 ** attempt)

    logger.warning("Triage exhausted {} retries, falling back to medium", _retries + 1)
    return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "medium"} for p in papers]


_GEMINI_RETRIES = 2
_GEMINI_REQUEST_TIMEOUT = 180
_INLINE_PDF_MB = 10  # PDFs más grandes se suben via Files API


def _upload_pdf_blocking(
    client: genai.Client,
    pdf_bytes: bytes,
    arxiv_id: str,
) -> Any:
    """Sube un PDF a la Files API de Gemini y espera a que esté ACTIVE.

    Retorna el objeto File o None si falla.
    Debe llamarse desde asyncio.to_thread.
    """
    try:
        uploaded = client.files.upload(
            file=io.BytesIO(pdf_bytes),
            config={"mime_type": "application/pdf", "display_name": arxiv_id},
        )
        # Esperar hasta que el archivo esté ACTIVE (normalmente <5s)
        deadline = time.time() + 60
        while uploaded.state.name != "ACTIVE":
            if time.time() > deadline:
                logger.warning("Files API: timeout waiting for {} to be ACTIVE", arxiv_id)
                return None
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        return uploaded
    except Exception as exc:
        logger.error("Files API upload failed for {}: {}", arxiv_id, exc)
        return None


def _delete_file_blocking(client: genai.Client, file_name: str) -> None:
    """Elimina un archivo de la Files API (llamar desde to_thread)."""
    try:
        client.files.delete(name=file_name)
    except Exception as exc:
        logger.warning("Files API delete failed for {}: {}", file_name, exc)


async def _analysis_batch_gemini(
    papers: list[dict[str, Any]],
    client: genai.Client,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Analyze papers using Gemini native SDK.

    - PDF ≤ 10MB → inline (from_bytes)
    - PDF >  10MB → Files API upload → URI reference → delete after
    - Sin PDF      → solo abstract como texto
    """
    results: list[dict[str, Any]] = []

    for paper in papers:
        pdf_bytes: bytes = paper.get("pdf_bytes", b"") or b""
        header = _paper_metadata_header(paper)
        arxiv_id = paper.get("arxiv_id", "")
        size_mb = len(pdf_bytes) / (1024 * 1024)

        # ── Construir la parte PDF del prompt ────────────────────────────────
        uploaded_file_name: str | None = None  # para borrar después

        if not pdf_bytes:
            pdf_part: Any = paper.get("abstract", "")
            source = "abstract only"
        elif size_mb <= _INLINE_PDF_MB:
            pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
            source = f"PDF inline ({size_mb:.1f}MB)"
        else:
            # PDF grande → Files API
            logger.info(
                "PDF large ({:.1f}MB) for [{}] — uploading via Files API",
                size_mb, arxiv_id,
            )
            uploaded = await asyncio.to_thread(
                _upload_pdf_blocking, client, pdf_bytes, arxiv_id
            )
            if uploaded:
                pdf_part = types.Part.from_uri(
                    file_uri=uploaded.uri, mime_type="application/pdf"
                )
                uploaded_file_name = uploaded.name
                source = f"PDF Files API ({size_mb:.1f}MB)"
                logger.info("Files API upload ready: {} → {}", arxiv_id, uploaded.uri)
            else:
                # Fallback a abstract si la subida falla
                pdf_part = paper.get("abstract", "")
                source = "abstract only (upload failed)"

        parts: list[Any] = [
            pdf_part,
            f"Metadatos del paper:\n{header}\n\n"
            f"Analiza este paper en profundidad basándote en el documento completo.",
        ]

        # ── Intentos de análisis ──────────────────────────────────────────────
        result: dict[str, Any] | None = None
        for attempt in range(_GEMINI_RETRIES + 1):
            try:
                logger.info(
                    "Analyzing [{}] with Gemini ({}) attempt {}/{}",
                    arxiv_id, source, attempt + 1, _GEMINI_RETRIES + 1,
                )
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=settings.gemini_model,
                        contents=[_ANALYSIS_SYSTEM] + parts,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            max_output_tokens=16384,
                        ),
                    ),
                    timeout=_GEMINI_REQUEST_TIMEOUT,
                )
                items = _parse_analysis(response.text or '{"papers":[]}')
                result = next(
                    (item.model_dump() for item in items if item.arxiv_id == arxiv_id),
                    items[0].model_dump() if items else None,
                )
                break  # éxito
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "Gemini parse failed for {} (attempt {}/{}): {}",
                    arxiv_id, attempt + 1, _GEMINI_RETRIES + 1, exc,
                )
                if attempt < _GEMINI_RETRIES:
                    await asyncio.sleep(3 * (attempt + 1))
            except asyncio.TimeoutError:
                logger.warning(
                    "Gemini timeout for {} after {}s (attempt {}/{} )",
                    arxiv_id, _GEMINI_REQUEST_TIMEOUT, attempt + 1, _GEMINI_RETRIES + 1,
                )
                if attempt < _GEMINI_RETRIES:
                    await asyncio.sleep(3 * (attempt + 1))
            except Exception as exc:
                logger.error("Gemini call failed for {}: {}", arxiv_id, exc)
                break  # error no recuperable

        # ── Limpiar archivo de Files API si se usó ────────────────────────
        if uploaded_file_name:
            await asyncio.to_thread(_delete_file_blocking, client, uploaded_file_name)
            logger.debug("Files API: deleted {}", uploaded_file_name)

        results.append(result if result is not None else _empty_analysis(paper))

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
        logger.info(
            "Analyzing {} paper(s) with Groq fallback ({:.0f}K chars)",
            len(papers), len(papers_text) / 1000,
        )
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            items = _parse_analysis(response.choices[0].message.content or '{"papers":[]}')
        except openai.BadRequestError as exc:
            logger.warning("Groq analysis JSON fallback triggered: {}", exc)
            data = await _request_json_reply(client, settings, messages, max_tokens=8192)
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
