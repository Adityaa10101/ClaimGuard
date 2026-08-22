import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from src.extractor import extract_claim_from_narrative
from src.rules_engine import verify_claim

# Load environment variables (.env)
load_dotenv()

# ──────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION (SPA)
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClaimGuard — Deterministic ESG Auditing",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ──────────────────────────────────────────────────────────────────────
# STRICT LIGHT THEME & GLOBAL RESET CSS
# ──────────────────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Smooth scrolling and anchor offset for fixed/sticky navigation */
html {
    scroll-behavior: smooth;
}

section[id], div[id] {
    scroll-margin-top: 130px !important;
}

/* Forcefully hide Streamlit default sidebar and header chrome */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
header { visibility: hidden !important; height: 0 !important; }
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }

/* Global App Container — Strict Light Theme & Typography Scale */
.stApp {
    background-color: #ffffff !important;
    color: #0a0a0a !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    font-size: 1.05rem;
}

.main {
    overflow: visible !important;
}

.main .block-container {
    padding-top: 5.5rem !important;
    padding-bottom: 4rem !important;
    max-width: 1200px !important;
    overflow: visible !important;
}

/* Universal Link Styling — Zero Default Underlines */
a, a:hover, a:focus, a:active, a:visited {
    text-decoration: none !important;
}

/* Reusable Section Spacing System & Master Grid Alignment */
.section {
    max-width: 1200px;
    margin: 0 auto;
    padding: 70px 24px;
    box-sizing: border-box;
}

.hero-section {
    padding: 10px 24px 35px 24px;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    color: #0a0a0a !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
}

/* Ensure Material Icon ligatures are preserved and never overridden by plain text */
[data-testid="stIconMaterial"],
[data-testid="stIcon"],
.material-icons,
.material-symbols-rounded,
.material-symbols-outlined,
[class*="material-symbols"],
[class*="material-icons"] {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}

/* Native Streamlit Buttons (Pills) */
.stButton > button {
    border-radius: 9999px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    white-space: nowrap !important;
    cursor: pointer !important;
    text-decoration: none !important;
}

.stButton > button[kind="primary"],
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #0a0a0a !important;
    color: #ffffff !important;
    border: none !important;
    padding: 12px 32px !important;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1) !important;
}

.stButton > button[kind="primary"]:hover,
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #262626 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15) !important;
}

.stButton > button[kind="secondary"],
div[data-testid="stButton"] > button[kind="secondary"] {
    background-color: #ffffff !important;
    color: #0a0a0a !important;
    border: 1px solid #e5e5e5 !important;
    padding: 10px 24px !important;
}

.stButton > button[kind="secondary"]:hover,
div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background-color: #f9fafb !important;
    border-color: #0a0a0a !important;
}

/* Fixed/Sticky Top Navbar Container — Smoothly persists across entire scroll */
.cg-navbar-wrapper {
    position: fixed !important;
    top: 14px !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 999999 !important;
    pointer-events: none !important;
    display: flex !important;
    justify-content: center !important;
    padding: 0 24px !important;
}

.cg-navbar {
    width: 100% !important;
    max-width: 1200px !important;
    pointer-events: auto !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding: 12px 24px !important;
    background: rgba(255, 255, 255, 0.95) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 9999px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06) !important;
    margin: 0 auto !important;
}

.cg-nav-left {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none !important;
}

.cg-logo-icon {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
}

.cg-logo-text {
    display: flex;
    flex-direction: column;
}

.cg-brand {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0a0a0a;
    letter-spacing: -0.02em;
    line-height: 1.1;
}

.cg-tagline {
    font-size: 0.72rem;
    color: #6b7280;
    font-weight: 400;
    letter-spacing: 0.01em;
}

.cg-nav-center {
    display: flex;
    align-items: center;
    gap: 4px;
    background: #f9fafb;
    padding: 4px;
    border-radius: 9999px;
    border: 1px solid #f3f4f6;
}

.cg-nav-pill {
    padding: 7px 18px;
    border-radius: 9999px;
    font-size: 0.92rem;
    font-weight: 500;
    color: #6b7280;
    text-decoration: none !important;
    transition: all 0.2s ease;
}

.cg-nav-pill:hover {
    color: #0a0a0a;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.cg-nav-right {
    display: flex;
    align-items: center;
    gap: 10px;
}

.cg-nav-action-sec {
    padding: 8px 18px;
    border-radius: 9999px;
    font-size: 0.88rem;
    font-weight: 500;
    color: #0a0a0a;
    background: #ffffff;
    border: 1px solid #e5e5e5;
    text-decoration: none !important;
    transition: all 0.2s ease;
}

.cg-nav-action-sec:hover {
    background: #f9fafb;
    border-color: #0a0a0a;
}

.cg-nav-action-pri {
    padding: 8px 22px;
    border-radius: 9999px;
    font-size: 0.88rem;
    font-weight: 600;
    color: #ffffff !important;
    background: #0a0a0a !important;
    border: none;
    text-decoration: none !important;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    cursor: pointer;
}

.cg-nav-action-pri:hover {
    background: #262626 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    color: #ffffff !important;
}

/* HERO SECTION (CENTERED & BALANCED) */
.cg-hero-container {
    text-align: center;
    max-width: 920px;
    margin: 0 auto;
}

.cg-hero-badge-wrap {
    display: flex;
    justify-content: center;
    margin-bottom: 1.15rem;
}

.cg-micro-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 18px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 9999px;
    font-size: 0.84rem;
    font-weight: 500;
    color: #374151;
    letter-spacing: 0.01em;
}

.cg-pulse-dot {
    width: 8px;
    height: 8px;
    background-color: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
}

.cg-hero-title {
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1.12;
    letter-spacing: -0.035em;
    color: #0a0a0a;
    margin: 0 0 1.1rem 0;
}

.cg-gradient-accent {
    color: #0a0a0a;
    display: inline-block;
}

.cg-hero-subtitle {
    font-size: 1.18rem;
    line-height: 1.65;
    color: #4b5563;
    max-width: 720px;
    margin: 0 auto 1.8rem auto;
    font-weight: 400;
}

/* CTA ACTION BUTTONS */
.cg-cta-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    margin-bottom: 1.75rem;
}

.cg-btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    white-space: nowrap;
    padding: 13px 32px;
    border-radius: 9999px;
    font-size: 0.98rem;
    font-weight: 600;
    color: #ffffff !important;
    background: #0a0a0a !important;
    border: none;
    text-decoration: none !important;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
}

.cg-btn-primary:hover {
    background: #262626 !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
    color: #ffffff !important;
}

.cg-btn-secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    white-space: nowrap;
    padding: 13px 30px;
    border-radius: 9999px;
    font-size: 0.98rem;
    font-weight: 500;
    color: #0a0a0a !important;
    background: #ffffff !important;
    border: 1px solid #e5e5e5;
    text-decoration: none !important;
    cursor: pointer;
    transition: all 0.2s ease;
}

.cg-btn-secondary:hover {
    background: #f9fafb !important;
    border-color: #0a0a0a;
    color: #0a0a0a !important;
    transform: translateY(-2px);
}

/* FEATURE PILLS ROW */
.cg-features-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 10px;
    max-width: 880px;
    margin: 0 auto 1.25rem auto;
}

.cg-feature-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 16px;
    background: #f9fafb;
    border: 1px solid #e5e5e5;
    border-radius: 9999px;
    font-size: 0.84rem;
    font-weight: 500;
    color: #374151;
    transition: all 0.2s ease;
}

.cg-feature-pill:hover {
    background: #ffffff;
    border-color: #0a0a0a;
    color: #0a0a0a;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.cg-hero-flow-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 18px;
    background: #ffffff;
    border: 1px dashed #d1d5db;
    border-radius: 9999px;
    font-size: 0.82rem;
    font-family: 'JetBrains Mono', monospace;
    color: #4b5563;
}

/* SECTIONS */
.cg-section-divider {
    border: none;
    height: 1px;
    background: #e5e7eb;
    margin: 0;
}

.cg-section-header {
    text-align: center;
    max-width: 860px;
    margin: 0 auto 2.25rem auto;
}

.cg-section-tag {
    font-size: 0.78rem;
    font-weight: 700;
    color: #0a0a0a;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.cg-section-title {
    font-size: 2.15rem;
    font-weight: 800;
    color: #0a0a0a;
    letter-spacing: -0.025em;
    margin-bottom: 10px;
}

.cg-section-desc {
    font-size: 1.08rem;
    color: #6b7280;
    max-width: 680px;
    margin: 0 auto;
    line-height: 1.6;
}

/* PIPELINE WORKFLOW (01 -> 02 -> 03 -> 04) */
.cg-pipeline-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}

.cg-pipeline-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 22px;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
    height: 100%;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.cg-pipeline-card:hover {
    border-color: #0a0a0a;
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
}

.cg-pipeline-badge-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}

.cg-step-num {
    font-size: 0.74rem;
    font-weight: 700;
    color: #0a0a0a;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 2px 8px;
    font-family: 'JetBrains Mono', monospace;
}

.cg-step-arrow {
    font-size: 0.88rem;
    color: #9ca3af;
    font-weight: 600;
}

/* CARDS GENERAL */
.cg-grid-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}

.cg-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
}

.cg-grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}

.cg-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 22px;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
    height: 100%;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.cg-card:hover {
    border-color: #0a0a0a;
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
}

.cg-card-secondary {
    background: #fafafa;
    border: 1px dashed #d1d5db;
    border-radius: 14px;
    padding: 22px;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
    height: 100%;
}

.cg-card-secondary:hover {
    border-color: #9ca3af;
    background: #fdfdfd;
}

.cg-step-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
}

.cg-card-title {
    font-size: 1.12rem;
    font-weight: 700;
    color: #0a0a0a;
    margin-bottom: 8px;
    letter-spacing: -0.01em;
}

.cg-card-desc {
    font-size: 0.94rem;
    color: #6b7280;
    line-height: 1.6;
    margin: 0;
}

.cg-rule-list {
    list-style: none;
    padding: 0;
    margin: 12px 0 0 0;
}

.cg-rule-item {
    font-size: 0.88rem;
    color: #4b5563;
    padding: 5px 0;
    display: flex;
    align-items: flex-start;
    gap: 6px;
    line-height: 1.4;
    border-top: 1px solid #f3f4f6;
}

.cg-rule-bullet {
    color: #10b981;
    font-weight: 700;
}

.cg-badge-mvp {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    background: #0a0a0a;
    color: #ffffff;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}

.cg-badge-roadmap {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    background: #e5e7eb;
    color: #4b5563;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}

.cg-badge-future {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 9999px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    font-size: 0.72rem;
    font-weight: 700;
    color: #4b5563;
    letter-spacing: 0.05em;
    margin-bottom: 10px;
    width: fit-content;
}

.cg-badge-count {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    background: #0a0a0a;
    color: #ffffff;
    font-size: 0.7rem;
    font-weight: 700;
    margin-left: 6px;
    vertical-align: middle;
}

/* ARCHITECTURE PIPELINE BOXES */
.cg-arch-container {
    display: grid;
    grid-template-columns: 1fr auto 1fr auto 1fr;
    gap: 12px;
    align-items: center;
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 24px;
    margin: 1rem 0;
}

.cg-arch-box {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    text-align: left;
}

.cg-arch-box h4 {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0a0a0a;
    margin: 0 0 6px 0;
}

.cg-arch-box p {
    font-size: 0.9rem;
    color: #6b7280;
    line-height: 1.5;
    margin: 0;
}

.cg-arch-arrow {
    font-size: 1.35rem;
    color: #9ca3af;
    font-weight: 700;
    text-align: center;
}

/* TRAP & SOLUTION */
.cg-trap-container {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 26px;
    margin: 1rem 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    align-items: center;
}

.cg-trap-side {
    background: #ffffff;
    border: 1px solid #fecaca;
    border-left: 4px solid #ef4444;
    border-radius: 12px;
    padding: 22px;
}

.cg-trap-side h4 {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #991b1b;
}

.cg-sol-side {
    background: #ffffff;
    border: 1px solid #bbf7d0;
    border-left: 4px solid #10b981;
    border-radius: 12px;
    padding: 22px;
}

.cg-sol-side h4 {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #166534;
}

.cg-trap-text {
    font-size: 0.94rem;
    color: #374151;
    line-height: 1.6;
    margin: 0;
}

/* EXAMPLE VERIFICATION SHOWCASE */
.cg-example-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.cg-example-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f3f4f6;
}

.cg-example-claim-box {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 0.92rem;
    color: #374151;
    line-height: 1.5;
    margin-bottom: 16px;
    font-style: italic;
}

.cg-example-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 14px;
}

.cg-stat-box {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px;
    text-align: center;
}

.cg-stat-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 2px;
}

.cg-stat-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0a0a0a;
    font-family: 'JetBrains Mono', monospace;
}

/* AUDIT VIEW COMPONENTS */
.cg-stage-header {
    font-size: 0.9rem;
    font-weight: 700;
    color: #0a0a0a;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.cg-header-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.cg-header-card .cg-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #0a0a0a;
    margin-bottom: 6px;
    letter-spacing: -0.02em;
}

.cg-header-card .cg-subtitle {
    font-size: 0.98rem;
    color: #6b7280;
    line-height: 1.5;
}

.cg-badge-pass {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    border-radius: 9999px;
    padding: 8px 24px;
    font-weight: 700;
    font-size: 1.1rem;
}

.cg-badge-flagged {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #fef2f2;
    color: #b91c1c;
    border: 1px solid #fecaca;
    border-radius: 9999px;
    padding: 8px 24px;
    font-weight: 700;
    font-size: 1.1rem;
}

.cg-metric-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}

.cg-metric-card .metric-lbl {
    font-size: 0.78rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}

.cg-metric-card .metric-val {
    font-size: 1.4rem;
    font-weight: 800;
    color: #0a0a0a;
}

.cg-action-area {
    margin-top: 1rem;
    padding-top: 0.5rem;
}

/* FOOTER */
.cg-footer {
    text-align: center;
    padding: 36px 0 20px 0;
    border-top: 1px solid #e5e7eb;
    margin-top: 2rem;
}

.cg-footer p {
    font-size: 0.9rem;
    color: #9ca3af;
    margin: 0;
}

@media (max-width: 900px) {
    .cg-hero-title { font-size: 2.5rem; }
    .cg-pipeline-grid { grid-template-columns: 1fr 1fr; }
    .cg-grid-4 { grid-template-columns: 1fr 1fr; }
    .cg-grid-3 { grid-template-columns: 1fr; }
    .cg-grid-2 { grid-template-columns: 1fr; }
    .cg-arch-container { grid-template-columns: 1fr; }
    .cg-arch-arrow { display: none; }
    .cg-trap-container { grid-template-columns: 1fr; }
    .cg-nav-center { display: none; }
}
</style>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# SPA ROUTING STATE INITIALIZATION
# ──────────────────────────────────────────────────────────────────────
if "view" in st.query_params:
    qp_view = st.query_params.get("view")
    if qp_view in ["landing", "audit_preset", "audit_custom"]:
        st.session_state.current_view = qp_view

if "current_view" not in st.session_state:
    st.session_state.current_view = "landing"


# ──────────────────────────────────────────────────────────────────────
# STICKY TOP NAVBAR COMPONENT
# ──────────────────────────────────────────────────────────────────────
def render_navbar(active_view="landing"):
    if active_view == "landing":
        st.markdown("""<div class="cg-navbar-wrapper">
<nav class="cg-navbar">
<a href="?view=landing" target="_self" class="cg-nav-left">
<div class="cg-logo-icon">
<svg width="20" height="20" viewBox="0 0 32 32" fill="none">
<path d="M16 2L4 7v8c0 7.18 5.12 13.84 12 15 6.88-1.16 12-7.82 12-15V7L16 2z" fill="#0a0a0a" fill-opacity="0.08" stroke="#0a0a0a" stroke-width="2"/>
<path d="M11.5 16l3 3 6-6" stroke="#0a0a0a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
</div>
<div class="cg-logo-text">
<span class="cg-brand">ClaimGuard</span>
<span class="cg-tagline">Trust, made verifiable.</span>
</div>
</a>
<div class="cg-nav-center">
<a href="#problem" class="cg-nav-pill">Problem</a>
<a href="#how-it-works" class="cg-nav-pill">How It Works</a>
<a href="?view=audit_preset" target="_self" class="cg-nav-pill">Verification</a>
<a href="#architecture" class="cg-nav-pill">Architecture</a>
</div>
<div class="cg-nav-right">
<a href="https://github.com/Adityaa10101/ClaimGuard" target="_blank" class="cg-nav-action-sec">View GitHub</a>
<a href="?view=audit_custom" target="_self" class="cg-nav-action-pri">Run Audit</a>
</div>
</nav>
</div>""", unsafe_allow_html=True)
    else:  # audit view navbar
        st.markdown("""<div class="cg-navbar-wrapper">
<nav class="cg-navbar">
<a href="?view=landing" target="_self" class="cg-nav-left">
<div class="cg-logo-icon">
<svg width="20" height="20" viewBox="0 0 32 32" fill="none">
<path d="M16 2L4 7v8c0 7.18 5.12 13.84 12 15 6.88-1.16 12-7.82 12-15V7L16 2z" fill="#0a0a0a" fill-opacity="0.08" stroke="#0a0a0a" stroke-width="2"/>
<path d="M11.5 16l3 3 6-6" stroke="#0a0a0a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
</div>
<div class="cg-logo-text">
<span class="cg-brand">ClaimGuard</span>
<span class="cg-tagline">Trust, made verifiable.</span>
</div>
</a>
<div class="cg-nav-center">
<a href="?view=landing#problem" target="_self" class="cg-nav-pill">Problem</a>
<a href="?view=landing#how-it-works" target="_self" class="cg-nav-pill">How It Works</a>
<a href="?view=audit_preset" target="_self" class="cg-nav-pill" style="color: #0a0a0a; background: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">Verification</a>
<a href="?view=landing#architecture" target="_self" class="cg-nav-pill">Architecture</a>
</div>
<div class="cg-nav-right">
<a href="https://github.com/Adityaa10101/ClaimGuard" target="_blank" class="cg-nav-action-sec">View GitHub</a>
<a href="?view=landing" target="_self" class="cg-nav-action-pri">← Home</a>
</div>
</nav>
</div>""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# VIEW 1: LANDING & OVERVIEW PAGE
# ──────────────────────────────────────────────────────────────────────
def render_landing_view():
    # 1. Sticky Top Navbar
    render_navbar(active_view="landing")

    # 2. Centered Hero Section (Balanced vertical rhythm)
    st.markdown("""<div class="section hero-section">
<div class="cg-hero-container">
<div class="cg-hero-badge-wrap">
<div class="cg-micro-pill">
<span class="cg-pulse-dot"></span>
<span>Verification Engine Ready &nbsp;•&nbsp; SEBI BRSR Core</span>
</div>
</div>
<h1 class="cg-hero-title">Deterministic ESG Auditing<br><span class="cg-gradient-accent">Reimagined.</span></h1>
<p class="cg-hero-subtitle">LLMs extract the qualitative claim. Pure Python deterministically verifies the numbers against ground-truth tabular disclosures.</p>
<div class="cg-cta-row">
<a href="?view=audit_preset" target="_self" class="cg-btn-primary">
<span>Run ESG Audit</span>
<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>
</a>
<a href="#architecture" class="cg-btn-secondary">
<span>View Architecture</span>
</a>
</div>
<div class="cg-features-row">
<div class="cg-feature-pill">⚡ Deterministic Math</div>
<div class="cg-feature-pill">🧠 Groq Llama-3 Extraction</div>
<div class="cg-feature-pill">🐍 Pure Python Engine</div>
<div class="cg-feature-pill">🎯 0.05% Tolerance</div>
<div class="cg-feature-pill">📑 SEBI BRSR Core</div>
</div>
<div class="cg-hero-flow-pill">
<span>Claim Input</span> → <span>LLM Extraction</span> → <span>Deterministic Verification</span> → <span>PASS / FLAG Proof</span>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 3. Problem: The AI Greenwashing Trap
    st.markdown("""<div class="section" id="problem">
<div class="cg-section-header">
<div class="cg-section-tag">The Fundamental Flaw &nbsp;•&nbsp; <span class="cg-badge-mvp">CURRENT MVP</span></div>
<div class="cg-section-title">The AI Greenwashing Trap</div>
<p class="cg-section-desc">Corporate sustainability disclosures contain qualitative PR narratives masking quantitative tabular metrics.</p>
</div>
<div class="cg-trap-container">
<div class="cg-trap-side">
<h4>🚨 The Probabilistic Arithmetic Risk</h4>
<p class="cg-trap-text">While LLMs excel at natural language parsing, neural networks are non-deterministic and prone to mathematical calculation errors. Large language models should not perform arithmetic verification, YoY delta calculations, or compliance checks.</p>
</div>
<div class="cg-sol-side">
<h4>🛡️ The ClaimGuard Separation</h4>
<p class="cg-trap-text">ClaimGuard strictly separates responsibilities: <strong>LLMs perform semantic claim extraction into typed JSON schemas</strong>, while <strong>deterministic Python executes exact calculations</strong> against ground-truth CSV metrics with a strict 0.05% tolerance threshold.</p>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 4. How ClaimGuard Works: Sequential 4-Stage Pipeline
    st.markdown("""<div class="section" id="how-it-works">
<div class="cg-section-header">
<div class="cg-section-tag">Deterministic Workflow &nbsp;•&nbsp; <span class="cg-badge-mvp">CURRENT MVP</span></div>
<div class="cg-section-title">How ClaimGuard Works</div>
<p class="cg-section-desc">A four-stage sequential pipeline bridging qualitative narratives with quantitative ground truth.</p>
</div>
<div class="cg-pipeline-grid">
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">STAGE 01</span>
<span class="cg-step-arrow">→</span>
</div>
<div class="cg-card-title">Unstructured Ingestion</div>
<p class="cg-card-desc">Feed in PR narrative statements and ground-truth tabular CSV disclosures (SEBI BRSR filings, corporate reports).</p>
</div>
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">STAGE 02</span>
<span class="cg-step-arrow">→</span>
</div>
<div class="cg-card-title">LLM Schema Extraction</div>
<p class="cg-card-desc">Groq Llama-3 strictly parses metric name, baseline year, and claimed percentage into a typed Pydantic JSON schema.</p>
</div>
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">STAGE 03</span>
<span class="cg-step-arrow">→</span>
</div>
<div class="cg-card-title">Python Verification</div>
<p class="cg-card-desc">Pure Python and Pandas dynamically map fiscal year columns, compute exact YoY mathematical deltas, and calculate variance.</p>
</div>
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">STAGE 04</span>
<span class="cg-step-arrow">✓</span>
</div>
<div class="cg-card-title">Verifiable Evidence</div>
<p class="cg-card-desc">Outputs a verifiable audit decision: PASS (variance ≤ 0.05%) or FLAGGED with explicit mathematical reasoning.</p>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 5. Example Verification (Immediate Proof of Product)
    st.markdown("""<div class="section" id="example-verification">
<div class="cg-section-header">
<div class="cg-section-tag">Audit Proof &nbsp;•&nbsp; <span class="cg-badge-mvp">CURRENT MVP</span></div>
<div class="cg-section-title">Example Verification</div>
<p class="cg-section-desc">See how ClaimGuard evaluates PR claims against ground-truth BRSR metrics in practice.</p>
</div>
<div class="cg-grid-2">
<div class="cg-example-card">
<div class="cg-example-header">
<span class="cg-card-title">Demo Case B — Flagged Greenwashing</span>
<span class="cg-badge-flagged" style="font-size: 0.82rem; padding: 4px 14px;">🚨 FLAGGED</span>
</div>
<div class="cg-example-claim-box">
"Achieved a 20.00% reduction in total Scope 1 &amp; Scope 2 greenhouse gas emissions in FY24 compared to FY23 baseline."
</div>
<div class="cg-example-stats">
<div class="cg-stat-box">
<div class="cg-stat-label">Claimed</div>
<div class="cg-stat-value">20.00%</div>
</div>
<div class="cg-stat-box">
<div class="cg-stat-label">Calculated</div>
<div class="cg-stat-value">2.59%</div>
</div>
<div class="cg-stat-box">
<div class="cg-stat-label">Variance</div>
<div class="cg-stat-value" style="color: #b91c1c;">17.41%</div>
</div>
<div class="cg-stat-box">
<div class="cg-stat-label">Tolerance</div>
<div class="cg-stat-value">0.05%</div>
</div>
</div>
<p class="cg-card-desc" style="font-size: 0.86rem; color: #991b1b; background: #fef2f2; padding: 10px 12px; border-radius: 8px; border: 1px solid #fecaca;">
<strong>Finding:</strong> Narrative claims 20.00% drop, but ground-truth tabular CSV shows 10,500 MT → 10,228 MT (actual reduction: 2.59%). Variance exceeds 0.05% threshold.
</p>
</div>

<div class="cg-example-card">
<div class="cg-example-header">
<span class="cg-card-title">Demo Case A — Verified Disclosure</span>
<span class="cg-badge-pass" style="font-size: 0.82rem; padding: 4px 14px;">✅ PASS</span>
</div>
<div class="cg-example-claim-box">
"Achieved a 2.59% reduction in total Scope 1 &amp; Scope 2 greenhouse gas emissions in FY24 compared to FY23 baseline."
</div>
<div class="cg-example-stats">
<div class="cg-stat-box">
<div class="cg-stat-label">Claimed</div>
<div class="cg-stat-value">2.59%</div>
</div>
<div class="cg-stat-box">
<div class="cg-stat-label">Calculated</div>
<div class="cg-stat-value">2.59%</div>
</div>
<div class="cg-stat-box">
<div class="cg-stat-label">Variance</div>
<div class="cg-stat-value" style="color: #15803d;">0.00%</div>
</div>
<div class="cg-stat-box">
<div class="cg-stat-label">Tolerance</div>
<div class="cg-stat-value">0.05%</div>
</div>
</div>
<p class="cg-card-desc" style="font-size: 0.86rem; color: #166534; background: #f0fdf4; padding: 10px 12px; border-radius: 8px; border: 1px solid #bbf7d0;">
<strong>Finding:</strong> Narrative claim matches calculated Python delta from ground-truth disclosures exactly (10,500 MT → 10,228 MT). Variance: 0.00%.
</p>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 6. 15 Deterministic Validation Rules (4 Domains with Counts & Sub-items)
    st.markdown("""<div class="section" id="rules">
<div class="cg-section-header">
<div class="cg-section-tag">Coverage Engine &nbsp;•&nbsp; <span class="cg-badge-mvp">CURRENT MVP</span></div>
<div class="cg-section-title">15 Deterministic Validation Rules</div>
<p class="cg-section-desc">15 deterministic mathematical rules organized into 4 core ESG validation domains.</p>
</div>
<div class="cg-grid-4">
<div class="cg-card">
<div class="cg-step-label">Domain 1 <span class="cg-badge-count">5 Rules</span></div>
<div class="cg-card-title">Emissions</div>
<p class="cg-card-desc">Scope 1, Scope 2, and Scope 3 greenhouse gas auditing rules:</p>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Scope 1 &amp; 2 subtotal summation</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> YoY percentage delta verification</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Base-year restatement matching</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Scope 3 upstream/downstream consistency</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Absolute metric ton variance check</li>
</ul>
</div>
<div class="cg-card">
<div class="cg-step-label">Domain 2 <span class="cg-badge-count">4 Rules</span></div>
<div class="cg-card-title">Energy</div>
<p class="cg-card-desc">Electricity, fuel, and renewable power auditing rules:</p>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Renewable mix percentage check</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Grid electricity &amp; fuel totals</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Captive generation balance</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Energy intensity per revenue ratio</li>
</ul>
</div>
<div class="cg-card">
<div class="cg-step-label">Domain 3 <span class="cg-badge-count">3 Rules</span></div>
<div class="cg-card-title">Water</div>
<p class="cg-card-desc">Consumption, withdrawal, and recycling rules:</p>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Surface vs groundwater variance</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Facility water recycling rate</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Consumption intensity boundary</li>
</ul>
</div>
<div class="cg-card">
<div class="cg-step-label">Domain 4 <span class="cg-badge-count">3 Rules</span></div>
<div class="cg-card-title">General</div>
<p class="cg-card-desc">Fundamental mathematical and boundary logic:</p>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Baseline year period alignment</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Metric unit scale consistency</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> &gt;100% impossibility &amp; zero-div guard</li>
</ul>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 7. Dedicated Architecture Section
    st.markdown("""<div class="section" id="architecture">
<div class="cg-section-header">
<div class="cg-section-tag">System Design &nbsp;•&nbsp; <span class="cg-badge-mvp">CURRENT MVP</span></div>
<div class="cg-section-title">ClaimGuard Verification Architecture</div>
<p class="cg-section-desc">Strict three-layer decoupled architecture ensuring arithmetic integrity across sustainability disclosures.</p>
</div>
<div class="cg-arch-container">
<div class="cg-arch-box">
<h4>1. Semantic Extractor</h4>
<p>Groq Llama-3 / Offline Regex parser converts raw PR text into a structured <code>ExtractedClaim</code> JSON schema. Zero math executed.</p>
</div>
<div class="cg-arch-arrow">→</div>
<div class="cg-arch-box">
<h4>2. Ground-Truth Mapper</h4>
<p>Pandas ingestion layer dynamically maps fiscal year columns (e.g. <code>fy23_value</code>, <code>fy24_value</code>) from tabular <code>metrics.csv</code>.</p>
</div>
<div class="cg-arch-arrow">→</div>
<div class="cg-arch-box">
<h4>3. Deterministic Engine</h4>
<p>Pure Python mathematical engine computes exact percentage deltas and issues a verified <code>PASS</code> or <code>FLAGGED</code> audit result.</p>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 8. Roadmap / Next Phase (Visually Secondary & Clearly Demarcated)
    st.markdown("""<div class="section" id="roadmap">
<div class="cg-section-header">
<div class="cg-section-tag">Post-MVP Vision &nbsp;•&nbsp; <span class="cg-badge-roadmap">NEXT PHASE</span></div>
<div class="cg-section-title">Roadmap / Next Phase</div>
<p class="cg-section-desc">Future enterprise capabilities planned for post-hackathon deployment (not included in current MVP release).</p>
</div>
<div class="cg-grid-3">
<div class="cg-card-secondary">
<div class="cg-badge-future">PLANNED NEXT PHASE</div>
<div class="cg-card-title">150-Page BRSR PDF Ingestion</div>
<p class="cg-card-desc">Automated ingestion of full 150-page annual sustainability filings using OCR, multimodal document parsing, and semantic vector retrieval.</p>
</div>
<div class="cg-card-secondary">
<div class="cg-badge-future">PLANNED NEXT PHASE</div>
<div class="cg-card-title">FastAPI Microservices</div>
<p class="cg-card-desc">Decoupled REST API endpoints for seamless automated integration into enterprise ERP systems, audit firms, and ESG rating providers.</p>
</div>
<div class="cg-card-secondary">
<div class="cg-badge-future">PLANNED NEXT PHASE</div>
<div class="cg-card-title">Multi-Year Trend Auditing</div>
<p class="cg-card-desc">Multi-year rolling trend regression and time-series anomaly detection to identify systemic data smoothing across consecutive reporting cycles.</p>
</div>
</div>
</div>""", unsafe_allow_html=True)

    # 9. Footer
    st.markdown("""<div class="cg-footer">
<p>🛡️ ClaimGuard &nbsp;•&nbsp; Built for Prasunethon 2.0 Hackathon &nbsp;•&nbsp; Deterministic ESG &amp; BRSR Auditing</p>
</div>""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# VIEW 2: AUDIT ENGINE (PRESET / CUSTOM)
# ──────────────────────────────────────────────────────────────────────
def render_audit_view(is_custom=False):
    # Sticky Top Navbar for unified navigation across views
    render_navbar(active_view="audit")

    # Header Card
    st.markdown("""<div class="cg-header-card">
<div class="cg-title">🛡️ ClaimGuard Audit Engine</div>
<div class="cg-subtitle">Deterministic ESG &amp; BRSR verification engine. Combines LLM structured claim extraction with pure Python mathematical verification.</div>
</div>""", unsafe_allow_html=True)

    # Stage 01: Evaluation Case
    st.markdown('<div class="cg-stage-header">01 — Select Evaluation Case</div>', unsafe_allow_html=True)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PRESET_CLEAN_DIR = os.path.join(BASE_DIR, "data", "preset_clean")
    PRESET_FLAGGED_DIR = os.path.join(BASE_DIR, "data", "preset_flagged")

    case_options = [
        "Demo Case A — Verified Claim (Expected: PASS)",
        "Demo Case B — Greenwashing Detected (Expected: FLAG)",
        "Custom Input Upload"
    ]
    default_index = 2 if is_custom else 0

    ctrl_col1, ctrl_col2 = st.columns([3, 2], gap="large")
    with ctrl_col1:
        preset_choice = st.radio(
            "Evaluation Case Selection:",
            case_options,
            index=default_index,
            horizontal=False,
            label_visibility="collapsed"
        )
    with ctrl_col2:
        user_groq_key = st.text_input(
            "Groq API Key",
            type="password",
            help="Optional • Used for LLM claim extraction"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Stage 02: Evidence Ingestion
    st.markdown('<div class="cg-stage-header">02 — Review Evidence Data</div>', unsafe_allow_html=True)

    narrative_content = ""
    metrics_df = None

    col1, col2 = st.columns([1, 1], gap="large")

    if preset_choice == "Demo Case A — Verified Claim (Expected: PASS)":
        narrative_path = os.path.join(PRESET_CLEAN_DIR, "narrative.txt")
        metrics_path = os.path.join(PRESET_CLEAN_DIR, "metrics.csv")
        if os.path.exists(narrative_path):
            with open(narrative_path, "r", encoding="utf-8") as f:
                narrative_content = f.read()
        if os.path.exists(metrics_path):
            metrics_df = pd.read_csv(metrics_path)

        with col1:
            st.markdown('<div class="cg-section-tag">1. Narrative PR Text</div>', unsafe_allow_html=True)
            st.text_area("Raw Narrative Text (BRSR / PR Statement)", value=narrative_content, height=270, disabled=True, label_visibility="collapsed")

        with col2:
            st.markdown('<div class="cg-section-tag">2. Ground-Truth Metrics (CSV)</div>', unsafe_allow_html=True)
            st.dataframe(metrics_df, use_container_width=True, height=270)

    elif preset_choice == "Demo Case B — Greenwashing Detected (Expected: FLAG)":
        narrative_path = os.path.join(PRESET_FLAGGED_DIR, "narrative.txt")
        metrics_path = os.path.join(PRESET_FLAGGED_DIR, "metrics.csv")
        if os.path.exists(narrative_path):
            with open(narrative_path, "r", encoding="utf-8") as f:
                narrative_content = f.read()
        if os.path.exists(metrics_path):
            metrics_df = pd.read_csv(metrics_path)

        with col1:
            st.markdown('<div class="cg-section-tag">1. Narrative PR Text</div>', unsafe_allow_html=True)
            st.text_area("Raw Narrative Text (BRSR / PR Statement)", value=narrative_content, height=270, disabled=True, label_visibility="collapsed")

        with col2:
            st.markdown('<div class="cg-section-tag">2. Ground-Truth Metrics (CSV)</div>', unsafe_allow_html=True)
            st.dataframe(metrics_df, use_container_width=True, height=270)

    else:  # Custom Input Upload
        with col1:
            st.markdown('<div class="cg-section-tag">1. Narrative PR Text</div>', unsafe_allow_html=True)
            narrative_content = st.text_area(
                "Paste or Type Narrative Text (BRSR / PR Statement)",
                value="",
                height=250,
                placeholder="Paste or type your sustainability PR claim or BRSR narrative text here...",
                label_visibility="collapsed"
            )

        with col2:
            st.markdown('<div class="cg-section-tag">2. Ground-Truth Metrics (CSV)</div>', unsafe_allow_html=True)
            uploaded_csv = st.file_uploader("Upload Ground-Truth Metrics CSV", type=["csv"])
            if uploaded_csv:
                metrics_df = pd.read_csv(uploaded_csv)
                st.success(f"✓ `{uploaded_csv.name}` loaded successfully ({len(metrics_df)} rows).")
                st.dataframe(metrics_df, use_container_width=True, height=170)
            else:
                st.info("Upload a `metrics.csv` file containing ground-truth FY columns to complete the audit setup.")

    # Stage 03: Run Verification (Placed directly below Step 02 without excessive gap)
    st.markdown('<div class="cg-action-area"><div class="cg-stage-header">03 — Execute Verification</div></div>', unsafe_allow_html=True)

    action_col1, action_col2 = st.columns([2, 1])
    with action_col1:
        run_audit_pressed = st.button("Run Deterministic Audit →", type="primary", key="run_audit_pipeline_btn")

    if run_audit_pressed:
        if not narrative_content or metrics_df is None:
            st.error("Please ensure both narrative text and metrics CSV data are loaded before running the audit.")
        else:
            with st.spinner("Extracting structured claim via LLM & executing pure Python mathematical verification..."):
                # Step 1: Extraction via LLM (or offline fallback)
                extracted_claim = extract_claim_from_narrative(
                    narrative_text=narrative_content,
                    api_key=user_groq_key if user_groq_key else None
                )

                # Step 2: Deterministic Rules Engine verification (Pure Python Math)
                audit_result = verify_claim(
                    claim=extracted_claim,
                    metrics_source=metrics_df
                )

            # Audit Findings Presentation
            st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)
            st.markdown('<div class="cg-section-title">Audit Findings &amp; Verification Report</div>', unsafe_allow_html=True)

            status_col, info_col = st.columns([1, 3])
            with status_col:
                if audit_result.status == "PASS":
                    st.markdown('<div class="cg-badge-pass">✅ PASS</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="cg-badge-flagged">🚨 FLAGGED</div>', unsafe_allow_html=True)

            with info_col:
                if audit_result.status == "PASS":
                    st.success(audit_result.discrepancy_reason)
                else:
                    st.error(audit_result.discrepancy_reason)

            st.markdown("<br>", unsafe_allow_html=True)

            # Quantitative Breakdown Metrics
            m1, m2, m3, m4 = st.columns(4)
            b_year = audit_result.baseline_year or "FY23"
            t_year = audit_result.target_year or "FY24"
            b_val = audit_result.baseline_value if audit_result.baseline_value is not None else 0.0
            t_val = audit_result.target_value if audit_result.target_value is not None else 0.0

            with m1:
                st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Claimed Reduction</div>
<div class="metric-val">{audit_result.claimed_percentage:.2f}%</div>
</div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Calculated Python Delta</div>
<div class="metric-val">{audit_result.calculated_delta:.2f}%</div>
</div>""", unsafe_allow_html=True)
            with m3:
                st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Mathematical Variance</div>
<div class="metric-val">{audit_result.variance:.2f}%</div>
</div>""", unsafe_allow_html=True)
            with m4:
                st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Ground Truth ({b_year} → {t_year})</div>
<div class="metric-val">{b_val:,.0f} → {t_val:,.0f}</div>
</div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            t1, t2 = st.tabs(["📋 Extracted Claim JSON (LLM Output)", "📊 Deterministic Math Details"])

            with t1:
                st.json(extracted_claim.model_dump())
            with t2:
                st.markdown(f"""
                **Ground Truth Metric Row**: `{audit_result.matched_metric}`  
                **Baseline ({b_year})**: `{b_val:,.2f}`  
                **Target ({t_year})**: `{t_val:,.2f}`  
                **Formula**: `(({b_year}_Value - {t_year}_Value) / {b_year}_Value) * 100`  
                **Calculated Reduction**: `(({b_val:,.2f} - {t_val:,.2f}) / {b_val:,.2f}) * 100 = {audit_result.calculated_delta}%`  
                """)


# ──────────────────────────────────────────────────────────────────────
# SPA DISPATCHER
# ──────────────────────────────────────────────────────────────────────
if st.session_state.current_view == "landing":
    render_landing_view()
elif st.session_state.current_view == "audit_custom":
    render_audit_view(is_custom=True)
else:  # audit_preset
    render_audit_view(is_custom=False)
