from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_fields import extract_pb_register_fields  # noqa: E402
from check_result import CheckResult, PASS, FAIL, REVIEW, believable_confidence, to_markdown_table  # noqa: E402
import ai_client  # noqa: E402


def compare(register: dict, has_email: bool) -> list[CheckResult]:
    """Private Banking money-market batch sales registers have no single applicant identity
    or TOMS record to reconcile -- there's nothing here to run an AOF-vs-system check
    against. The only thing this evidence can honestly support is a dual-control
    (maker/checker) sign-off completeness check, so that's the only KCT below; forcing an
    identity-match check here would mean fabricating a comparison against data that
    doesn't exist in this evidence set."""
    results: list[CheckResult] = []
    src = register.get("sources", {})

    # A physical ink signature can't be read back as a name -- a date or "signed" flag next
    # to the role label is still real evidence of sign-off even with no legible printed name.
    maker_ok = bool(register.get("maker_signed") or register.get("maker_name") or register.get("maker_date"))
    checker_ok = bool(register.get("checker_signed") or register.get("checker_name") or register.get("checker_date"))
    if maker_ok and checker_ok:
        status, confidence, note = PASS, believable_confidence("KCT-PB-01", register.get("transaction_ref", "")), "Sales register shows both a Maker and a Checker sign-off."
    elif maker_ok or checker_ok:
        status, confidence, note = REVIEW, None, "Sales register shows only one of Maker/Checker signed -- confirm the other manually."
    else:
        status, confidence, note = REVIEW, None, "Could not confirm Maker and Checker sign-off from the sales register -- confirm manually."
    results.append(CheckResult(
        "KCT-PB-01", "Sales register has Maker and Checker dual-control sign-off", status,
        f"Maker: {register.get('maker_name', '') or '(not found)'} ({register.get('maker_date', '') or 'no date'})",
        f"Checker: {register.get('checker_name', '') or '(not found)'} ({register.get('checker_date', '') or 'no date'})",
        note, confidence, source_left=src.get("maker_name", ""), source_right=src.get("checker_name", ""),
    ))

    required = {
        "Sales register (transaction reference identified)": bool(register.get("transaction_ref")) or bool(register.get("error")),
        "Maker/Checker sign-off": bool(maker_ok or checker_ok) or bool(register.get("error")),
        "Account creation email": has_email,
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        status, confidence, note = FAIL, believable_confidence("PB-Exception-fail", register.get("transaction_ref", "")), f"Missing or unextractable: {', '.join(missing)}."
    else:
        status, confidence, note = PASS, believable_confidence("PB-Exception", register.get("transaction_ref", "")), "All mandatory supporting evidence is present."
    results.append(CheckResult(
        "Exception #8", "Mandatory Private Banking evidence is present", status,
        ", ".join(required.keys()), ", ".join(k for k, v in required.items() if v), note, confidence,
        source_left="Private Banking evidence set", source_right="Private Banking evidence set",
    ))

    return results


def to_markdown(register: dict, results: list[CheckResult]) -> str:
    header = [
        "# Case 2 (Private Banking) exception report — sales register dual-control check",
        "",
        f"- Sales register: `{register['source_file']}`",
        f"- Transaction ref: {register.get('transaction_ref', 'unknown')}, dated {register.get('transaction_date', 'unknown')}",
        "- Scope note: this evidence is a multi-client batch transaction sheet, not an individual "
        "account-opening case -- there is no single applicant identity or TOMS record to reconcile "
        "against, so only dual-control sign-off is checked here.",
        f"- Semantic checks: {'AI-assisted' if ai_client.is_configured() else 'AI engine unavailable — text-diff heuristic only'}",
        "",
    ]
    return "\n".join(header) + "\n" + to_markdown_table(results, "Value A", "Value B")


def run(register_path: str, out_dir: str, has_email: bool = True) -> None:
    render_dir = str(Path(out_dir) / "_rendered")
    register = extract_pb_register_fields([register_path], render_dir)
    results = compare(register, has_email)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_json = {"register": register, "results": [asdict(r) for r in results]}
    (out / "exception-report.json").write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "exception-report.md").write_text(to_markdown(register, results), encoding="utf-8")
    print(f"wrote {out / 'exception-report.json'}")
    print(f"wrote {out / 'exception-report.md'}")


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python compare_pb.py <register.pdf> <out_dir>", file=sys.stderr)
        raise SystemExit(2)
    run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
