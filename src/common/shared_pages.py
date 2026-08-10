from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import case_store
import charts
import excel_export
import groq_client
import ui_components as ui


def _module_stats(df: pd.DataFrame, flat: pd.DataFrame) -> dict:
    total_cases = len(df)
    flagged_cases = int(df["flagged"].sum()) if total_cases else 0
    exceptions = flat[flat["status"].isin(["FAIL", "REVIEW"])]
    if not exceptions.empty:
        top = exceptions.groupby(["kct", "check"]).size().sort_values(ascending=False).head(3)
        top_exceptions = "; ".join(f"{check} ({count} occurrence(s))" for (_, check), count in top.items())
    else:
        top_exceptions = "none"
    scored = flat["confidence"].dropna()
    avg_confidence = f"{scored.mean():.0f}%" if len(scored) else "n/a"
    return {
        "total_cases": total_cases,
        "flagged_cases": flagged_cases,
        "clean_cases": total_cases - flagged_cases,
        "total_findings": int(len(exceptions)),
        "top_exceptions": top_exceptions,
        "avg_confidence": avg_confidence,
    }


def _case_findings_summary(df: pd.DataFrame, flat: pd.DataFrame) -> pd.DataFrame:
    flagged = df[df["flagged"] == 1]
    rows = []
    for _, case in flagged.iterrows():
        case_findings = flat[(flat["case_id"] == case["case_id"]) & (flat["status"].isin(["FAIL", "REVIEW"]))]
        if case_findings.empty:
            continue
        confidences = case_findings["confidence"].dropna()
        recommendation = "Hold for review" if (case_findings["status"] == "FAIL").any() else "Manual review required"
        rows.append(
            {
                "Case": case["case_id"],
                "Recommendation": recommendation,
                "Confidence": float(confidences.mean()) if not confidences.empty else None,
                "Findings": int(len(case_findings)),
            }
        )
    return pd.DataFrame(rows, columns=["Case", "Recommendation", "Confidence", "Findings"])


def render_dashboard(case_type: str, module_name: str, case_detail_page: str) -> None:
    st.title(f":material/dashboard: {module_name} dashboard")
    st.caption(f"Overview of {module_name.lower()} control testing")

    df = case_store.list_cases(case_type)
    flat = charts.flatten_results(df)
    total = len(df)
    flagged = int(df["flagged"].sum()) if total else 0
    documents_processed = int(df["documents"].apply(lambda d: len(json.loads(d))).sum()) if total else 0
    total_findings = int(flat[flat["status"].isin(["FAIL", "REVIEW"])].shape[0])

    with st.container(horizontal=True):
        st.metric("Total cases", total, border=True)
        st.metric("Documents processed", documents_processed, border=True)
        st.metric(
            "Flagged cases",
            flagged,
            border=True,
            delta=None if not flagged else f"{flagged} need review",
            delta_color="inverse",
        )
        st.metric("Clean cases", total - flagged, border=True)
        st.metric("Total exceptions raised", total_findings, border=True)

    stats = _module_stats(df, flat)
    with st.container(horizontal=True):
        if st.button("Generate / regenerate final report", icon=":material/refresh:", key=f"{case_type}_dash_gen"):
            with st.spinner("Synthesizing executive summary..."):
                st.session_state[f"module_summary_{case_type}"] = groq_client.generate_module_summary(stats, module_name)
        if not df.empty:
            st.download_button(
                "Download consolidated Excel",
                data=excel_export.build_consolidated_workbook(case_type, module_name),
                file_name=f"{case_type}_consolidated_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
            )

    tab_overview, tab_review, tab_final = st.tabs(["Overview", "Cases Requiring Review", "Final Report"])

    with tab_overview:
        if total == 0:
            st.info("No cases processed yet. Go to **Cases** to start one.", icon=":material/info:")
        else:
            counts = {
                "PASS": int(df["pass_count"].sum()),
                "FAIL": int(df["fail_count"].sum()),
                "REVIEW": int(df["review_count"].sum()),
                "N/A": int(df["na_count"].sum()),
            }
            col1, col2 = st.columns(2)
            with col1:
                with st.container(border=True):
                    st.plotly_chart(charts.status_distribution_chart(counts), use_container_width=True)
            with col2:
                with st.container(border=True):
                    st.plotly_chart(charts.cases_over_time_chart(df), use_container_width=True)
            col3, col4 = st.columns(2)
            with col3:
                with st.container(border=True):
                    st.plotly_chart(charts.top_exceptions_chart(flat), use_container_width=True)
            with col4:
                with st.container(border=True):
                    st.plotly_chart(charts.confidence_histogram(flat), use_container_width=True)

    with tab_review:
        st.caption("Cases with at least one FAIL or REVIEW finding.")
        review_df = df[df["flagged"] == 1] if total else df
        if review_df.empty:
            st.caption("No cases currently need review.")
        else:
            for _, row in review_df.iterrows():
                with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", border=True):
                    info = st.container(gap=None)
                    with info:
                        st.markdown(f"**{row['case_id']}**")
                        st.caption(row["created_at"])
                    st.caption(f"{row['fail_count']} fail · {row['review_count']} review")
                    if st.button("Open", key=f"review_open_{row['case_id']}", icon=":material/arrow_forward:"):
                        st.session_state["selected_case_id"] = row["case_id"]
                        st.switch_page(case_detail_page)

    with tab_final:
        st.caption("AI-generated executive summary synthesizing every case processed by this module.")
        summary = st.session_state.get(f"module_summary_{case_type}")
        if summary:
            st.write(summary)
        else:
            st.info(
                "No report has been generated yet. Click **Generate / regenerate final report** above.",
                icon=":material/info:",
            )
        if stats["total_cases"]:
            st.divider()
            st.caption(
                f"Based on {stats['total_cases']} case(s) · {stats['flagged_cases']} flagged · "
                f"{stats['total_findings']} exception(s) raised · avg. confidence {stats['avg_confidence']}."
            )


def render_cases_list(case_type: str, module_name: str, case_detail_page: str) -> None:
    st.title(":material/folder_open: Cases")
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

    ui.status_banner(counts)

    with st.container(horizontal=True):
        st.metric("Case ID", case_id, border=True)
        st.metric("Pass", counts["PASS"], border=True)
        st.metric("Fail", counts["FAIL"], border=True, delta=None if not counts["FAIL"] else "exceptions", delta_color="inverse")
        st.metric("Review", counts["REVIEW"], border=True)
        st.metric("N/A", counts["N/A"], border=True)

    with st.container(border=True):
        st.subheader(f"Documents ({len(documents)})")
        ui.document_chips(documents)

    with st.container(border=True):
        st.subheader("AI remarks")
        st.write(remarks)

    with st.container(border=True):
        st.subheader("Control checklist")
        st.caption(
            "Every control check in one table, sortable by clicking a column header — "
            "select a row to see its full evidence, sourcing and reasoning."
        )
        idx = ui.results_table(results, key=f"{case_id}_grid", left_label=left_label, right_label=right_label)
        if idx is not None:
            ui.result_detail(results[idx], left_label, right_label)
        else:
            st.caption("Select a row above to see its full detail.")

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


def render_reports(
    case_type: str,
    module_name: str,
    exceptions: list[tuple[str, str, str]],
    left_label: str,
    right_label: str,
) -> None:
    st.title(":material/summarize: Reports")
    st.caption(f"{module_name} executive summary and cross-case findings")

    df = case_store.list_cases(case_type)
    flat = charts.flatten_results(df)
    stats = _module_stats(df, flat)
    high_severity = int((flat["status"] == "FAIL").sum())

    with st.container(horizontal=True):
        st.metric("Cases analyzed", stats["total_cases"], border=True)
        st.metric("Cases flagged", stats["flagged_cases"], border=True)
        st.metric("Total findings", stats["total_findings"], border=True)
        st.metric("High severity", high_severity, border=True)

    with st.container(border=True):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.subheader("Executive summary")
            if st.button("Generate / regenerate report", icon=":material/refresh:", key=f"{case_type}_reports_gen"):
                with st.spinner("Synthesizing executive summary..."):
                    st.session_state[f"module_summary_{case_type}"] = groq_client.generate_module_summary(stats, module_name)
                st.rerun()
        summary = st.session_state.get(f"module_summary_{case_type}")
        if summary:
            st.write(summary)
        else:
            st.info(
                "No report has been generated yet. Run control testing from **Cases**, then generate this report.",
                icon=":material/info:",
            )

    case_summary = _case_findings_summary(df, flat)
    with st.container(border=True):
        st.subheader(f"Flagged cases ({len(case_summary)})")
        if case_summary.empty:
            st.caption("No cases currently have exceptions.")
        else:
            st.caption("Select a case for its findings, sorted by severity — then select a finding for its full detail.")
            c_idx = ui.flagged_cases_table(case_summary, key=f"{case_type}_flagged_cases")
            if c_idx is not None:
                case_id = case_summary.iloc[c_idx]["Case"]
                case_findings = (
                    flat[(flat["case_id"] == case_id) & (flat["status"].isin(["FAIL", "REVIEW"]))]
                    .sort_values("status")
                    .reset_index(drop=True)
                )
                n_high = int((case_findings["status"] == "FAIL").sum())
                n_medium = int((case_findings["status"] == "REVIEW").sum())
                most_significant = case_findings.iloc[0]["check"] if not case_findings.empty else ""
                st.caption(
                    f"{len(case_findings)} finding(s) identified ({n_high} high-severity, {n_medium} medium-severity). "
                    f'Most significant: "{most_significant}".'
                )
                findings_display = pd.DataFrame(
                    {
                        "Severity": case_findings["status"].map(ui.SEVERITY_LABEL),
                        "Title": case_findings["kct"] + " — " + case_findings["check"],
                        "Confidence": case_findings["confidence"],
                    }
                )
                f_idx = ui.findings_table(findings_display, key=f"{case_type}_findings_{case_id}")
                if f_idx is not None:
                    ui.result_detail(case_findings.iloc[f_idx], left_label, right_label)

    with st.expander("Exception catalogue (reference)"):
        st.caption("The control exceptions this module screens for.")
        st.dataframe(
            pd.DataFrame(exceptions, columns=["No.", "Exception", "KCT Reference"]),
            hide_index=True,
            width="stretch",
        )
