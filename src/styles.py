"""
ClaimGuard — Shared Design System (Monochrome)
Inject this CSS identically on every page to keep the two-page app
visually consistent. Import and call load_css() at the top of each page.
"""

import streamlit as st


def load_css():
    """Inject the shared ClaimGuard monochrome design-system CSS."""
    st.markdown(_SHARED_CSS, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# MONOCHROME DESIGN TOKENS
#   bg:        #ffffff / #fafafa
#   text:      #0a0a0a
#   secondary: #6b7280
#   border:    #e5e7eb
#   accent:    solid black fills, white text
# ──────────────────────────────────────────────────────────────────────

_SHARED_CSS = """
<style>
/* ===== Import Inter font ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ===== GLOBAL RESET ===== */
#MainMenu, footer {
    display: none !important;
}

.stApp {
    background-color: #ffffff !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e5e7eb !important;
}

section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] p {
    color: #0a0a0a !important;
}

section[data-testid="stSidebar"] .stRadio > label {
    color: #0a0a0a !important;
    font-weight: 500 !important;
}

/* Sidebar page links — active state uses black background */
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
    color: #0a0a0a !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    transition: background-color 0.2s ease !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
    background-color: #f3f4f6 !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
    background-color: #0a0a0a !important;
    color: #ffffff !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] span {
    color: #ffffff !important;
}

/* ===== HEADINGS ===== */
h1, h2, h3 {
    color: #0a0a0a !important;
    font-family: 'Inter', sans-serif !important;
}

.stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: #0a0a0a !important;
}

/* ===== ALL BUTTONS — shared pill base ===== */
.stButton > button,
div[data-testid="stButton"] > button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: nowrap !important;
    width: fit-content !important;
    padding: 14px 32px !important;
    border-radius: 999px !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    box-shadow: none !important;
}

/* ===== PRIMARY BUTTON — solid black pill ===== */
.stButton > button[kind="primary"],
div[data-testid="stButton"] > button[kind="primary"] {
    background: #000000 !important;
    color: #ffffff !important;
    border: none !important;
}

.stButton > button[kind="primary"]:hover,
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #1f2937 !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
    transform: translateY(-1px) !important;
}

/* ===== SECONDARY BUTTON — outlined pill ===== */
.stButton > button[kind="secondary"],
div[data-testid="stButton"] > button[kind="secondary"] {
    background: #ffffff !important;
    color: #000000 !important;
    border: 1px solid #000000 !important;
}

.stButton > button[kind="secondary"]:hover,
div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #fafafa !important;
}

/* ===== CALLOUT BOX — monochrome tip/highlight ===== */
.cg-callout {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #0a0a0a;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 20px 0;
    display: flex;
    align-items: flex-start;
    gap: 14px;
}

.cg-callout .cg-callout-icon {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    margin-top: 2px;
}

.cg-callout .cg-callout-text {
    font-size: 0.9rem;
    color: #0a0a0a;
    line-height: 1.6;
    font-family: 'Inter', sans-serif;
}

.cg-callout .cg-callout-text strong {
    font-weight: 700;
}

/* ===== CARDS — white with thin border + soft shadow ===== */
.cg-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    transition: box-shadow 0.25s ease, transform 0.25s ease;
}

.cg-card:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);
}

/* ===== HEADER CARD ===== */
.cg-header-card {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
}

.cg-header-card .cg-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    color: #0a0a0a;
    letter-spacing: -0.03em;
    margin-bottom: 6px;
    line-height: 1.2;
}

.cg-header-card .cg-subtitle {
    font-size: 1rem;
    color: #6b7280;
    font-weight: 400;
    line-height: 1.5;
}

/* ===== METRIC CARDS (Audit Dashboard) ===== */
.cg-metric-card {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}

.cg-metric-card .metric-val {
    font-size: 1.8rem;
    font-weight: 700;
    color: #0a0a0a;
    font-family: 'Inter', sans-serif;
}

.cg-metric-card .metric-lbl {
    font-size: 0.8rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 500;
    margin-bottom: 4px;
}

/* ===== PASS / FLAGGED BADGES ===== */
.cg-badge-pass {
    display: inline-block;
    background: #0a0a0a;
    color: #ffffff;
    padding: 14px 28px;
    border-radius: 12px;
    font-weight: 800;
    font-size: 1.4rem;
    letter-spacing: 1px;
    font-family: 'Inter', sans-serif;
}

.cg-badge-flagged {
    display: inline-block;
    background: #0a0a0a;
    color: #ffffff;
    padding: 14px 28px;
    border-radius: 12px;
    font-weight: 800;
    font-size: 1.4rem;
    letter-spacing: 1px;
    font-family: 'Inter', sans-serif;
    border: 2px solid #dc2626;
}

/* ===== PILL BADGES (feature pills on landing) ===== */
.cg-pill-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 20px;
}

.cg-pill {
    display: inline-block;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 999px;
    padding: 6px 16px;
    font-size: 0.8rem;
    font-weight: 500;
    color: #0a0a0a;
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.01em;
}

/* ===== HERO SECTION (landing page) ===== */
.cg-hero {
    padding: 40px 0 48px;
}

.cg-hero h1 {
    font-family: 'Inter', sans-serif !important;
    font-size: 3rem;
    font-weight: 900;
    color: #0a0a0a !important;
    letter-spacing: -0.04em;
    line-height: 1.08;
    margin-bottom: 16px;
}

.cg-hero h1 .cg-emphasis {
    font-weight: 900;
    /* Uses font-size bump instead of color — pure monochrome */
    font-style: normal;
}

.cg-hero .cg-hero-subtitle {
    font-size: 1.15rem;
    color: #6b7280;
    font-weight: 400;
    line-height: 1.6;
    max-width: 560px;
    margin-bottom: 28px;
}

.cg-hero .cg-hero-cta-row {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
}

/* ===== DIVIDER ===== */
.cg-divider {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 40px 0;
}

/* ===== SECTION HEADINGS ===== */
.cg-section-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: #0a0a0a;
    letter-spacing: -0.02em;
    margin-bottom: 24px;
}

/* ===== DATA / CODE BOX ===== */
.cg-code-box {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 14px;
    font-family: 'Menlo', 'Consolas', monospace;
    font-size: 0.85rem;
    color: #0a0a0a;
}

/* ===== STREAMLIT WIDGET OVERRIDES ===== */
.stTextArea textarea {
    background-color: #fafafa !important;
    border: 1px solid #e5e7eb !important;
    color: #0a0a0a !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
}

.stDataFrame {
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
}

div[data-testid="stFileUploader"] {
    background-color: #fafafa !important;
    border: 1px dashed #d1d5db !important;
    border-radius: 10px !important;
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 0px !important;
    border-bottom: 1px solid #e5e7eb !important;
}

.stTabs [data-baseweb="tab"] {
    color: #6b7280 !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 20px !important;
}

.stTabs [aria-selected="true"] {
    color: #0a0a0a !important;
    border-bottom-color: #0a0a0a !important;
    font-weight: 600 !important;
}

/* Radio buttons */
.stRadio > div {
    gap: 4px !important;
}

.stRadio label {
    font-family: 'Inter', sans-serif !important;
}

/* Info / Success / Error boxes */
.stAlert {
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
}
</style>
"""
