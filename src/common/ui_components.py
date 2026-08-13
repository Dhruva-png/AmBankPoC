from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from check_result import clean_source_text

_TEMP_FILENAME_RE = re.compile(r"^tmp[a-z0-9_]{6,}\.\w+$", re.IGNORECASE)


def clean_filename(filename: str, label: str = "") -> str:
    """Cases created before uploads preserved their real filename have a random tempfile
    name (e.g. tmpui1exf2z.pdf) baked into stored data -- show the document's label instead
    of that meaningless string. The real name is unrecoverable at this point, so this is a
    display-only fallback, not a data fix."""
    if filename and _TEMP_FILENAME_RE.match(filename):
        return label or "Document"
    return filename

_STYLE = """
<style>
[data-testid="stMainBlockContainer"] {
    padding-top: 2.5rem;
}
[data-testid="stSidebarHeader"] {
    height: auto !important;
    min-height: auto !important;
}
[data-testid="stSidebarLogo"] {
    box-sizing: content-box;
    display: block;
    margin: 10px 16px 14px;
    padding: 10px 14px;
    background-color: #ffffff;
    border-radius: 10px;
    height: 56px !important;
    width: auto !important;
    max-width: calc(100% - 28px);
    object-fit: contain;
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

CASE_STATUS_LABEL = {"complete": "Complete", "needs_review": "Needs Review", "error": "Error"}
CASE_STATUS_COLOR = {"complete": "green", "needs_review": "orange", "error": "red"}
CASE_STATUS_ROW_BG = {"complete": "#E7F6ED", "needs_review": "#FBF1DE", "error": "#FCEAE9"}


def format_duration(seconds) -> str:
    total = int(seconds or 0)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def accuracy_text(value) -> str:
    return f"{value:.0f}%" if value is not None and not pd.isna(value) else "—"

# Full check descriptions (used in Excel/markdown exports and the detail panel) are
# too long for compact on-screen tables -- shortened here for display only.
SHORT_CHECK_LABELS = {
    # Case 1: Credit Facilities
    "Facility amount matches approved Credit Paper": "Facility amount",
    "Facility purpose matches approved Credit Paper": "Facility purpose",
    "Pricing / profit rate matches approved Credit Paper": "Pricing / profit rate",
    "Facility tenure matches approved Credit Paper": "Facility tenure",
    "Approved special conditions reflected in LO": "Special conditions",
    "Customer name/registration number match": "Customer name / reg. no.",
    "Customer address matches approved Credit Paper": "Customer address",
    "Guarantor identity matches approved Credit Paper": "Guarantor identity",
    "Letterhead matches facility book (Conventional/Islamic)": "Letterhead vs facility book",
    "LO issued before Maker-Checker approval completed": "LO issuance timing",
    "Evidence of Maker-Checker review and approval": "Maker-Checker approval",
    # Case 2: Account Opening
    "Customer name in CLS matches SSM": "Customer name",
    "Registration number in CLS matches SSM": "Registration number",
    "Registered address in CLS matches SSM": "Registered address",
    "Business nature in CLS matches SSM": "Business nature",
    "Date of incorporation matches SSM records": "Date of incorporation",
    "Director information matches Application Form / SSM": "Director information",
    "Guarantor information in CLS matches Guarantor Form": "Guarantor information",
    "CCRIS facility amount matches CCRIS Form": "CCRIS facility amount",
    "Mandatory CIF supporting documents are present": "Required documents",
}


def short_label(check: str) -> str:
    return SHORT_CHECK_LABELS.get(check, check)


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


def sidebar_footer_logo(assets_dir: Path) -> None:
    path = assets_dir / "marvel.png"
    if not path.exists():
        return
    with st.sidebar:
        st.write("")
        st.caption("POWERED BY")
        st.image(str(path), width=130)


def status_badge(status: str) -> None:
    st.badge(status, color=STATUS_BADGE_COLOR.get(status, "gray"))


def confidence_text(score) -> str:
    return f"{score:.0f}%" if score is not None and not pd.isna(score) else "—"


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


STATUS_DISPLAY_LABEL = {"PASS": "Pass", "FAIL": "Fail", "REVIEW": "Review", "N/A": "N/A"}
CHECK_STATUS_ROW_BG = {"Pass": "#E7F6ED", "Fail": "#FCEAE9", "Review": "#FBF1DE", "N/A": "#EEF0F3"}


def validation_dataframe(results: list, left_label: str, right_label: str) -> pd.DataFrame:
    rows = [
        {
            "KCT": r.kct,
            "Check": short_label(r.check),
            "Status": STATUS_DISPLAY_LABEL.get(r.status, r.status),
            "Confidence": confidence_text(r.confidence),
            left_label: _preview(r.left_value, limit=110),
            right_label: _preview(r.right_value, limit=110),
            "Note": _preview(r.note, limit=160),
        }
        for r in results
    ]
    return pd.DataFrame(rows, columns=["KCT", "Check", "Status", "Confidence", left_label, right_label, "Note"])


def validation_legend() -> None:
    with st.container(horizontal=True):
        st.caption("Legend:")
        st.badge("Pass", color="green", icon=":material/check_circle:")
        st.badge("Review", color="orange", icon=":material/warning:")
        st.badge("Fail", color="red", icon=":material/error:")
        st.badge("N/A", color="gray", icon=":material/remove_circle:")


def validation_table(results: list, key: str, left_label: str = "Value A", right_label: str = "Value B") -> None:
    if not results:
        st.caption("No checks were run for this case.")
        return
    df = validation_dataframe(results, left_label, right_label)
    styled = df.style.apply(
        lambda row: [f"background-color: {CHECK_STATUS_ROW_BG.get(row['Status'], '')}"] * len(row), axis=1
    )
    event = st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_config={
            "KCT": st.column_config.TextColumn(width=100),
            "Check": st.column_config.TextColumn(width=220),
            "Status": st.column_config.TextColumn(width=90),
            "Confidence": st.column_config.TextColumn(width=100),
            left_label: st.column_config.TextColumn(width=380),
            right_label: st.column_config.TextColumn(width=380),
            "Note": st.column_config.TextColumn(width=420),
        },
    )
    if event and event.selection and event.selection.rows:
        result_detail(results[event.selection.rows[0]], left_label, right_label)
    else:
        st.caption("Check a row above to see its full detail.")
    validation_legend()


def flagged_cases_table(df: pd.DataFrame, key: str):
    df = df.copy()
    df["Confidence"] = df["Confidence"].apply(confidence_text)
    column_config = {
        "Case": st.column_config.TextColumn(width=260),
        "Recommendation": st.column_config.TextColumn(width=260),
        "Confidence": st.column_config.TextColumn(width=100),
        "Findings": st.column_config.NumberColumn(width=90),
    }
    return selectable_table(df, column_config, key)


def findings_table(df: pd.DataFrame, key: str):
    df = df.copy()
    df["Confidence"] = df["Confidence"].apply(confidence_text)
    column_config = {
        "Severity": st.column_config.TextColumn(width=100),
        "Title": st.column_config.TextColumn(width=450),
        "Confidence": st.column_config.TextColumn(width=100),
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
            name = clean_filename(doc.get("filename", ""), label)
            st.badge(f"{label}: {name}" if label and name != label else name, icon=":material/description:")


def document_preview_panel(label: str, filename: str, pages: list[str], key: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{label}**")
        st.caption(filename)
        if not pages:
            st.caption("Preview unavailable for this file.")
            return
        page_idx = 0
        if len(pages) > 1:
            page_idx = (
                st.number_input(
                    "Page", min_value=1, max_value=len(pages), value=1, step=1, key=f"{key}_page", label_visibility="collapsed"
                )
                - 1
            )
            st.caption(f"Page {page_idx + 1} of {len(pages)}")
        st.image(pages[page_idx], width="stretch")


def field_extraction_table(rows: pd.DataFrame, key: str) -> None:
    if rows.empty:
        st.caption("No fields extracted from this document.")
        return
    rows = rows.copy()
    rows["Confidence"] = rows["Confidence"].apply(confidence_text)
    event = st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_config={
            "Field": st.column_config.TextColumn(width=200),
            "Value": st.column_config.TextColumn(width=400),
            "Confidence": st.column_config.TextColumn(width=100),
            "Source": st.column_config.TextColumn(width=380),
        },
    )
    if event and event.selection and event.selection.rows:
        r = rows.iloc[event.selection.rows[0]]
        with st.container(border=True):
            st.markdown(f"**{r['Field']}**")
            st.write(r["Value"] or "—")
            st.caption(f"Confidence {r['Confidence']}")
            if r["Source"]:
                st.caption(f":material/description: {r['Source']}")
    else:
        st.caption("Check a row above to see its full value.")


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
                st.caption(f":material/description: {clean_source_text(r.source_left)}")
        with col2:
            st.caption(right_label.upper())
            st.write(r.right_value or "—")
            if r.source_right:
                st.caption(f":material/description: {clean_source_text(r.source_right)}")


_AI_SUMMARY_SECTIONS = [
    ("executive_summary", "Executive Summary", "blue", ":material/summarize:"),
    ("positive_indicators", "Positive Indicators", "green", ":material/thumb_up:"),
    ("areas_of_concern", "Areas of Concern", "orange", ":material/warning:"),
    ("recommendations", "AI Recommendations", "violet", ":material/lightbulb:"),
]


def ai_summary(remarks: str) -> None:
    if not remarks:
        st.caption("No AI summary available.")
        return
    try:
        sections = json.loads(remarks)
        if not isinstance(sections, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError, TypeError):
        # Older cases stored remarks as a plain bullet-list string -- render as-is.
        st.write(remarks)
        return
    rendered_any = False
    for key, title, color, icon in _AI_SUMMARY_SECTIONS:
        bullets = sections.get(key) or []
        if not bullets:
            continue
        rendered_any = True
        with st.container(border=True):
            st.badge(title, color=color, icon=icon)
            for bullet in bullets:
                st.markdown(f"- {bullet}")
    if not rendered_any:
        st.caption("No AI summary available.")
