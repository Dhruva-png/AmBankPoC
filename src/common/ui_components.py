from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

_STYLE = """
<style>
[data-testid="stMainBlockContainer"] {
    padding-top: 2.5rem;
}
[data-testid="stSidebarLogo"] {
    box-sizing: content-box;
    display: block;
    margin: 14px 16px 18px;
    padding: 12px 16px;
    background-color: #ffffff;
    border-radius: 10px;
}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child h3 {
    color: #ffffff;
    font-size: 1.02rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0;
}
[data-testid="stSidebarUserContent"] [data-testid="stCaptionContainer"] {
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.68rem;
    font-weight: 600;
    opacity: 0.6;
    margin-top: 0.1rem;
}
[data-testid="stSidebarUserContent"] [data-testid="stPageLink-NavLink"] {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 8px;
    transition: background-color 120ms ease;
}
[data-testid="stSidebarUserContent"] [data-testid="stPageLink-NavLink"]:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
[data-testid="stSidebarUserContent"] [data-testid="stPageLink-NavLink"] [data-testid="stMarkdownContainer"] p {
    color: rgba(255, 255, 255, 0.88);
    font-size: 0.9rem;
}
.st-key-navlink-current [data-testid="stPageLink-NavLink"] {
    background-color: rgba(91, 155, 255, 0.16);
    border-left: 3px solid #5B9BFF;
    padding-left: 9px;
}
.st-key-navlink-current [data-testid="stPageLink-NavLink"] [data-testid="stMarkdownContainer"] p {
    color: #ffffff;
    font-weight: 600;
}
[data-testid="stMetricValue"] {
    font-weight: 700;
}
[data-testid="stMetricLabel"] {
    opacity: 0.75;
}
</style>
"""

STATUS_BADGE_COLOR = {"PASS": "green", "FAIL": "red", "REVIEW": "orange", "N/A": "gray"}
STATUS_ICON = {
    "PASS": ":material/check_circle:",
    "FAIL": ":material/error:",
    "REVIEW": ":material/warning:",
    "N/A": ":material/remove_circle:",
}
SEVERITY_LABEL = {"FAIL": "High", "REVIEW": "Medium"}


def inject_style() -> None:
    st.markdown(_STYLE, unsafe_allow_html=True)


def render_logo(assets_dir: Path) -> None:
    for candidate in ("logo.png", "logo.jpg", "logo.jpeg"):
        path = assets_dir / candidate
        if path.exists():
            st.logo(str(path), size="large")
            return


def sidebar_brand(app_name: str, tagline: str) -> None:
    with st.sidebar:
        st.markdown(f"### {app_name}")
        st.caption(tagline)
        st.write("")


def sidebar_nav(pages: list, current_url_path: str) -> None:
    with st.sidebar:
        for page in pages:
            is_current = page.url_path == current_url_path
            key = "navlink-current" if is_current else f"navlink-{page.url_path or 'home'}"
            with st.container(key=key):
                st.page_link(page)


def status_badge(status: str) -> None:
    st.badge(status, color=STATUS_BADGE_COLOR.get(status, "gray"))


def confidence_text(score) -> str:
    return f"{score:.0f}%" if score is not None else "—"


def _preview(value: str, limit: int = 60) -> str:
    text = (value or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def selectable_table(df: pd.DataFrame, column_config: dict, key: str):
    if df.empty:
        return None
    event = st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_config=column_config,
    )
    if event and event.selection and event.selection.rows:
        return event.selection.rows[0]
    return 0


def results_dataframe(results, left_label: str = "Value A", right_label: str = "Value B") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "KCT": r.kct,
                "Check": r.check,
                "Status": r.status,
                "Confidence": r.confidence,
                left_label: _preview(r.left_value),
                right_label: _preview(r.right_value),
            }
            for r in results
        ]
    )


def results_table(results, key: str, left_label: str = "Value A", right_label: str = "Value B"):
    df = results_dataframe(results, left_label, right_label)
    column_config = {
        "KCT": st.column_config.TextColumn(width="small"),
        "Check": st.column_config.TextColumn(width="large"),
        "Status": st.column_config.TextColumn(width="small"),
        "Confidence": st.column_config.ProgressColumn(width="small", min_value=0, max_value=100, format="%.0f%%"),
        left_label: st.column_config.TextColumn(width="medium"),
        right_label: st.column_config.TextColumn(width="medium"),
    }
    return selectable_table(df, column_config, key)


def flagged_cases_table(df: pd.DataFrame, key: str):
    column_config = {
        "Case": st.column_config.TextColumn(width="medium"),
        "Recommendation": st.column_config.TextColumn(width="medium"),
        "Confidence": st.column_config.ProgressColumn(width="medium", min_value=0, max_value=100, format="%.0f%%"),
        "Findings": st.column_config.NumberColumn(width="small"),
    }
    return selectable_table(df, column_config, key)


def findings_table(df: pd.DataFrame, key: str):
    column_config = {
        "Severity": st.column_config.TextColumn(width="small"),
        "Title": st.column_config.TextColumn(width="large"),
        "Confidence": st.column_config.ProgressColumn(width="medium", min_value=0, max_value=100, format="%.0f%%"),
    }
    return selectable_table(df, column_config, key)


def status_banner(counts: dict, noun: str = "case") -> None:
    fail = counts.get("FAIL", 0)
    review = counts.get("REVIEW", 0)
    if fail:
        st.error(f"{fail} exception(s) raised on this {noun} — hold for review.", icon=":material/error:")
    elif review:
        st.warning(f"{review} item(s) flagged for manual review.", icon=":material/warning:")
    else:
        st.success(f"All controls passed for this {noun}.", icon=":material/check_circle:")


def document_chips(documents: list[dict]) -> None:
    with st.container(horizontal=True):
        for doc in documents:
            label = doc.get("label", "")
            st.badge(f"{label}: {doc['filename']}" if label else doc["filename"], icon=":material/description:")


def result_detail(r, left_label: str, right_label: str) -> None:
    icon = STATUS_ICON.get(r.status, ":material/help:")
    with st.container(border=True):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.markdown(f"{icon} **{r.kct} — {r.check}**")
            with st.container(horizontal=True):
                status_badge(r.status)
                st.caption(f"Confidence {confidence_text(r.confidence)}")
        st.write(r.note)
        col1, col2 = st.columns(2)
        with col1:
            st.caption(left_label.upper())
            st.write(r.left_value or "—")
            if r.source_left:
                st.caption(f":material/description: {r.source_left}")
        with col2:
            st.caption(right_label.upper())
            st.write(r.right_value or "—")
            if r.source_right:
                st.caption(f":material/description: {r.source_right}")
