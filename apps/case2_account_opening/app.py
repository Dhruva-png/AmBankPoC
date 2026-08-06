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
    page_title="AmBank POC · Case 2 — Account Opening (CIF)",
    page_icon="🏦",
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
        app_name="AmBank KCT AI",
        tagline="Case 2 · Account Opening (CIF)",
        assets_dir=APP_DIR / "assets",
        monogram="C2",
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
            "AmBank Internal Audit POC · Case 2 v1.0</div>",
            unsafe_allow_html=True,
        )
    return page


def _save_upload(uploaded_file, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def page_run_comparison() -> None:
    ui.page_hero(
        "Case 2 · Account Opening (CIF)",
        "CLS/CCRIS vs. Supporting Documents — Exception Checker",
        "Upload the five CIF-creation documents (CLS extract, CCRIS screen/email "
        "evidence, SSM search, CCRIS application form, guarantor form). The tool "
        "extracts customer, guarantor and facility data from each — using Groq's "
        "vision model for the scanned forms — and cross-checks them against the "
        "Case 2 exception catalogue, with a confidence score and exact source for "
        "every result.",
    )

    if not groq_client.is_configured():
        st.warning(
            "Groq is not configured. Three of these five documents are scanned "
            "images with no text layer (SSM search, CCRIS application form, "
            "guarantor application form) and the email thread is a screenshot too "
            "— all four need Groq's vision model to read. Set GROQ_API_KEY_1 "
            "(and optionally GROQ_API_KEY_2) in `.env` to enable full extraction. "
            "Only the CLS extract can be read without it."
        )

    use_sample = st.checkbox("Use the committed XYZ Sdn Bhd sample instead of uploading", value=all(p.exists() for p in SAMPLE_FILES.values()))

    paths = {}
    if use_sample:
        if all(p.exists() for p in SAMPLE_FILES.values()):
            paths = {k: str(v) for k, v in SAMPLE_FILES.items()}
            st.caption("Using the committed sample document set.")
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
        st.info("Provide all five documents (or use the sample) to run the comparison.")
        return

    if st.button("Run Comparison", type="primary"):
        render_dir = tempfile.mkdtemp(prefix="case2_render_")
        with st.spinner("Extracting fields (Groq vision for scanned documents) and comparing..."):
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

    ui.section_header("Summary")
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("Pass", counts[PASS]), ("Fail", counts[FAIL]), ("Review", counts[REVIEW]), ("N/A", counts[NA])]):
        with col:
            st.markdown(ui.metric_card(label, str(value)), unsafe_allow_html=True)

    ui.section_header("Exception Checklist")
    for r in results:
        st.markdown(
            f"""<div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                <div style="font-weight:700;color:var(--text-heading);">{r.kct} — {r.check}</div>
                <div>{ui.status_badge(r.status)} &nbsp; {ui.confidence_badge(r.confidence)}</div>
            </div>
            <div style="font-size:0.88rem;color:var(--text-body);margin-bottom:0.6rem;">{r.note}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
                <div>
                    <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:0.2rem;">Value A</div>
                    <div style="font-size:0.85rem;">{r.left_value or '—'}</div>
                    <div style="margin-top:0.35rem;">{ui.source_tag(r.source_left) if r.source_left else ''}</div>
                </div>
                <div>
                    <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:0.2rem;">Value B</div>
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
            to_markdown(cls, email, ssm, ccris_app, guarantor_app, results),
            file_name="case2-exception-report.md",
        )
    with col2:
        import json as _json

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

    with st.expander("Raw extracted fields (CLS)"):
        ui.render_json(cls)
    with st.expander("Raw extracted fields (SSM)"):
        ui.render_json(ssm)
    with st.expander("Raw extracted fields (CCRIS Application Form)"):
        ui.render_json(ccris_app)
    with st.expander("Raw extracted fields (Guarantor Application Form)"):
        ui.render_json(guarantor_app)
    with st.expander("Raw extracted fields (Email Request)"):
        ui.render_json(email)


def page_exception_catalogue() -> None:
    ui.page_hero(
        "Case 2 · Account Opening (CIF)",
        "Exception Catalogue & KCTs",
        "The nine exceptions this checker screens for. Source: docs/poc-scope.md, "
        "extracted from the POC scope deck.",
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
    ui.section_header("Exceptions")
    for num, desc, kct in exceptions:
        st.markdown(f"**#{num}** — {desc} &nbsp;·&nbsp; `{kct}`")


def page_about() -> None:
    ui.page_hero(
        "AmBank Internal Audit POC",
        "About This Proof of Concept",
        "Assessing whether AI can assist in verifying customer information "
        "captured in CLS and CCRIS during CIF creation.",
    )
    st.markdown(
        """
        Customer Information File (CIF) creation is a critical onboarding
        process. Recent reviews identified inaccuracies, omissions, and
        inconsistencies between customer information entered into CLS/CCRIS
        and the supporting documents provided by the Relationship Manager.
        This POC assesses whether AI can help verify accuracy, completeness
        and consistency, and flag control gaps during CIF creation.

        Three of the five source documents in this case are scanned images
        (SSM search, CCRIS application form, guarantor application form) and
        the email evidence is a screenshot too — all four are read with
        Groq's vision model rather than a text layer. Every result shown
        here reports a confidence score and the exact document/page it was
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
