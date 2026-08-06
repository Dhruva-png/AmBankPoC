import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))
sys.path.insert(0, str(REPO_ROOT / "src" / "case1_credit_facilities"))

import groq_client  # noqa: E402
import ui_components as ui  # noqa: E402
from extract_fields import extract_credit_paper_fields, extract_lo_fields  # noqa: E402
from compare import compare, to_markdown, PASS, FAIL, REVIEW, NA  # noqa: E402

st.set_page_config(
    page_title="AmBank POC · Case 1 — Credit Facilities",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

SAMPLE_DIR = REPO_ROOT / "samples" / "case-1-credit-facilities" / "hadyan-sdn-bhd"
SAMPLE_CP = SAMPLE_DIR / "Credit Paper - AR2025 - Hadyan Sdn Bhd.docx"
SAMPLE_LO = SAMPLE_DIR / "Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc"


def render_sidebar() -> str:
    ui.sidebar_logo(
        app_name="AmBank KCT AI",
        tagline="Case 1 · Credit Facilities",
        assets_dir=APP_DIR / "assets",
        monogram="C1",
    )
    with st.sidebar:
        page = st.radio(
            "Navigation",
            ["Run Comparison", "Exception Catalogue", "About This POC"],
            label_visibility="collapsed",
        )
        st.markdown('<hr style="border-top:1px solid rgba(255,255,255,0.12);margin:0.75rem 0;">', unsafe_allow_html=True)
    ui.sidebar_groq_status(groq_client.status())
    with st.sidebar:
        st.markdown(
            '<div style="font-size:0.65rem;color:rgba(255,255,255,0.35);margin-top:1.5rem;text-align:center;">'
            "AmBank Internal Audit POC · Case 1 v1.0</div>",
            unsafe_allow_html=True,
        )
    return page


def _save_upload(uploaded_file, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def page_run_comparison() -> None:
    ui.page_hero(
        "Case 1 · Credit Facilities",
        "Letter of Offer vs. Credit Paper — Exception Checker",
        "Upload an approved Credit Paper and the corresponding issued Letter of "
        "Offer. The tool extracts the KCT-relevant fields from each, runs the "
        "Case 1 exception checks (facility amount, purpose, pricing, tenure, "
        "special conditions, customer details, letterhead), and reports every "
        "result with a confidence score and the exact source it was read from.",
    )

    use_sample = st.checkbox("Use the committed Hadyan Sdn Bhd sample instead of uploading", value=not groq_client.is_configured() and SAMPLE_CP.exists())

    cp_path = lo_path = None
    if use_sample:
        if SAMPLE_CP.exists() and SAMPLE_LO.exists():
            cp_path, lo_path = str(SAMPLE_CP), str(SAMPLE_LO)
            st.caption(f"Using sample: `{SAMPLE_CP.name}` + `{SAMPLE_LO.name}`")
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
        st.info("Provide both documents (or use the sample) to run the comparison.")
        return

    if st.button("Run Comparison", type="primary"):
        with st.spinner("Extracting fields and comparing against the Credit Paper..."):
            try:
                cp = extract_credit_paper_fields(cp_path)
                lo = extract_lo_fields(lo_path)
                results = compare(cp, lo)
            except Exception as exc:
                st.error(f"Extraction/comparison failed: {exc}")
                return
        st.session_state["case1_results"] = (cp, lo, results)

    if "case1_results" not in st.session_state:
        return

    cp, lo, results = st.session_state["case1_results"]
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, REVIEW, NA)}

    ui.section_header("Summary")
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("Pass", counts[PASS]), ("Fail", counts[FAIL]), ("Review", counts[REVIEW]), ("N/A", counts[NA])]):
        with col:
            st.markdown(ui.metric_card(label, str(value)), unsafe_allow_html=True)

    ui.section_header("Exception Checklist")
    for r in results:
        with st.container():
            st.markdown(
                f"""<div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                    <div style="font-weight:700;color:var(--text-heading);">{r.kct} — {r.check}</div>
                    <div>{ui.status_badge(r.status)} &nbsp; {ui.confidence_badge(r.confidence)}</div>
                </div>
                <div style="font-size:0.88rem;color:var(--text-body);margin-bottom:0.6rem;">{r.note}</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
                    <div>
                        <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:0.2rem;">Credit Paper</div>
                        <div style="font-size:0.85rem;">{r.left_value or '—'}</div>
                        <div style="margin-top:0.35rem;">{ui.source_tag(r.source_left) if r.source_left else ''}</div>
                    </div>
                    <div>
                        <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:0.2rem;">Letter of Offer</div>
                        <div style="font-size:0.85rem;">{r.right_value or '—'}</div>
                        <div style="margin-top:0.35rem;">{ui.source_tag(r.source_right) if r.source_right else ''}</div>
                    </div>
                </div>
                </div>""",
                unsafe_allow_html=True,
            )

    ui.section_header("Export")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download Markdown report",
            to_markdown(cp, lo, results),
            file_name="case1-exception-report.md",
        )
    with col2:
        import json as _json

        st.download_button(
            "Download JSON report",
            _json.dumps(
                {
                    "credit_paper": cp,
                    "letter_of_offer": {k: v for k, v in lo.items() if k != "raw_text"},
                    "results": [asdict(r) for r in results],
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            file_name="case1-exception-report.json",
        )

    with st.expander("Raw extracted fields (Credit Paper)"):
        ui.render_json({k: v for k, v in cp.items()})
    with st.expander("Raw extracted fields (Letter of Offer)"):
        ui.render_json({k: v for k, v in lo.items() if k != "raw_text"})


def page_exception_catalogue() -> None:
    ui.page_hero(
        "Case 1 · Credit Facilities",
        "Exception Catalogue & KCTs",
        "The nine exceptions this checker screens for, and the KCT each maps to. "
        "Source: docs/poc-scope.md, extracted from the POC scope deck.",
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
    ui.section_header("Exceptions")
    for num, desc, kct in exceptions:
        st.markdown(f"**#{num}** — {desc} &nbsp;·&nbsp; `{kct}`")


def page_about() -> None:
    ui.page_hero(
        "AmBank Internal Audit POC",
        "About This Proof of Concept",
        "Assessing whether AI can assist in identifying control breaches and "
        "exceptions during Letter of Offer preparation and review.",
    )
    st.markdown(
        """
        The Letter of Offer (LO) is a critical customer-facing document that
        formalizes approved credit facilities and terms. Recent testing
        identified several discrepancies between the approved Credit Paper and
        the issued LO, together with weaknesses in the Maker-Checker review
        process. This POC assesses whether AI can assist in identifying control
        breaches and exceptions during LO preparation and review.

        Deterministic checks (facility amount, customer details, letterhead)
        are matched exactly and always score 100% confidence. Judgement-based
        checks (purpose wording, special conditions) are sent to Groq for a
        semantic read with a self-reported confidence score and reasoning —
        every result also shows exactly which document and section it was
        sourced from.
        """
    )


def main() -> None:
    ui.inject_css()
    page = render_sidebar()
    if page == "Run Comparison":
        page_run_comparison()
    elif page == "Exception Catalogue":
        page_exception_catalogue()
    else:
        page_about()


if __name__ == "__main__":
    main()
