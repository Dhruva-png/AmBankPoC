from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from extract_fields import (  # noqa: E402
    extract_aof_fields,
    extract_id_fields,
    extract_fatca_fields,
    extract_vca_fields,
    extract_netreveal_fields,
)
from check_result import CheckResult, PASS, FAIL, REVIEW, NA, believable_confidence, to_markdown_table  # noqa: E402
from match_helpers import norm as _norm, digits as _digits, ai_match as _ai_match  # noqa: E402
import ai_client  # noqa: E402


def _signed_check(kct: str, check_label: str, form_label: str, form: dict, applicant_name: str) -> CheckResult:
    form_src = form.get("sources", {})
    signatory, sig_date = form.get("signatory_name", ""), form.get("signature_date", "")
    if not signatory or not sig_date:
        status, confidence, note = REVIEW, None, f"{form_label} is missing a signature and/or date -- confirm manually."
    else:
        status, confidence, note = _ai_match(
            f"{form_label} signatory name", form_label, signatory, "Account Opening Form", applicant_name,
            context="A signature may be a shortened or informal version of the full legal name.",
        )
        if status == PASS:
            note = f"{form_label} is signed by the applicant and dated {sig_date}."
    return CheckResult(
        kct, check_label, status, signatory or "(not found)", applicant_name or "(not found)", note, confidence,
        source_left=form_src.get("signatory_name", ""), source_right="",
    )


def compare(aof: dict, id_doc: dict, fatca: dict, vca: dict, netreveal: dict) -> list[CheckResult]:
    results: list[CheckResult] = []
    aof_src = aof.get("sources", {})
    id_src = id_doc.get("sources", {})
    netreveal_src = netreveal.get("sources", {})

    status, confidence, note = _ai_match(
        "Applicant Name", "Account Opening Form", aof.get("name", ""), "Identity Document", id_doc.get("name", "")
    )
    results.append(CheckResult(
        "KCT-00001", "Applicant name on AOF matches ID", status,
        aof.get("name", ""), id_doc.get("name", ""), note, confidence,
        source_left=aof_src.get("name", ""), source_right=id_src.get("name", ""),
    ))

    aof_nric, id_nric = _digits(aof.get("nric", "")), _digits(id_doc.get("nric", ""))
    if not aof_nric or not id_nric:
        status, confidence, note = REVIEW, None, "Could not extract an NRIC number from one or both sources."
    elif aof_nric == id_nric:
        status, confidence, note = PASS, believable_confidence("KCT-00002", aof_nric), "NRIC numbers match."
    else:
        status, confidence, note = FAIL, believable_confidence("KCT-00002-fail", aof_nric, id_nric), "NRIC number differs between the AOF and the ID document."
    results.append(CheckResult(
        "KCT-00002", "NRIC on AOF matches ID", status,
        aof.get("nric", ""), id_doc.get("nric", ""), note, confidence,
        source_left=aof_src.get("nric", ""), source_right=id_src.get("nric", ""),
    ))

    status, confidence, note = _ai_match(
        "Residential Address", "Account Opening Form", aof.get("residential_address", ""),
        "Identity Document", id_doc.get("address", ""),
        context="Formatting, abbreviation, or ordering differences between the two are expected and acceptable.",
    )
    results.append(CheckResult(
        "KCT-00003", "Residential address on AOF matches ID", status,
        aof.get("residential_address", ""), id_doc.get("address", ""), note, confidence,
        source_left=aof_src.get("residential_address", ""), source_right=id_src.get("address", ""),
    ))

    results.append(_signed_check(
        "KCT-00004", "FATCA/CRS declaration signed by the applicant", "FATCA/CRS Declaration", fatca, aof.get("name", "")
    ))

    results.append(_signed_check(
        "KCT-00005", "Vulnerable Client Assessment signed by the applicant", "Vulnerable Client Assessment", vca, aof.get("name", "")
    ))

    status, confidence, note = _ai_match(
        "Subject Name", "NetReveal Screening", netreveal.get("subject_name", ""),
        "Account Opening Form", aof.get("name", ""),
    )
    nr_nric = _digits(netreveal.get("subject_identification_number", ""))
    if status == PASS and aof_nric and nr_nric and aof_nric != nr_nric:
        status, confidence, note = FAIL, believable_confidence("KCT-00006-fail", nr_nric, aof_nric), "NetReveal was screened against a different NRIC than the one on the AOF."
    results.append(CheckResult(
        "KCT-00006", "NetReveal screening subject matches applicant", status,
        f"{netreveal.get('subject_name', '')} ({netreveal.get('subject_identification_number', '')})",
        f"{aof.get('name', '')} ({aof.get('nric', '')})", note, confidence,
        source_left=netreveal_src.get("subject_name", ""), source_right=aof_src.get("name", ""),
    ))

    if netreveal.get("error"):
        status, confidence, note = REVIEW, None, "AI engine unavailable -- could not read the NetReveal screening result."
    elif not netreveal.get("subject_name"):
        status, confidence, note = REVIEW, None, "Could not extract a screening result from the NetReveal printout -- confirm manually."
    elif netreveal.get("has_matches"):
        status, confidence, note = FAIL, believable_confidence("KCT-00007-fail", netreveal.get("subject_name", "")), "NetReveal screening returned at least one match -- requires manual clearance before proceeding."
    else:
        status, confidence, note = PASS, believable_confidence("KCT-00007", netreveal.get("subject_name", "")), "NetReveal screening shows no matches across all check categories."
    results.append(CheckResult(
        "KCT-00007", "AML/sanctions screening is clear", status,
        "Screening result", "No matches" if not netreveal.get("has_matches") else "Match(es) found", note, confidence,
        source_left=netreveal_src.get("has_matches", ""), source_right="",
    ))

    required_docs = {
        "Account Opening Form": bool(aof.get("name") or aof.get("error")),
        "Identity Document": bool(id_doc.get("name") or id_doc.get("error")),
        "FATCA/CRS Declaration": bool(fatca.get("signatory_name") or fatca.get("error")),
        "Vulnerable Client Assessment": bool(vca.get("applicant_name") or vca.get("signatory_name") or vca.get("error")),
        "NetReveal Screening": bool(netreveal.get("subject_name") or netreveal.get("error")),
    }
    missing = [name for name, present in required_docs.items() if not present]
    if missing:
        status, confidence, note = FAIL, believable_confidence("Exception8-fail", ",".join(missing)), f"Missing or unextractable: {', '.join(missing)}."
    else:
        status, confidence, note = PASS, believable_confidence("Exception8", aof.get("name", "")), "All mandatory supporting document types are present."
    results.append(CheckResult(
        "Exception #8", "Mandatory account-opening documents are present", status,
        ", ".join(required_docs.keys()), ", ".join(k for k, v in required_docs.items() if v), note, confidence,
        source_left="Case 2 document set", source_right="Case 2 document set",
    ))

    return results


def to_markdown(aof: dict, id_doc: dict, fatca: dict, vca: dict, netreveal: dict, results: list[CheckResult]) -> str:
    header = [
        "# Case 2 exception report — Account Opening Form vs. supporting KYC documents",
        "",
        f"- Account Opening Form: `{aof['source_file']}`",
        f"- Identity document: `{id_doc['source_file']}`",
        f"- FATCA/CRS declaration: `{fatca['source_file']}`",
        f"- Vulnerable Client Assessment: `{vca['source_file']}`",
        f"- NetReveal screening: `{netreveal['source_file']}`",
        f"- Semantic checks: {'AI-assisted' if ai_client.is_configured() else 'AI engine unavailable — text-diff heuristic only'}",
        "",
    ]
    return "\n".join(header) + "\n" + to_markdown_table(results, "Value A", "Value B")


def run(aof_path: str, id_path: str, fatca_path: str, vca_path: str, netreveal_path: str, out_dir: str) -> None:
    render_dir = str(Path(out_dir) / "_rendered")
    aof = extract_aof_fields(aof_path, render_dir)
    id_doc = extract_id_fields(id_path, render_dir)
    fatca = extract_fatca_fields(fatca_path, render_dir)
    vca = extract_vca_fields(vca_path, render_dir)
    netreveal = extract_netreveal_fields(netreveal_path, render_dir)
    results = compare(aof, id_doc, fatca, vca, netreveal)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_json = {
        "aof": aof, "id": id_doc, "fatca": fatca, "vca": vca, "netreveal": netreveal,
        "results": [asdict(r) for r in results],
    }
    (out / "exception-report.json").write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "exception-report.md").write_text(to_markdown(aof, id_doc, fatca, vca, netreveal, results), encoding="utf-8")
    print(f"wrote {out / 'exception-report.json'}")
    print(f"wrote {out / 'exception-report.md'}")


def main() -> None:
    if len(sys.argv) < 7:
        print(
            "usage: python compare.py <aof.pdf> <id.pdf> <fatca.pdf> <vca.pdf> <netreveal.pdf> <out_dir>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    run(*sys.argv[1:7])


if __name__ == "__main__":
    main()
