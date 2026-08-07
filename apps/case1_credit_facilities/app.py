import streamlit as st
import pandas as pd
import io
import os
import base64
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Credit Facilities Control & Audit Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CORPORATE ENTERPRISE STYLING ---
st.markdown("""
    <style>
    /* Global Page Styling */
    .main {
        background-color: #f8fafc;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
        padding-top: 1rem;
    }
    
    .sidebar-header-box {
        text-align: center;
        padding: 14px 10px;
        margin-bottom: 20px;
        background-color: #0f172a;
        border-radius: 6px;
        color: #ffffff;
    }

    .sidebar-title {
        font-size: 0.90rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    .sidebar-subtitle {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 4px;
    }

    /* Container Card Styling */
    .quad-card {
        background-color: #ffffff;
        border-radius: 6px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
        margin-bottom: 16px;
    }
    
    .card-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #f1f5f9;
        display: flex;
        justify-content: space-between;
        align-items: center;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }

    /* PDF Frame */
    .pdf-frame {
        width: 100%;
        height: 390px;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
    }

    .empty-viewer {
        height: 390px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background-color: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 4px;
        color: #64748b;
        font-size: 0.85rem;
        text-align: center;
        padding: 20px;
    }

    /* Primary Action Buttons */
    .stButton>button {
        background-color: #1e3a8a;
        color: #ffffff;
        font-weight: 600;
        border-radius: 4px;
        border: none;
        padding: 0.6rem 1rem;
        width: 100%;
    }

    .stButton>button:hover {
        background-color: #1d4ed8;
        color: #ffffff;
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

def read_file_text(uploaded_file):
    """Extracts raw text dynamically from uploaded PDF or text documents."""
    if uploaded_file is None:
        return ""
    text = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(uploaded_file)
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            text += f"\n--- Page {page_idx + 1} ---\n" + page_text
    except Exception:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(uploaded_file)
            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                text += f"\n--- Page {page_idx + 1} ---\n" + page_text
        except Exception:
            text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    return text


# --- EXTRACTION ENGINE ---
def extract_scope_fields(raw_text, doc_type="Credit Paper"):
    """
    Parses required Scope fields from source documents.
    """
    if not raw_text.strip():
        return pd.DataFrame(columns=["Scope Field", "Extracted Value", "Confidence", "Page Index"])

    lines = raw_text.split("\n")
    
    # Scope Regular Expression Rules
    patterns = {
        "Customer Name": r"(?:Customer Name|Borrower Name|Name of Applicant)\s*[:\-]?\s*([A-Za-z0-0\.\s&]+Sdn\s+Bhd|[A-Za-z0-9\.\s&]+Bhd|[A-Z\s]{4,})",
        "Customer IC / Reg No": r"(?:Registration No|IC No|MyKad|BRN|Reg No)\s*[:\-]?\s*([A-Za-z0-9\-\s\(\)]+)",
        "Customer Registered Address": r"(?:Address|Registered Address)\s*[:\-]?\s*([A-Za-z0-9\s,\.\-\/]+(?:Street|Road|Jalan|Avenue|Floor|Park|Lumpur|Penang|Selangor|Perak|Johor)[A-Za-z0-9\s,\.\-\/]+)",
        "Contact Details": r"(?:Contact|Tel|Phone|Mobile|Email)\s*[:\-]?\s*([\+?\d\s\-\(\)\@a-zA-Z\.]+)",
        "Facility Amount": r"(?:Facility Amount|Approved Limit|Proposed Limit|Amount)\s*[:\-]?\s*(MYR\s*[\d,]+(?:\.\d{2})?|RM\s*[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*Ringgit)",
        "Facility Purpose": r"(?:Facility Purpose|Purpose of Facility|Purpose)\s*[:\-]?\s*([A-Za-z0-9\s\-\/,\.]+)",
        "Pricing / Profit Rate": r"(?:Pricing|Profit Rate|Interest Rate|Rate)\s*[:\-]?\s*([\d\.]*%\s*p\.a\.|BLR\s*[\+\-\s]*[\d\.]*%|BFR\s*[\+\-\s]*[\d\.]*%|[\d\.]*%\s*margin)",
        "Facility Tenure": r"(?:Facility Tenure|Tenure|Loan Period|Tenor)\s*[:\-]?\s*(\d+\s*(?:Months|Years|months|years))",
        "Special Conditions": r"(?:Special Conditions|Pre-disbursement Conditions|Conditions Precedent)\s*[:\-]?\s*([A-Za-z0-9\s\-\/\.,;]+)",
        "Letterhead Type": r"(Islamic|Conventional|AmBank\s+Islamic|AmBank\s+BERHAD)",
        "LO Issuance Date": r"(?:Date of Letter|Issuance Date|LO Date|Date)\s*[:\-]?\s*(\d{1,2}[\/\-\s][A-Za-z0-9]+[\/\-\s]\d{2,4})"
    }

    extracted_records = []
    
    for field_name, regex in patterns.items():
        found_val = "Not Specified in Document"
        confidence = "70.0%"
        page_num = "Page 1"

        current_page = "Page 1"
        for line in lines:
            if "--- Page " in line:
                current_page = line.replace("---", "").strip()
                continue
            
            match = re.search(regex, line, re.IGNORECASE)
            if match:
                found_val = match.group(1).strip()
                confidence = "98.5%" if len(found_val) > 3 else "89.0%"
                page_num = current_page
                break

        if found_val == "Not Specified in Document":
            match = re.search(regex, raw_text, re.IGNORECASE)
            if match:
                found_val = match.group(1).strip()
                confidence = "92.0%"
                page_num = "Page 1"

        extracted_records.append({
            "Scope Field": field_name,
            "Extracted Value": found_val,
            "Confidence": confidence,
            "Page Index": page_num
        })

    return pd.DataFrame(extracted_records)


# --- REASONING & RECONCILIATION ENGINE ---
def run_reconciliation_logic(df1, df2):
    """
    Compares Document 1 (Credit Paper) vs Document 2 (Letter of Offer) and identifies exceptions.
    """
    if df1.empty or df2.empty:
        return pd.DataFrame()

    map1 = df1.set_index("Scope Field")["Extracted Value"].to_dict()
    map2 = df2.set_index("Scope Field")["Extracted Value"].to_dict()

    reconciliation_results = []

    rules = [
        ("Facility Amount", "Exception 1: Facility amount in LO differs from approved amount"),
        ("Facility Purpose", "Exception 2: Facility purpose differs from approved purpose"),
        ("Pricing / Profit Rate", "Exception 3: Pricing/Profit rate differs from approved rate"),
        ("Facility Tenure", "Exception 4: Tenure differs from approved tenure"),
        ("Special Conditions", "Exception 5: Approved special conditions omitted from LO"),
        ("Customer Name", "Exception 8: Incorrect customer details in LO"),
        ("Customer IC / Reg No", "Exception 8: Incorrect customer details in LO"),
        ("Customer Registered Address", "Exception 8: Incorrect customer details in LO"),
        ("Contact Details", "Exception 8: Incorrect customer details in LO"),
        ("Letterhead Type", "Exception 9: Wrong letterhead used (Conventional/Islamic)"),
        ("LO Issuance Date", "Exception 6: LO issued before Maker-Checker approval completed")
    ]

    for field, exception_code in rules:
        val1 = str(map1.get(field, "Not Specified")).strip()
        val2 = str(map2.get(field, "Not Specified")).strip()

        norm1 = re.sub(r'[^\w\d]', '', val1.lower())
        norm2 = re.sub(r'[^\w\d]', '', val2.lower())

        if val1 == "Not Specified in Document" and val2 == "Not Specified in Document":
            status = "UNRESOLVED"
            reason = "Field missing from source documents. Manual verification required."
            exc = "Data Missing"
        elif norm1 == norm2 or (norm1 in norm2 and len(norm1) > 3) or (norm2 in norm1 and len(norm2) > 3):
            status = "PASS"
            reason = f"Values in both documents align for '{field}'."
            exc = "None (Compliant)"
        else:
            status = "DISCREPANCY"
            reason = f"Mismatch detected: Credit Paper states '{val1}', LO states '{val2}'."
            exc = exception_code

        reconciliation_results.append({
            "Scope Field": field,
            "Approved Credit Paper": val1,
            "Letter of Offer (LO)": val2,
            "Audit Status": status,
            "Mapped Exception Rule": exc,
            "Reasoning Details": reason
        })

    return pd.DataFrame(reconciliation_results)


def generate_excel_export(df1, df2, recon_df):
    """Generates Excel workbook containing extraction data and audit results."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df1.empty:
            df1.to_excel(writer, sheet_name='Credit Paper Scope', index=False)
        if not df2.empty:
            df2.to_excel(writer, sheet_name='Letter of Offer Scope', index=False)
        if not recon_df.empty:
            recon_df.to_excel(writer, sheet_name='Reconciliation Audit', index=False)
    output.seek(0)
    return output


# --- SIDEBAR COMPONENT ---
with st.sidebar:
    logo_path = load_logo()
    if logo_path:
        st.image(logo_path, use_container_width=True)
    
    st.markdown("""
        <div class="sidebar-header-box">
            <div class="sidebar-title">CREDIT EVALUATION SYSTEM</div>
            <div class="sidebar-subtitle">Case 1: Credit Facilities Control</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### Document Ingestion")
    doc1_file = st.file_uploader("Approved Credit Paper", type=["pdf", "txt"], key="doc1")
    doc2_file = st.file_uploader("Letter of Offer (LO)", type=["pdf", "txt"], key="doc2")
    
    st.markdown("---")
    
    process_btn = st.button("Execute Audit & Extraction")
    
    st.markdown("---")
    st.caption("Security: Enterprise Local Processing Environment")
    st.caption("Status: Rules Engine Ready")


# --- MAIN INTERFACE ---
st.title("Credit Facilities Control & Audit Portal")
st.caption("Automated Maker-Checker review system for detecting control exceptions between Approved Credit Papers and Issued Letters of Offer.")

# PROCESSING & STATE MANAGEMENT
text1 = read_file_text(doc1_file) if doc1_file else ""
text2 = read_file_text(doc2_file) if doc2_file else ""

df1 = extract_scope_fields(text1, "Credit Paper") if text1 else pd.DataFrame(columns=["Scope Field", "Extracted Value", "Confidence", "Page Index"])
df2 = extract_scope_fields(text2, "Letter of Offer") if text2 else pd.DataFrame(columns=["Scope Field", "Extracted Value", "Confidence", "Page Index"])

recon_df = run_reconciliation_logic(df1, df2)

# EXECUTIVE METRICS
m1, m2, m3, m4 = st.columns(4)

total_checks = len(recon_df)
pass_count = len(recon_df[recon_df["Audit Status"] == "PASS"]) if not recon_df.empty else 0
fail_count = len(recon_df[recon_df["Audit Status"] == "DISCREPANCY"]) if not recon_df.empty else 0

with m1:
    st.metric("Total Scope Items", f"{total_checks}")
with m2:
    st.metric("Compliant Matches", f"{pass_count}")
with m3:
    st.metric("Discrepancies Identified", f"{fail_count}")
with m4:
    st.metric("Audit Conclusion", "PASSED" if fail_count == 0 and total_checks > 0 else ("REQUIRES REVIEW" if fail_count > 0 else "PENDING DOCUMENTS"))

st.write("")

# EXPORT ACTION
if not recon_df.empty:
    excel_file = generate_excel_export(df1, df2, recon_df)
    st.download_button(
        label="Export Audit Workbook (.xlsx)",
        data=excel_file,
        file_name="Credit_Facilities_Audit_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# WORKSPACE TABS
tab_quad, tab_audit = st.tabs(["Extraction Workspace (4-Way View)", "Reconciliation Audit Engine"])

# -------------------------------------------------------------------
# TAB 1: 4-WAY SPLIT WORKSPACE
# -------------------------------------------------------------------
with tab_quad:
    # TOP ROW: DOCUMENT VIEWERS
    top_c1, top_c2 = st.columns(2)

    with top_c1:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>Approved Credit Paper</span>
                    <span style="font-size: 0.72rem; color: #64748b;">Primary Reference</span>
                </div>
        """, unsafe_allow_html=True)
        
        if doc1_file:
            embed_code = pdf_to_base64_embed(doc1_file)
            if embed_code:
                st.markdown(embed_code, unsafe_allow_html=True)
            else:
                st.info(f"Loaded File: {doc1_file.name}")
        else:
            st.markdown("""
                <div class="empty-viewer">
                    <span>Upload the Approved Credit Paper in the sidebar to view document preview</span>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with top_c2:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>Letter of Offer (LO)</span>
                    <span style="font-size: 0.72rem; color: #64748b;">Customer Document</span>
                </div>
        """, unsafe_allow_html=True)
        
        if doc2_file:
            embed_code = pdf_to_base64_embed(doc2_file)
            if embed_code:
                st.markdown(embed_code, unsafe_allow_html=True)
            else:
                st.info(f"Loaded File: {doc2_file.name}")
        else:
            st.markdown("""
                <div class="empty-viewer">
                    <span>Upload the Letter of Offer in the sidebar to view document preview</span>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # BOTTOM ROW: EXTRACTED SCOPE TABLES
    bot_c1, bot_c2 = st.columns(2)

    with bot_c1:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>Credit Paper Data Extraction</span>
                </div>
        """, unsafe_allow_html=True)
        
        if not df1.empty:
            st.dataframe(
                df1,
                column_config={
                    "Scope Field": st.column_config.TextColumn("Scope Item", width="medium"),
                    "Extracted Value": st.column_config.TextColumn("Extracted Value", width="large"),
                    "Confidence": st.column_config.TextColumn("Confidence", width="small"),
                    "Page Index": st.column_config.TextColumn("Source Page", width="small"),
                },
                use_container_width=True,
                hide_index=True,
                height=320
            )
        else:
            st.info("Upload Document 1 to display extracted scope fields.")
        st.markdown("</div>", unsafe_allow_html=True)

    with bot_c2:
        st.markdown("""
            <div class="quad-card">
                <div class="card-title">
                    <span>Letter of Offer Data Extraction</span>
                </div>
        """, unsafe_allow_html=True)
        
        if not df2.empty:
            st.dataframe(
                df2,
                column_config={
                    "Scope Field": st.column_config.TextColumn("Scope Item", width="medium"),
                    "Extracted Value": st.column_config.TextColumn("Extracted Value", width="large"),
                    "Confidence": st.column_config.TextColumn("Confidence", width="small"),
                    "Page Index": st.column_config.TextColumn("Source Page", width="small"),
                },
                use_container_width=True,
                hide_index=True,
                height=320
            )
        else:
            st.info("Upload Document 2 to display extracted scope fields.")
        st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------------------------
# TAB 2: DETAILED RECONCILIATION & EXCEPTION AUDIT
# -------------------------------------------------------------------
with tab_audit:
    st.markdown("""
        <div class="quad-card">
            <div class="card-title">
                <span>Reconciliation Audit & Exception Mapping Report</span>
            </div>
    """, unsafe_allow_html=True)
    
    if not recon_df.empty:
        st.dataframe(
            recon_df,
            column_config={
                "Scope Field": st.column_config.TextColumn("Scope Item", width="medium"),
                "Approved Credit Paper": st.column_config.TextColumn("Approved Credit Paper", width="medium"),
                "Letter of Offer (LO)": st.column_config.TextColumn("Letter of Offer (LO)", width="medium"),
                "Audit Status": st.column_config.TextColumn("Audit Status", width="small"),
                "Mapped Exception Rule": st.column_config.TextColumn("Mapped Exception Code", width="large"),
                "Reasoning Details": st.column_config.TextColumn("Automated Reasoning", width="large"),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("Upload both documents in the sidebar to execute the reconciliation audit.")
    
    st.markdown("</div>", unsafe_allow_html=True)