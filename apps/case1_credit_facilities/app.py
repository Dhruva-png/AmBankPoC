import json as _json
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))
sys.path.insert(0, str(REPO_ROOT / "src" / "case1_credit_facilities"))

import case_store  # noqa: E402
import excel_export  # noqa: E402
import groq_client  # noqa: E402
import shared_pages  # noqa: E402
import ui_components as ui  # noqa: E402
from extract_fields import extract_credit_paper_fields, extract_lo_fields  # noqa: E402
from compare import compare, to_markdown, PASS, FAIL, REVIEW, NA  # noqa: E402

st.set_page_config(
    page_title="AmBank KCT Intelligence · Credit Facilities",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

CASE_TYPE = "case1"
SAMPLE_DIR = REPO_ROOT / "samples" / "case-1-credit-facilities" / "hadyan-sdn-bhd"
SAMPLE_CP = SAMPLE_DIR / "Credit Paper - AR2025 - Hadyan Sdn Bhd.docx"
SAMPLE_LO = SAMPLE_DIR / "Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc"

NAV_PAGES = ["Control Testing", "Dashboard", "Case Manager", "Exception Catalogue", "Control Scope"]


def render_sidebar() -> str:
    ui.sidebar_logo(
        app_name="AmBank KCT Intelligence",
        tagline="Credit Facilities Module",
        assets_dir=APP_DIR / "assets",
        monogram="AK",
    )
    with st.sidebar:
        st.markdown('<div class="sb-section-label">Navigate</div>', unsafe_allow_html=True)
        page = st.radio("Navigation", NAV_PAGES, label_visibility="collapsed")
    ui.sidebar_groq_status(groq_client.status())
    ui.sidebar_module_indicator([("Credit Facilities", True), ("Account Opening (CIF)", False)])
    with st.sidebar:
        st.markdown(
            '<div style="font-size:0.65rem;color:#5B6272;margin-top:1.4rem;text-align:center;">'
            "AmBank Internal Audit &nbsp;·&nbsp; Build 1.0</div>",
            unsafe_allow_html=True,
        )
    return page


def _save_upload(uploaded_file, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def page_run_comparison() -> None:
    ui.breadcrumb("AmBank Internal Audit", "Credit Facilities", "Control Testing")
    ui.page_header(
        "Letter of Offer vs. Credit Paper",
        "Automated KCT-00001–00007 control testing: extracts facility terms from the "
        "approved Credit Paper and the issued Letter of Offer, then reconciles them "
        "field by field with confidence scoring and full source attribution.",
    )

    use_sample = st.checkbox("Use committed reference sample (Hadyan Sdn Bhd)", value=not groq_client.is_configured() and SAMPLE_CP.exists())

    cp_path = lo_path = None
    if use_sample:
        if SAMPLE_CP.exists() and SAMPLE_LO.exists():
            cp_path, lo_path = str(SAMPLE_CP), str(SAMPLE_LO)
            st.caption(f"Reference sample: `{SAMPLE_CP.name}` + `{SAMPLE_LO.name}`")
        else:
            st.warning("Sample files not found in samples/case-1-credit-facilities/hadyan-sdn-bhd/.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            cp_upload = st.file_uploader("Approved Credit Paper (.docx)", type=["docx"])
            if cp_upload:
                cp_path = _save_upload(cp_upload, ".docx")
        with col2:
            lo_upload = st.file_uploader("Issued Letter of Offer (.doc, .docx or .pdf)", type=["doc", "docx", "pdf"])
            if lo_upload:
                lo_path = _save_upload(lo_upload, Path(lo_upload.name).suffix)

    if not (cp_path and lo_path):
        st.info("Provide both documents (or use the reference sample) to run control testing.")
        return

    if st.button("Run Control Testing", type="primary"):
        started = time.time()
        with st.spinner("Extracting fields and reconciling against the Credit Paper..."):
            try:
                cp = extract_credit_paper_fields(cp_path)
                lo = extract_lo_fields(lo_path)
                results = compare(cp, lo)
            except Exception as exc:
                st.error(f"Extraction/comparison failed: {exc}")
                return
        with st.spinner("Generating AI remarks..."):
            remarks = groq_client.generate_case_remarks(results, f"Case 1 (Credit Facilities) — {cp.get('customer', 'Unknown Customer')}")
        elapsed = time.time() - started
        processed_at = datetime.now().isoformat(timespec="seconds")
        documents = [
            {"label": "Credit Paper", "filename": Path(cp_path).name},
            {"label": "Letter of Offer", "filename": Path(lo_path).name},
        ]
        case_id = case_store.save_case(CASE_TYPE, documents, results, elapsed, remarks)
        st.session_state["case1_results"] = (cp, lo, results, case_id, remarks, elapsed, documents, processed_at)

    if "case1_results" not in st.session_state:
        return

    cp, lo, results, case_id, remarks, elapsed, documents, processed_at = st.session_state["case1_results"]
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, REVIEW, NA)}

    ui.section_header("Result Summary")
    ui.stat_strip([
        ("Case ID", case_id),
        ("Pass", str(counts[PASS])),
        ("Fail", str(counts[FAIL])),
        ("Review", str(counts[REVIEW])),
        ("N/A", str(counts[NA])),
    ])

    ui.section_header("AI Remarks")
    st.markdown(f'<div class="detail-note">{remarks}</div>', unsafe_allow_html=True)

    ui.section_header("Control Checklist")
    st.caption("Select a row to view full evidence, sourcing and reasoning for that control.")
    idx = ui.results_grid(results, key="case1_grid")

    if idx is not None:
        ui.detail_panel(results[idx], "Credit Paper", "Letter of Offer")
    else:
        ui.empty_panel("No results to display.")

    ui.section_header("Export")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download Excel workbook",
            excel_export.build_workbook(
                case_meta={
                    "title": "Case 1 — Credit Facilities Control Testing Report",
                    "case_id": case_id,
                    "module": "Credit Facilities",
                    "processed_at": processed_at,
                    "processing_time": f"{elapsed:.1f}s",
                    "documents": ", ".join(d["filename"] for d in documents),
                    "overall_status": "FLAGGED" if (counts[FAIL] or counts[REVIEW]) else "CLEAR",
                    "ai_engine": "Groq" if groq_client.is_configured() else "Not configured",
                },
                results=results,
                remarks=remarks,
                left_label="Credit Paper",
                right_label="Letter of Offer",
            ),
            file_name=f"{case_id}-report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with col2:
        st.download_button(
            "Download Markdown report",
            to_markdown(cp, lo, results),
            file_name=f"{case_id}-report.md",
        )
    with col3:
        st.download_button(
            "Download JSON report",
            _json.dumps(
                {
                    "case_id": case_id,
                    "credit_paper": cp,
                    "letter_of_offer": {k: v for k, v in lo.items() if k != "raw_text"},
                    "results": [asdict(r) for r in results],
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            file_name=f"{case_id}-report.json",
        )

    with st.expander("Raw extracted fields — Credit Paper"):
        ui.render_json({k: v for k, v in cp.items()})
    with st.expander("Raw extracted fields — Letter of Offer"):
        ui.render_json({k: v for k, v in lo.items() if k != "raw_text"})


def page_exception_catalogue() -> None:
    ui.breadcrumb("AmBank Internal Audit", "Credit Facilities", "Exception Catalogue")
    ui.page_header(
        "Exception Catalogue",
        "The nine control exceptions this module screens for, mapped to their KCT reference. "
        "Source: docs/poc-scope.md.",
    )
    exceptions = [
        ("1", "Facility amount in LO differs from approved amount", "KCT-00001"),
        ("2", "Facility purpose differs from approved purpose", "KCT-00002"),
        ("3", "Pricing/Profit rate differs from approved rate", "KCT-00003"),
        ("4", "Tenure differs from approved tenure", "KCT-00004"),
        ("5", "Approved special conditions omitted from LO", "KCT-00005"),
        ("6", "LO issued before Maker-Checker approval completed", "KCT-00006"),
        ("7", "No evidence of Maker-Checker review and approval", "KCT-00007"),
        ("8", "Incorrect customer details in LO", "—"),
        ("9", "Wrong letterhead used (Conventional/Islamic)", "—"),
    ]
    df = pd.DataFrame(exceptions, columns=["No.", "Exception", "KCT Reference"])
    st.dataframe(df, hide_index=True, width="stretch")


def page_about() -> None:
    ui.breadcrumb("AmBank Internal Audit", "Credit Facilities", "Control Scope")
    ui.page_header(
        "Control Scope",
        "Purpose and boundaries of the Credit Facilities control testing module.",
    )
    st.markdown(
        """
        The Letter of Offer (LO) is a critical customer-facing document that
        formalizes approved credit facilities and terms. Prior manual testing
        identified discrepancies between the approved Credit Paper and the
        issued LO, along with weaknesses in the Maker-Checker review process.
        This module automates that reconciliation.

        Deterministic checks — facility amount, customer details, letterhead —
        are matched exactly and score 100% confidence. Judgement-based checks —
        purpose wording, special conditions — are routed through a language
        model for a semantic read, returned with a self-reported confidence
        score and reasoning. Every result names the exact document and section
        it was sourced from.
        """
    )


def main() -> None:
    ui.inject_css()
    page = render_sidebar()
    if page == "Control Testing":
        page_run_comparison()
    elif page == "Dashboard":
        shared_pages.render_dashboard(CASE_TYPE, "Credit Facilities")
    elif page == "Case Manager":
        shared_pages.render_case_manager(CASE_TYPE, "Credit Facilities", "Credit Paper", "Letter of Offer")
    elif page == "Exception Catalogue":
        page_exception_catalogue()
    else:
        page_about()


if __name__ == "__main__":
    main()
