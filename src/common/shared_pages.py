from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import ai_client
import case_store
import charts
import document_preview
import excel_export
import ui_components as ui


@st.cache_data(show_spinner="Rendering document preview...")
def _rendered_pages(path: str, out_dir: str) -> list[str]:
    try:
        return document_preview.render_document_pages(path, out_dir)
    except Exception:
        return []


def _document_field_rows(results, side: str) -> pd.DataFrame:
    value_attr, source_attr = f"{side}_value", f"source_{side}"
    rows = [
        {
            "Field": ui.short_label(r.check),
            "Value": getattr(r, value_attr) or "—",
            "Confidence": r.confidence,
            "Source": getattr(r, source_attr) or "—",
        }
        for r in results
    ]
    return pd.DataFrame(rows, columns=["Field", "Value", "Confidence", "Source"])


def _document_field_rows_for_file(results, filename: str) -> pd.DataFrame:
    rows = []
    for r in results:
        if r.source_left and filename in r.source_left:
            rows.append(
                {"Field": ui.short_label(r.check), "Value": r.left_value or "—", "Confidence": r.confidence, "Source": r.source_left}
            )
        if r.source_right and filename in r.source_right:
            rows.append(
                {"Field": ui.short_label(r.check), "Value": r.right_value or "—", "Confidence": r.confidence, "Source": r.source_right}
            )
    return pd.DataFrame(rows, columns=["Field", "Value", "Confidence", "Source"])


def _render_document_extraction(case_id: str, documents: list[dict], results) -> None:
    render_root = str(case_store.document_dir(case_id) / "_pages")
    st.subheader("Document extraction")

    if len(documents) == 2:
        preview_cols = st.columns(2)
        for col, doc in zip(preview_cols, documents):
            with col:
                path = case_store.document_path(case_id, doc["filename"])
                pages = _rendered_pages(str(path), render_root) if path else []
                ui.document_preview_panel(doc.get("label", ""), doc["filename"], pages, key=f"{case_id}_{doc['filename']}_preview")
        data_cols = st.columns(2)
        for col, doc, side in zip(data_cols, documents, ("left", "right")):
            with col:
                st.caption(doc.get("label", ""))
                ui.field_extraction_table(_document_field_rows(results, side), key=f"{case_id}_{side}_fields")
    else:
        tabs = st.tabs([d.get("label", d["filename"]) for d in documents])
        for tab, doc in zip(tabs, documents):
            with tab:
                path = case_store.document_path(case_id, doc["filename"])
                pages = _rendered_pages(str(path), render_root) if path else []
                col1, col2 = st.columns(2)
                with col1:
                    ui.document_preview_panel(doc.get("label", ""), doc["filename"], pages, key=f"{case_id}_{doc['filename']}_preview")
                with col2:
                    ui.field_extraction_table(
                        _document_field_rows_for_file(results, doc["filename"]), key=f"{case_id}_{doc['filename']}_fields"
                    )


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
                st.session_state[f"module_summary_{case_type}"] = ai_client.generate_module_summary(stats, module_name)
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


_CASE_STATUS_EMOJI = {"complete": "\U0001F7E2", "needs_review": "\U0001F7E0", "error": "\U0001F534"}


def _case_management_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        documents = json.loads(row["documents"])
        try:
            completed = datetime.fromisoformat(row["created_at"])
            uploaded = completed - pd.Timedelta(seconds=row["processing_seconds"] or 0)
            uploaded_text, completed_text = uploaded.strftime("%Y-%m-%d %H:%M"), completed.strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            uploaded_text = completed_text = row["created_at"]
        status = row.get("status") or ("needs_review" if row["flagged"] else "complete")
        rows.append(
            {
                "Case ID": row["case_id"],
                "Customer": row.get("customer_name") or "—",
                "File Name": ", ".join(d["filename"] for d in documents) or "—",
                "Uploaded": uploaded_text,
                "Completed": completed_text,
                "Processing Time": ui.format_duration(row["processing_seconds"]),
                "Status": f"{_CASE_STATUS_EMOJI.get(status, '')} {ui.CASE_STATUS_LABEL.get(status, status)}",
                "Accuracy": ui.accuracy_text(row.get("accuracy")),
            }
        )
    return pd.DataFrame(
        rows, columns=["Case ID", "Customer", "File Name", "Uploaded", "Completed", "Processing Time", "Status", "Accuracy"]
    )


def render_cases_list(case_type: str, module_name: str, case_detail_page: str) -> None:
    st.title(":material/folder_open: Case Management")
    st.caption("Monitor and review every processed case.")

    with st.container(horizontal=True):
        if st.button("New case", icon=":material/add:", type="primary"):
            st.session_state["selected_case_id"] = None
            st.switch_page(case_detail_page)

    df = case_store.list_cases(case_type)
    if df.empty:
        with st.container(border=True):
            st.caption(f"No {module_name.lower()} cases yet. Click **New case** to run your first control test.")
        return

    display = _case_management_dataframe(df)

    toolbar = st.columns([1, 2, 1], vertical_alignment="bottom")
    with toolbar[0]:
        show_n = st.selectbox("Show entries", [10, 25, 50, "All"], key=f"{case_type}_show_n")
    with toolbar[1]:
        search = st.text_input(
            "Search cases", key=f"{case_type}_search", label_visibility="collapsed",
            placeholder="Search by case ID, customer, or file name...",
        )
    with toolbar[2]:
        export_scope = st.session_state.get(f"{case_type}_export_scope", [])
        export_ids = export_scope or df["case_id"].tolist()
        st.download_button(
            f"Excel ({'selected' if export_scope else 'all'})",
            data=excel_export.build_consolidated_workbook(case_type, module_name, case_ids=export_ids),
            file_name=f"{case_type}_cases_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
        )

    if search:
        mask = (
            display["Case ID"].str.contains(search, case=False, na=False)
            | display["Customer"].str.contains(search, case=False, na=False)
            | display["File Name"].str.contains(search, case=False, na=False)
        )
        display = display[mask].reset_index(drop=True)

    total_matches = len(display)
    if show_n != "All":
        display = display.head(int(show_n))

    with st.container(border=True):
        event = st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="multi-row",
            key=f"{case_type}_case_table",
            column_config={
                "Case ID": st.column_config.TextColumn(width="medium"),
                "Customer": st.column_config.TextColumn(width="medium"),
                "File Name": st.column_config.TextColumn(width="large"),
                "Uploaded": st.column_config.TextColumn(width="small"),
                "Completed": st.column_config.TextColumn(width="small"),
                "Processing Time": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="small"),
                "Accuracy": st.column_config.TextColumn(width="small"),
            },
        )
        st.caption(f"Showing {len(display)} of {total_matches} case(s).")

        selected_rows = event.selection.rows if event and event.selection else []
        selected_ids = [display.iloc[i]["Case ID"] for i in selected_rows]
        st.session_state[f"{case_type}_export_scope"] = selected_ids

        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button("Open", key=f"{case_type}_open_selected", icon=":material/arrow_forward:", disabled=len(selected_ids) != 1):
                st.session_state["selected_case_id"] = selected_ids[0]
                st.switch_page(case_detail_page)
        with action_cols[1]:
            confirm_key = f"{case_type}_confirm_bulk_delete"
            if not st.session_state.get(confirm_key):
                if st.button(
                    f"Delete{f' ({len(selected_ids)})' if selected_ids else ''}",
                    key=f"{case_type}_delete_selected", icon=":material/delete:", disabled=not selected_ids,
                ):
                    st.session_state[confirm_key] = True
                    st.rerun()
            else:
                with st.container(horizontal=True):
                    if st.button(f"Confirm delete ({len(selected_ids)})", key=f"{case_type}_confirm_delete", type="primary", icon=":material/delete_forever:"):
                        for cid in selected_ids:
                            case_store.delete_case(cid)
                        st.session_state.pop(confirm_key, None)
                        st.toast(f"Deleted {len(selected_ids)} case(s)", icon=":material/delete:")
                        st.rerun()
                    if st.button("Cancel", key=f"{case_type}_cancel_delete", type="tertiary"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()


def render_case_actions(case_id: str, back_page: str) -> None:
    confirm_key = f"confirm_delete_detail_{case_id}"
    with st.container(horizontal=True):
        if st.button("← Back to cases", type="tertiary", key=f"back_{case_id}"):
            st.switch_page(back_page)
        if st.session_state.get(confirm_key):
            st.caption("Delete this case permanently?")
            if st.button("Confirm delete", key=f"confirm_detail_{case_id}", icon=":material/delete_forever:", type="primary"):
                case_store.delete_case(case_id)
                st.session_state.pop(confirm_key, None)
                st.session_state["selected_case_id"] = None
                st.toast(f"Case {case_id} deleted", icon=":material/delete:")
                st.switch_page(back_page)
            if st.button("Cancel", key=f"cancel_detail_{case_id}", type="tertiary"):
                st.session_state.pop(confirm_key, None)
                st.rerun()
        else:
            if st.button("Delete case", key=f"delete_detail_{case_id}", icon=":material/delete:", type="tertiary"):
                st.session_state[confirm_key] = True
                st.rerun()


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
    case_status: str = "",
    error_message: str = "",
) -> None:
    if case_status == case_store.STATUS_ERROR:
        st.error(f"Processing failed for {case_id} -- no results were produced.", icon=":material/error:")
        with st.container(border=True):
            st.subheader("Error detail")
            st.write(error_message or "Unknown error.")
        if documents:
            with st.container(border=True):
                st.subheader(f"Documents supplied ({len(documents)})")
                ui.document_chips(documents)
        return

    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "FAIL", "REVIEW", "N/A")}
    status = case_status or (case_store.STATUS_NEEDS_REVIEW if (counts["FAIL"] or counts["REVIEW"]) else case_store.STATUS_COMPLETE)
    applicable = counts["PASS"] + counts["FAIL"] + counts["REVIEW"]
    accuracy = round(counts["PASS"] / applicable * 100, 1) if applicable else 100.0

    ui.status_banner(counts)

    with st.container(horizontal=True):
        st.metric("Case ID", case_id, border=True)
        st.metric("Accuracy", ui.accuracy_text(accuracy), border=True)
        st.metric("Pass", counts["PASS"], border=True)
        st.metric("Fail", counts["FAIL"], border=True, delta=None if not counts["FAIL"] else "exceptions", delta_color="inverse")
        st.metric("Review", counts["REVIEW"], border=True)

    with st.container(border=True):
        st.subheader(f"Documents ({len(documents)})")
        ui.document_chips(documents)

    with st.container(border=True):
        _render_document_extraction(case_id, documents, results)

    with st.container(border=True):
        st.subheader("Validation")
        st.caption(f"Every control check for this case -- {left_label} vs {right_label}. Check a row for full detail.")
        ui.validation_table(results, key=f"{case_id}_validation", left_label=left_label, right_label=right_label)

    with st.container(border=True):
        st.subheader("AI Recommendations")
        ui.ai_summary(remarks)

    st.subheader("Export")
    with st.container(horizontal=True):
        st.download_button(
            "Excel workbook",
            excel_export.build_workbook(
                case_meta={
                    "title": f"{module_name} Control Testing Report",
                    "case_id": case_id,
                    "module": module_name,
                    "processed_at": processed_at,
                    "processing_time": ui.format_duration(processing_seconds),
                    "documents": ", ".join(d["filename"] for d in documents),
                    "overall_status": ui.CASE_STATUS_LABEL.get(status, status),
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
                    st.session_state[f"module_summary_{case_type}"] = ai_client.generate_module_summary(stats, module_name)
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
            st.caption("Select a case, then a finding, for full detail.")
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
                st.caption(f"{len(case_findings)} finding(s) — {n_high} high, {n_medium} medium.")
                findings_display = pd.DataFrame(
                    {
                        "Severity": case_findings["status"].map(ui.SEVERITY_LABEL),
                        "Title": case_findings["kct"] + " — " + case_findings["check"].apply(ui.short_label),
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
