from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

API_BASE = "https://generativelanguage.googleapis.com/v1beta"

TEXT_MODEL = "gemini-3.5-flash-lite"
VISION_MODEL = "gemini-3.5-flash-lite"

REQUEST_TIMEOUT = 45


def _keys() -> list[str]:
    keys = [
        os.environ.get("GEMINI_API_KEY_1", "").strip(),
        os.environ.get("GEMINI_API_KEY_2", "").strip(),
    ]
    single = os.environ.get("GEMINI_API_KEY", "").strip()
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
        resp = requests.get(f"{API_BASE}/models", headers={"x-goog-api-key": key}, timeout=8)
        if resp.status_code in (401, 403):
            return False, f"rejected ({resp.status_code})"
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


class AIClientError(Exception):
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
        raise AIClientError("AI engine is not configured for this environment.")

    url = f"{API_BASE}/models/{model}:generateContent"
    last_error: Exception | None = None
    for cycle in range(max_cycles):
        rate_limited_wait = 0.0
        for key in keys:
            headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 10))
                    last_error = AIClientError("AI engine is temporarily at capacity, retrying.")
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
                last_error = AIClientError(f"AI engine request failed ({resp.status_code}). {detail}".strip())
                if resp.status_code in (400, 401, 403):
                    raise last_error
            except requests.exceptions.RequestException:
                last_error = AIClientError("AI engine is temporarily unreachable.")
        if rate_limited_wait and cycle < max_cycles - 1:
            time.sleep(min(rate_limited_wait, 30) + 1)
    raise AIClientError(f"AI engine is currently unavailable. {last_error}")


def _response_text(data: dict) -> str:
    parts = data["candidates"][0]["content"].get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def chat_json(prompt: str, model: str = TEXT_MODEL, max_tokens: int = 1200, temperature: float = 0.0) -> dict:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 1},
        },
    }
    data = _post(model, body)
    return _extract_json(_response_text(data))


def vision_json(
    prompt: str,
    image_b64: str,
    mime_type: str = "image/png",
    model: str = VISION_MODEL,
    max_tokens: int = 1200,
) -> dict:
    return vision_json_multi(prompt, [(image_b64, mime_type)], model=model, max_tokens=max_tokens)


def vision_json_multi(
    prompt: str,
    images: list[tuple[str, str]],
    model: str = VISION_MODEL,
    max_tokens: int = 1200,
) -> dict:
    parts: list[dict] = [{"text": prompt}]
    for image_b64, mime_type in images:
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_b64}})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "topP": 0.1,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 1},
        },
    }
    data = _post(model, body)
    return _extract_json(_response_text(data))


def image_file_to_b64(path: str) -> tuple[str, str]:
    suffix = Path(path).suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime


_REMARKS_PROMPT = """You are a senior internal audit reviewer at a bank finalizing a control-testing workbook for {case_label}.

Below are the automated KCT control testing results for this case:

{results_summary}

Write 3-5 short bullet points (each one sentence, under 20 words) for the audit workbook. Cover: overall reliability of the reconciled documents, any FAIL exceptions by KCT number, and any REVIEW items needing manual follow-up. Skip anything that passed cleanly -- only call out what a reviewer needs to act on. No headings, no restating the full table, no filler sentences.

Return strict JSON only:
{{"bullets": ["...", "..."]}}"""


def generate_case_remarks(results, case_label: str) -> str:
    if not is_configured():
        return "- Automated remarks unavailable -- AI engine not configured for this run."
    lines = []
    for r in results:
        conf = f"{r.confidence:.0f}%" if r.confidence is not None else "n/a"
        lines.append(f"- {r.kct} ({r.check}): {r.status}, confidence {conf} -- {r.note}")
    try:
        result = chat_json(
            _REMARKS_PROMPT.format(case_label=case_label, results_summary="\n".join(lines)),
            max_tokens=1200,
        )
        bullets = [b.strip() for b in result.get("bullets", []) if b.strip()]
        return "\n".join(f"- {b}" for b in bullets) or "- AI remarks generation returned no content."
    except Exception as exc:
        return f"- AI remarks generation failed ({exc})."


_MODULE_SUMMARY_PROMPT = """You are a senior internal audit reviewer at a bank summarizing the results of an AI-assisted key control testing (KCT) exercise for {module_name}.

Aggregate statistics across all {total_cases} case(s) processed so far:
- Flagged (containing at least one exception or review item): {flagged_cases}
- Clean (all controls passed): {clean_cases}
- Total exceptions raised (FAIL + REVIEW findings): {total_findings}
- Most frequent exception(s): {top_exceptions}
- Average AI confidence across scored checks: {avg_confidence}

Write a concise, professional executive summary (3-5 sentences) for an internal audit reporting pack. Assess overall control effectiveness across the population reviewed, call out the most frequent or significant exception(s), and state whether the population warrants escalation or is broadly satisfactory. Formal audit tone, third person, no headings, do not simply restate the raw numbers.

Return strict JSON only:
{{"summary": "..."}}"""


def generate_module_summary(stats: dict, module_name: str) -> str:
    if not is_configured():
        return (
            "Automated executive summary unavailable -- AI engine not configured for this run. "
            "Refer to the KPI figures and case list below for the underlying statistics."
        )
    if not stats.get("total_cases"):
        return "No cases have been processed yet -- run control testing on at least one case, then generate this report."
    try:
        result = chat_json(
            _MODULE_SUMMARY_PROMPT.format(
                module_name=module_name,
                total_cases=stats.get("total_cases", 0),
                flagged_cases=stats.get("flagged_cases", 0),
                clean_cases=stats.get("clean_cases", 0),
                total_findings=stats.get("total_findings", 0),
                top_exceptions=stats.get("top_exceptions") or "none",
                avg_confidence=stats.get("avg_confidence") or "n/a",
            ),
            max_tokens=1200,
        )
        return result.get("summary", "").strip() or "AI summary generation returned no content."
    except Exception as exc:
        return f"AI summary generation failed ({exc}). Refer to the KPI figures and case list below for the underlying statistics."
