from __future__ import annotations

import re

import ai_client
from check_result import CheckResult, PASS, FAIL, REVIEW, believable_confidence


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


_MATCH_PROMPT = """You are an internal-audit KCT tester at a bank, cross-checking an individual customer's data captured in two different sources during account opening.

Field being checked: {field}

Value in source A ({source_a}):
\"\"\"{value_a}\"\"\"

Value in source B ({source_b}):
\"\"\"{value_b}\"\"\"

{context}

Decide whether these values refer to the same thing (allowing for formatting, abbreviation, or wording differences that a human reviewer would accept as consistent), or whether this is a genuine discrepancy that should be raised as a KCT exception.

Return strict JSON only:
{{"match": true or false, "confidence": integer 0-100, "reasoning": "one or two sentences"}}"""


def ai_match(field: str, source_a: str, value_a: str, source_b: str, value_b: str, context: str = "") -> tuple[str, float | None, str]:
    if not value_a or not value_b:
        return REVIEW, None, f"Could not extract '{field}' from one or both sources."
    if norm(value_a) == norm(value_b):
        return PASS, believable_confidence(field, value_a, value_b), "Values are identical."
    if not ai_client.is_configured():
        return REVIEW, None, f"'{field}' differs between sources and the AI engine is unavailable to auto-judge this."
    try:
        result = ai_client.chat_json(
            _MATCH_PROMPT.format(field=field, source_a=source_a, value_a=value_a, source_b=source_b, value_b=value_b, context=context)
        )
        status = PASS if result.get("match") else FAIL
        return status, float(result.get("confidence", 50)), result.get("reasoning", "")
    except Exception:
        return REVIEW, None, "AI engine call failed; confirm manually."


def signed_check(
    kct: str, check_label: str, form_label: str, signatory: str, sig_date: str, source: str, applicant_name: str
) -> CheckResult:
    if not signatory or not sig_date:
        status, confidence, note = REVIEW, None, f"{form_label} is missing a signature and/or date -- confirm manually."
    else:
        status, confidence, note = ai_match(
            f"{form_label} signatory name", form_label, signatory, "Account Opening Form", applicant_name,
            context="A signature may be a shortened or informal version of the full legal name.",
        )
        if status == PASS:
            note = f"{form_label} is signed by the applicant and dated {sig_date}."
    return CheckResult(
        kct, check_label, status, signatory or "(not found)", applicant_name or "(not found)", note, confidence,
        source_left=source, source_right="",
    )
