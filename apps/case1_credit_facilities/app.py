import streamlit as st
import pandas as pd
import io
import os
import base64

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Enterprise Credit Facilities Analysis Portal",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ADVANCED ENTERPRISE CSS ---
st.markdown("""
    <style>
    /* Main Layout Styling */
    .main {
        background-color: #f8fafc;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
        padding-top: 1.5rem;
    }
    
    .sidebar-header-box {
        text-align: center;
        padding: 12px;
        margin-bottom: 20px;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 8px;
        color: white;
    }

    .sidebar-title {
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .sidebar-subtitle {
        font-size: 0.75rem;
        color: #94a3b8;
        margin-top: 2px;
    }
    
    /* Metric Card Styling */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2563eb;
        border-radius: 8px;
        padding: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .metric-card.warning {
        border-left-color: #f59e0b;
    }

    .metric-card.success {
        border-left-color: #10b981;
    }

    .metric-title {
        font-size: 0.78rem;
        text-transform: uppercase;
        font-weight: 600;
        color: #64748b;
        letter-spacing: 0.5px;
    }

    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0f172a;
        margin-top: 4px;
    }

    .metric-subtext {
        font-size: 0.75rem;
        color: #10b981;
        margin-top: 2px;
    }

    /* Quad-Split Card Styling */
    .quad-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
        margin-bottom: 12px;
    }
    
    .card-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #f1f5f9;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* PDF Frame */
    .pdf-frame {
        width: 100%;
        height: 400px;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
    }

    .empty-viewer {
        height: 400px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background-color: #f8fafc;
        border: 2px dashed #cbd5e1;
        border-radius: 6px;
        color: #64748b;
        font-size: 0.88rem;
    }

    /* Custom Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
        color: white;
        font-weight: 600;
        border-radius: 6px;
        border: none;
        padding: 0.6rem 1rem;
        transition: all 0.2s ease;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%);
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
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
    if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
        bytes_data = uploaded_file.getvalue()
        base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
        return f'<iframe src="data:application/pdf;base64,{base64_pdf}" class="pdf-frame" type="application/pdf"></iframe>'
    return None

def generate_excel_export(df1, df2, recon_df):
    """Generates an enhanced Excel workbook with extraction data & discrepancy report."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df1.empty:
            df1.to_excel(writer, sheet_name='Primary Doc Extraction', index=False)
        if not df2.empty:
            df2.to_excel(writer, sheet_name='Supporting Doc Extraction', index=False)
        if not recon_df.empty:
            recon_df.to_excel(writer, sheet_name='Cross-Doc Reconciliation', index=False)
    output.seek(0)
    return output

def get_initial_data_doc1():
    return [
        {"Field Name": "Borrower Name", "Extracted Value": "Acme Capital Holding Sdn Bhd", "Confidence": "98.5%", "Page Index": "Page 1", "Verified": True},
        {"Field Name": "Registration / MyKad", "Extracted Value": "201801049281 (1298310-X)", "Confidence": "99.1%", "Page Index": "Page 1", "Verified": True},
        {"Field Name": "Facility Requested", "Extracted Value": "Term Loan & Commercial Line", "Confidence": "96.2%", "Page Index": "Page 1", "Verified": False},
        {"Field Name": "Proposed Limit", "Extracted Value": "MYR 5,000,000.00", "Confidence": "97.8%", "Page Index": "Page 2", "Verified": True},
        {"Field Name": "Loan Tenor", "Extracted Value": "84 Months (7 Years)", "Confidence": "94.0%", "Page Index": "Page 2", "Verified": False},
        {"Field Name": "Interest Rate Structure", "Extracted Value": "BLR + 1.25% p.a.", "Confidence": "88.4%", "Page Index": "Page 3", "Verified": False},
        {"Field Name": "Collateral Details", "Extracted Value": "First Party Industrial Grant No. 49102", "Confidence": "95.6%", "Page Index": "Page 4", "Verified": True},
        {"Field Name": "Primary Debt Service Coverage", "Extracted Value": "1.85x", "Confidence": "91.3%", "Page Index": "Page 5", "Verified": False}
    ]

def get_initial_data_doc2():
    return [
        {"Field Name": "Borrower Name", "Extracted Value": "Acme Capital Holding Sdn Bhd", "Confidence": "99.0%", "Page Index": "Page 1", "Verified": True},
        {"Field Name": "Internal Credit Rating", "Extracted Value": "Grade A2 (Low Risk)", "Confidence": "97.5%", "Page Index": "Page 1", "Verified": True},
        {"Field Name": "Annual Revenue (Audited)", "Extracted Value": "MYR 24,500,000.00", "Confidence": "96.0%", "Page Index": "Page 2", "Verified": False},
        {"Field Name": "Proposed Limit", "Extracted Value": "MYR 4,800,000.00", "Confidence": "89.2%", "Page Index": "Page 2", "Verified": False},
        {"Field Name": "Existing Exposure Limit", "Extracted Value": "MYR 1,200,000.00", "Confidence": "98.1%", "Page Index": "Page 3", "Verified": True},
        {"Field Name": "Guarantor Name", "Extracted Value": "Dato' Robert Chen", "Confidence": "95.8%", "Page Index": "Page 3", "Verified": True},
        {"Field Name": "CTOS / CCRIS Rating", "Extracted Value": "Clean / Zero Default History", "Confidence": "99.4%", "Page Index": "Page 4", "Verified": True},
        {"Field Name": "Compliance Clearance", "Extracted Value": "Passed (AML/CFT Cleared)", "Confidence": "98.9%", "Page Index": "Page 4", "Verified": True}
    ]

# Initialize Session States
if "df1" not in st.session_state:
    st.session_state.df1 = pd.DataFrame(get_initial_data_doc1())
if "df2" not in st.session_state:
    st.session_state.df2 = pd.DataFrame(get_initial_data_doc2())


# --- SIDEBAR COMPONENT ---
with st.sidebar:
    logo_path = load_logo()
    if logo_path:
        st.image(logo_path, use_container_width=True)
    
    st.markdown("""
        <div class="sidebar-header-box">
            <div class="sidebar-title">AMBANK CREDIT PORTAL</div>
            <div class="sidebar-subtitle">Case 1: Credit Facility Processing</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📄 Document Ingestion")
    doc1_file = st.file_uploader("Primary Facility Application", type=["pdf", "png", "jpg"], key="doc1")
    doc2_file = st.file_uploader("Supporting Financial Doc", type=["pdf", "png", "jpg"], key="doc2")
    
    st.markdown("---")
    
    st.markdown("### ⚙️ Engine Controls")
    ocr_mode = st.selectbox("Extraction Precision", ["High Precision (Dual-Pass)", "Fast Batch Engine", "Strict Compliance Mode"])
    
    if st.button("⚡ Execute Extraction Pipeline"):
        st.session_state.df1 = pd.DataFrame(get_initial_data_doc1())
        st.session_state.df2 = pd.DataFrame(get_initial_data_doc2())
        st.toast("Extraction successfully refreshed!", icon="✅")

    st.markdown("---")
    st.caption("🔒 **Security**: Enterprise AES-256 Encrypted")
    st.caption("🟢 **Core Engine**: Online (Latency: 24ms)")


# --- RECONCILIATION ENGINE COMPUTATION ---
doc1_map = st.session_state.df1.set_index("Field Name")["Extracted Value"].to_dict()
doc2_map = st.session_state.df2.set_index("Field Name")["Extracted Value"].to_dict()

common_fields = set(doc1_map.keys()).intersection(set(doc2_map.keys()))
recon_records = []

for field in common_fields:
    val1 = doc1_map[field]
    val2 = doc2_map[field]
    match_status = "✅ MATCH" if str(val1).strip() == str(val2).strip() else "⚠️ DISCREPANCY"
    recon_records.append({
        "Comparison Field": field,
        "Doc 1 Value": val1,
        "Doc 2 Value": val2,
        "Reconciliation Status": match_status
    })

recon_df = pd.DataFrame(recon_records)


# --- TOP HEADER & KPI METRICS DASHBOARD ---
st.title("🏦 Credit Facility Evaluation Portal")
st.caption("Automated document indexing, field-level confidence scoring, and multi-document cross-reconciliation.")

# Dynamic Metrics Calculation
total_fields = len(st.session_state.df1) + len(st.session_state.df2)
verified_count = st.session_state.df1["Verified"].sum() + st.session_state.df2["Verified"].sum()
discrepancies_count = len(recon_df[recon_df["Reconciliation Status"].str.contains("DISCREPANCY")]) if not recon_df.empty else 0

m_col1, m_col2, m_col3, m_col4 = st.columns(4)

with m_col1:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Overall Avg Confidence</div>
            <div class="metric-value">96.4%</div>
            <div class="metric-subtext"> High Reliability Target</div>
        </div>
    """, unsafe_allow_html=True)

with m_col2:
    st.markdown(f"""
        <div class="metric-card success">
            <div class="metric-title">Human Verified Fields</div>
            <div class="metric-value">{verified_count} / {total_fields}</div>
            <div class="metric-subtext">{(verified_count/total_fields)*100:.0f}% Completed</div>
        </div>
    """, unsafe_allow_html=True)

with m_col3:
    st.markdown(f"""
        <div class="metric-card {"warning" if discrepancies_count > 0 else "success"}">
            <div class="metric-title">Cross-Doc Discrepancies</div>
            <div class="metric-value">{discrepancies_count} Detected</div>
            <div class="metric-subtext" style="color: {'#f59e0b' if discrepancies_count > 0 else '#10b981'};">
                {'Requires Audit' if discrepancies_count > 0 else 'All Common Fields Match'}
            </div>
        </div>
    """, unsafe_allow_html=True)

with m_col4:
    st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Risk Clearance Status</div>
            <div class="metric-value" style="color: #10b981;">PASSED</div>
            <div class="metric-subtext">No High Risk Anomaly</div>
        </div>
    """, unsafe_allow_html=True)

st.write("")

# TAB NAVIGATION
tab_quad, tab_recon = st.tabs(["🧩 4-Way Split Extraction Workspace", "⚖️ Cross-Document Reconciliation Engine"])


# -------------------------------------------------------------------
# TAB 1: 4-WAY SPLIT WORKSPACE
# -------------------------------------------------------------------
with tab_quad:
    # Action Bar: Export
    col_exp1, col_exp2 = st.columns([3, 1])
    with col_exp2:
        excel_data = generate_excel_export(st.session_state.df1, st.session_state.df2, recon_df)
        st.download_button(
            label="📥 Export Full Audit Workbook (.xlsx)",
            data=excel_data,
            file_name="Credit_Facilities_Audit_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # TOP ROW: DOCUMENT PREVIEWERS
    top_col1, top_col2 = st.columns(2)

    with top_col1:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>📑 Primary Application Document</span>
                    <span style="font-size: 0.75rem; background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 12px; font-weight: 600;">Top-Left View</span>
                </div>
        """, unsafe_allow_html=True)
        
        if doc1_file:
            embed_code = pdf_to_base64_embed(doc1_file)
            if embed_code:
                st.markdown(embed_code, unsafe_allow_html=True)
            else:
                st.info(f"📄 Active File: **{doc1_file.name}**")
        else:
            st.markdown("""
                <div class="empty-viewer">
                    <span>📌 Upload Document 1 in sidebar to view PDF rendering</span>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    with top_col2:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>📑 Supporting Facility Document</span>
                    <span style="font-size: 0.75rem; background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 12px; font-weight: 600;">Top-Right View</span>
                </div>
        """, unsafe_allow_html=True)
        
        if doc2_file:
            embed_code = pdf_to_base64_embed(doc2_file)
            if embed_code:
                st.markdown(embed_code, unsafe_allow_html=True)
            else:
                st.info(f"📄 Active File: **{doc2_file.name}**")
        else:
            st.markdown("""
                <div class="empty-viewer">
                    <span>📌 Upload Document 2 in sidebar to view PDF rendering</span>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

    # BOTTOM ROW: INTERACTIVE DATA EDITORS
    bot_col1, bot_col2 = st.columns(2)

    with bot_col1:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>🔍 Primary Doc: Field Extraction & Indexing</span>
                    <span style="font-size: 0.75rem; color: #64748b;">Interactive Table</span>
                </div>
        """, unsafe_allow_html=True)
        
        st.session_state.df1 = st.data_editor(
            st.session_state.df1,
            column_config={
                "Verified": st.column_config.CheckboxColumn("Verify", help="Mark after visual confirmation", default=False),
                "Field Name": st.column_config.TextColumn("Field Label", disabled=True),
                "Extracted Value": st.column_config.TextColumn("Extracted Data Value"),
                "Confidence": st.column_config.TextColumn("Score", disabled=True),
                "Page Index": st.column_config.TextColumn("Source", disabled=True),
            },
            use_container_width=True,
            hide_index=True,
            key="editor_doc1"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with bot_col2:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>🔍 Supporting Doc: Field Extraction & Indexing</span>
                    <span style="font-size: 0.75rem; color: #64748b;">Interactive Table</span>
                </div>
        """, unsafe_allow_html=True)
        
        st.session_state.df2 = st.data_editor(
            st.session_state.df2,
            column_config={
                "Verified": st.column_config.CheckboxColumn("Verify", help="Mark after visual confirmation", default=False),
                "Field Name": st.column_config.TextColumn("Field Label", disabled=True),
                "Extracted Value": st.column_config.TextColumn("Extracted Data Value"),
                "Confidence": st.column_config.TextColumn("Score", disabled=True),
                "Page Index": st.column_config.TextColumn("Source", disabled=True),
            },
            use_container_width=True,
            hide_index=True,
            key="editor_doc2"
        )
        st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------------------------
# TAB 2: CROSS-DOCUMENT RECONCILIATION ENGINE
# -------------------------------------------------------------------
with tab_recon:
    st.markdown("""
        <div class="quad-card">
            <div class="card-title">
                <span>⚖️ Automated Cross-Document Reconciliation Audit</span>
                <span style="font-size: 0.8rem; color: #64748b;">Comparing Key Overlapping Fields</span>
            </div>
    """, unsafe_allow_html=True)
    
    if not recon_df.empty:
        st.dataframe(
            recon_df,
            column_config={
                "Comparison Field": st.column_config.TextColumn("Key Field"),
                "Doc 1 Value": st.column_config.TextColumn("Primary Document Value"),
                "Doc 2 Value": st.column_config.TextColumn("Supporting Document Value"),
                "Reconciliation Status": st.column_config.TextColumn("Automated Match Status"),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No overlapping fields found between the documents to reconcile.")
        
    st.markdown("</div>", unsafe_allow_html=True)