import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))
sys.path.insert(0, str(REPO_ROOT / "src" / "case2_account_opening"))

import ui_components as ui  # noqa: E402

st.set_page_config(
    page_title="AmBank Document Intelligence Module · Accounts",
    page_icon=":material/shield_person:",
    layout="wide",
)
ui.inject_style()
ui.render_logo(APP_DIR / "assets")

pages = [
    st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("app_pages/cases.py", title="Accounts", icon=":material/folder_open:"),
    st.Page("app_pages/case_detail.py", title="Case detail", icon=":material/description:"),
    st.Page("app_pages/reports.py", title="Reports", icon=":material/summarize:"),
]
nav = st.navigation(pages, position="hidden")

ui.sidebar_brand("AmBank Document Intelligence Module", "Accounts")
ui.sidebar_nav(pages, nav.url_path)

nav.run()
