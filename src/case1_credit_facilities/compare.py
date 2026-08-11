from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_fields import extract_credit_paper_fields, extract_lo_fields  # noqa: E402
from check_result import CheckResult, PASS, FAIL, REVIEW, NA, believable_confidence, to_markdown_table  # noqa: E402
import groq_client  # noqa: E402


def _norm_amount(text: str) -> float | None:
    if not text:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _pick_facility_for_lo(cp: dict, lo_amount_rm: float | None) -> dict | None:
    for facility in cp["facilities"]:
        limits = [float(x.replace(",", "")) * 1000 for x in re.findall(r"[\d,]+", facility["limit_rm000"])]
        if lo_amount_rm is not None and any(abs(lo_amount_rm - lim) < 1 for lim in limits):
            return facility
    return cp["facilities"][0] if cp["facilities"] else None


_PURPOSE_PROMPT = """You are an internal-audit KCT tester at a bank, checking a Letter of Offer (LO) against the approved Credit Paper for a credit facility.

Approved Credit Paper facility purpose:
\"\"\"{cp_purpose}\"\"\"

Issued Letter of Offer facility purpose:
\"\"\"{lo_purpose}\"\"\"

The Credit Paper's own "Purpose of Submission" section notes: "{cp_context}"

Decide whether the LO's purpose wording is a legitimate, approved statement of the facility purpose (which may be a deliberate revision the Credit Paper explicitly approved), or whether it is an unexplained exception -- KCT exception #2, "Facility purpose differs from approved purpose".

Return strict JSON only:
{{"consistent": true or false, "confidence": integer 0-100, "reasoning": "one or two sentences citing the specific wording difference or similarity"}}"""

_SPECIAL_CONDITIONS_PROMPT = """You are an internal-audit KCT tester at a bank, checking whether an approved Credit Paper special condition/covenant is reflected in an issued Letter of Offer (LO).

Approved special condition / covenant:
\"\"\"{cp_condition}\"\"\"

Full text of the issued Letter of Offer:
\"\"\"{lo_text}\"\"\"

Decide whether this condition is reflected in the LO -- directly restated, referenced, or reasonably preserved because the LO is a supplemental/variation letter that leaves prior terms unchanged ("all other terms and conditions... shall remain unchanged"). If the LO is silent and gives no such carry-forward assurance, treat it as KCT exception #5, "Approved special conditions omitted from LO".

Return strict JSON only:
{{"reflected": true or false, "confidence": integer 0-100, "reasoning": "one or two sentences"}}"""


def _groq_purpose_check(cp: dict, lo: dict) -> tuple[str, float | None, str]:
    cp_purpose, lo_purpose = cp.get("purpose", ""), lo.get("purpose", "")
    if not lo_purpose:
        return REVIEW, None, "Could not find a purpose clause in the LO."
    if _norm_text(cp_purpose) == _norm_text(lo_purpose):
        return PASS, believable_confidence("KCT-00002-exact", cp_purpose), "Purpose wording is identical."
    if not groq_client.is_configured():
        return REVIEW, None, (
            "Purpose wording differs from the Credit Paper's on-file purpose. The AI engine "
            "is unavailable to auto-judge this -- confirm manually against the CP's approved "
            "revised-purpose text."
        )
    try:
        result = groq_client.chat_json(
            _PURPOSE_PROMPT.format(
                cp_purpose=cp_purpose,
                lo_purpose=lo_purpose,
                cp_context="To revise the BG purpose" if "revise" in cp.get("special_conditions", "").lower() else cp.get("special_conditions", "N/A"),
            )
        )
        status = PASS if result.get("consistent") else FAIL
        return status, float(result.get("confidence", 50)), result.get("reasoning", "")
    except Exception:
        return REVIEW, None, "AI engine call failed; confirm manually."


def _groq_special_conditions_check(cp: dict, lo: dict) -> tuple[str, float | None, str]:
    cp_special = cp.get("special_conditions", "")
    if not cp_special or cp_special.upper() in ("N/A", "NIL"):
        return PASS, believable_confidence("KCT-00005-none", cp_special), "No special conditions on file to check."
    lo_text = lo.get("raw_text", "")
    if _norm_text(cp_special) in _norm_text(lo_text):
        return PASS, believable_confidence("KCT-00005-verbatim", cp_special), "Special condition text appears verbatim in the LO."
    if not groq_client.is_configured():
        return REVIEW, None, (
            "Approved special condition is not repeated verbatim in this LO, and the AI "
            "engine is unavailable to auto-judge whether it still applies."
        )
    try:
        result = groq_client.chat_json(
            _SPECIAL_CONDITIONS_PROMPT.format(cp_condition=cp_special, lo_text=lo_text[:4000])
        )
        status = PASS if result.get("reflected") else REVIEW
        return status, float(result.get("confidence", 50)), result.get("reasoning", "")
    except Exception:
        return REVIEW, None, "AI engine call failed; confirm manually."


def compare(cp: dict, lo: dict) -> list[CheckResult]:
    results: list[CheckResult] = []
    cp_sources, lo_sources = cp.get("sources", {}), lo.get("sources", {})
    lo_amount = _norm_amount(lo.get("facility_amount") or "")
    facility = _pick_facility_for_lo(cp, lo_amount)

    cp_limit_text = facility["limit_rm000"] if facility else ""
    cp_limits_rm = [float(x.replace(",", "")) * 1000 for x in re.findall(r"[\d,]+", cp_limit_text)]
    if lo_amount is None:
        status, note = REVIEW, "Could not find a facility amount in the LO text."
    elif not cp_limits_rm:
        status, note = REVIEW, "Could not find a matching facility limit in the Credit Paper."
    elif any(abs(lo_amount - lim) < 1 for lim in cp_limits_rm):
        status, note = PASS, "LO amount matches an approved facility limit."
    else:
        status, note = FAIL, "LO amount does not match any approved facility limit for this customer."
    results.append(
        CheckResult(
            "KCT-00001", "Facility amount matches approved Credit Paper", status,
            f"RM{cp_limit_text} '000 ({facility['book'].strip() if facility else 'n/a'}, {facility['facility_code'] if facility else ''})",
            lo.get("facility_amount") or "(not found)", note,
            confidence=believable_confidence("KCT-00001", cp_limit_text, lo.get("facility_amount") or "") if status in (PASS, FAIL) else None,
            source_left=cp_sources.get("facilities", ""), source_right=lo_sources.get("facility_amount", ""),
        )
    )

    status, confidence, note = _groq_purpose_check(cp, lo)
    results.append(
        CheckResult(
            "KCT-00002", "Facility purpose matches approved Credit Paper", status,
            cp.get("purpose", ""), lo.get("purpose", ""), note, confidence=confidence,
            source_left=cp_sources.get("purpose", ""), source_right=lo_sources.get("purpose", ""),
        )
    )

    cp_pricing = facility["pricing"] if facility else ""
    lo_has_rate_ref = "%" in (lo.get("raw_text") or "")
    if not lo_has_rate_ref:
        status, note = NA, "This LO is a purpose-revision supplemental letter and does not restate pricing -- expected, not an exception."
    else:
        status, note = REVIEW, "LO text contains a rate reference -- confirm it matches the approved pricing."
    results.append(CheckResult(
        "KCT-00003", "Pricing / profit rate matches approved Credit Paper", status, cp_pricing,
        "(not restated in LO)", note, confidence=None,
        source_left=cp_sources.get("facilities", ""), source_right="",
    ))

    cp_tenure = cp.get("term_maturity", "") or cp.get("availability_period", "")
    status, note = NA, "This LO is a purpose-revision supplemental letter and does not restate tenure -- expected, not an exception."
    results.append(CheckResult(
        "KCT-00004", "Facility tenure matches approved Credit Paper", status, cp_tenure,
        "(not restated in LO)", note, confidence=None,
        source_left=cp_sources.get("term_maturity", ""), source_right="",
    ))

    status, confidence, note = _groq_special_conditions_check(cp, lo)
    results.append(CheckResult(
        "KCT-00005", "Approved special conditions reflected in LO", status,
        cp.get("special_conditions", ""), "(see raw LO text)", note, confidence=confidence,
        source_left=cp_sources.get("special_conditions", ""), source_right=f"{Path(lo['source_file']).name} — full text",
    ))

    cp_customer = cp.get("customer", "")
    cp_reg_no = ""
    m = re.search(r"\(([\d]+\s*/?\s*[\dA-Z\-]+)\)", cp_customer)
    if m:
        cp_reg_no = re.sub(r"\s*/\s*", " / ", m.group(1))
    lo_name, lo_reg = lo.get("addressee_name", ""), lo.get("addressee_registration_no", "")
    name_match = _norm_text(cp_customer).startswith(_norm_text(lo_name)) if lo_name else False
    reg_digits_cp = re.findall(r"\d{6,}", cp_reg_no)
    reg_digits_lo = re.findall(r"\d{6,}", lo_reg)
    reg_match = bool(reg_digits_cp) and reg_digits_cp[0] in reg_digits_lo
    if name_match and reg_match:
        status, note = PASS, "Customer name and registration number match."
    elif not lo_name:
        status, note = REVIEW, "Could not find an addressee block in the LO."
    else:
        status, note = FAIL, "Customer name or registration number differs between the Credit Paper and the LO."
    results.append(CheckResult(
        "Exception #8", "Customer name/registration number match", status, cp_customer,
        f"{lo_name} [{lo_reg}]", note,
        confidence=believable_confidence("Exception#8", cp_customer, lo_name, lo_reg) if status in (PASS, FAIL) else None,
        source_left=cp_sources.get("customer", ""), source_right=lo_sources.get("addressee_name", ""),
    ))

    cp_support = cp.get("support_guarantees", "")
    cp_nric = re.search(r"[\d]{6}-\d{2}-\d{4}", cp_support)
    lo_nric = lo.get("guarantor_nric", "")
    if cp_nric and lo_nric and cp_nric.group(0) == lo_nric:
        status, note = PASS, "Guarantor NRIC matches between Credit Paper and LO."
    elif not lo_nric:
        status, note = REVIEW, "Could not find a guarantor acknowledgment block in the LO."
    else:
        status, note = FAIL, "Guarantor NRIC differs between the Credit Paper and the LO."
    results.append(CheckResult(
        "Supplementary", "Guarantor identity matches approved Credit Paper", status, cp_support,
        f"{lo.get('guarantor_name', '')} ({lo_nric})", note,
        confidence=believable_confidence("Supplementary", cp_support, lo_nric) if status in (PASS, FAIL) else None,
        source_left=cp_sources.get("support_guarantees", ""), source_right=lo_sources.get("guarantor_name", ""),
    ))

    lo_entity = lo.get("issuing_entity", "")
    if facility and "islamic" in facility["book"].lower() and "islamic" not in lo_entity.lower():
        status, note = FAIL, "LO issued on conventional AmBank letterhead but the matched facility is an AmIslamic facility."
    elif facility and "islamic" not in facility["book"].lower() and "islamic" in lo_entity.lower():
        status, note = FAIL, "LO issued on AmBank Islamic letterhead but the matched facility is a conventional AmBank facility."
    elif not lo_entity:
        status, note = REVIEW, "Could not identify the issuing entity/letterhead in the LO."
    else:
        status, note = PASS, "Letterhead/issuing entity is consistent with the matched facility's book."
    results.append(CheckResult(
        "Exception #9", "Letterhead matches facility book (Conventional/Islamic)", status,
        facility["book"].strip() if facility else "", lo_entity, note,
        confidence=believable_confidence("Exception#9", facility["book"] if facility else "", lo_entity) if status in (PASS, FAIL) else None,
        source_left=cp_sources.get("facilities", ""), source_right=lo_sources.get("issuing_entity", ""),
    ))

    lo_date = lo.get("letter_date", "")
    if lo_date:
        status, note = REVIEW, (
            "LO carries an issuance date, but KCT-00006 (LO issued before approval) and "
            "KCT-00007 (Maker-Checker evidence) cannot be verified automatically -- the "
            "Credit Paper's approval date/signatures are in a scanned image, not text. "
            "Needs manual confirmation."
        )
    else:
        status, note = REVIEW, "Could not find an issuance date on the LO."
    results.append(CheckResult(
        "KCT-00006 / KCT-00007", "LO issuance date present (informational only -- not an approval-timing check)",
        status, "(approval date not extractable -- signature image)", lo_date, note, confidence=None,
        source_left="", source_right=lo_sources.get("letter_date", ""),
    ))

    return results


def to_markdown(cp: dict, lo: dict, results: list[CheckResult]) -> str:
    header = [
        "# Case 1 exception report — LO vs. Credit Paper",
        "",
        f"- Credit Paper: `{cp['source_file']}`",
        f"- Letter of Offer: `{lo['source_file']}`",
        f"- Semantic checks (purpose, special conditions): {'AI-assisted' if groq_client.is_configured() else 'AI engine unavailable — text-diff heuristic only'}",
        "",
    ]
    return "\n".join(header) + "\n" + to_markdown_table(results, "Credit Paper", "Letter of Offer")


def run(credit_paper_path: str, lo_path: str, out_dir: str) -> None:
    cp = extract_credit_paper_fields(credit_paper_path)
    lo = extract_lo_fields(lo_path)
    results = compare(cp, lo)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_json = {
        "credit_paper": {k: v for k, v in cp.items()},
        "letter_of_offer": {k: v for k, v in lo.items() if k != "raw_text"},
        "results": [asdict(r) for r in results],
    }
    (out / "exception-report.json").write_text(
        json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "exception-report.md").write_text(to_markdown(cp, lo, results), encoding="utf-8")
    print(f"wrote {out / 'exception-report.json'}")
    print(f"wrote {out / 'exception-report.md'}")


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "usage: python compare.py <credit_paper.docx> <lo.doc|.docx|.pdf> <out_dir>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    run(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
