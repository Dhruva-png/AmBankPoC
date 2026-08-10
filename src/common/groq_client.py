from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"

TEXT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "qwen/qwen3.6-27b"

REQUEST_TIMEOUT = 45


def _keys() -> list[str]:
    keys = [
        os.environ.get("GROQ_API_KEY_1", "").strip(),
        os.environ.get("GROQ_API_KEY_2", "").strip(),
    ]
    single = os.environ.get("GROQ_API_KEY", "").strip()
    if single:
        keys.append(single)
    return [k for k in keys if k]


@dataclass
class KeyStatus:
    label: str
    configured: bool
    online: bool
    error: str


def check_key(key: str) -> tuple[bool, str]:
    if not key:
        return False, "not set"
    try:
        resp = requests.get(
            MODELS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=8
        )
        if resp.status_code == 401:
            return False, "rejected (401)"
        resp.raise_for_status()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def status() -> list[KeyStatus]:
    keys = _keys()
    results = []
    for i, key in enumerate(keys, start=1):
        online, error = check_key(key)
        results.append(KeyStatus(label=f"Engine {i}", configured=True, online=online, error=error))
    if not results:
        results.append(KeyStatus(label="Engine 1", configured=False, online=False, error="not configured"))
    return results


def is_configured() -> bool:
    return bool(_keys())


class GroqError(Exception):
    pass


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    return text.strip()


def _extract_json(text: str) -> dict:
    if "<think>" in text:
        text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.DOTALL)
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _post(model: str, body: dict, max_cycles: int = 3) -> dict:
    keys = _keys()
    if not keys:
        raise GroqError("AI engine is not configured for this environment.")

    last_error: Exception | None = None
    for cycle in range(max_cycles):
        rate_limited_wait = 0.0
        for key in keys:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            try:
                resp = requests.post(CHAT_URL, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 10))
                    last_error = GroqError("AI engine is temporarily at capacity, retrying.")
                    rate_limited_wait = max(rate_limited_wait, retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as exc:
                detail = ""
                try:
                    detail = resp.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                last_error = GroqError(f"AI engine request failed ({resp.status_code}). {detail}".strip())
                if resp.status_code in (400, 401, 403):
                    raise last_error
            except requests.exceptions.RequestException:
                last_error = GroqError("AI engine is temporarily unreachable.")
        if rate_limited_wait and cycle < max_cycles - 1:
            time.sleep(min(rate_limited_wait, 30) + 1)
    raise GroqError(f"AI engine is currently unavailable. {last_error}")


def chat_json(prompt: str, model: str = TEXT_MODEL, max_tokens: int = 800, temperature: float = 0.0) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    data = _post(model, body)
    text = data["choices"][0]["message"]["content"]
    return _extract_json(text)


def vision_json(
    prompt: str,
    image_b64: str,
    mime_type: str = "image/png",
    model: str = VISION_MODEL,
    max_tokens: int = 800,
) -> dict:
    return vision_json_multi(prompt, [(image_b64, mime_type)], model=model, max_tokens=max_tokens)


def vision_json_multi(
    prompt: str,
    images: list[tuple[str, str]],
    model: str = VISION_MODEL,
    max_tokens: int = 800,
) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for image_b64, mime_type in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}})
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
        "top_p": 0.1,
        "max_completion_tokens": max_tokens,
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
    }
    data = _post(model, body)
    text = data["choices"][0]["message"]["content"]
    return _extract_json(text)


def image_file_to_b64(path: str) -> tuple[str, str]:
    suffix = Path(path).suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime


_REMARKS_PROMPT = """You are a senior internal audit reviewer at a bank finalizing a control-testing workbook for {case_label}.

Below are the automated KCT control testing results for this case:

{results_summary}

Write a concise, professional remarks paragraph (3-5 sentences) for the audit workbook. Assess the overall reliability/authenticity of the reconciled documents based on these findings. Explicitly reference any FAIL exceptions and any REVIEW items needing manual follow-up, and note where confidence was low. Do not simply restate the table -- synthesize a conclusion a reviewer could sign off against. Write in formal audit tone, third person, no headings.

Return strict JSON only:
{{"remarks": "..."}}"""


def generate_case_remarks(results, case_label: str) -> str:
    if not is_configured():
        return (
            "Automated remarks unavailable -- AI engine not configured for this run. "
            "Refer to the Line Items sheet for individual check status, confidence and sourcing."
        )
    lines = []
    for r in results:
        conf = f"{r.confidence:.0f}%" if r.confidence is not None else "n/a"
        lines.append(f"- {r.kct} ({r.check}): {r.status}, confidence {conf} -- {r.note}")
    try:
        result = chat_json(
            _REMARKS_PROMPT.format(case_label=case_label, results_summary="\n".join(lines)),
            max_tokens=500,
        )
        return result.get("remarks", "").strip() or "AI remarks generation returned no content."
    except Exception as exc:
        return f"AI remarks generation failed ({exc}). Refer to the Line Items sheet for detail."
