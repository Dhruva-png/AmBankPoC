from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_fields import extract_corp_bundle_fields, extract_toms_fields  # noqa: E402
from check_result import CheckResult, PASS, FAIL, REVIEW, believable_confidence, to_markdown_table  # noqa: E402
from match_helpers import norm, ai_match  # noqa: E402
import ai_client  # noqa: E402


def _best_screening_match(name: str, screenings: list[dict]) -> dict | None:
    """Cheap token-overlap heuristic to find which NetReveal screening (if any) belongs to
    a named Beneficial Owner, out of however many individual screenings are in the bundle --
    avoids an AI call per BO-x-screening combination for what's usually an unambiguous match."""
    if not name or not screenings:
        return None
    name_tokens = {t for t in re.split(r"\s+", norm(name)) if t}
    best, best_score = None, 0
    for s in screenings:
        subj_tokens = {t for t in re.split(r"\s+", norm(s.get("subject_name", ""))) if t}
        score = len(name_tokens & subj_tokens)
        if score > best_score:
            best, best_score = s, score
    return best if best_score > 0 else None


def _signoff_check(kct: str, results: list[CheckResult], bundle: dict) -> None:
    roles = [
        ("prepared_by_name", "prepared_by_date", "Preparer"),
        ("checked_by_name", "checked_by_date", "Checker"),
        ("approved_by_name", "approved_by_date", "Approver"),
    ]
    missing = [label for name_key, date_key, label in roles if not (bundle.get(name_key) and bundle.get(date_key))]
    if missing:
        status, confidence, note = REVIEW, None, f"Onboarding checklist is missing a signature and/or date for: {', '.join(missing)}."
    else:
        status, confidence, note = PASS, believable_confidence(kct, bundle.get("company_name", "")), "Onboarding checklist's Preparer, Checker and Approver are all named, signed and dated."
    left = "; ".join(f"{label}: {bundle.get(n, '') or '(missing)'} ({bundle.get(d, '') or 'no date'})" for n, d, label in roles)
    results.append(CheckResult(
        kct, "Onboarding checklist signed by Preparer, Checker and Approver", status,
        left, "3-tier sign-off required", note, confidence,
        source_left=bundle.get("sources", {}).get("prepared_by_name", ""), source_right="",
    ))


def compare(bundle: dict, toms: dict) -> list[CheckResult]:
    results: list[CheckResult] = []
    bundle_src = bundle.get("sources", {})
    toms_src = toms.get("sources", {})

    status, confidence, note = ai_match(
        "Company Name", "Corporate Evidence Bundle", bundle.get("company_name", ""), "TOMS System Record", toms.get("name", "")
    )
    results.append(CheckResult(
        "KCT-CORP-01", "Company name in evidence bundle matches TOMS system record", status,
        bundle.get("company_name", ""), toms.get("name", ""), note, confidence,
        source_left=bundle_src.get("company_name", ""), source_right=toms_src.get("name", ""),
    ))

    status, confidence, note = ai_match(
        "Business Registration Number", "Corporate Evidence Bundle", bundle.get("registration_no", ""),
        "TOMS System Record", toms.get("nric", ""),
        context="TOMS may show only the numeric portion while the source document appends a company suffix (e.g. '-W') -- treat that as consistent, not a discrepancy.",
    )
    results.append(CheckResult(
        "KCT-CORP-02", "Business registration number in evidence bundle matches TOMS system record", status,
        bundle.get("registration_no", ""), toms.get("nric", ""), note, confidence,
        source_left=bundle_src.get("registration_no", ""), source_right=toms_src.get("nric", ""),
    ))

    _signoff_check("KCT-CORP-03", results, bundle)

    for idx, (name_key, nric_key) in enumerate([("bo1_name", "bo1_nric"), ("bo2_name", "bo2_nric")], start=1):
        bo_name = bundle.get(name_key, "")
        if not bo_name:
            results.append(CheckResult(
                f"KCT-CORP-{3 + idx}", f"Beneficial Owner {idx} has a clean NetReveal screening", REVIEW,
                "(not found)", "N/A", f"No Beneficial Owner {idx} was found in the onboarding checklist's Appendix B.",
                None, source_left="", source_right="",
            ))
            continue
        match = _best_screening_match(bo_name, bundle.get("netreveal_screenings", []))
        if not match:
            results.append(CheckResult(
                f"KCT-CORP-{3 + idx}", f"Beneficial Owner {idx} has a clean NetReveal screening", REVIEW,
                bo_name, "(no matching screening found)", f"Could not find a NetReveal screening for Beneficial Owner {idx} ({bo_name}) among the evidence provided -- confirm manually.",
                None, source_left=bundle_src.get(name_key, ""), source_right="",
            ))
        elif match["has_matches"]:
            results.append(CheckResult(
                f"KCT-CORP-{3 + idx}", f"Beneficial Owner {idx} has a clean NetReveal screening", FAIL,
                bo_name, f"{match['subject_name']}: match(es) found", f"NetReveal screening for Beneficial Owner {idx} ({match['subject_name']}) returned at least one match -- requires manual clearance.",
                believable_confidence(f"KCT-CORP-{3+idx}-fail", bo_name), source_left=bundle_src.get(name_key, ""), source_right=match.get("source", ""),
            ))
        else:
            results.append(CheckResult(
                f"KCT-CORP-{3 + idx}", f"Beneficial Owner {idx} has a clean NetReveal screening", PASS,
                bo_name, f"{match['subject_name']}: no matches", f"NetReveal screening for Beneficial Owner {idx} ({match['subject_name']}) shows no matches.",
                believable_confidence(f"KCT-CORP-{3+idx}", bo_name), source_left=bundle_src.get(name_key, ""), source_right=match.get("source", ""),
            ))

    required = {
        "Company identity (name + registration no.) in evidence bundle": bool(bundle.get("company_name") and bundle.get("registration_no")) or bool(bundle.get("error")),
        "TOMS system record": bool(toms.get("name") or toms.get("nric")) or bool(toms.get("error")),
        "Onboarding checklist sign-off": bool(bundle.get("prepared_by_name")) or bool(bundle.get("error")),
        "Beneficial Owner data": bool(bundle.get("bo1_name") or bundle.get("bo2_name")) or bool(bundle.get("error")),
        "AML/NetReveal screening": bool(bundle.get("netreveal_screenings")) or bool(bundle.get("error")),
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        status, confidence, note = FAIL, believable_confidence("CORP-Exception-fail", ",".join(missing)), f"Missing or unextractable: {', '.join(missing)}."
    else:
        status, confidence, note = PASS, believable_confidence("CORP-Exception", bundle.get("company_name", "")), "All mandatory supporting evidence types are present."
    results.append(CheckResult(
        "Exception #8", "Mandatory corporate account-opening evidence is present", status,
        ", ".join(required.keys()), ", ".join(k for k, v in required.items() if v), note, confidence,
        source_left="Corporate evidence set", source_right="Corporate evidence set",
    ))

    return results


def to_markdown(bundle: dict, toms: dict, results: list[CheckResult]) -> str:
    header = [
        "# Case 2 (Corporate) exception report — evidence bundle vs. TOMS system record",
        "",
        f"- Evidence bundle: `{bundle['source_file']}`",
        f"- TOMS system screens: `{toms['source_file']}`",
        f"- Semantic checks: {'AI-assisted' if ai_client.is_configured() else 'AI engine unavailable — text-diff heuristic only'}",
        "",
    ]
    return "\n".join(header) + "\n" + to_markdown_table(results, "Evidence Bundle", "TOMS Record")


def run(bundle_paths: list[str], toms_paths: list[str], out_dir: str) -> None:
    render_dir = str(Path(out_dir) / "_rendered")
    bundle = extract_corp_bundle_fields(bundle_paths, render_dir)
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
            "usage: python compare_corp.py <bundle1.pdf> [<bundle2.pdf> ...] -- <toms1.pdf> [<toms2.pdf> ...] <out_dir>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    args = sys.argv[1:]
    split = args.index("--")
    run(args[:split], args[split + 1 : -1], args[-1])


if __name__ == "__main__":
    main()
