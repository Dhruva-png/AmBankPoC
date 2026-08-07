import streamlit as st
import pandas as pd
import io
import os
import base64

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Credit Facilities Analysis Engine",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR POLISHED UI & SIDEBAR ---
st.markdown("""
    <style>
    /* Global Page Styling */
    .main {
        background-color: #f8f9fa;
    }
    
    /* Professional Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
        padding-top: 1rem;
    }
    
    .sidebar-header {
        text-align: center;
        padding-bottom: 15px;
        margin-bottom: 15px;
        border-bottom: 1px solid #e2e8f0;
    }
    
    .sidebar-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1e293b;
        margin-top: 10px;
    }

    .sidebar-subtitle {
        font-size: 0.8rem;
        color: #64748b;
        margin-bottom: 10px;
    }
    
    /* Card / Container Styling */
    .quad-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
        margin-bottom: 15px;
        height: 100%;
    }
    
    .card-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 2px solid #2563eb;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Primary Action Button */
    .stButton>button {
        width: 100%;
        background-color: #1e40af;
        color: white;
        font-weight: 600;
        border-radius: 6px;
        border: none;
        padding: 0.55rem 1rem;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #1e3a8a;
        color: #ffffff;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* PDF Embed Style */
    .pdf-frame {
        width: 100%;
        height: 420px;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
    }

    .empty-viewer {
        height: 420px;
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #f1f5f9;
        border: 2px dashed #cbd5e1;
        border-radius: 6px;
        color: #64748b;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)


# --- HELPER FUNCTIONS ---
def load_logo():
    """Finds and displays logo.jpg safely."""
    possible_paths = ["logo.jpg", "assets/logo.jpg", "../logo.jpg", "apps/case1_credit_facilities/logo.jpg"]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def pdf_to_base64_embed(uploaded_file):
    """Converts uploaded PDF file to embedded Base64 HTML iframe."""
    if uploaded_file is not None and uploaded_file.name.endswith(".pdf"):
        bytes_data = uploaded_file.getvalue()
        base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" class="pdf-frame" type="application/pdf"></iframe>'
        return pdf_display
    return None

def generate_excel_export(df1, df2):
    """Generates an Excel workbook containing extraction data from both documents."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df1.empty:
            df1.to_excel(writer, sheet_name='Doc 1 Extraction', index=False)
        if not df2.empty:
            df2.to_excel(writer, sheet_name='Doc 2 Extraction', index=False)
        
        # Combined Consolidated Tab
        combined_df = pd.concat([
            df1.assign(Source="Document 1"),
            df2.assign(Source="Document 2")
        ], ignore_index=True)
        combined_df.to_excel(writer, sheet_name='Consolidated View', index=False)
    output.seek(0)
    return output

def mock_extract_data(doc_name, doc_type="doc1"):
    """
    Automated Extraction Logic providing Field-level confidence scores and Page Indexing.
    """
    if doc_type == "doc1":
        data = [
            {"Field Name": "Borrower Name", "Extracted Value": "Acme Capital Holding Sdn Bhd", "Confidence": "98.5%", "Page Index": "Page 1"},
            {"Field Name": "Registration / MyKad", "Extracted Value": "201801049281 (1298310-X)", "Confidence": "99.1%", "Page Index": "Page 1"},
            {"Field Name": "Facility Requested", "Extracted Value": "Term Loan & Commercial Line", "Confidence": "96.2%", "Page Index": "Page 1"},
            {"Field Name": "Proposed Limit", "Extracted Value": "MYR 5,000,000.00", "Confidence": "97.8%", "Page Index": "Page 2"},
            {"Field Name": "Loan Tenor", "Extracted Value": "84 Months (7 Years)", "Confidence": "94.0%", "Page Index": "Page 2"},
            {"Field Name": "Interest Rate Structure", "Extracted Value": "BLR + 1.25% p.a.", "Confidence": "92.4%", "Page Index": "Page 3"},
            {"Field Name": "Collateral Details", "Extracted Value": "First Party Industrial Grant No. 49102", "Confidence": "95.6%", "Page Index": "Page 4"},
            {"Field Name": "Primary Debt Service Coverage", "Extracted Value": "1.85x", "Confidence": "91.3%", "Page Index": "Page 5"}
        ]
    else:
        data = [
            {"Field Name": "Entity Name Verification", "Extracted Value": "Acme Capital Holding Sdn Bhd", "Confidence": "99.0%", "Page Index": "Page 1"},
            {"Field Name": "Internal Credit Rating", "Extracted Value": "Grade A2 (Low Risk)", "Confidence": "97.5%", "Page Index": "Page 1"},
            {"Field Name": "Annual Revenue (Audited)", "Extracted Value": "MYR 24,500,000.00", "Confidence": "96.0%", "Page Index": "Page 2"},
            {"Field Name": "EBITDA Margin", "Extracted Value": "18.4%", "Confidence": "93.2%", "Page Index": "Page 2"},
            {"Field Name": "Existing Exposure Limit", "Extracted Value": "MYR 1,200,000.00", "Confidence": "98.1%", "Page Index": "Page 3"},
            {"Field Name": "Guarantor Name", "Extracted Value": "Dato' Robert Chen", "Confidence": "95.8%", "Page Index": "Page 3"},
            {"Field Name": "CTOS / CCRIS Rating", "Extracted Value": "Clean / Zero Default History", "Confidence": "99.4%", "Page Index": "Page 4"},
            {"Field Name": "Compliance Clearance", "Extracted Value": "Passed (Anti-Money Laundering Cleared)", "Confidence": "98.9%", "Page Index": "Page 4"}
        ]
    return pd.DataFrame(data)


# --- SIDEBAR COMPONENT ---
with st.sidebar:
    logo_path = load_logo()
    if logo_path:
        st.image(logo_path, use_container_width=True)
    
    st.markdown("""
        <div class="sidebar-header">
            <div class="sidebar-title">Credit Evaluation Portal</div>
            <div class="sidebar-subtitle">Document Analysis & Facility Review</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📄 Document Upload")
    doc1_file = st.file_uploader("Upload Primary Credit Document", type=["pdf", "png", "jpg"], key="doc1")
    doc2_file = st.file_uploader("Upload Supporting Facility File", type=["pdf", "png", "jpg"], key="doc2")
    
    st.markdown("---")
    
    process_btn = st.button("⚡ Run Extraction Engine")
    
    st.markdown("---")
    st.markdown("##### 📌 System Status")
    st.caption("• Extraction Engine: **Online**")
    st.caption("• Verification Status: **Ready**")


# --- MAIN CONTENT LAYOUT (4-WAY SPLIT) ---

st.title("🏦 Credit Facilities Intelligent Extraction")
st.caption("Automated document indexing, field extraction, confidence scoring, and side-by-side verification.")

# Load Data State
if "df1" not in st.session_state:
    st.session_state.df1 = mock_extract_data(doc1_file.name if doc1_file else "Doc 1", "doc1")
if "df2" not in st.session_state:
    st.session_state.df2 = mock_extract_data(doc2_file.name if doc2_file else "Doc 2", "doc2")

if process_btn:
    with st.spinner("Processing credit documents and compiling index metrics..."):
        st.session_state.df1 = mock_extract_data(doc1_file.name if doc1_file else "Doc 1", "doc1")
        st.session_state.df2 = mock_extract_data(doc2_file.name if doc2_file else "Doc 2", "doc2")
        st.success("Extraction and field indexing completed successfully!")

# Top Bar Action - Excel Export
excel_data = generate_excel_export(st.session_state.df1, st.session_state.df2)

st.download_button(
    label="📊 Export Full Analysis to Excel (.xlsx)",
    data=excel_data,
    file_name="Credit_Facilities_Extraction_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.write("")

# -------------------------------------------------------------------
# TOP ROW: DOCUMENT VIEWERS (SPLIT 2-WAYS)
# -------------------------------------------------------------------
top_col1, top_col2 = st.columns(2)

with top_col1:
    st.markdown("""
        <div class="quad-card">
            <div class="card-title">
                <span>📁 Primary Credit Document Preview</span>
                <span style="font-size: 0.8rem; color: #64748b;">Top-Left View</span>
            </div>
    """, unsafe_allow_html=True)
    
    if doc1_file:
        embed_code = pdf_to_base64_embed(doc1_file)
        if embed_code:
            st.markdown(embed_code, unsafe_allow_html=True)
        else:
            st.info(f"Loaded File: **{doc1_file.name}** ({doc1_file.type})")
    else:
        st.markdown("""
            <div class="empty-viewer">
                <span>Upload Document 1 in sidebar to view PDF rendering</span>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

with top_col2:
    st.markdown("""
        <div class="quad-card">
            <div class="card-title">
                <span>📁 Supporting Facility Document Preview</span>
                <span style="font-size: 0.8rem; color: #64748b;">Top-Right View</span>
            </div>
    """, unsafe_allow_html=True)
    
    if doc2_file:
        embed_code = pdf_to_base64_embed(doc2_file)
        if embed_code:
            st.markdown(embed_code, unsafe_allow_html=True)
        else:
            st.info(f"Loaded File: **{doc2_file.name}** ({doc2_file.type})")
    else:
        st.markdown("""
            <div class="empty-viewer">
                <span>Upload Document 2 in sidebar to view PDF rendering</span>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------------------------
# BOTTOM ROW: EXTRACTED CONTENT & METRICS (SPLIT 2-WAYS)
# -------------------------------------------------------------------
bot_col1, bot_col2 = st.columns(2)

with bot_col1:
    st.markdown("""
        <div class="quad-card">
            <div class="card-title">
                <span>🔍 Document 1: Field Extracted Data & Index</span>
                <span style="font-size: 0.8rem; color: #16a34a;">Bottom-Left View</span>
            </div>
    """, unsafe_allow_html=True)
    
    st.dataframe(
        st.session_state.df1,
        column_config={
            "Field Name": st.column_config.TextColumn("Field Name", width="medium"),
            "Extracted Value": st.column_config.TextColumn("Extracted Value", width="large"),
            "Confidence": st.column_config.TextColumn("Confidence Level", width="small"),
            "Page Index": st.column_config.TextColumn("Page Source", width="small"),
        },
        use_container_width=True,
        hide_index=True,
        height=350
    )
    st.markdown("</div>", unsafe_allow_html=True)

with bot_col2:
    st.markdown("""
        <div class="quad-card">
            <div class="card-title">
                <span>🔍 Document 2: Field Extracted Data & Index</span>
                <span style="font-size: 0.8rem; color: #16a34a;">Bottom-Right View</span>
            </div>
    """, unsafe_allow_html=True)
    
    st.dataframe(
        st.session_state.df2,
        column_config={
            "Field Name": st.column_config.TextColumn("Field Name", width="medium"),
            "Extracted Value": st.column_config.TextColumn("Extracted Value", width="large"),
            "Confidence": st.column_config.TextColumn("Confidence Level", width="small"),
            "Page Index": st.column_config.TextColumn("Page Source", width="small"),
        },
        use_container_width=True,
        hide_index=True,
        height=350
    )
    st.markdown("</div>", unsafe_allow_html=True)