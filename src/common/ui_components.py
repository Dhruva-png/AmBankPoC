from __future__ import annotations

import json as _json
from pathlib import Path

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --navy: #0B1524;
            --navy-mid: #16233A;
            --gold: #C9A227;
            --gold-soft: #FBF3DC;
            --surface-page: #F5F6F8;
            --surface: #FFFFFF;
            --border: #E1E5EB;
            --border-light: #EDF0F4;
            --text-heading: #101828;
            --text-body: #344054;
            --text-muted: #667085;
            --success: #067647;
            --success-bg: #ECFDF3;
            --warning: #B54708;
            --warning-bg: #FFFAEB;
            --danger: #B42318;
            --danger-bg: #FEF3F2;
            --info: #1849A9;
            --info-bg: #EFF4FF;
            --font: "Inter", "Segoe UI", system-ui, sans-serif;
            --font-mono: "JetBrains Mono", "Fira Code", Consolas, monospace;
        }

        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .main .block-container {
            background-color: var(--surface-page) !important;
            font-family: var(--font) !important;
            color: var(--text-body) !important;
        }
        p, li, span, label, div { color: var(--text-body); }
        h1, h2, h3, h4 { color: var(--text-heading) !important; font-family: var(--font) !important; }
        .main .block-container { padding: 1.75rem 2.25rem 3rem !important; max-width: 1360px; }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--navy) 0%, var(--navy-mid) 100%) !important;
            border-right: 1px solid rgba(255,255,255,0.08) !important;
        }
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] label {
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] .stRadio > div { gap: 0.3rem; }
        [data-testid="stSidebar"] .stRadio > div > label {
            background: transparent !important;
            border: 1px solid transparent;
            border-radius: 8px !important;
            color: rgba(255,255,255,0.78) !important;
            padding: 0.65rem 0.75rem !important;
            font-weight: 600;
            font-size: 0.87rem;
        }
        [data-testid="stSidebar"] .stRadio > div > label:hover {
            background: rgba(255,255,255,0.08) !important;
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
            background: rgba(201,162,39,0.16) !important;
            border-color: rgba(201,162,39,0.35);
            box-shadow: inset 3px 0 0 var(--gold);
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.08) !important;
            color: rgba(255,255,255,0.85) !important;
            border: 1px solid rgba(255,255,255,0.16) !important;
            border-radius: 8px;
            font-size: 0.82rem;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255,255,255,0.16) !important;
        }
        [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12) !important; }

        .sidebar-logo-block { padding: 1.35rem 1.1rem 1.05rem; }
        .sidebar-logo-row { display: flex; align-items: center; gap: 0.7rem; }
        .sidebar-monogram {
            width: 38px; height: 38px; border-radius: 9px;
            background: linear-gradient(135deg, var(--gold) 0%, #8A6D14 100%);
            color: var(--navy); font-weight: 800; font-size: 1.05rem;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }
        .sidebar-app-name { font-size: 1.08rem; font-weight: 800; color: #FFFFFF; line-height: 1.2; }
        .sidebar-app-tagline {
            font-size: 0.66rem; color: rgba(255,255,255,0.5); letter-spacing: 0.1em;
            text-transform: uppercase; margin-top: 0.55rem;
        }
        .sidebar-status-row { padding: 0.15rem 0; font-size: 0.76rem; color: rgba(255,255,255,0.6); }
        .dot-online { color: #4ADE9F; }
        .dot-offline { color: #F87171; }

        .page-hero {
            position: relative;
            background: linear-gradient(135deg, #FFFFFF 0%, #F7F8FA 55%, var(--gold-soft) 100%);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.5rem 1.75rem;
            margin: 0 0 1.4rem;
            box-shadow: 0 12px 30px rgba(16,24,40,0.05);
        }
        .page-kicker {
            color: var(--navy); font-size: 0.72rem; font-weight: 800;
            letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.45rem;
        }
        .page-hero h1 { font-size: 1.85rem; font-weight: 750; margin: 0 0 0.4rem; color: var(--text-heading) !important; }
        .page-hero p { color: var(--text-muted) !important; font-size: 0.95rem; max-width: 800px; margin: 0; }

        .section-header {
            font-size: 0.74rem; font-weight: 800; color: var(--text-heading);
            text-transform: uppercase; letter-spacing: 0.1em;
            border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; margin: 1.5rem 0 0.9rem;
        }
        .section-header::before {
            content: ""; display: inline-block; width: 7px; height: 7px; margin-right: 0.5rem;
            border-radius: 50%; background: var(--gold);
        }

        .card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
            padding: 1.3rem 1.45rem; margin-bottom: 1rem; box-shadow: 0 6px 18px rgba(16,24,40,0.04);
        }
        .card-metric {
            background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
            padding: 1.05rem 1.1rem; text-align: left; box-shadow: 0 6px 18px rgba(16,24,40,0.04);
        }
        .metric-value { font-size: 1.9rem; font-weight: 750; color: var(--text-heading); line-height: 1.1; }
        .metric-label {
            font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.08em; margin-top: 0.35rem; font-weight: 700;
        }

        .badge {
            display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px;
            font-size: 0.7rem; font-weight: 700; letter-spacing: 0.03em;
        }
        .badge-pass { background: var(--success-bg); color: var(--success); }
        .badge-fail { background: var(--danger-bg); color: var(--danger); }
        .badge-review { background: var(--warning-bg); color: var(--warning); }
        .badge-na { background: var(--border-light); color: var(--text-muted); }
        .badge-conf-high { background: var(--success-bg); color: var(--success); }
        .badge-conf-medium { background: var(--warning-bg); color: var(--warning); }
        .badge-conf-low { background: var(--danger-bg); color: var(--danger); }

        .source-tag {
            display: inline-flex; align-items: center; gap: 0.3rem;
            background: var(--info-bg); color: var(--info); border-radius: 6px;
            padding: 0.14rem 0.55rem; font-size: 0.68rem; font-weight: 600;
        }

        [data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: 8px !important; background: var(--surface) !important; }
        [data-testid="stAlert"] { border-radius: 8px !important; }
        [data-testid="stDataFrame"] thead th { background-color: var(--navy) !important; color: #FFFFFF !important; }
        .stButton > button {
            background: var(--navy) !important; color: #FFFFFF !important; border: none !important;
            border-radius: 8px !important; font-weight: 600 !important; padding: 0.5rem 1.15rem !important;
        }
        .stButton > button:hover { background: var(--navy-mid) !important; }
        .stDownloadButton > button {
            background: var(--gold) !important; color: var(--navy) !important; border: none !important;
            border-radius: 8px !important; font-weight: 700 !important;
        }
        .json-box {
            background: var(--surface-page); border: 1px solid var(--border); border-radius: 8px;
            padding: 0.9rem 1rem; font-family: var(--font-mono); font-size: 0.76rem;
            color: var(--text-body); overflow-x: auto; line-height: 1.7; white-space: pre-wrap;
        }
        #MainMenu, footer, header { visibility: hidden; }
        [data-testid="stDecoration"] { display: none; }
        @media (max-width: 900px) {
            .main .block-container { padding: 1rem !important; }
            .page-hero h1 { font-size: 1.4rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_logo(app_name: str, tagline: str, assets_dir: Path, monogram: str) -> None:
    logo_path = assets_dir / "logo.png"
    with st.sidebar:
        st.markdown('<div class="sidebar-logo-block">', unsafe_allow_html=True)
        if logo_path.exists():
            st.image(str(logo_path), width=150)
            st.markdown(f'<div class="sidebar-app-tagline">{tagline}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div class="sidebar-logo-row">
                    <div class="sidebar-monogram">{monogram}</div>
                    <div class="sidebar-app-name">{app_name}</div>
                </div>
                <div class="sidebar-app-tagline">{tagline}</div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<hr style="border-top:1px solid rgba(255,255,255,0.12);margin:0 0 0.75rem;">', unsafe_allow_html=True)


def sidebar_groq_status(key_statuses) -> None:
    with st.sidebar:
        for ks in key_statuses:
            if not ks.configured:
                dot, text = "dot-offline", f"{ks.label}: not configured"
            elif ks.online:
                dot, text = "dot-online", f"{ks.label}: online"
            else:
                dot, text = "dot-offline", f"{ks.label}: {ks.error or 'offline'}"
            st.markdown(
                f'<div class="sidebar-status-row"><span class="{dot}">●</span> &nbsp;{text}</div>',
                unsafe_allow_html=True,
            )


def page_hero(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-kicker">{kicker}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def status_badge(status: str) -> str:
    mapping = {"PASS": "badge-pass", "FAIL": "badge-fail", "REVIEW": "badge-review", "N/A": "badge-na"}
    cls = mapping.get(status, "badge-na")
    return f'<span class="badge {cls}">{status}</span>'


def confidence_badge(score) -> str:
    if score is None:
        return '<span class="badge badge-na">N/A</span>'
    score = float(score)
    if score >= 85:
        cls, tier = "badge-conf-high", "High"
    elif score >= 60:
        cls, tier = "badge-conf-medium", "Medium"
    else:
        cls, tier = "badge-conf-low", "Low"
    return f'<span class="badge {cls}">{tier} · {score:.0f}%</span>'


def source_tag(text: str) -> str:
    return f'<span class="source-tag">📄 {text}</span>'


def metric_card(label: str, value: str) -> str:
    return f"""
    <div class="card-metric">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>"""


def render_json(data) -> None:
    text = _json.dumps(data, indent=2, ensure_ascii=False, default=str)
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(f'<div class="json-box">{escaped}</div>', unsafe_allow_html=True)
