import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import case_store
import groq_client
import shared_pages
from compare import compare, to_markdown
from extract_fields import classify_document, extract_credit_paper_fields, extract_lo_fields

DOC_LABELS = {"credit_paper": "Credit Paper", "letter_of_offer": "Letter of Offer"}
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
    shared_pages.render_case_actions(case_id, "app_pages/cases.py")
    shared_pages.render_case_results(
        case_id=case["case_id"],
        documents=case["documents"],
        results=case["results"],
        remarks=case["remarks"] or "",
        processing_seconds=case["processing_seconds"] or 0,
        processed_at=case["created_at"],
        module_name="Credit Facilities",
        left_label="Credit Paper",
        right_label="Letter of Offer",
        markdown_report=case["markdown_report"] or "",
    )
    st.stop()

st.caption("New case · upload the Credit Paper and Letter of Offer in any order — the system classifies each one automatically.")
if st.button("← Back to cases", type="tertiary"):
    st.switch_page("app_pages/cases.py")

cp_path = lo_path = None
uploads = st.file_uploader(
    "Upload documents (Credit Paper + Letter of Offer)",
    type=["doc", "docx", "pdf"],
    accept_multiple_files=True,
)
if uploads:
    signature = tuple((f.name, f.size) for f in uploads)
    if st.session_state.get("case1_classify_sig") != signature:
        saved = [(_save_upload(f, Path(f.name).suffix), f.name) for f in uploads]
        with st.spinner("Classifying uploaded documents..."):
            classified = []
            for path, name in saved:
                try:
                    category = classify_document(path)
                except Exception:
                    category = "unknown"
                classified.append({"path": path, "name": name, "category": category})
        st.session_state["case1_classify_sig"] = signature
        st.session_state["case1_classify_result"] = classified
    classified = st.session_state["case1_classify_result"]

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
        key="case1_classify_editor",
    )

    counts = edited["Classified type"].value_counts().to_dict()
    problems = [label for label in DOC_LABELS.values() if counts.get(label, 0) != 1]
    if problems:
        st.warning(f"Each document type must appear exactly once. Please correct: {', '.join(problems)}.")
    else:
        label_to_key = {v: k for k, v in DOC_LABELS.items()}
        path_by_file = {c["name"]: c["path"] for c in classified}
        role_by_file = dict(zip(edited["File"], edited["Classified type"]))
        resolved = {label_to_key[role]: path_by_file[name] for name, role in role_by_file.items() if role in label_to_key}
        cp_path = resolved.get("credit_paper")
        lo_path = resolved.get("letter_of_offer")

if not (cp_path and lo_path):
    st.info("Upload the Credit Paper and Letter of Offer to run control testing.", icon=":material/info:")
    st.stop()

if st.button("Run control testing", icon=":material/play_arrow:", type="primary"):
    started = time.time()
    with st.spinner("Extracting fields and reconciling against the Credit Paper..."):
        try:
            cp = extract_credit_paper_fields(cp_path)
            lo = extract_lo_fields(lo_path)
            results = compare(cp, lo)
        except Exception as exc:
            st.error(f"Extraction/comparison failed: {exc}")
            st.stop()
    with st.spinner("Generating remarks..."):
        remarks = groq_client.generate_case_remarks(
            results, f"Case 1 (Credit Facilities) — {cp.get('customer', 'Unknown Customer')}"
        )
    elapsed = time.time() - started
    documents = [
        {"label": "Credit Paper", "filename": Path(cp_path).name},
        {"label": "Letter of Offer", "filename": Path(lo_path).name},
    ]
    markdown_report = to_markdown(cp, lo, results)
    new_case_id = case_store.save_case("case1", documents, results, elapsed, remarks, markdown_report)
    case_store.store_documents(new_case_id, [cp_path, lo_path])
    st.session_state["selected_case_id"] = new_case_id
    st.toast(f"Case {new_case_id} created", icon=":material/check_circle:")
    st.rerun()
