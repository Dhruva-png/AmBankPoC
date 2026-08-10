from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import case_store
import charts
import excel_export
import ui_components as ui


def render_dashboard(case_type: str, module_name: str) -> None:
    st.title(f":material/dashboard: {module_name} dashboard")
    st.caption(f"Overview of {module_name.lower()} control testing")

    df = case_store.list_cases(case_type)
    total = len(df)
    flagged = int(df["flagged"].sum()) if total else 0

    with st.container(horizontal=True):
        st.metric("Total cases", total, border=True)
        st.metric("Flagged", flagged, border=True, delta=None if not flagged else f"{flagged} need review", delta_color="inverse")
        st.metric("Clean", total - flagged, border=True)
        st.metric(
            "Avg. processing time",
            f"{df['processing_seconds'].mean():.1f}s" if total else "—",
            border=True,
        )

    if not df.empty:
        st.download_button(
            "Download consolidated workbook",
            data=excel_export.build_consolidated_workbook(case_type, module_name),
            file_name=f"{case_type}_consolidated_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
        )

    if total == 0:
        st.info("No cases processed yet. Go to **Cases** to start one.", icon=":material/info:")
        return

    counts = {
        "PASS": int(df["pass_count"].sum()),
        "FAIL": int(df["fail_count"].sum()),
        "REVIEW": int(df["review_count"].sum()),
        "N/A": int(df["na_count"].sum()),
    }
    flat = charts.flatten_results(df)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Check status distribution")
            st.plotly_chart(charts.status_distribution_chart(counts), use_container_width=True)
    with col2:
        with st.container(border=True):
            st.subheader("Cases processed over time")
            st.plotly_chart(charts.cases_over_time_chart(df), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.subheader("Most frequent exceptions")
            st.plotly_chart(charts.top_exceptions_chart(flat), use_container_width=True)
    with col4:
        with st.container(border=True):
            st.subheader("AI confidence distribution")
            st.plotly_chart(charts.confidence_histogram(flat), use_container_width=True)


def render_cases_list(case_type: str, module_name: str, case_detail_page: str) -> None:
    st.title(f":material/folder_open: Cases")
    st.caption(f"Every {module_name.lower()} case processed by this module")

    with st.container(horizontal=True):
        if st.button("New case", icon=":material/add:", type="primary"):
            st.session_state["selected_case_id"] = None
            st.switch_page(case_detail_page)

    df = case_store.list_cases(case_type)
    with st.container(border=True):
        st.subheader(f"All cases ({len(df)})")
        if df.empty:
            st.caption("No cases yet. Click **New case** to run your first control test.")
            return

        for _, row in df.iterrows():
            doc_count = len(json.loads(row["documents"]))
            with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", border=True):
                info = st.container(gap=None)
                with info:
                    st.markdown(f"**{row['case_id']}**")
                    st.caption(f"{row['created_at']} · {doc_count} document(s)")

                st.badge(
                    "FLAGGED" if row["flagged"] else "CLEAR",
                    color="red" if row["flagged"] else "green",
                )
                st.caption(f"{row['pass_count']} pass · {row['fail_count']} fail · {row['review_count']} review")

                if st.button("Open", key=f"open_{row['case_id']}", icon=":material/arrow_forward:"):
                    st.session_state["selected_case_id"] = row["case_id"]
                    st.switch_page(case_detail_page)


def render_case_results(
    case_id: str,
    documents: list[dict],
    results: list,
    remarks: str,
    processing_seconds: float,
    processed_at: str,
    module_name: str,
    left_label: str,
    right_label: str,
    markdown_report: str,
) -> None:
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "FAIL", "REVIEW", "N/A")}

    with st.container(horizontal=True):
        st.metric("Case ID", case_id, border=True)
        st.metric("Pass", counts["PASS"], border=True)
        st.metric("Fail", counts["FAIL"], border=True, delta=None if not counts["FAIL"] else "exceptions", delta_color="inverse")
        st.metric("Review", counts["REVIEW"], border=True)
        st.metric("N/A", counts["N/A"], border=True)

    with st.container(border=True):
        st.subheader("AI remarks")
        st.write(remarks)

    with st.container(border=True):
        st.subheader("Control checklist")
        st.caption("Select a row to view full evidence, sourcing and reasoning for that control.")
        idx = ui.results_table(results, key=f"{case_id}_grid")
        if idx is not None:
            ui.result_detail(results[idx], left_label, right_label)

    st.subheader("Export")
    overall_status = "FLAGGED" if (counts["FAIL"] or counts["REVIEW"]) else "CLEAR"
    with st.container(horizontal=True):
        st.download_button(
            "Excel workbook",
            excel_export.build_workbook(
                case_meta={
                    "title": f"{module_name} Control Testing Report",
                    "case_id": case_id,
                    "module": module_name,
                    "processed_at": processed_at,
                    "processing_time": f"{processing_seconds:.1f}s",
                    "documents": ", ".join(d["filename"] for d in documents),
                    "overall_status": overall_status,
                },
                results=results,
                remarks=remarks,
                left_label=left_label,
                right_label=right_label,
            ),
            file_name=f"{case_id}-report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
        )
        st.download_button("Markdown report", markdown_report, file_name=f"{case_id}-report.md", icon=":material/description:")


def render_reports(case_type: str, module_name: str, exceptions: list[tuple[str, str, str]]) -> None:
    st.title(f":material/summarize: Reports")
    st.caption(f"{module_name} exception catalogue and cross-case findings")

    df = case_store.list_cases(case_type)
    flat = charts.flatten_results(df) if not df.empty else pd.DataFrame()

    with st.container(border=True):
        st.subheader("Exception catalogue")
        st.caption("The control exceptions this module screens for.")
        st.dataframe(
            pd.DataFrame(exceptions, columns=["No.", "Exception", "KCT Reference"]),
            hide_index=True,
            width="stretch",
        )

    if flat.empty:
        st.info("No cases processed yet - exception frequency will appear here once cases have been run.", icon=":material/info:")
        return

    exception_rows = flat[flat["status"].isin(["FAIL", "REVIEW"])]
    with st.container(border=True):
        st.subheader("Exception frequency across all cases")
        if exception_rows.empty:
            st.caption("No exceptions have been raised across any processed case.")
        else:
            summary = (
                exception_rows.groupby(["kct"])
                .agg(occurrences=("case_id", "count"), avg_confidence=("confidence", "mean"))
                .reset_index()
                .sort_values("occurrences", ascending=False)
                .rename(columns={"kct": "KCT"})
            )
            st.dataframe(
                summary,
                hide_index=True,
                width="stretch",
                column_config={
                    "occurrences": st.column_config.NumberColumn("Occurrences"),
                    "avg_confidence": st.column_config.ProgressColumn("Avg. confidence", min_value=0, max_value=100, format="%.0f%%"),
                },
            )
