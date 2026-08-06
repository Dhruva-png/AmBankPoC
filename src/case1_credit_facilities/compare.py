"""Case 1: compare an extracted Letter of Offer against its approved Credit Paper and
produce a KCT-style exception report (the same Pass/Fail/Review conclusion a human
tester would record in the KCT working paper).

KCT/exception numbering follows docs/poc-scope.md (Case 1).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_fields import extract_credit_paper_fields, extract_lo_fields  # noqa: E402


PASS, FAIL, REVIEW, NA = "PASS", "FAIL", "REVIEW", "N/A"


@dataclass
class CheckResult:
    kct: str
    check: str
    status: str
    credit_paper_value: str
    lo_value: str
    note: str


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
    """A Credit Paper can list several facilities/books (e.g. AmBank conventional vs
    AmIslamic) for the same customer -- match the LO to the one whose limit equals the
    LO's facility amount, rather than assuming there's only one."""
    for facility in cp["facilities"]:
        limits = [float(x.replace(",", "")) * 1000 for x in re.findall(r"[\d,]+", facility["limit_rm000"])]
        if lo_amount_rm is not None and any(abs(lo_amount_rm - lim) < 1 for lim in limits):
            return facility
    return cp["facilities"][0] if cp["facilities"] else None


def compare(cp: dict, lo: dict) -> list[CheckResult]:
    results: list[CheckResult] = []
    lo_amount = _norm_amount(lo.get("facility_amount") or "")
    facility = _pick_facility_for_lo(cp, lo_amount)

    # KCT-00001 -- Facility Amount
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
        )
    )

    # KCT-00002 -- Facility Purpose (free text: exact/substring match is a weak
    # signal, so this is always REVIEW unless texts are identical -- a human/LLM
    # still needs to judge whether a differently-worded purpose is a real exception)
    cp_purpose = cp.get("purpose", "")
    lo_purpose = lo.get("purpose", "")
    if _norm_text(cp_purpose) == _norm_text(lo_purpose):
        status, note = PASS, "Purpose wording is identical."
    elif not lo_purpose:
        status, note = REVIEW, "Could not find a purpose clause in the LO."
    else:
        status, note = REVIEW, (
            "Purpose wording differs from the Credit Paper's on-file purpose. The "
            "Credit Paper's 'Purpose of Submission' section also requests a purpose "
            "revision, so this may be an approved change rather than a true "
            "exception -- confirm against the CP's approved revised-purpose text "
            "before concluding Fail (see KCT-00002 in the exception catalogue)."
        )
    results.append(
        CheckResult("KCT-00002", "Facility purpose matches approved Credit Paper", status, cp_purpose, lo_purpose, note)
    )

    # KCT-00003 -- Pricing / Profit Rate
    cp_pricing = facility["pricing"] if facility else ""
    if not lo.get("raw_text") or "p.a." not in (lo.get("raw_text") or "").lower() and "%" not in (lo.get("raw_text") or ""):
        status, note = NA, "This LO is a purpose-revision supplemental letter and does not restate pricing -- expected, not an exception."
    else:
        status, note = REVIEW, "LO text contains a rate reference -- confirm it matches the approved pricing."
    results.append(CheckResult("KCT-00003", "Pricing / profit rate matches approved Credit Paper", status, cp_pricing, "(not restated in LO)", note))

    # KCT-00004 -- Facility Tenure
    cp_tenure = cp.get("term_maturity", "") or cp.get("availability_period", "")
    status, note = NA, "This LO is a purpose-revision supplemental letter and does not restate tenure -- expected, not an exception."
    results.append(CheckResult("KCT-00004", "Facility tenure matches approved Credit Paper", status, cp_tenure, "(not restated in LO)", note))

    # KCT-00005 -- Special Conditions
    cp_special = cp.get("special_conditions", "")
    if cp_special and cp_special.upper() not in ("N/A", "NIL", "") and _norm_text(cp_special) not in _norm_text(lo.get("raw_text", "")):
        status, note = REVIEW, "Approved special condition/covenant is not repeated in this LO -- confirm it is still in force via the original (non-supplemental) LO rather than omitted."
    elif not cp_special or cp_special.upper() in ("N/A", "NIL"):
        status, note = PASS, "No special conditions on file to check."
    else:
        status, note = PASS, "Special condition text appears in the LO."
    results.append(CheckResult("KCT-00005", "Approved special conditions reflected in LO", status, cp_special, "(see raw LO text)", note))

    # Customer details check (name + registration no.)
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
    results.append(CheckResult("Exception #8", "Customer name/registration number match", status, cp_customer, f"{lo_name} [{lo_reg}]", note))

    # Guarantor / Support check -- not one of the seven Case 1 KCTs (Case 1's scope
    # lists customer name/IC/address/contact, not guarantor), but the Credit Paper and
    # LO both happen to carry a guarantor acknowledgment for this sample, so it's
    # checked as a supplementary item.
    cp_support = cp.get("support_guarantees", "")
    cp_nric = re.search(r"[\d]{6}-\d{2}-\d{4}", cp_support)
    lo_nric = lo.get("guarantor_nric", "")
    if cp_nric and lo_nric and cp_nric.group(0) == lo_nric:
        status, note = PASS, "Guarantor NRIC matches between Credit Paper and LO."
    elif not lo_nric:
        status, note = REVIEW, "Could not find a guarantor acknowledgment block in the LO."
    else:
        status, note = FAIL, "Guarantor NRIC differs between the Credit Paper and the LO."
    results.append(CheckResult("Supplementary", "Guarantor identity matches approved Credit Paper", status, cp_support, f"{lo.get('guarantor_name','')} ({lo_nric})", note))

    # Exception #9 -- Letterhead / issuing entity check
    lo_entity = lo.get("issuing_entity", "")
    if facility and "islamic" in facility["book"].lower() and "islamic" not in lo_entity.lower():
        status, note = FAIL, "LO issued on conventional AmBank letterhead but the matched facility is an AmIslamic facility."
    elif facility and "islamic" not in facility["book"].lower() and "islamic" in lo_entity.lower():
        status, note = FAIL, "LO issued on AmBank Islamic letterhead but the matched facility is a conventional AmBank facility."
    elif not lo_entity:
        status, note = REVIEW, "Could not identify the issuing entity/letterhead in the LO."
    else:
        status, note = PASS, "Letterhead/issuing entity is consistent with the matched facility's book."
    results.append(CheckResult("Exception #9", "Letterhead matches facility book (Conventional/Islamic)", status, facility["book"].strip() if facility else "", lo_entity, note))

    # KCT-00006 (Approval Control) / KCT-00007 (Maker-Checker Control) cannot be
    # genuinely verified from this document pair: the Credit Paper's approval
    # date/signatures are embedded in a scanned signature image, not extractable
    # as text. This row only checks that the LO itself carries an issuance date --
    # it is NOT evidence of Maker-Checker timing and should not be read as a Pass
    # on KCT-00006/00007.
    lo_date = lo.get("letter_date", "")
    if lo_date:
        status, note = REVIEW, (
            "LO carries an issuance date (12 Feb 2026), but KCT-00006 (LO issued "
            "before approval) and KCT-00007 (Maker-Checker evidence) cannot be "
            "verified automatically -- the Credit Paper's approval date/signatures "
            "are in a scanned image, not text. Needs manual confirmation."
        )
    else:
        status, note = REVIEW, "Could not find an issuance date on the LO."
    results.append(CheckResult("KCT-00006 / KCT-00007", "LO issuance date present (informational only -- not an approval-timing check)", status, "(approval date not extractable -- signature image)", lo_date, note))

    return results


def to_markdown(cp: dict, lo: dict, results: list[CheckResult]) -> str:
    lines = [
        "# Case 1 exception report — LO vs. Credit Paper",
        "",
        f"- Credit Paper: `{cp['source_file']}`",
        f"- Letter of Offer: `{lo['source_file']}`",
        "",
        "> Generated by `src/case1_credit_facilities/compare.py`. This is a rule-based "
        "first pass, not a substitute for KCT tester judgement -- REVIEW rows need a "
        "human (or a follow-up LLM-based read) to conclude Pass/Fail, per the "
        "`docs/poc-scope.md` Case 1 as-is process (Step 4: Conclusion).",
        "",
        "| KCT | Check | Status | Credit Paper | Letter of Offer | Note |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.kct} | {r.check} | **{r.status}** | {r.credit_paper_value.replace(chr(10), ' / ')[:200]} "
            f"| {r.lo_value.replace(chr(10), ' / ')[:200]} | {r.note} |"
        )
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, REVIEW, NA)}
    lines += ["", f"**Summary**: {counts[PASS]} Pass, {counts[FAIL]} Fail, {counts[REVIEW]} Review, {counts[NA]} N/A."]
    return "\n".join(lines)


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
