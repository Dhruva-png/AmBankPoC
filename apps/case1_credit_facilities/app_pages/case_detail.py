import tempfile
import time
from pathlib import Path

import streamlit as st

import case_store
import groq_client
import shared_pages
from compare import compare, to_markdown
from extract_fields import extract_credit_paper_fields, extract_lo_fields

APP_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_DIR.parents[1]
SAMPLE_DIR = REPO_ROOT / "samples" / "case-1-credit-facilities" / "hadyan-sdn-bhd"
SAMPLE_CP = SAMPLE_DIR / "Credit Paper - AR2025 - Hadyan Sdn Bhd.docx"
SAMPLE_LO = SAMPLE_DIR / "Letter of Offer - Revise Purpose - Hadyan Sdn Bhd.doc"


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
        module_name="Credit Facilities",
        left_label="Credit Paper",
        right_label="Letter of Offer",
        markdown_report=case["markdown_report"] or "",
    )
    st.stop()

st.caption("New case · upload the approved Credit Paper and the issued Letter of Offer, then run control testing.")
if st.button("← Back to cases", type="tertiary"):
    st.switch_page("app_pages/cases.py")

use_sample = st.checkbox("Use committed reference sample (Hadyan Sdn Bhd)", value=False)

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
    st.info("Provide both documents (or use the reference sample) to run control testing.", icon=":material/info:")
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
    st.session_state["selected_case_id"] = new_case_id
    st.toast(f"Case {new_case_id} created", icon=":material/check_circle:")
    st.rerun()
