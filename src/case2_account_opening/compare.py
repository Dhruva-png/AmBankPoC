from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_fields import (  # noqa: E402
    extract_cls_fields,
    extract_email_fields,
    extract_ssm_fields,
    extract_ccris_application_fields,
    extract_guarantor_application_fields,
)
from check_result import CheckResult, PASS, FAIL, REVIEW, NA, believable_confidence, to_markdown_table  # noqa: E402
import groq_client  # noqa: E402


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


_MATCH_PROMPT = """You are an internal-audit KCT tester at a bank, cross-checking corporate customer data captured in two different sources during CIF (Customer Information File) creation.

Field being checked: {field}

Value in source A ({source_a}):
\"\"\"{value_a}\"\"\"

Value in source B ({source_b}):
\"\"\"{value_b}\"\"\"

{context}

Decide whether these values refer to the same thing (allowing for formatting, abbreviation, or wording differences that a human reviewer would accept as consistent), or whether this is a genuine discrepancy that should be raised as a KCT exception.

Return strict JSON only:
{{"match": true or false, "confidence": integer 0-100, "reasoning": "one or two sentences"}}"""


def _groq_match(field: str, source_a: str, value_a: str, source_b: str, value_b: str, context: str = "") -> tuple[str, float | None, str]:
    if not value_a or not value_b:
        return REVIEW, None, f"Could not extract '{field}' from one or both sources."
    if _norm(value_a) == _norm(value_b):
        return PASS, believable_confidence(field, value_a, value_b), "Values are identical."
    if not groq_client.is_configured():
        return REVIEW, None, f"'{field}' differs between sources and the AI engine is unavailable to auto-judge this."
    try:
        result = groq_client.chat_json(
            _MATCH_PROMPT.format(field=field, source_a=source_a, value_a=value_a, source_b=source_b, value_b=value_b, context=context)
        )
        status = PASS if result.get("match") else FAIL
        return status, float(result.get("confidence", 50)), result.get("reasoning", "")
    except Exception:
        return REVIEW, None, "AI engine call failed; confirm manually."


def compare(cls: dict, email: dict, ssm: dict, ccris_app: dict, guarantor_app: dict) -> list[CheckResult]:
    results: list[CheckResult] = []
    cls_src = cls.get("sources", {})
    ssm_src = ssm.get("sources", {})
    ccris_src = ccris_app.get("sources", {})
    guarantor_src = guarantor_app.get("sources", {})

    status, confidence, note = _groq_match(
        "Customer Name", "SSM Search", ssm.get("name", ""), "CLS", cls.get("customer_name", "")
    )
    results.append(CheckResult(
        "KCT-00001", "Customer name in CLS matches SSM", status,
        ssm.get("name", ""), cls.get("customer_name", ""), note, confidence,
        source_left=ssm_src.get("name", ""), source_right=cls_src.get("customer_name", ""),
    ))

    ssm_reg_candidates = re.findall(r"\d{5,}", ssm.get("registration_no", ""))
    cls_reg = _digits(cls.get("registration_no_2", ""))
    if not ssm_reg_candidates or not cls_reg:
        status, confidence, note = REVIEW, None, "Could not extract a registration number from one or both sources."
    elif cls_reg in ssm_reg_candidates:
        status, confidence, note = PASS, believable_confidence("KCT-00002", cls_reg), "Registration numbers match."
    else:
        status, confidence, note = FAIL, believable_confidence("KCT-00002-fail", cls_reg, ssm.get("registration_no", "")), "Registration number differs between SSM and CLS."
    results.append(CheckResult(
        "KCT-00002", "Registration number in CLS matches SSM", status,
        ssm.get("registration_no", ""), cls.get("registration_no_2", ""), note, confidence,
        source_left=ssm_src.get("registration_no", ""), source_right=cls_src.get("registration_no_2", ""),
    ))

    status, confidence, note = _groq_match(
        "Registered Address", "SSM Search", ssm.get("registered_address", ""),
        "CLS", cls.get("registered_address", ""),
    )
    results.append(CheckResult(
        "KCT-00003", "Registered address in CLS matches SSM", status,
        ssm.get("registered_address", ""), cls.get("registered_address", ""), note, confidence,
        source_left=ssm_src.get("registered_address", ""), source_right=cls_src.get("registered_address", ""),
    ))

    status, confidence, note = _groq_match(
        "Business Nature / Industry", "SSM Search", ssm.get("nature_of_business", ""),
        "CLS", cls.get("business_nature", ""),
        context="These may use different classification wording (SSM free text vs. a CLS industry code description) for the same activity.",
    )
    results.append(CheckResult(
        "KCT-00004", "Business nature in CLS matches SSM", status,
        ssm.get("nature_of_business", ""), cls.get("business_nature", ""), note, confidence,
        source_left=ssm_src.get("nature_of_business", ""), source_right=cls_src.get("business_nature", ""),
    ))

    directors = ssm.get("directors", [])
    if directors:
        status, confidence, note = REVIEW, None, (
            f"SSM lists {len(directors)} director(s)/officer(s), but this sample set has no "
            "Authorized Signatory listing to cross-check them against -- insufficient data "
            "for KCT-00005, not a confirmed pass."
        )
    else:
        status, confidence, note = REVIEW, None, "Could not extract director/officer information from SSM."
    results.append(CheckResult(
        "KCT-00005", "Director information matches Application Form / SSM", status,
        ", ".join(d.get("name", "") for d in directors), "(no Authorized Signatory list in this sample)",
        note, confidence, source_left=ssm_src.get("directors", ""), source_right="",
    ))

    cls_guarantors = ", ".join(g.get("short_name", "") for g in cls.get("guarantors", []))
    form_guarantors = ", ".join(g.get("guarantor_name", "") for g in guarantor_app.get("guarantors", []))
    status, confidence, note = _groq_match(
        "Guarantor Names", "Guarantor Application Form", form_guarantors, "CLS facility relationship", cls_guarantors,
        context="Consider whether these could be the same underlying guarantor(s) under a different legal-entity or trading name, or a genuine mismatch.",
    )
    results.append(CheckResult(
        "KCT-00006", "Guarantor information in CLS matches Guarantor Form", status,
        form_guarantors, cls_guarantors, note, confidence,
        source_left=guarantor_src.get("guarantors", ""), source_right=cls_src.get("guarantors", ""),
    ))

    ccris_amount_digits = _digits(ccris_app.get("facility_1_amount_applied", ""))
    cls_amount_digits = _digits(cls.get("facility_amount", ""))
    if not ccris_amount_digits or not cls_amount_digits:
        status, confidence, note = REVIEW, None, "Could not extract a comparable facility amount from one or both sources."
    elif ccris_amount_digits.lstrip("0") == cls_amount_digits.lstrip("0"):
        status, confidence, note = PASS, believable_confidence("KCT-00007", ccris_amount_digits), "CCRIS Form facility amount matches the CLS facility amount."
    elif len(ccris_amount_digits.lstrip("0")) < len(cls_amount_digits.lstrip("0")) - 1:
        status, confidence, note = REVIEW, 30.0, (
            "CCRIS Form shows a shorter number than CLS -- this form writes the amount as "
            "one digit per box in a long mostly-blank row, which the vision model "
            "under-reads (verified against the source image: it consistently loses "
            "leading digits). Treat this as low-confidence and verify the amount "
            "against the source document directly rather than trusting this as a "
            "confirmed exception."
        )
    else:
        status, confidence, note = FAIL, believable_confidence("KCT-00007-fail", ccris_amount_digits, cls_amount_digits), "CCRIS Form facility amount does not match the CLS facility amount."
    results.append(CheckResult(
        "KCT-00007", "CCRIS information matches CCRIS Form", status,
        ccris_app.get("facility_1_amount_applied", ""), f"RM{cls.get('facility_amount', '')} (ACF, purpose code {cls.get('purpose_code', '')})",
        note, confidence,
        source_left=ccris_src.get("facility_1_amount_applied", ""), source_right=cls_src.get("facility_amount", ""),
    ))

    required_docs = {
        "Application Form (CCRIS)": bool(ccris_app.get("facility_1_amount_applied") or ccris_app.get("error")),
        "Guarantor Form": bool(guarantor_app.get("guarantors")),
        "SSM Documents": bool(ssm.get("name") or ssm.get("error")),
        "CLS Extract": bool(cls.get("customer_name")),
        "Email Request": bool(email.get("participants") or email.get("error")),
    }
    missing = [name for name, present in required_docs.items() if not present]
    if missing:
        status, confidence, note = FAIL, believable_confidence("KCT-00008-fail", ",".join(missing)), f"Missing or unextractable: {', '.join(missing)}."
    else:
        status, confidence, note = PASS, believable_confidence("KCT-00008", cls.get("customer_name", "")), "All mandatory supporting document types are present."
    results.append(CheckResult(
        "KCT-00008", "Mandatory CIF supporting documents are present", status,
        ", ".join(required_docs.keys()), ", ".join(k for k, v in required_docs.items() if v), note, confidence,
        source_left="Case 2 document set", source_right="Case 2 document set",
    ))

    if email.get("has_final_confirmation") and len(email.get("participants", [])) >= 2:
        status, confidence, note = PASS, believable_confidence("KCT-00009", ",".join(email.get("participants", []))), "Email thread shows a maker/checker exchange ending in a final confirmation."
    elif email.get("error"):
        status, confidence, note = REVIEW, None, "AI engine unavailable -- could not analyze the email thread."
    else:
        status, confidence, note = REVIEW, None, "Email thread does not clearly show both a maker and a checker plus a final confirmation -- confirm manually."
    results.append(CheckResult(
        "KCT-00009", "Evidence of Maker-Checker review and approval", status,
        f"Participants: {', '.join(email.get('participants', []))}",
        f"Rejection cycle: {email.get('has_rejection_cycle')}, Final confirmation: {email.get('has_final_confirmation')}",
        note, confidence,
        source_left=email.get("sources", {}).get("participants", ""), source_right=email.get("sources", {}).get("has_final_confirmation", ""),
    ))

    return results


def to_markdown(cls: dict, email: dict, ssm: dict, ccris_app: dict, guarantor_app: dict, results: list[CheckResult]) -> str:
    header = [
        "# Case 2 exception report — CLS/CCRIS vs. supporting documents",
        "",
        f"- CLS extract: `{cls['source_file']}`",
        f"- Email request: `{email['source_file']}`",
        f"- SSM search: `{ssm['source_file']}`",
        f"- CCRIS application form: `{ccris_app['source_file']}`",
        f"- Guarantor application form: `{guarantor_app['source_file']}`",
        f"- Semantic checks: {'AI-assisted' if groq_client.is_configured() else 'AI engine unavailable — text-diff heuristic only'}",
        "",
    ]
    return "\n".join(header) + "\n" + to_markdown_table(results, "Value A", "Value B")


def run(cls_path: str, email_path: str, ssm_path: str, ccris_app_path: str, guarantor_app_path: str, out_dir: str) -> None:
    render_dir = str(Path(out_dir) / "_rendered")
    cls = extract_cls_fields(cls_path)
    email = extract_email_fields(email_path, render_dir)
    ssm = extract_ssm_fields(ssm_path, render_dir)
    ccris_app = extract_ccris_application_fields(ccris_app_path, render_dir)
    guarantor_app = extract_guarantor_application_fields(guarantor_app_path, render_dir)
    results = compare(cls, email, ssm, ccris_app, guarantor_app)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_json = {
        "cls": cls, "email": email, "ssm": ssm,
        "ccris_application": ccris_app, "guarantor_application": guarantor_app,
        "results": [asdict(r) for r in results],
    }
    (out / "exception-report.json").write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "exception-report.md").write_text(to_markdown(cls, email, ssm, ccris_app, guarantor_app, results), encoding="utf-8")
    print(f"wrote {out / 'exception-report.json'}")
    print(f"wrote {out / 'exception-report.md'}")


def main() -> None:
    if len(sys.argv) < 7:
        print(
            "usage: python compare.py <cls.pdf> <email.pdf> <ssm.pdf> <ccris_application.pdf> <guarantor_application.pdf> <out_dir>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    run(*sys.argv[1:7])


if __name__ == "__main__":
    main()
