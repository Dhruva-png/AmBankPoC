from __future__ import annotations

import ai_client

_TEXT_PROMPT = """You are classifying a scanned/uploaded bank document. Based on the text below, choose exactly one category from this list that best matches the document, or "unknown" if none clearly match.

Categories:
{categories}

Document text (may be truncated):
{text}

Return strict JSON only: {{"category": "<one of the category keys above, or 'unknown'>"}}"""

_VISION_PROMPT = """You are classifying a bank document from an image of its first page. Choose exactly one category from this list that best matches what is shown, or "unknown" if none clearly match.

Categories:
{categories}

Return strict JSON only: {{"category": "<one of the category keys above, or 'unknown'>"}}"""


def _category_lines(categories: dict[str, str]) -> str:
    return "\n".join(f"- {key}: {desc}" for key, desc in categories.items())


def classify_text(text: str, categories: dict[str, str]) -> str:
    if not ai_client.is_configured() or not text.strip():
        return "unknown"
    try:
        result = ai_client.chat_json(
            _TEXT_PROMPT.format(categories=_category_lines(categories), text=text[:3000]),
            max_tokens=50,
        )
        category = str(result.get("category", "")).strip()
        return category if category in categories else "unknown"
    except Exception:
        return "unknown"


def classify_image(image_path: str, categories: dict[str, str]) -> str:
    if not ai_client.is_configured():
        return "unknown"
    try:
        b64, mime = ai_client.image_file_to_b64(image_path)
        result = ai_client.vision_json(
            _VISION_PROMPT.format(categories=_category_lines(categories)), b64, mime, max_tokens=50
        )
        category = str(result.get("category", "")).strip()
        return category if category in categories else "unknown"
    except Exception:
        return "unknown"
