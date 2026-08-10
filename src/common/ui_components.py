from __future__ import annotations

import json as _json
from pathlib import Path

import pandas as pd
import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --ink: #0F1420;
            --body: #333B47;
            --muted: #6B7280;
            --faint: #98A2B3;
            --surface: #FFFFFF;
            --canvas: #F5F6F8;
            --border: #DDE1E6;
            --border-strong: #C7CDD6;
            --sidebar: #12161F;
            --sidebar-border: #262B38;
            --accent: #2451D6;
            --accent-ink: #1D3FAE;
            --success: #146C3A;
            --success-bg: #E7F6ED;
            --success-border: #BCE3CB;
            --danger: #B3261E;
            --danger-bg: #FCEAE9;
            --danger-border: #F3C6C2;
            --warning: #91600A;
            --warning-bg: #FBF1DE;
            --warning-border: #EDD8A8;
            --neutral: #5B6472;
            --neutral-bg: #EEF0F3;
            --neutral-border: #D8DCE2;
            --font: "Inter", "Segoe UI", system-ui, sans-serif;
            --font-mono: "JetBrains Mono", "Fira Code", Consolas, monospace;
        }

        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .main .block-container {
            background-color: var(--canvas) !important;
            font-family: var(--font) !important;
            color: var(--body) !important;
            font-size: 14px;
        }
        p, li, span, label, div { color: var(--body); }
        h1, h2, h3, h4 { color: var(--ink) !important; font-family: var(--font) !important; }
        .main .block-container { padding: 1.35rem 2rem 3rem !important; max-width: 1400px; }

        [data-testid="stSidebar"] {
            background: var(--sidebar) !important;
            border-right: 1px solid var(--sidebar-border) !important;
        }
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] label {
            color: #E7E9EE !important;
        }
        [data-testid="stSidebar"] .stRadio > div { gap: 0.15rem; }
        [data-testid="stSidebar"] .stRadio > div > label {
            background: transparent !important;
            border: 1px solid transparent;
            border-radius: 4px !important;
            color: #B4BAC6 !important;
            padding: 0.5rem 0.65rem !important;
            font-weight: 500;
            font-size: 0.85rem;
        }
        [data-testid="stSidebar"] .stRadio > div > label:hover {
            background: rgba(255,255,255,0.05) !important;
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
            background: rgba(36,81,214,0.16) !important;
            color: #FFFFFF !important;
            box-shadow: inset 2px 0 0 var(--accent);
        }
        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.06) !important;
            color: #C6CAD3 !important;
            border: 1px solid var(--sidebar-border) !important;
            border-radius: 4px;
            font-size: 0.78rem;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255,255,255,0.11) !important;
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] hr { border-color: var(--sidebar-border) !important; margin: 0.6rem 0 !important; }

        .sb-logo { padding: 1.1rem 1rem 0.9rem; display: flex; align-items: center; gap: 0.6rem; }
        .sb-mark {
            width: 26px; height: 26px; border-radius: 4px;
            border: 1px solid rgba(255,255,255,0.18);
            color: #E7E9EE; font-weight: 700; font-size: 0.72rem;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0; letter-spacing: 0.02em;
        }
        .sb-name { font-size: 0.86rem; font-weight: 700; color: #FFFFFF; line-height: 1.2; letter-spacing: -0.01em; }
        .sb-tagline { font-size: 0.66rem; color: #7C8494; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 0.1rem; }

        .sb-section-label {
            font-size: 0.63rem; font-weight: 700; color: #626A7A; letter-spacing: 0.1em;
            text-transform: uppercase; padding: 0 0.15rem; margin: 0.9rem 0 0.4rem;
        }
        .sb-status-row { padding: 0.1rem 0.15rem; font-size: 0.74rem; color: #9AA1AF; display:flex; align-items:center; gap:0.4rem; }
        .sb-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; display:inline-block; }
        .sb-dot-on { background: #3FB871; }
        .sb-dot-off { background: #E5534B; }
        .sb-app-link {
            display: block; padding: 0.45rem 0.6rem; border-radius: 4px; border: 1px solid var(--sidebar-border);
            font-size: 0.76rem; color: #B4BAC6 !important; text-decoration: none !important; margin-bottom: 0.35rem;
        }
        .sb-app-link:hover { background: rgba(255,255,255,0.05); color: #FFFFFF !important; }
        .sb-app-link .sb-app-link-name { font-weight: 600; color: #E7E9EE; }

        .app-breadcrumb {
            font-size: 0.72rem; color: var(--muted); margin-bottom: 0.5rem; letter-spacing: 0.01em;
        }
        .page-header { padding-bottom: 0.9rem; margin-bottom: 1.1rem; border-bottom: 1px solid var(--border); }
        .page-header h1 {
            font-size: 1.32rem; font-weight: 700; margin: 0 0 0.3rem; letter-spacing: -0.01em; color: var(--ink) !important;
        }
        .page-header p { font-size: 0.85rem; color: var(--muted) !important; margin: 0; max-width: 780px; line-height: 1.5; }

        .section-header {
            font-size: 0.68rem; font-weight: 700; color: var(--muted);
            text-transform: uppercase; letter-spacing: 0.09em;
            border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; margin: 1.3rem 0 0.75rem;
        }

        .stat-strip {
            display: flex; border: 1px solid var(--border); border-radius: 6px; background: var(--surface);
            margin-bottom: 0.25rem; overflow: hidden;
        }
        .stat-item { flex: 1; padding: 0.7rem 1rem; border-right: 1px solid var(--border); }
        .stat-item:last-child { border-right: none; }
        .stat-value { font-size: 1.45rem; font-weight: 700; color: var(--ink); line-height: 1.1; font-variant-numeric: tabular-nums; }
        .stat-label { font-size: 0.66rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.2rem; font-weight: 600; }

        .panel {
            background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
            padding: 1rem 1.15rem; margin-bottom: 0.9rem;
        }
        .panel-placeholder { color: var(--faint); font-size: 0.85rem; padding: 1.5rem; text-align: center; }

        .detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: 0.55rem; }
        .detail-kct { font-family: var(--font-mono); font-size: 0.7rem; color: var(--muted); font-weight: 600; }
        .detail-title { font-size: 0.98rem; font-weight: 700; color: var(--ink); margin: 0.1rem 0 0; }
        .detail-badges { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
        .detail-note { font-size: 0.83rem; color: var(--body); margin: 0.5rem 0 0.9rem; line-height: 1.55; padding: 0.6rem 0.75rem; background: var(--canvas); border-radius: 4px; border-left: 2px solid var(--border-strong); }
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; }
        .detail-col-label { font-size: 0.64rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; font-weight: 700; margin-bottom: 0.3rem; }
        .detail-col-value { font-size: 0.84rem; color: var(--body); line-height: 1.5; word-break: break-word; }
        .detail-col-source { font-family: var(--font-mono); font-size: 0.68rem; color: var(--faint); margin-top: 0.4rem; }

        .chip {
            display: inline-block; padding: 0.1rem 0.45rem; border-radius: 3px; border: 1px solid;
            font-size: 0.68rem; font-weight: 700; letter-spacing: 0.03em; line-height: 1.5;
        }
        .chip-pass { background: var(--success-bg); color: var(--success); border-color: var(--success-border); }
        .chip-fail { background: var(--danger-bg); color: var(--danger); border-color: var(--danger-border); }
        .chip-review { background: var(--warning-bg); color: var(--warning); border-color: var(--warning-border); }
        .chip-na { background: var(--neutral-bg); color: var(--neutral); border-color: var(--neutral-border); }

        .conf-wrap { display: inline-flex; align-items: center; gap: 0.4rem; }
        .conf-track { width: 46px; height: 5px; background: var(--neutral-bg); border-radius: 3px; overflow: hidden; }
        .conf-fill { height: 100%; border-radius: 3px; }
        .conf-text { font-size: 0.7rem; color: var(--muted); font-variant-numeric: tabular-nums; font-weight: 600; }

        [data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: 6px !important; background: var(--surface) !important; }
        [data-testid="stExpander"] summary { font-size: 0.82rem !important; font-weight: 600; }
        [data-testid="stAlert"] { border-radius: 6px !important; font-size: 0.83rem; }

        [data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 6px !important; overflow: hidden; }

        .stButton > button {
            background: var(--accent) !important; color: #FFFFFF !important; border: none !important;
            border-radius: 4px !important; font-weight: 600 !important; font-size: 0.85rem !important;
            padding: 0.42rem 1rem !important;
        }
        .stButton > button:hover { background: var(--accent-ink) !important; }
        .stDownloadButton > button {
            background: var(--surface) !important; color: var(--body) !important; border: 1px solid var(--border-strong) !important;
            border-radius: 4px !important; font-weight: 600 !important; font-size: 0.82rem !important;
        }
        .stDownloadButton > button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }

        .json-box {
            background: var(--canvas); border: 1px solid var(--border); border-radius: 6px;
            padding: 0.8rem 0.9rem; font-family: var(--font-mono); font-size: 0.74rem;
            color: var(--body); overflow-x: auto; line-height: 1.65; white-space: pre-wrap;
        }
        #MainMenu, footer, header { visibility: hidden; }
        [data-testid="stDecoration"] { display: none; }
        @media (max-width: 900px) {
            .main .block-container { padding: 1rem !important; }
            .detail-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_logo(app_name: str, tagline: str, assets_dir: Path, monogram: str) -> None:
    logo_path = assets_dir / "logo.png"
    with st.sidebar:
        if logo_path.exists():
            st.markdown('<div class="sb-logo">', unsafe_allow_html=True)
            st.image(str(logo_path), width=140)
            st.markdown(f'<div class="sb-tagline">{tagline}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div class="sb-logo">
                    <div class="sb-mark">{monogram}</div>
                    <div>
                        <div class="sb-name">{app_name}</div>
                        <div class="sb-tagline">{tagline}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('<hr>', unsafe_allow_html=True)


def sidebar_module_indicator(modules: list[tuple[str, bool]]) -> None:
    with st.sidebar:
        st.markdown('<div class="sb-section-label">Suite Modules</div>', unsafe_allow_html=True)
        for name, active in modules:
            style = "opacity:1;box-shadow:inset 2px 0 0 var(--accent);" if active else "opacity:0.55;"
            note = "Current module" if active else "Run separately"
            st.markdown(
                f'<div class="sb-app-link" style="{style}">'
                f'<span class="sb-app-link-name">{name}</span><br>{note}</div>',
                unsafe_allow_html=True,
            )


def sidebar_groq_status(key_statuses) -> None:
    with st.sidebar:
        st.markdown('<div class="sb-section-label">AI Engine Status</div>', unsafe_allow_html=True)
        for ks in key_statuses:
            if not ks.configured:
                dot, text = "sb-dot-off", f"{ks.label} — not configured"
            elif ks.online:
                dot, text = "sb-dot-on", f"{ks.label} — online"
            else:
                dot, text = "sb-dot-off", f"{ks.label} — {ks.error or 'offline'}"
            st.markdown(
                f'<div class="sb-status-row"><span class="sb-dot {dot}"></span>{text}</div>',
                unsafe_allow_html=True,
            )


def breadcrumb(*parts: str) -> None:
    st.markdown(f'<div class="app-breadcrumb">{" / ".join(parts)}</div>', unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="page-header"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


def section_header(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def stat_strip(items: list[tuple[str, str]]) -> None:
    cells = "".join(
        f'<div class="stat-item"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="stat-strip">{cells}</div>', unsafe_allow_html=True)


_STATUS_CHIP = {"PASS": "chip-pass", "FAIL": "chip-fail", "REVIEW": "chip-review", "N/A": "chip-na"}
_STATUS_COLOR = {"PASS": "#146C3A", "FAIL": "#B3261E", "REVIEW": "#91600A", "N/A": "#5B6472"}


def status_chip(status: str) -> str:
    return f'<span class="chip {_STATUS_CHIP.get(status, "chip-na")}">{status}</span>'


def confidence_meter(score) -> str:
    if score is None:
        return '<span class="conf-text">—</span>'
    score = float(score)
    color = "#146C3A" if score >= 85 else "#91600A" if score >= 60 else "#B3261E"
    return (
        f'<span class="conf-wrap"><span class="conf-track">'
        f'<span class="conf-fill" style="width:{score:.0f}%;background:{color};"></span></span>'
        f'<span class="conf-text">{score:.0f}%</span></span>'
    )


def results_dataframe(results) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "KCT": r.kct,
                "Check": r.check,
                "Status": r.status,
                "Confidence": r.confidence,
            }
            for r in results
        ]
    )


def results_grid(results, key: str):
    df = results_dataframe(results)
    styled = df.style.map(lambda v: f"color:{_STATUS_COLOR.get(v, '#333')};font-weight:700;", subset=["Status"])
    event = st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_config={
            "KCT": st.column_config.TextColumn(width="small"),
            "Check": st.column_config.TextColumn(width="large"),
            "Status": st.column_config.TextColumn(width="small"),
            "Confidence": st.column_config.NumberColumn(width="small", format="%.0f%%"),
        },
    )
    if event and event.selection and event.selection.rows:
        return event.selection.rows[0]
    return 0 if len(results) else None


def detail_panel(r, left_label: str, right_label: str) -> None:
    st.markdown(
        f"""
        <div class="panel">
            <div class="detail-head">
                <div>
                    <div class="detail-kct">{r.kct}</div>
                    <div class="detail-title">{r.check}</div>
                </div>
                <div class="detail-badges">{status_chip(r.status)}{confidence_meter(r.confidence)}</div>
            </div>
            <div class="detail-note">{r.note}</div>
            <div class="detail-grid">
                <div>
                    <div class="detail-col-label">{left_label}</div>
                    <div class="detail-col-value">{r.left_value or '—'}</div>
                    <div class="detail-col-source">{r.source_left or ''}</div>
                </div>
                <div>
                    <div class="detail-col-label">{right_label}</div>
                    <div class="detail-col-value">{r.right_value or '—'}</div>
                    <div class="detail-col-source">{r.source_right or ''}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_panel(text: str) -> None:
    st.markdown(f'<div class="panel panel-placeholder">{text}</div>', unsafe_allow_html=True)


def render_json(data) -> None:
    text = _json.dumps(data, indent=2, ensure_ascii=False, default=str)
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(f'<div class="json-box">{escaped}</div>', unsafe_allow_html=True)
