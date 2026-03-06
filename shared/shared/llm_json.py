"""Helpers for extracting JSON payloads from imperfect LLM responses."""

from __future__ import annotations

import json
from typing import Any


def extract_json_payload(content: str) -> Any:
    """Parse JSON even if the model wrapped it in prose or code fences."""
    text = _strip_code_fences(content)
    if not text:
        raise json.JSONDecodeError("Empty content", "", 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        segment = _find_balanced_json_segment(text)
        if segment is None:
            raise
        return json.loads(segment)


def _strip_code_fences(content: str) -> str:
    text = (content or "").strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _find_balanced_json_segment(text: str) -> str | None:
    start = next((i for i, ch in enumerate(text) if ch in "{["), -1)
    if start < 0:
        return None

    stack: list[str] = []
    in_string = False
    escaped = False

    for idx in range(start, len(text)):
        ch = text[idx]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append(ch)
            continue
        if ch in "}]":
            if not stack:
                return None
            opener = stack.pop()
            if (opener, ch) not in {("{", "}"), ("[", "]")}:
                return None
            if not stack:
                return text[start : idx + 1]

    return None
