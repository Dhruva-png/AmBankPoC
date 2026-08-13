import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import ai_client
import case_store
import shared_pages
from compare import compare, to_markdown
from extract_fields import classify_document, extract_credit_paper_fields, extract_lo_fields

DOC_LABELS = {"credit_paper": "Credit Paper", "letter_of_offer": "Letter of Offer"}
CATEGORY_LABELS = {**DOC_LABELS, "unknown": "Unclassified"}


def _save_upload(uploaded_file, dest_dir: str) -> str:
    # Keep the original filename (not a random tempfile name) -- extraction derives each
    # check's "source" label from this path's basename, so a random name here means every
    # source reference shown to the auditor is meaningless instead of the real document name.
    dest = Path(dest_dir) / uploaded_file.name
    dest.write_bytes(uploaded_file.getbuffer())
    return str(dest)


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
        module_name="Credit Forms",
        left_label="Credit Paper",
        right_label="Letter of Offer",
        markdown_report=case["markdown_report"] or "",
        case_status=case.get("status") or "",
        error_message=case.get("error_message") or "",
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
        upload_dir = tempfile.mkdtemp(prefix="case1_upload_")
        saved = [(_save_upload(f, upload_dir), f.name) for f in uploads]
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
    documents = [
        {"label": "Credit Paper", "filename": Path(cp_path).name},
        {"label": "Letter of Offer", "filename": Path(lo_path).name},
    ]
    with st.spinner("Extracting fields and reconciling against the Credit Paper..."):
        try:
            cp = extract_credit_paper_fields(cp_path)
            lo = extract_lo_fields(lo_path)
            results = compare(cp, lo)
        except Exception as exc:
            error_case_id = case_store.save_error_case("case1", documents, "", str(exc))
            case_store.store_documents(error_case_id, [cp_path, lo_path])
            st.error(f"Extraction/comparison failed: {exc}. Logged as {error_case_id} for follow-up.")
            st.stop()
    customer_name = cp.get("customer", "") or "Unknown Customer"
    with st.spinner("Generating remarks..."):
        remarks = ai_client.generate_case_remarks(results, f"Case 1 (Credit Forms) — {customer_name}")
    elapsed = time.time() - started
    markdown_report = to_markdown(cp, lo, results)
    new_case_id = case_store.save_case(
        "case1", documents, results, elapsed, remarks, markdown_report, customer_name=customer_name
    )
    case_store.store_documents(new_case_id, [cp_path, lo_path])
    st.session_state["selected_case_id"] = new_case_id
    st.toast(f"Case {new_case_id} created", icon=":material/check_circle:")
    st.rerun()
