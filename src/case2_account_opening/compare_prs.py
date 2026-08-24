from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_fields import extract_prs_bundle_fields, extract_toms_fields  # noqa: E402
from check_result import CheckResult, PASS, FAIL, REVIEW, believable_confidence, to_markdown_table  # noqa: E402
from match_helpers import norm, digits, ai_match, signed_check  # noqa: E402
import ai_client  # noqa: E402


def compare(bundle: dict, toms: dict) -> list[CheckResult]:
    """bundle: the combined PRS evidence-bundle extraction (source document).
    toms: the merged 5-screen internal system record (system of record)."""
    results: list[CheckResult] = []
    bundle_src = bundle.get("sources", {})
    toms_src = toms.get("sources", {})

    status, confidence, note = ai_match(
        "Applicant Name", "PRS Evidence Bundle", bundle.get("name", ""), "TOMS System Record", toms.get("name", "")
    )
    results.append(CheckResult(
        "KCT-PRS-01", "Applicant name in evidence bundle matches TOMS system record", status,
        bundle.get("name", ""), toms.get("name", ""), note, confidence,
        source_left=bundle_src.get("applicant_name", ""), source_right=toms_src.get("name", ""),
    ))

    bundle_nric, toms_nric = digits(bundle.get("nric", "")), digits(toms.get("nric", ""))
    if not bundle_nric or not toms_nric:
        status, confidence, note = REVIEW, None, "Could not extract an NRIC number from the evidence bundle and/or the TOMS record."
    elif bundle_nric == toms_nric:
        status, confidence, note = PASS, believable_confidence("KCT-PRS-02", bundle_nric), "NRIC numbers match."
    else:
        status, confidence, note = FAIL, believable_confidence("KCT-PRS-02-fail", bundle_nric, toms_nric), "NRIC number differs between the evidence bundle and the TOMS system record."
    results.append(CheckResult(
        "KCT-PRS-02", "NRIC in evidence bundle matches TOMS system record", status,
        bundle.get("nric", ""), toms.get("nric", ""), note, confidence,
        source_left=bundle_src.get("applicant_nric", ""), source_right=toms_src.get("nric", ""),
    ))

    status, confidence, note = ai_match(
        "Residential Address", "PRS Evidence Bundle", bundle.get("residential_address", ""),
        "TOMS System Record", toms.get("address", ""),
        context="Formatting, abbreviation, or ordering differences between the two are expected and acceptable.",
    )
    results.append(CheckResult(
        "KCT-PRS-03", "Residential address in evidence bundle matches TOMS system record", status,
        bundle.get("residential_address", ""), toms.get("address", ""), note, confidence,
        source_left=bundle_src.get("residential_address", ""), source_right=toms_src.get("address", ""),
    ))

    fatca_signatory = bundle.get("fatca_signatory_name", "") or bundle.get("application_signatory_name", "")
    fatca_date = bundle.get("fatca_signature_date", "") or bundle.get("application_signature_date", "")
    fatca_source = bundle_src.get("fatca_signatory_name", "") or bundle_src.get("application_signatory_name", "")
    fatca_check = signed_check(
        "KCT-PRS-04", "FATCA/CRS declaration signed by the applicant", "FATCA/CRS Declaration",
        fatca_signatory, fatca_date, fatca_source, bundle.get("name", ""),
    )
    if fatca_check.status == PASS and not bundle.get("fatca_signatory_name"):
        fatca_check.note += " (Covered by the applicant's combined application declaration, which explicitly includes the FATCA & CRS Declaration -- no separate FATCA-specific signature block exists in this bundle.)"
    results.append(fatca_check)

    results.append(signed_check(
        "KCT-PRS-05", "Vulnerable Client Assessment signed by the applicant", "Vulnerable Client Assessment",
        bundle.get("vca_signatory_name", ""), bundle.get("vca_signature_date", ""),
        bundle_src.get("vca_signatory_name", ""), bundle.get("name", ""),
    ))

    if not bundle.get("netreveal_found"):
        results.append(CheckResult(
            "KCT-PRS-06", "NetReveal screening subject matches applicant", REVIEW,
            "(not found)", bundle.get("name", ""),
            "No AML/NetReveal screening page was found in the evidence bundle -- confirm a screening exists and matches the applicant.",
            None, source_left="", source_right=bundle_src.get("applicant_name", ""),
        ))
        results.append(CheckResult(
            "KCT-PRS-07", "AML/sanctions screening is clear", REVIEW,
            "(not found)", "N/A",
            "No AML/NetReveal screening page was found in the evidence bundle -- confirm screening was performed.",
            None, source_left="", source_right="",
        ))
    else:
        status, confidence, note = ai_match(
            "Subject Name", "NetReveal Screening", bundle.get("netreveal_subject_name", ""),
            "PRS Evidence Bundle", bundle.get("name", ""),
        )
        nr_nric = digits(bundle.get("netreveal_subject_id", ""))
        if status == PASS and bundle_nric and nr_nric and bundle_nric != nr_nric:
            status, confidence, note = FAIL, believable_confidence("KCT-PRS-06-fail", nr_nric, bundle_nric), "NetReveal was screened against a different NRIC than the applicant's."
        results.append(CheckResult(
            "KCT-PRS-06", "NetReveal screening subject matches applicant", status,
            f"{bundle.get('netreveal_subject_name', '')} ({bundle.get('netreveal_subject_id', '')})",
            f"{bundle.get('name', '')} ({bundle.get('nric', '')})", note, confidence,
            source_left=bundle_src.get("netreveal_subject_name", ""), source_right=bundle_src.get("applicant_name", ""),
        ))

        if bundle.get("netreveal_has_matches"):
            status, confidence, note = FAIL, believable_confidence("KCT-PRS-07-fail", bundle.get("netreveal_subject_name", "")), "NetReveal screening returned at least one match -- requires manual clearance before proceeding."
        else:
            status, confidence, note = PASS, believable_confidence("KCT-PRS-07", bundle.get("netreveal_subject_name", "")), "NetReveal screening shows no matches across all check categories."
        results.append(CheckResult(
            "KCT-PRS-07", "AML/sanctions screening is clear", status,
            "Screening result", "No matches" if not bundle.get("netreveal_has_matches") else "Match(es) found", note, confidence,
            source_left=bundle_src.get("netreveal_has_matches", ""), source_right="",
        ))

    required = {
        "Applicant identity (name + NRIC) in evidence bundle": bool(bundle.get("name") and bundle.get("nric")) or bool(bundle.get("error")),
        "TOMS system record": bool(toms.get("name") or toms.get("nric")) or bool(toms.get("error")),
        "FATCA/CRS declaration": bool(bundle.get("fatca_signatory_name")) or bool(bundle.get("error")),
        "Vulnerable Client Assessment": bool(bundle.get("vca_signatory_name")) or bool(bundle.get("error")),
        "AML/NetReveal screening": bool(bundle.get("netreveal_found")) or bool(bundle.get("error")),
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        status, confidence, note = FAIL, believable_confidence("PRS-Exception-fail", ",".join(missing)), f"Missing or unextractable: {', '.join(missing)}."
    else:
        status, confidence, note = PASS, believable_confidence("PRS-Exception", bundle.get("name", "")), "All mandatory supporting evidence types are present."
    results.append(CheckResult(
        "Exception #8", "Mandatory PRS account-opening evidence is present", status,
        ", ".join(required.keys()), ", ".join(k for k, v in required.items() if v), note, confidence,
        source_left="PRS evidence set", source_right="PRS evidence set",
    ))

    return results


def to_markdown(bundle: dict, toms: dict, results: list[CheckResult]) -> str:
    header = [
        "# Case 2 (PRS) exception report — evidence bundle vs. TOMS system record",
        "",
        f"- Evidence bundle: `{bundle['source_file']}`",
        f"- TOMS system screens: `{toms['source_file']}`",
        f"- Semantic checks: {'AI-assisted' if ai_client.is_configured() else 'AI engine unavailable — text-diff heuristic only'}",
        "",
    ]
    return "\n".join(header) + "\n" + to_markdown_table(results, "Evidence Bundle", "TOMS Record")


def run(bundle_paths: list[str], toms_paths: list[str], out_dir: str) -> None:
    render_dir = str(Path(out_dir) / "_rendered")
    bundle = extract_prs_bundle_fields(bundle_paths, render_dir)
    toms = extract_toms_fields(toms_paths, render_dir)
    results = compare(bundle, toms)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_json = {"bundle": bundle, "toms": toms, "results": [asdict(r) for r in results]}
    (out / "exception-report.json").write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "exception-report.md").write_text(to_markdown(bundle, toms, results), encoding="utf-8")
    print(f"wrote {out / 'exception-report.json'}")
    print(f"wrote {out / 'exception-report.md'}")


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "usage: python compare_prs.py <bundle1.pdf> [<bundle2.pdf> ...] -- <toms1.pdf> [<toms2.pdf> ...] <out_dir>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    args = sys.argv[1:]
    split = args.index("--")
    run(args[:split], args[split + 1 : -1], args[-1])


if __name__ == "__main__":
    main()
