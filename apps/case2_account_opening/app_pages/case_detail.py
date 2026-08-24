import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import ai_client
import case_store
import shared_pages
from compare import compare, to_markdown
from extract_fields import (
    classify_document,
    extract_aof_fields,
    extract_fatca_fields,
    extract_id_fields,
    extract_netreveal_fields,
    extract_vca_fields,
)

DOC_LABELS = {
    "aof": "Account Opening Form", "id": "Identity Document", "fatca": "FATCA/CRS Declaration",
    "vca": "Vulnerable Client Assessment", "netreveal": "AML Screening (NetReveal)",
}
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
        module_name="Accounts",
        left_label="Value A",
        right_label="Value B",
        markdown_report=case["markdown_report"] or "",
        case_status=case.get("status") or "",
        error_message=case.get("error_message") or "",
    )
    st.stop()

st.caption(
    "New case · upload the five account-opening documents (Account Opening Form, Identity "
    "Document, FATCA/CRS Declaration, Vulnerable Client Assessment, AML Screening) in any "
    "order — the system classifies each one automatically."
)
if st.button("← Back to cases", type="tertiary"):
    st.switch_page("app_pages/cases.py")

paths = {}
uploads = st.file_uploader(
    "Upload documents (Account Opening Form, Identity Document, FATCA/CRS Declaration, "
    "Vulnerable Client Assessment, AML Screening)",
    type=["pdf"],
    accept_multiple_files=True,
)
if uploads:
    signature = tuple((f.name, f.size) for f in uploads)
    if st.session_state.get("case2_classify_sig") != signature:
        render_dir = tempfile.mkdtemp(prefix="case2_classify_")
        saved = [(_save_upload(f, render_dir), f.name) for f in uploads]
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
    missing = [label for label in DOC_LABELS.values() if counts.get(label, 0) == 0]
    if missing:
        st.warning(f"Missing required document type(s): {', '.join(missing)}.")
    else:
        label_to_key = {v: k for k, v in DOC_LABELS.items()}
        path_by_file = {c["name"]: c["path"] for c in classified}
        role_by_file = dict(zip(edited["File"], edited["Classified type"]))
        ignored = []
        for name, role in role_by_file.items():
            key = label_to_key.get(role)
            if not key:
                continue
            if key in paths:
                ignored.append(name)
                continue
            paths[key] = path_by_file[name]
        if ignored:
            st.caption(f"Ignored {len(ignored)} extra document(s) not needed for this case: {', '.join(ignored)}.")

if len(paths) < 5:
    st.info("Provide all five documents to run control testing.", icon=":material/info:")
    st.stop()

if st.button("Run control testing", icon=":material/play_arrow:", type="primary"):
    started = time.time()
    render_dir = tempfile.mkdtemp(prefix="case2_render_")
    documents = [{"label": DOC_LABELS[key], "filename": Path(p).name} for key, p in paths.items()]
    with st.spinner("Extracting fields and reconciling..."):
        try:
            aof = extract_aof_fields(paths["aof"], render_dir)
            id_doc = extract_id_fields(paths["id"], render_dir)
            fatca = extract_fatca_fields(paths["fatca"], render_dir)
            vca = extract_vca_fields(paths["vca"], render_dir)
            netreveal = extract_netreveal_fields(paths["netreveal"], render_dir)
            results = compare(aof, id_doc, fatca, vca, netreveal)
        except Exception as exc:
            error_case_id = case_store.save_error_case("case2", documents, "", str(exc))
            case_store.store_documents(error_case_id, list(paths.values()))
            st.error(f"Extraction/comparison failed: {exc}. Logged as {error_case_id} for follow-up.")
            st.stop()
    customer_display_name = aof.get("name", "") or "Unknown Customer"
    id_name = case_store.combine_document_names(aof.get("name", ""), id_doc.get("name", ""))
    with st.spinner("Generating remarks..."):
        remarks = ai_client.generate_case_remarks(results, f"Case 2 (Accounts) — {customer_display_name}")
    elapsed = time.time() - started
    markdown_report = to_markdown(aof, id_doc, fatca, vca, netreveal, results)
    new_case_id = case_store.save_case(
        "case2", documents, results, elapsed, remarks, markdown_report, customer_name=id_name
    )
    case_store.store_documents(new_case_id, list(paths.values()))
    st.session_state["selected_case_id"] = new_case_id
    st.toast(f"Case {new_case_id} created", icon=":material/check_circle:")
    st.rerun()
