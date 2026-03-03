"""Obsidian vault writer – creates Markdown notes directly in the vault folder."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from shared.config import Settings


# ── Frontmatter helper ───────────────────────────────────────────────────────

_YAML_SPECIAL = re.compile(r'[:#\[\]{}>,|&*!%@`\\]')


def _yaml_value(value: Any) -> str:
    """Format a single value for YAML, quoting when necessary."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if _YAML_SPECIAL.search(s) or s.strip() != s:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def _frontmatter(fields: dict[str, Any]) -> str:
    """Build a valid YAML frontmatter block for Obsidian."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            items = ", ".join(_yaml_value(v) for v in value)
            lines.append(f"{key}: [{items}]")
        else:
            lines.append(f"{key}: {_yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines)


def _safe_filename(text: str, max_len: int = 80) -> str:
    """Sanitise a string into a valid filename."""
    clean = re.sub(r'[<>:"/\\|?*\n\r]', "", text)
    clean = clean.strip(". ")
    return clean[:max_len] if clean else "untitled"


# ── Writers ──────────────────────────────────────────────────────────────────


def write_arxiv_paper(paper: dict[str, Any], settings: Settings) -> str:
    """Write a single Arxiv paper as a Markdown note with LLM analysis."""
    folder = settings.obsidian_subfolder("Papers")
    filename = _safe_filename(paper.get("title", "paper")) + ".md"
    filepath = folder / filename

    if filepath.exists():
        existing = filepath.read_text(encoding="utf-8")
        if "Error en análisis" not in existing and "Análisis no disponible" not in existing:
            logger.debug("Paper note already exists: {}", filepath.name)
            return str(filepath)
        logger.info("Overwriting broken paper note: {}", filepath.name)

    relevance = paper.get("relevance", "unknown")
    authors = paper.get("authors", [])
    fm = _frontmatter(
        {
            "title": paper.get("title", ""),
            "authors": authors[:5],
            "arxiv_id": paper.get("arxiv_id", ""),
            "published": paper.get("published", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "categories": paper.get("categories", []),
            "relevance": relevance,
            "tags": ["paper", "arxiv", "ai-research", f"relevance-{relevance}"],
            "created": datetime.now(UTC).strftime("%Y-%m-%d"),
        }
    )

    summary = paper.get("summary", "")
    conclusions = paper.get("conclusions", "")
    contributions = paper.get("contributions", "")
    key_takeaways = paper.get("key_takeaways", "")

    body = f"""{fm}

## Resumen

{summary if summary else paper.get('abstract', '')}

## Abstract original

{paper.get('abstract', '')}

## Conclusiones

{conclusions if conclusions else '> _Sin análisis_'}

## Aportes clave

{contributions if contributions else '> _Sin análisis_'}

## Puntos importantes

{key_takeaways if key_takeaways else '> _Sin análisis_'}

## Notas

"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote paper note: {}", filepath.name)
    return str(filepath)


def write_marketplace_summary(
    listings: list[dict[str, Any]], settings: Settings
) -> str:
    """Write a daily summary of FB Marketplace deals (only great bargains)."""
    folder = settings.obsidian_subfolder("FB-Marketplace")
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"deals-{date_str}.md"
    filepath = folder / filename

    deals = [l for l in listings if l.get("is_deal")]
    total_scraped = len(listings)

    fm = _frontmatter(
        {
            "title": f"Gangas Marketplace – {date_str}",
            "date": date_str,
            "deals_found": len(deals),
            "total_scraped": total_scraped,
            "tags": ["marketplace", "deals", "gangas", "daily"],
        }
    )

    if not deals:
        body = f"""{fm}

# Gangas Marketplace – {date_str}

> [!note] Sin gangas hoy
> Se revisaron **{total_scraped}** artículos pero ninguno tenía un precio
> excepcionalmente atractivo.
"""
        filepath.write_text(body, encoding="utf-8")
        logger.info("Wrote marketplace summary (no deals): {}", filepath.name)
        return str(filepath)

    items_md = ""
    for item in deals[:30]:
        title = item.get("title", "Sin título")
        price = item.get("price", "N/A")
        location = item.get("location", "N/A")
        url = item.get("url", "")
        reason = item.get("deal_reason", "")
        market_price = item.get("estimated_market_price", "")
        discount = item.get("discount_pct", 0)

        items_md += f"### {title}\n"
        items_md += f"- **Precio:** {price}"
        if market_price:
            items_md += f" ← mercado: ~{market_price}"
        if discount:
            items_md += f" (**{discount}% OFF**)"
        items_md += "\n"
        items_md += f"- **Ubicación:** {location}\n"
        if url:
            items_md += f"- **Link:** {url}\n"
        if reason:
            items_md += f"\n> [!tip] ¿Por qué es ganga?\n> {reason}\n"
        items_md += "\n---\n\n"

    body = f"""{fm}

# Gangas Marketplace – {date_str}

> [!abstract] Resumen
> De **{total_scraped}** artículos revisados, se encontraron **{len(deals)}** gangas
> con precios significativamente por debajo del mercado.

{items_md}
"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote marketplace deals: {}", filepath.name)
    return str(filepath)


def write_youtube_summary(
    videos: list[dict[str, Any]], settings: Settings
) -> str:
    """Write a daily summary of scraped YouTube videos with rich metadata."""
    folder = settings.obsidian_subfolder("YouTube")
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"youtube-{date_str}.md"
    filepath = folder / filename

    fm = _frontmatter(
        {
            "title": f"YouTube Feed – {date_str}",
            "date": date_str,
            "total_videos": len(videos),
            "tags": ["youtube", "feed", "daily"],
        }
    )

    items_md = ""
    for v in videos[:40]:
        title = v.get('title', 'Sin título')
        channel = v.get('channel', 'N/A')
        url = v.get('url', '')
        views = v.get('views', '')
        duration = v.get('duration', '')
        upload_date = v.get('upload_date', '')
        description = (v.get('description', '') or '')[:400]
        tags = v.get('tags', [])
        subtitles = (v.get('subtitles', '') or '')[:500]

        tags_str = ", ".join(tags[:8]) if tags else "N/A"

        items_md += f"### {title}\n"
        items_md += f"- **Canal:** {channel}\n"
        if url:
            items_md += f"- **Link:** {url}\n"
        if upload_date:
            items_md += f"- **Fecha:** {upload_date}\n"
        if duration:
            items_md += f"- **Duración:** {duration}\n"
        if views:
            items_md += f"- **Views:** {views}\n"
        if tags_str != "N/A":
            items_md += f"- **Tags:** {tags_str}\n"
        if description:
            items_md += f"\n> [!info] Descripción\n> {description}\n"
        if subtitles:
            items_md += f"\n> [!quote] Transcripción (extracto)\n> {subtitles}\n"
        items_md += "\n---\n\n"

    body = f"""{fm}

## YouTube Feed – {date_str}

Se encontraron **{len(videos)}** videos relevantes.

{items_md}
"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote YouTube summary: {}", filepath.name)
    return str(filepath)


def _strip_llm_frontmatter(content: str) -> str:
    """Remove any frontmatter or leading # title the LLM may have added."""
    text = content.strip()
    # Strip YAML frontmatter block(s)
    while text.startswith("---"):
        end = text.find("---", 3)
        if end == -1:
            break
        text = text[end + 3:].strip()
    # Strip leading # title line(s)
    while text.startswith("# "):
        newline = text.find("\n")
        if newline == -1:
            text = ""
            break
        text = text[newline + 1:].strip()
    return text


def write_idea_note(
    title: str, content: str, tags: list[str], settings: Settings
) -> str:
    """Write a free-form idea note (generated by the LLM)."""
    folder = settings.obsidian_subfolder("Ideas")
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = _safe_filename(f"{date_str}-{title}") + ".md"
    filepath = folder / filename

    all_tags = ["idea"] + [t.lstrip("#") for t in tags]

    fm = _frontmatter(
        {
            "title": title,
            "date": date_str,
            "tags": all_tags,
        }
    )

    # Sanitise: remove any frontmatter / # title the LLM included
    clean_content = _strip_llm_frontmatter(content)

    body = f"""{fm}

# {title}

{clean_content}
"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote idea note: {}", filepath.name)
    return str(filepath)
