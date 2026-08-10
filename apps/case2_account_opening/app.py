import json as _json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))
sys.path.insert(0, str(REPO_ROOT / "src" / "case2_account_opening"))

import groq_client  # noqa: E402
import ui_components as ui  # noqa: E402
from extract_fields import (  # noqa: E402
    extract_cls_fields,
    extract_email_fields,
    extract_ssm_fields,
    extract_ccris_application_fields,
    extract_guarantor_application_fields,
)
from compare import compare, to_markdown, PASS, FAIL, REVIEW, NA  # noqa: E402

st.set_page_config(
    page_title="AmBank KCT Intelligence · Account Opening",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

SAMPLE_DIR = REPO_ROOT / "samples" / "case-2-account-opening" / "xyz-sdn-bhd"
SAMPLE_FILES = {
    "cls": SAMPLE_DIR / "XYZ Sdn Bhd - CLS Extract.pdf",
    "email": SAMPLE_DIR / "XYZ Sdn Bhd - Email Request.pdf",
    "ssm": SAMPLE_DIR / "XYZ Sdn Bhd - SSM Search.pdf",
    "ccris_app": SAMPLE_DIR / "XYZ Sdn Bhd - CCRIS Application Form.pdf",
    "guarantor_app": SAMPLE_DIR / "XYZ Sdn Bhd - Guarantor Application Form.pdf",
}


def render_sidebar() -> str:
    ui.sidebar_logo(
        app_name="AmBank KCT Intelligence",
        tagline="Account Opening Module",
        assets_dir=APP_DIR / "assets",
        monogram="AK",
    )
    with st.sidebar:
        st.markdown('<div class="sb-section-label">Navigate</div>', unsafe_allow_html=True)
        page = st.radio(
            "Navigation",
            ["Control Testing", "Exception Catalogue", "Control Scope"],
            label_visibility="collapsed",
        )
    ui.sidebar_groq_status(groq_client.status())
    ui.sidebar_module_indicator([("Credit Facilities", False), ("Account Opening (CIF)", True)])
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
    ui.breadcrumb("AmBank Internal Audit", "Account Opening", "Control Testing")
    ui.page_header(
        "CLS/CCRIS vs. Supporting Documents",
        "Automated KCT-00001–00009 control testing: extracts customer, guarantor "
        "and facility data from the CIF creation document set and reconciles CLS/"
        "CCRIS system records against the supporting evidence, with confidence "
        "scoring and full source attribution.",
    )

    if not groq_client.is_configured():
        st.warning(
            "AI engine not configured. Three of these five documents are scanned "
            "images with no text layer (SSM search, CCRIS application form, "
            "guarantor application form) and the email evidence is a screenshot "
            "too — all four require the vision model to read. Set GROQ_API_KEY_1 "
            "(and optionally GROQ_API_KEY_2) in `.env` to enable full extraction. "
            "Only the CLS extract can be read without it."
        )

    use_sample = st.checkbox("Use committed reference sample (XYZ Sdn Bhd)", value=all(p.exists() for p in SAMPLE_FILES.values()))

    paths = {}
    if use_sample:
        if all(p.exists() for p in SAMPLE_FILES.values()):
            paths = {k: str(v) for k, v in SAMPLE_FILES.items()}
            st.caption("Using the committed reference document set.")
        else:
            st.warning("Sample files not found in samples/case-2-account-opening/xyz-sdn-bhd/.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            cls_upload = st.file_uploader("CLS Extract (.pdf)", type=["pdf"])
            ssm_upload = st.file_uploader("SSM Search (.pdf)", type=["pdf"])
            ccris_upload = st.file_uploader("CCRIS Application Form (.pdf)", type=["pdf"])
        with col2:
            guarantor_upload = st.file_uploader("Guarantor Application Form (.pdf)", type=["pdf"])
            email_upload = st.file_uploader("Email Request (.pdf)", type=["pdf"])
        uploads = {
            "cls": cls_upload, "ssm": ssm_upload, "ccris_app": ccris_upload,
            "guarantor_app": guarantor_upload, "email": email_upload,
        }
        for key, upload in uploads.items():
            if upload:
                paths[key] = _save_upload(upload, ".pdf")

    if len(paths) < 5:
        st.info("Provide all five documents (or use the reference sample) to run control testing.")
        return

    if st.button("Run Control Testing", type="primary"):
        render_dir = tempfile.mkdtemp(prefix="case2_render_")
        with st.spinner("Extracting fields (vision model for scanned documents) and reconciling..."):
            try:
                cls = extract_cls_fields(paths["cls"])
                email = extract_email_fields(paths["email"], render_dir)
                ssm = extract_ssm_fields(paths["ssm"], render_dir)
                ccris_app = extract_ccris_application_fields(paths["ccris_app"], render_dir)
                guarantor_app = extract_guarantor_application_fields(paths["guarantor_app"], render_dir)
                results = compare(cls, email, ssm, ccris_app, guarantor_app)
            except Exception as exc:
                st.error(f"Extraction/comparison failed: {exc}")
                return
        st.session_state["case2_results"] = (cls, email, ssm, ccris_app, guarantor_app, results)

    if "case2_results" not in st.session_state:
        return

    cls, email, ssm, ccris_app, guarantor_app, results = st.session_state["case2_results"]
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, REVIEW, NA)}

    ui.section_header("Result Summary")
    ui.stat_strip([
        ("Pass", str(counts[PASS])),
        ("Fail", str(counts[FAIL])),
        ("Review", str(counts[REVIEW])),
        ("N/A", str(counts[NA])),
    ])

    ui.section_header("Control Checklist")
    st.caption("Select a row to view full evidence, sourcing and reasoning for that control.")
    idx = ui.results_grid(results, key="case2_grid")

    if idx is not None:
        ui.detail_panel(results[idx], "Value A", "Value B")
    else:
        ui.empty_panel("No results to display.")

    ui.section_header("Export")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download Markdown report",
            to_markdown(cls, email, ssm, ccris_app, guarantor_app, results),
            file_name="case2-exception-report.md",
        )
    with col2:
        st.download_button(
            "Download JSON report",
            _json.dumps(
                {
                    "cls": cls, "email": email, "ssm": ssm,
                    "ccris_application": ccris_app, "guarantor_application": guarantor_app,
                    "results": [asdict(r) for r in results],
                },
                indent=2, ensure_ascii=False, default=str,
            ),
            file_name="case2-exception-report.json",
        )

    with st.expander("Raw extracted fields — CLS"):
        ui.render_json(cls)
    with st.expander("Raw extracted fields — SSM"):
        ui.render_json(ssm)
    with st.expander("Raw extracted fields — CCRIS Application Form"):
        ui.render_json(ccris_app)
    with st.expander("Raw extracted fields — Guarantor Application Form"):
        ui.render_json(guarantor_app)
    with st.expander("Raw extracted fields — Email Request"):
        ui.render_json(email)


def page_exception_catalogue() -> None:
    ui.breadcrumb("AmBank Internal Audit", "Account Opening", "Exception Catalogue")
    ui.page_header(
        "Exception Catalogue",
        "The nine control exceptions this module screens for. Source: docs/poc-scope.md.",
    )
    exceptions = [
        ("1", "Customer name in CLS differs from Application Form / SSM", "KCT-00001"),
        ("2", "Company registration number incorrectly keyed in CLS", "KCT-00002"),
        ("3", "Registered address differs from SSM records", "KCT-00003"),
        ("4", "Business nature / industry information incorrectly captured", "KCT-00004"),
        ("5", "Director information differs from Application Form or SSM", "KCT-00005"),
        ("6", "Guarantor information differs from Guarantor Form", "KCT-00006"),
        ("7", "CCRIS information does not match CCRIS Form", "KCT-00007"),
        ("8", "Mandatory CIF supporting documents are missing", "KCT-00008"),
        ("9", "CIF approved without sufficient Maker-Checker verification evidence", "KCT-00009"),
    ]
    import pandas as pd

    df = pd.DataFrame(exceptions, columns=["No.", "Exception", "KCT Reference"])
    st.dataframe(df, hide_index=True, width="stretch")


def page_about() -> None:
    ui.breadcrumb("AmBank Internal Audit", "Account Opening", "Control Scope")
    ui.page_header(
        "Control Scope",
        "Purpose and boundaries of the Account Opening (CIF) control testing module.",
    )
    st.markdown(
        """
        Customer Information File (CIF) creation is a critical onboarding
        process. Prior reviews identified inaccuracies, omissions, and
        inconsistencies between customer information entered into CLS/CCRIS
        and the supporting documents provided by the Relationship Manager.
        This module automates that verification.

        Three of the five source documents are scanned images (SSM search,
        CCRIS application form, guarantor application form) and the email
        evidence is a screenshot too — all four are read with a vision model
        rather than a text layer. Every result names the exact document and
        page it was sourced from.
        """
    )


def main() -> None:
    ui.inject_css()
    page = render_sidebar()
    if page == "Control Testing":
        page_run_comparison()
    elif page == "Exception Catalogue":
        page_exception_catalogue()
    else:
        page_about()


if __name__ == "__main__":
    main()
