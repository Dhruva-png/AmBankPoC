import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import case_store
import groq_client
import shared_pages
from compare import compare, to_markdown
from extract_fields import (
    classify_document,
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
CATEGORY_LABELS = {**DOC_LABELS, "unknown": "Unclassified"}


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

st.caption("New case · upload the five CIF-creation documents in any order — the system classifies each one automatically.")
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
    uploads = st.file_uploader(
        "Upload documents (CLS Extract, Email Request, SSM Search, CCRIS Application Form, Guarantor Application Form)",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if uploads:
        signature = tuple((f.name, f.size) for f in uploads)
        if st.session_state.get("case2_classify_sig") != signature:
            render_dir = tempfile.mkdtemp(prefix="case2_classify_")
            saved = [(_save_upload(f, ".pdf"), f.name) for f in uploads]
            with st.spinner("Classifying uploaded documents..."):
                classified = []
                for path, name in saved:
                    try:
                        category = classify_document(path, render_dir)
                    except Exception:
                        category = "unknown"
                    classified.append({"path": path, "name": name, "category": category})
            st.session_state["case2_classify_sig"] = signature
            st.session_state["case2_classify_result"] = classified
        classified = st.session_state["case2_classify_result"]

        display_df = pd.DataFrame(
            [{"File": c["name"], "Classified type": CATEGORY_LABELS.get(c["category"], "Unclassified")} for c in classified]
        )
        st.caption("Review the automatic classification and correct it if needed, then run control testing.")
        edited = st.data_editor(
            display_df,
            hide_index=True,
            width="stretch",
            disabled=["File"],
            column_config={
                "Classified type": st.column_config.SelectboxColumn(
                    options=list(DOC_LABELS.values()) + ["Unclassified"], required=True
                )
            },
            key="case2_classify_editor",
        )

        counts = edited["Classified type"].value_counts().to_dict()
        problems = [label for label in DOC_LABELS.values() if counts.get(label, 0) != 1]
        if problems:
            st.warning(f"Each document type must appear exactly once. Please correct: {', '.join(problems)}.")
        else:
            label_to_key = {v: k for k, v in DOC_LABELS.items()}
            path_by_file = {c["name"]: c["path"] for c in classified}
            role_by_file = dict(zip(edited["File"], edited["Classified type"]))
            for name, role in role_by_file.items():
                key = label_to_key.get(role)
                if key:
                    paths[key] = path_by_file[name]

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
    case_store.store_documents(new_case_id, list(paths.values()))
    st.session_state["selected_case_id"] = new_case_id
    st.toast(f"Case {new_case_id} created", icon=":material/check_circle:")
    st.rerun()
