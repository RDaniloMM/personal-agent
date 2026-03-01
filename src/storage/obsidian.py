"""Obsidian vault writer – creates Markdown notes directly in the vault folder."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import Settings


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
    """Write a single Arxiv paper as a Markdown note with LLM analysis.

    Returns the path of the created file.
    """
    folder = settings.obsidian_subfolder("Papers")
    filename = _safe_filename(paper.get("title", "paper")) + ".md"
    filepath = folder / filename

    if filepath.exists():
        # Overwrite notes that were written with a failed analysis
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

    # Build analysis sections from LLM output
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
    """Write a daily summary of FB Marketplace findings."""
    folder = settings.obsidian_subfolder("FB-Marketplace")
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"marketplace-{date_str}.md"
    filepath = folder / filename

    fm = _frontmatter(
        {
            "title": f"FB Marketplace – {date_str}",
            "date": date_str,
            "total_listings": len(listings),
            "tags": ["marketplace", "gadgets", "daily"],
        }
    )

    items_md = ""
    for item in listings[:50]:  # cap at 50 per note
        items_md += f"""
### {item.get('title', 'Sin título')}
- **Precio:** {item.get('price', 'N/A')}
- **Ubicación:** {item.get('location', 'N/A')}
- **Link:** {item.get('url', '')}

"""

    body = f"""{fm}

# FB Marketplace – {date_str}

Se encontraron **{len(listings)}** listings.

{items_md}
"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote marketplace summary: {}", filepath.name)
    return str(filepath)


def write_youtube_summary(
    videos: list[dict[str, Any]], settings: Settings
) -> str:
    """Write a daily summary of scraped YouTube videos."""
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
        items_md += f"""
### {v.get('title', 'Sin título')}
- **Canal:** {v.get('channel', 'N/A')}
- **Views:** {v.get('views', 'N/A')}
- **Link:** {v.get('url', '')}
- {v.get('description', '')[:200]}

"""

    body = f"""{fm}

# YouTube Feed – {date_str}

Se encontraron **{len(videos)}** videos relevantes.

{items_md}
"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote YouTube summary: {}", filepath.name)
    return str(filepath)


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

    body = f"""{fm}

# {title}

{content}
"""
    filepath.write_text(body, encoding="utf-8")
    logger.info("Wrote idea note: {}", filepath.name)
    return str(filepath)
