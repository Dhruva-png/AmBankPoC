from __future__ import annotations

import json

import streamlit as st

import case_store
import charts
import ui_components as ui


def render_dashboard(case_type: str, module_name: str) -> None:
    ui.breadcrumb("AmBank Internal Audit", module_name, "Dashboard")
    ui.page_header(
        "Dashboard",
        f"Aggregate view across every {module_name} case processed by this module.",
    )

    df = case_store.list_cases(case_type)

    total = len(df)
    flagged = int(df["flagged"].sum()) if total else 0
    clean = total - flagged
    avg_seconds = df["processing_seconds"].mean() if total else 0

    ui.section_header("Key Metrics")
    ui.stat_strip([
        ("Total Cases", str(total)),
        ("Flagged", str(flagged)),
        ("Clean", str(clean)),
        ("Avg. Processing Time", f"{avg_seconds:.1f}s" if total else "—"),
    ])

    if total == 0:
        st.info("No cases have been processed yet. Run a control test to populate the dashboard.")
        return

    counts = {
        "PASS": int(df["pass_count"].sum()),
        "FAIL": int(df["fail_count"].sum()),
        "REVIEW": int(df["review_count"].sum()),
        "N/A": int(df["na_count"].sum()),
    }
    flat = charts.flatten_results(df)

    ui.section_header("Trends")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.status_distribution_chart(counts), use_container_width=True)
    with col2:
        st.plotly_chart(charts.cases_over_time_chart(df), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(charts.top_exceptions_chart(flat), use_container_width=True)
    with col4:
        st.plotly_chart(charts.confidence_histogram(flat), use_container_width=True)


def render_case_manager(case_type: str, module_name: str, left_label: str, right_label: str) -> None:
    ui.breadcrumb("AmBank Internal Audit", module_name, "Case Manager")
    ui.page_header(
        "Case Manager",
        "Every case processed by this module: unique case ID, when it ran, documents supplied, "
        "and whether anything was flagged for review.",
    )

    df = case_store.list_cases(case_type)
    if df.empty:
        st.info("No cases have been processed yet.")
        return

    view = df.copy()
    view["Documents"] = view["documents"].apply(lambda raw: f"{len(json.loads(raw))} files")
    view["Flagged"] = view["flagged"].map({1: "FLAGGED", 0: "CLEAR"})
    view = view.rename(
        columns={
            "case_id": "Case ID",
            "created_at": "Processed At",
            "pass_count": "Pass",
            "fail_count": "Fail",
            "review_count": "Review",
            "na_count": "N/A",
            "processing_seconds": "Seconds",
        }
    )
    display_cols = ["Case ID", "Processed At", "Documents", "Flagged", "Pass", "Fail", "Review", "N/A", "Seconds"]
    view = view[display_cols]

    def _flag_color(val):
        return "color:#B3261E;font-weight:700;" if val == "FLAGGED" else "color:#146C3A;font-weight:700;"

    styled = view.style.map(_flag_color, subset=["Flagged"])
    ui.section_header("Case Register")
    event = st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"{case_type}_case_manager_grid",
    )
    idx = event.selection.rows[0] if (event and event.selection and event.selection.rows) else 0

    case_id = view.iloc[idx]["Case ID"]
    case = case_store.get_case(case_id)
    if not case:
        return

    ui.section_header(f"Case Detail — {case_id}")
    doc_list = ", ".join(d.get("filename", d.get("label", "")) for d in case["documents"])
    if case["fail_count"] > 0:
        overall_status = "FAIL"
    elif case["review_count"] > 0:
        overall_status = "REVIEW"
    else:
        overall_status = "PASS"
    st.markdown(
        f"""
        <div class="panel">
            <div class="detail-grid">
                <div>
                    <div class="detail-col-label">Case ID</div>
                    <div class="detail-col-value">{case['case_id']}</div>
                </div>
                <div>
                    <div class="detail-col-label">Processed At</div>
                    <div class="detail-col-value">{case['created_at']}</div>
                </div>
                <div>
                    <div class="detail-col-label">Documents Supplied</div>
                    <div class="detail-col-value">{doc_list}</div>
                </div>
                <div>
                    <div class="detail-col-label">Status</div>
                    <div class="detail-col-value">{ui.status_chip(overall_status)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if case.get("remarks"):
        ui.section_header("AI Remarks")
        st.markdown(f'<div class="detail-note">{case["remarks"]}</div>', unsafe_allow_html=True)

    ui.section_header("Checklist")
    results = case["results"]
    sub_idx = ui.results_grid(results, key=f"{case_id}_grid")
    if sub_idx is not None:
        ui.detail_panel(results[sub_idx], left_label, right_label)
