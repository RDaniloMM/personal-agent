"""LLM-powered paper analysis: relevance classification & key-point extraction.

Phase 1 (Triage): Groq (fast, cheap) — classifies relevance from abstract only.
Phase 2 (Analysis): Gemini (deep, large context) — full paper text analysis
including APA 7 thesis paragraph generation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

import openai
from loguru import logger
from pydantic import BaseModel, Field

from shared.config import Settings
from shared.prompts.obsidian_skill import OBSIDIAN_FORMATTING_SKILL


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
Example: {{"papers": [{{"arxiv_id": "2503.00001", "relevance": "high"}}]}}"""

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

Usa [[wiki-links]] para conceptos clave, **negrita** para términos importantes.
Ejemplo de formato JSON:
{{"papers": [{{"arxiv_id": "2503.00001", "summary": "...", "conclusions": "...", "contributions": "...", "key_takeaways": "...", "thesis_paragraph": "..."}}]}}

Escribe TODO en español.

{OBSIDIAN_FORMATTING_SKILL}"""

_ABSTRACT_LIMIT = 300
_FULL_TEXT_LIMIT = 100000  # ~100K chars — Gemini has large context window
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

    # Gemini client for deep analysis (OpenAI-compatible endpoint)
    gemini_client: openai.AsyncOpenAI | None = None
    if settings.gemini_api_key:
        gemini_client = openai.AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        logger.info("Using Gemini ({}) for deep paper analysis", settings.gemini_model)
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

    # ── Phase 2: Deep analysis (Gemini — full text) ───────────
    analysis_client = gemini_client or groq_client
    analysis_model = settings.gemini_model if gemini_client else settings.llm_model

    all_analyses: dict[str, dict[str, Any]] = {}
    for i in range(0, len(relevant_papers), _ANALYSIS_BATCH):
        batch = relevant_papers[i : i + _ANALYSIS_BATCH]
        analyses = await _analysis_batch(batch, analysis_client, analysis_model, settings)
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


def _paper_full_text_snippet(p: dict[str, Any]) -> str:
    """Build a rich snippet with full paper text for deep analysis."""
    full_text = (p.get("full_text", "") or "").strip()
    abstract = (p.get("abstract", "") or "").strip()
    cats = ",".join(p.get("categories", []))

    if full_text:
        # Use full text, truncated to limit
        content = full_text[:_FULL_TEXT_LIMIT]
        source_label = f"[FULL TEXT — {len(full_text):,} chars, showing first {len(content):,}]"
    else:
        # Fallback to abstract if PDF extraction failed
        content = abstract
        source_label = "[ABSTRACT ONLY — PDF not available]"

    return (
        f"---\n"
        f"arxiv_id: {p.get('arxiv_id', '')}\n"
        f"title: {p.get('title', '')}\n"
        f"categories: {cats}\n"
        f"{source_label}\n\n"
        f"{content}\n"
        f"---"
    )


def _parse_triage(content: str) -> list[TriageItem]:
    data = json.loads(content)
    if isinstance(data, list):
        data = {"papers": data}
    return TriageResponse.model_validate(data).papers


def _parse_analysis(content: str) -> list[AnalysisItem]:
    data = json.loads(content)
    if isinstance(data, list):
        data = {"papers": data}
    return AnalysisResponse.model_validate(data).papers


async def _triage_batch(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    settings: Settings,
    *,
    _retries: int = 2,
) -> list[dict[str, Any]]:
    papers_text = "\n".join(_paper_snippet(p) for p in papers)
    last_exc: Exception | None = None

    for attempt in range(_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": _TRIAGE_SYSTEM},
                    {"role": "user", "content": papers_text},
                ],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            items = _parse_triage(response.choices[0].message.content or '{"papers":[]}')
            return [item.model_dump() for item in items]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Triage parse/validation failed (attempt {}): {}", attempt + 1, exc)
            last_exc = exc
        except openai.BadRequestError as exc:
            logger.warning("Triage JSON generation failed (attempt {}): {}", attempt + 1, exc)
            last_exc = exc
        except Exception as exc:
            logger.error("Triage LLM call failed: {}", exc)
            return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "low"} for p in papers]

        if attempt < _retries:
            await asyncio.sleep(2 ** attempt)

    logger.warning("Triage exhausted {} retries, falling back to medium", _retries + 1)
    return [{"arxiv_id": p.get("arxiv_id", ""), "relevance": "medium"} for p in papers]


async def _analysis_batch(
    papers: list[dict[str, Any]],
    client: openai.AsyncOpenAI,
    model: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    papers_text = "\n\n".join(
        _paper_full_text_snippet(p) for p in papers
    )
    try:
        logger.info(
            "Analyzing {} paper(s) with {} ({:.0f}K chars input)",
            len(papers), model, len(papers_text) / 1000,
        )
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {"role": "user", "content": f"Analiza estos papers en profundidad basándote en su texto completo:\n{papers_text}"},
            ],
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
        items = _parse_analysis(response.choices[0].message.content or '{"papers":[]}')
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
