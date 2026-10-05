"""Accessibility controls: a persistent sidebar panel plus injected CSS.

Settings live in ``st.session_state`` under ``a11y_*`` keys, so they apply on every
screen. Items marked ``coming_soon`` are visible but disabled.
"""
from __future__ import annotations

import streamlit as st

from config import settings

FONT_SIZES = {"Small (14px)": 14, "Medium (16px)": 16, "Large (20px)": 20, "Extra Large (24px)": 24}
LINE_SPACING = {"Normal": None, "1.5x": 1.5, "2x": 2.0}
OVERLAYS = {
    "None": None,
    "Yellow": "rgba(255, 235, 59, 0.22)",
    "Blue": "rgba(33, 150, 243, 0.18)",
    "Green": "rgba(76, 175, 80, 0.18)",
    "Pink": "rgba(244, 143, 177, 0.25)",
}
EXTRA_TIME_FACTOR = 1.25

# Elements that carry readable text. Icon fonts live on <span>s, so spans are deliberately excluded
# from the font override to keep Streamlit's icons intact.
_TEXT = (
    ".stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, "
    ".stApp textarea, .stApp input, .stApp button p, .stApp td, .stApp th, .stApp caption, "
    ".stApp [data-testid='stMarkdownContainer'], .stApp [data-testid='stMetricValue'], "
    ".stApp [data-testid='stMetricLabel'], .ilt-q, .ilt-source, .ilt-header, .ilt-badge"
)


def init() -> None:
    defaults = {
        "a11y_font": "Medium (16px)", "a11y_contrast": False, "a11y_dyslexia": False,
        "a11y_spacing": "Normal", "a11y_overlay": "None", "a11y_extended": False, "a11y_reduced": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def time_factor() -> float:
    return EXTRA_TIME_FACTOR if st.session_state.get("a11y_extended") else 1.0


def render_panel() -> None:
    """The persistent accessibility panel (sidebar)."""
    with st.sidebar:
        with st.expander("♿ Accessibility", expanded=False):
            st.select_slider("Text size", options=list(FONT_SIZES), key="a11y_font")
            st.toggle("High contrast mode", key="a11y_contrast")
            st.toggle("Dyslexia-friendly font", key="a11y_dyslexia")
            st.selectbox("Line spacing", list(LINE_SPACING), key="a11y_spacing")
            st.selectbox("Colour overlay", list(OVERLAYS), key="a11y_overlay")
            st.toggle("Extended time (25% extra)", key="a11y_extended")
            st.toggle("Reduced distraction mode", key="a11y_reduced",
                      help="Hides the sidebar and simplifies the page.")
            st.divider()
            st.toggle("Read aloud (text-to-speech): Coming Soon", value=False, disabled=True, key="a11y_tts")
            st.toggle("BSL support: Coming Soon", value=False, disabled=True, key="a11y_bsl")
            st.selectbox("Language: Coming Soon", ["English"], disabled=True, key="a11y_lang")
            st.caption("Screen reader compatible: this platform uses semantic markup and labelled controls.")


def _css() -> str:
    px = FONT_SIZES.get(st.session_state["a11y_font"], 16)
    css = [f"html {{ font-size: {px}px !important; }}"]

    spacing = LINE_SPACING.get(st.session_state["a11y_spacing"])
    if spacing:
        css.append(f"{_TEXT} {{ line-height: {spacing} !important; }}")

    if st.session_state["a11y_dyslexia"]:
        css.append(
            f"@font-face {{ font-family: 'OpenDyslexic'; src: url('{settings.DYSLEXIA_FONT_URL}') format('woff'); "
            "font-display: swap; }"
            f"\n{_TEXT} {{ font-family: 'OpenDyslexic', 'Comic Sans MS', 'Verdana', sans-serif !important; "
            "letter-spacing: 0.02em; }\n"
            ".stApp [data-testid='stSidebar'] summary p { font-size: 0.85em !important; letter-spacing: 0 !important; }"
        )

    if st.session_state["a11y_contrast"]:
        css.append("""
        .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] { background: #000 !important; }
        .stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
        .stApp h6, .stApp span, .stApp td, .stApp th, .stApp caption, .stApp [data-testid="stMarkdownContainer"],
        .stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"], .stApp small,
        .stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] *,
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * { color: #fff !important; opacity: 1 !important; }
        [data-testid="stSidebar"] { border-right: 2px solid #ffeb3b; }
        .stApp a { color: #00e5ff !important; }
        .stApp button { background: #ffeb3b !important; color: #000 !important; border: 2px solid #fff !important;
                        font-weight: 700 !important; }
        .stApp button p, .stApp button span { color: #000 !important; }
        .stApp textarea, .stApp input, .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="input"] {
            background: #000 !important; color: #fff !important; border: 2px solid #fff !important; }
        .stApp textarea::placeholder, .stApp input::placeholder { color: #cfcfcf !important; opacity: 1 !important; }
        .stApp [data-testid="stExpander"], .stApp [data-testid="stVerticalBlockBorderWrapper"],
        .stApp [data-testid="stAlert"], .ilt-card { border: 2px solid #fff !important; background: #000 !important; }
        .ilt-badge { background: #ffeb3b !important; color: #000 !important; }
        .ilt-ln, .ilt-footer, .ilt-header p { color: #ddd !important; }
        """)

    if st.session_state["a11y_reduced"]:
        css.append("""
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stHeader"],
        [data-testid="stToolbar"], .ilt-footer { display: none !important; }
        .block-container { max-width: 860px !important; padding-top: 1rem !important; }
        """)
    return "\n".join(css)


def apply() -> None:
    """Inject CSS and the colour overlay for the current settings."""
    st.markdown(f"<style>{_css()}</style>", unsafe_allow_html=True)
    tint = OVERLAYS.get(st.session_state["a11y_overlay"])
    if tint:
        st.markdown(
            f"<div style='position:fixed;inset:0;background:{tint};pointer-events:none;z-index:999999;mix-blend-mode:multiply;'></div>",
            unsafe_allow_html=True,
        )
    if st.session_state["a11y_reduced"]:
        if st.button("Exit reduced distraction mode", key="exit_reduced"):
            st.session_state["a11y_reduced"] = False
            st.rerun()
