import tempfile
import time
from pathlib import Path

import streamlit as st

import case_store
import groq_client
import shared_pages
from compare import compare, to_markdown
from extract_fields import (
    extract_ccris_application_fields,
    extract_cls_fields,
    extract_email_fields,
    extract_guarantor_application_fields,
    extract_ssm_fields,
)

APP_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_DIR.parents[1]
SAMPLE_DIR = REPO_ROOT / "samples" / "case-2-account-opening" / "xyz-sdn-bhd"
SAMPLE_FILES = {
    "cls": SAMPLE_DIR / "XYZ Sdn Bhd - CLS Extract.pdf",
    "email": SAMPLE_DIR / "XYZ Sdn Bhd - Email Request.pdf",
    "ssm": SAMPLE_DIR / "XYZ Sdn Bhd - SSM Search.pdf",
    "ccris_app": SAMPLE_DIR / "XYZ Sdn Bhd - CCRIS Application Form.pdf",
    "guarantor_app": SAMPLE_DIR / "XYZ Sdn Bhd - Guarantor Application Form.pdf",
}
DOC_LABELS = {
    "cls": "CLS Extract", "email": "Email Request", "ssm": "SSM Search",
    "ccris_app": "CCRIS Application Form", "guarantor_app": "Guarantor Application Form",
}


def _save_upload(uploaded_file, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


st.title(":material/description: Case detail")

case_id = st.session_state.get("selected_case_id")

if case_id:
    case = case_store.get_case(case_id)
    if not case:
        st.error("This case no longer exists.")
        st.stop()
    st.caption(f"Existing case · processed {case['created_at']}")
    if st.button("← Back to cases", type="tertiary"):
        st.switch_page("app_pages/cases.py")
    shared_pages.render_case_results(
        case_id=case["case_id"],
        documents=case["documents"],
        results=case["results"],
        remarks=case["remarks"] or "",
        processing_seconds=case["processing_seconds"] or 0,
        processed_at=case["created_at"],
        module_name="Account Opening",
        left_label="Value A",
        right_label="Value B",
        markdown_report=case["markdown_report"] or "",
    )
    st.stop()

st.caption("New case · upload the five CIF-creation documents, then run control testing.")
if st.button("← Back to cases", type="tertiary"):
    st.switch_page("app_pages/cases.py")

use_sample = st.checkbox("Use committed reference sample (XYZ Sdn Bhd)", value=False)

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
    st.info("Provide all five documents (or use the reference sample) to run control testing.", icon=":material/info:")
    st.stop()

if st.button("Run control testing", icon=":material/play_arrow:", type="primary"):
    started = time.time()
    render_dir = tempfile.mkdtemp(prefix="case2_render_")
    with st.spinner("Extracting fields and reconciling..."):
        try:
            cls = extract_cls_fields(paths["cls"])
            email = extract_email_fields(paths["email"], render_dir)
            ssm = extract_ssm_fields(paths["ssm"], render_dir)
            ccris_app = extract_ccris_application_fields(paths["ccris_app"], render_dir)
            guarantor_app = extract_guarantor_application_fields(paths["guarantor_app"], render_dir)
            results = compare(cls, email, ssm, ccris_app, guarantor_app)
        except Exception as exc:
            st.error(f"Extraction/comparison failed: {exc}")
            st.stop()
    with st.spinner("Generating remarks..."):
        remarks = groq_client.generate_case_remarks(
            results, f"Case 2 (Account Opening) — {cls.get('customer_name', 'Unknown Customer')}"
        )
    elapsed = time.time() - started
    documents = [{"label": DOC_LABELS[key], "filename": Path(p).name} for key, p in paths.items()]
    markdown_report = to_markdown(cls, email, ssm, ccris_app, guarantor_app, results)
    new_case_id = case_store.save_case("case2", documents, results, elapsed, remarks, markdown_report)
    st.session_state["selected_case_id"] = new_case_id
    st.toast(f"Case {new_case_id} created", icon=":material/check_circle:")
    st.rerun()
