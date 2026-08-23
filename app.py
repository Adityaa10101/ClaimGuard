import os
import streamlit as st
import pandas as pd
from typing import Optional
from dotenv import load_dotenv
from src.extractor import extract_claim_from_narrative
from src.rules_engine import verify_claim
from src.pdf import (
    parse_pdf,
    EvidenceExtractor,
    discover_claims_in_document,
    discover_claims_from_text,
    audit_pdf_claim,
    ClaimCandidate,
    EntityBoundary,
    ExtractionMethod,
    EvidenceType,
    PDFAuditResult,
)

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

/* Strict Light Theme Controls for Native Streamlit Widgets */
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] label span,
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    color: #0a0a0a !important;
    font-weight: 500 !important;
}

div[data-testid="stTextArea"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stFileUploader"] label {
    color: #0a0a0a !important;
    font-weight: 600 !important;
}

div[data-testid="stTextArea"] textarea {
    background-color: #ffffff !important;
    color: #0a0a0a !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
}

div[data-testid="stTextArea"] textarea:disabled {
    background-color: #f9fafb !important;
    color: #374151 !important;
    border: 1px solid #e5e7eb !important;
    -webkit-text-fill-color: #374151 !important;
}

div[data-testid="stTextInput"] input {
    background-color: #ffffff !important;
    color: #0a0a0a !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
}

div[data-testid="stFileUploader"] section {
    background-color: #fafafa !important;
    border: 1px dashed #d1d5db !important;
    border-radius: 10px !important;
}

div[data-testid="stFileUploader"] section [data-testid="stMarkdownContainer"] span,
div[data-testid="stFileUploader"] section [data-testid="stMarkdownContainer"] small {
    color: #4b5563 !important;
}

div[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
}

div[data-testid="stExpander"] summary span {
    color: #0a0a0a !important;
    font-weight: 600 !important;
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

.cg-badge-unverified {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #fffbeb;
    color: #b45309;
    border: 1px solid #fde68a;
    border-radius: 9999px;
    padding: 8px 24px;
    font-weight: 700;
    font-size: 1.1rem;
}

.cg-badge-source {
    display: inline-flex;
    align-items: center;
    background: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    border-radius: 9999px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.cg-badge-derived {
    display: inline-flex;
    align-items: center;
    background: #eef2ff;
    color: #4f46e5;
    border: 1px solid #c7d2fe;
    border-radius: 9999px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.cg-pdf-provenance-banner {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 22px;
}

.cg-evidence-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 14px 16px;
    transition: all 0.15s ease;
}

.cg-evidence-card:hover {
    border-color: #d1d5db;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
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

/* VISUAL ARCHITECTURE FLOW DIAGRAM */
.cg-arch-visual {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 36px 24px;
    margin: 1.5rem 0;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.cg-arch-row {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
}

.cg-arch-top {
    max-width: 560px;
    width: 100%;
    gap: 80px;
    display: flex;
    justify-content: center;
}

.cg-arch-node {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px 22px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    min-width: 220px;
    max-width: 320px;
    transition: all 0.2s ease;
}

.cg-arch-node:hover {
    border-color: #0a0a0a;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.cg-arch-node-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #0a0a0a;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}

.cg-arch-node-desc {
    font-size: 0.82rem;
    color: #6b7280;
    line-height: 1.4;
}

.cg-arch-svg-fork {
    width: 100%;
    max-width: 560px;
    height: 40px;
    display: block;
}

.cg-arch-mobile-connector {
    display: none;
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

    .cg-arch-top {
        flex-direction: column;
        gap: 0px;
    }
    .cg-arch-svg-fork {
        display: none;
    }
    .cg-arch-mobile-connector {
        display: block !important;
        width: 2px;
        height: 20px;
        background-color: #d1d5db;
        margin: 8px 0;
    }
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
<h1 class="cg-hero-title">ClaimGuard<br><span class="cg-gradient-accent">Trust, made verifiable.</span></h1>
<p class="cg-hero-subtitle">Deterministic verification for ESG claims. LLMs extract the claim. Deterministic rules verify it.</p>
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
<p class="cg-section-desc">LLMs are probabilistic. ESG compliance is deterministic.</p>
</div>
<div class="cg-trap-container">
<div class="cg-trap-side">
<h4>🚨 The Trap</h4>
<p class="cg-trap-text">Large language models cannot reliably perform arithmetic verification, YoY delta calculations, or compliance checks.</p>
</div>
<div class="cg-sol-side">
<h4>🛡️ The Solution</h4>
<p class="cg-trap-text">ClaimGuard uses LLMs only for semantic extraction. Exact calculations are executed in Python against ground-truth CSV metrics with a strict 0.05% tolerance.</p>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 4. How ClaimGuard Works: Sequential 4-Stage Pipeline
    st.markdown("""<div class="section" id="how-it-works">
<div class="cg-section-header">
<div class="cg-section-tag">Deterministic Workflow &nbsp;•&nbsp; <span class="cg-badge-mvp">CURRENT MVP</span></div>
<div class="cg-section-title">How ClaimGuard Works</div>
<p class="cg-section-desc">A strict four-stage pipeline bridging narratives with quantitative ground truth.</p>
</div>
<div class="cg-pipeline-grid">
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">01 EXTRACT</span>
<span class="cg-step-arrow">→</span>
</div>
<div class="cg-card-title">Unstructured Ingestion</div>
<p class="cg-card-desc">Feed in narrative statements and tabular CSV disclosures.</p>
</div>
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">02 PARSE</span>
<span class="cg-step-arrow">→</span>
</div>
<div class="cg-card-title">LLM Extraction</div>
<p class="cg-card-desc">Groq Llama-3 extracts metric name, baseline year, and claimed percentage.</p>
</div>
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">03 CALCULATE</span>
<span class="cg-step-arrow">→</span>
</div>
<div class="cg-card-title">Python Verification</div>
<p class="cg-card-desc">Pandas dynamically computes exact mathematical deltas and variances.</p>
</div>
<div class="cg-pipeline-card">
<div class="cg-pipeline-badge-row">
<span class="cg-step-num">04 AUDIT</span>
<span class="cg-step-arrow">✓</span>
</div>
<div class="cg-card-title">Verifiable Evidence</div>
<p class="cg-card-desc">Outputs a verified PASS or FLAGGED decision with explicit reasoning.</p>
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
<span class="cg-card-title">Demo Case B — Greenwashing Detected</span>
<span class="cg-badge-flagged" style="font-size: 0.82rem; padding: 4px 14px;">🚨 FLAGGED</span>
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
<div class="cg-stat-label">Decision</div>
<div class="cg-stat-value" style="color: #b91c1c;">FLAGGED</div>
</div>
</div>
</div>

<div class="cg-example-card">
<div class="cg-example-header">
<span class="cg-card-title">Demo Case A — Verified Disclosure</span>
<span class="cg-badge-pass" style="font-size: 0.82rem; padding: 4px 14px;">✅ PASS</span>
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
<div class="cg-stat-label">Decision</div>
<div class="cg-stat-value" style="color: #15803d;">PASS</div>
</div>
</div>
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
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Scope 1 &amp; 2 Summation</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> YoY Percentage Delta</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Base-Year Matching</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Scope 3 Consistency</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Metric-Ton Variance</li>
</ul>
</div>
<div class="cg-card">
<div class="cg-step-label">Domain 2 <span class="cg-badge-count">4 Rules</span></div>
<div class="cg-card-title">Energy</div>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Renewable Mix</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Electricity &amp; Fuel Totals</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Captive Generation</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Energy Intensity</li>
</ul>
</div>
<div class="cg-card">
<div class="cg-step-label">Domain 3 <span class="cg-badge-count">3 Rules</span></div>
<div class="cg-card-title">Water</div>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Withdrawal Variance</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Recycling Rate</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Consumption Intensity</li>
</ul>
</div>
<div class="cg-card">
<div class="cg-step-label">Domain 4 <span class="cg-badge-count">3 Rules</span></div>
<div class="cg-card-title">General</div>
<ul class="cg-rule-list">
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Baseline Year Alignment</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Metric Unit Scale</li>
<li class="cg-rule-item"><span class="cg-rule-bullet">•</span> Impossibility Bounds</li>
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
<p class="cg-section-desc">Two interfaces. One verification engine.</p>
</div>
<div class="cg-arch-visual">
<div class="cg-arch-row cg-arch-top">
<div class="cg-arch-node">
<div class="cg-arch-node-title">Streamlit UI</div>
<div class="cg-arch-node-desc">Interactive audit interface</div>
</div>
<div class="cg-arch-mobile-connector"></div>
<div class="cg-arch-node">
<div class="cg-arch-node-title">FastAPI API</div>
<div class="cg-arch-node-desc">Programmatic audit interface</div>
</div>
</div>
<svg class="cg-arch-svg-fork" viewBox="0 0 560 40" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M 120 0 L 120 20 L 440 20 L 440 0 M 280 20 L 280 40" stroke="#d1d5db" stroke-width="2" stroke-linecap="round"/>
</svg>
<div class="cg-arch-mobile-connector" style="margin-top: 0; margin-bottom: 8px;"></div>
<div class="cg-arch-row">
<div class="cg-arch-node">
<div class="cg-arch-node-title">Extractor</div>
<div class="cg-arch-node-desc">Semantic claim extraction</div>
</div>
</div>
<svg viewBox="0 0 12 30" fill="none" xmlns="http://www.w3.org/2000/svg" style="width: 12px; height: 30px; margin: 6px 0; display: block;">
<line x1="6" y1="0" x2="6" y2="24" stroke="#d1d5db" stroke-width="2"/>
<path d="M 2 20 L 6 26 L 10 20" stroke="#d1d5db" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
<div class="cg-arch-row">
<div class="cg-arch-node">
<div class="cg-arch-node-title">15-Rule Deterministic Engine</div>
<div class="cg-arch-node-desc">Deterministic mathematical verification</div>
</div>
</div>
<svg viewBox="0 0 12 30" fill="none" xmlns="http://www.w3.org/2000/svg" style="width: 12px; height: 30px; margin: 6px 0; display: block;">
<line x1="6" y1="0" x2="6" y2="24" stroke="#d1d5db" stroke-width="2"/>
<path d="M 2 20 L 6 26 L 10 20" stroke="#d1d5db" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
<div class="cg-arch-row">
<div class="cg-arch-node" style="border-color: #0a0a0a; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);">
<div class="cg-arch-node-title">AuditResult</div>
<div class="cg-arch-node-desc">PASS / FLAGGED / UNVERIFIED + evidence</div>
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    # 8. Roadmap / Next Phase (Visually Secondary & Clearly Demarcated)
    st.markdown("""<div class="section" id="roadmap">
<div class="cg-section-header">
<div class="cg-section-tag"><span class="cg-badge-roadmap">NEXT PHASE</span></div>
<div class="cg-section-title">Roadmap</div>
</div>
<div class="cg-grid-3">
<div class="cg-card-secondary">
<div class="cg-card-title">Multi-Claim Document Auditing</div>
<p class="cg-card-desc"><b>What:</b> Automatically audit multiple supported claims from a single BRSR.<br><b>Why:</b> Move from one-claim verification to report-level audit workflows.</p>
</div>
<div class="cg-card-secondary">
<div class="cg-card-title">OCR &amp; Scanned Report Support</div>
<p class="cg-card-desc"><b>What:</b> Extract evidence from scanned and image-based sustainability reports.<br><b>Why:</b> Extend ClaimGuard beyond text-native BRSR filings.</p>
</div>
<div class="cg-card-secondary">
<div class="cg-card-title">Multi-Year Trend Auditing</div>
<p class="cg-card-desc"><b>What:</b> Detect anomalies and inconsistent sustainability trends across reporting cycles.<br><b>Why:</b> Identify suspicious changes and data smoothing over time.</p>
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
# ──────────────────────────────────────────────────────────────────────
# CANDIDATE AUDITABILITY VALIDATION
# ──────────────────────────────────────────────────────────────────────
def is_candidate_auditable(candidate: ClaimCandidate) -> tuple[bool, str]:
    """
    Determines whether a discovered ClaimCandidate is currently supported
    for deterministic audit by the Phase 6C engine and indexed evidence.
    """
    m = (candidate.metric or "").lower().strip()
    text = (candidate.claim_text or "").lower()

    is_scope1 = "scope 1" in m or ("scope 1" in text and "emissions" in text)
    is_scope2 = "scope 2" in m or ("scope 2" in text and "emissions" in text)
    is_combined = (
        any(k in m for k in ["total scope 1", "combined scope 1", "1 & 2", "1 and 2", "ghg emissions", "greenhouse gas emissions"])
        or (("scope 1" in text or "ghg" in text) and ("scope 2" in text or "emissions" in text))
    )

    if not (is_scope1 or is_scope2 or is_combined):
        return False, "Evidence not currently indexed in deterministic engine."

    if candidate.claimed_percentage is None:
        return False, "Missing quantitative percentage in claim."

    ent = (candidate.entity or "").upper()
    if ent in [EntityBoundary.UNKNOWN.value, "", "UNKNOWN"]:
        return False, "Unspecified corporate entity boundary."

    if not candidate.baseline_year or not candidate.target_year:
        return False, "Unspecified reporting baseline/target years."
    if candidate.baseline_year == candidate.target_year:
        return False, f"Identical baseline and target year ({candidate.baseline_year})."

    return True, "Supported for deterministic audit."


# ──────────────────────────────────────────────────────────────────────
# UNIFIED AUDIT FINDINGS PRESENTATION COMPONENT
# ──────────────────────────────────────────────────────────────────────
def render_audit_findings(audit_result, extracted_claim=None, pdf_audit: Optional[PDFAuditResult] = None):
    st.markdown('<hr class="cg-section-divider">', unsafe_allow_html=True)

    dec = getattr(audit_result, "audit_decision", None)
    dec_val = dec.value if dec else "UNVERIFIED"
    exec_status = getattr(audit_result, "execution_status", None)
    exec_val = exec_status.value if exec_status else "SUCCESS"
    is_unverified = dec_val == "UNVERIFIED" or exec_val in ["MISSING_DATA", "INVALID_DATA", "ERROR"]

    # 1. PDF Audit Provenance Header (if applicable)
    if pdf_audit is not None:
        has_matching_evidence = bool(pdf_audit.evidence or pdf_audit.derived_evidence)

        if has_matching_evidence and pdf_audit.source_pages:
            pages_str = ", ".join(map(str, pdf_audit.source_pages))
        elif pdf_audit.claim.source_page:
            pages_str = str(pdf_audit.claim.source_page)
        else:
            pages_str = "N/A"

        if not has_matching_evidence:
            ev_type_badge = '<span style="font-size: 0.74rem; font-weight: 600; background: #f3f4f6; color: #6b7280; padding: 3px 10px; border-radius: 9999px; border: 1px solid #e5e7eb;">NO MATCHING EVIDENCE</span>'
        elif pdf_audit.evidence_type == EvidenceType.SOURCE_REPORTED.value:
            ev_type_badge = '<span class="cg-badge-source">SOURCE REPORTED</span>'
        else:
            ev_type_badge = '<span class="cg-badge-derived">DERIVED METRIC</span>'

        st.markdown(f'''
        <div class="cg-pdf-provenance-banner">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                <div style="font-size: 0.82rem; font-weight: 700; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; display: flex; align-items: center; gap: 8px;">
                    <span>📑 PDF AUTO-AUDIT PROVENANCE</span> &nbsp;•&nbsp; {ev_type_badge}
                </div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #111827; background: #ffffff; padding: 4px 12px; border-radius: 6px; border: 1px solid #e5e7eb;">
                    📄 {pdf_audit.source_file or "BRSR Document"}
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
                <div>
                    <span style="font-size: 0.72rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em;">Reporting Entity</span><br/>
                    <strong style="color: #0a0a0a; font-size: 0.95rem;">{pdf_audit.entity or pdf_audit.claim.entity}</strong>
                </div>
                <div>
                    <span style="font-size: 0.72rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em;">Target Metric</span><br/>
                    <strong style="color: #0a0a0a; font-size: 0.95rem;">{pdf_audit.claim.metric or "Emissions"}</strong>
                </div>
                <div>
                    <span style="font-size: 0.72rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em;">Source Page</span><br/>
                    <strong style="color: #0a0a0a; font-size: 0.95rem;">Page {pages_str}</strong>
                </div>
                <div>
                    <span style="font-size: 0.72rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em;">Reporting Period</span><br/>
                    <strong style="color: #0a0a0a; font-size: 0.95rem;">{pdf_audit.claim.baseline_year or 'FY24'} → {pdf_audit.claim.target_year or 'FY25'}</strong>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    # 2. Result Hero Banner
    if exec_val == "ERROR":
        hero_cls, hero_icon, hero_title = "cg-badge-unverified", "⚠️", "AUDIT ERROR"
        hero_msg = "Verification could not be completed due to an unexpected execution error."
    elif dec_val == "PASS":
        hero_cls, hero_icon, hero_title = "cg-badge-pass", "✅", "VERIFIED"
        hero_msg = "The narrative claim is mathematically verified against source disclosures within 0.05% tolerance."
    elif dec_val == "FLAGGED":
        hero_cls, hero_icon, hero_title = "cg-badge-flagged", "🚨", "CLAIM FLAGGED"
        hero_msg = "The claimed percentage reduction does not match the independently calculated reduction from source disclosures."
    else:  # UNVERIFIED
        hero_cls, hero_icon, hero_title = "cg-badge-unverified", "⚠️", "AUDIT UNVERIFIED"
        hero_msg = "ClaimGuard will not force an unverified calculation without explicit source normalization support."

    st.markdown(f'''
    <div style="text-align: center; margin-bottom: 2rem;">
        <div class="{hero_cls}" style="font-size: 1.4rem; padding: 10px 30px; margin-bottom: 0.75rem;">
            {hero_icon} {hero_title}
        </div>
        <p style="font-size: 1.05rem; color: #4b5563; margin: 0;">{hero_msg}</p>
    </div>
    ''', unsafe_allow_html=True)

    # 3. Key Metric Strip (Handles UNVERIFIED without fake math)
    if is_unverified:
        claimed_display = f"{audit_result.claimed_percentage:.2f}%" if (audit_result.claimed_percentage is not None and audit_result.claimed_percentage > 0) else "—"
        calc_display = "—"
        var_display = "—"
        var_color = "#6b7280"
    else:
        claimed_display = f"{audit_result.claimed_percentage:.2f}%"
        calc_display = f"{audit_result.calculated_delta:.2f}%"
        var_display = f"{audit_result.variance:.2f}%"
        var_color = "#b91c1c" if audit_result.variance > 0.05 else "#15803d"

    st.markdown('<div class="cg-stage-header">Key Metrics</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Claimed</div>
<div class="metric-val">{claimed_display}</div>
</div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Calculated</div>
<div class="metric-val">{calc_display}</div>
</div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Variance</div>
<div class="metric-val" style="color: {var_color};">{var_display}</div>
</div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""<div class="cg-metric-card">
<div class="metric-lbl">Tolerance</div>
<div class="metric-val">0.05%</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Primary Finding Box
    st.markdown('<div class="cg-stage-header">Primary Finding</div>', unsafe_allow_html=True)
    rule_results = getattr(audit_result, "rule_results", [])
    flagged_rule = next((r for r in rule_results if r.status.value == "FLAGGED"), None)

    if exec_val == "ERROR":
        find_title, find_msg = "Execution Error", "Verification could not be completed."
        find_cls, find_bg, find_border = "#991b1b", "#fef2f2", "#fecaca"
    elif is_unverified:
        discrepancy_str = audit_result.discrepancy_reason or ""
        if "unit mismatch" in discrepancy_str.lower():
            find_title = "Audit Unverified: Unit Semantics Mismatch"
        elif "ambiguous entity" in discrepancy_str.lower():
            find_title = "Audit Unverified: Ambiguous Corporate Entity"
        elif "no source evidence" in discrepancy_str.lower() or "missing" in discrepancy_str.lower():
            find_title = "Audit Unverified: No Matching Tabular Evidence"
        else:
            find_title = f"Audit Unverified: {exec_val.replace('_', ' ')}"
        find_msg = discrepancy_str
        find_cls, find_bg, find_border = "#92400e", "#fffbeb", "#fde68a"
    elif dec_val == "PASS":
        find_title = "Verified Clean"
        find_msg = audit_result.discrepancy_reason or "Disclosed reduction matches independent calculation."
        find_cls, find_bg, find_border = "#166534", "#f0fdf4", "#bbf7d0"
    else:  # FLAGGED
        if flagged_rule:
            find_title = f"{flagged_rule.rule_id} — {flagged_rule.rule_name}"
        else:
            find_title = "Discrepancy Detected"
        find_msg = audit_result.discrepancy_reason
        find_cls, find_bg, find_border = "#991b1b", "#fef2f2", "#fecaca"

    st.markdown(f'''
    <div style="color: {find_cls}; background: {find_bg}; padding: 18px 22px; border-radius: 12px; border: 1px solid {find_border}; margin-bottom: 2rem;">
        <h4 style="margin: 0 0 8px 0; font-size: 1.05rem; color: {find_cls};">{find_title}</h4>
        <p style="margin: 0; font-size: 0.92rem; line-height: 1.5;">{find_msg}</p>
    </div>
    ''', unsafe_allow_html=True)

    # 5. SOURCE EVIDENCE PANEL
    if pdf_audit is not None:
        has_matching_evidence = bool(pdf_audit.evidence or pdf_audit.derived_evidence)
        st.markdown('<div class="cg-stage-header">Source Evidence Disclosures</div>', unsafe_allow_html=True)

        if not has_matching_evidence:
            st.markdown(f'''
            <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px 22px; color: #4b5563; margin-bottom: 2rem;">
                <div style="font-weight: 700; color: #0a0a0a; font-size: 0.95rem; margin-bottom: 6px;">No Matching Source Evidence Found</div>
                <div style="font-size: 0.88rem; line-height: 1.5;">
                    The deterministic engine does not currently have indexed tabular disclosures matching metric <strong>'{pdf_audit.claim.metric or 'Unknown'}'</strong> for entity <strong>{pdf_audit.claim.entity}</strong>.<br/>
                    To maintain strict audit integrity, unrelated disclosures from other sections are never substituted.
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            if pdf_audit.is_derived and pdf_audit.derivation_basis:
                st.markdown(f'''
                <div style="background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 10px; padding: 12px 16px; margin-bottom: 14px; font-size: 0.85rem; color: #3730a3; line-height: 1.5;">
                    <strong>ℹ️ Derivation Basis:</strong> {pdf_audit.derivation_basis}
                </div>
                ''', unsafe_allow_html=True)

            ev_cols = st.columns(min(len(pdf_audit.evidence), 4) if pdf_audit.evidence else 2)
            for i, ev in enumerate(pdf_audit.evidence):
                col_idx = i % len(ev_cols)
                badge_markup = (
                    '<span class="cg-badge-source" style="font-size: 0.7rem; padding: 2px 8px;">SOURCE REPORTED</span>'
                    if ev.evidence_type == EvidenceType.SOURCE_REPORTED.value
                    else '<span class="cg-badge-derived" style="font-size: 0.7rem; padding: 2px 8px;">DERIVED</span>'
                )
                with ev_cols[col_idx]:
                    st.markdown(f'''
                    <div class="cg-evidence-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-size: 0.75rem; font-weight: 700; color: #0a0a0a;">{ev.metric} ({ev.reporting_year})</span>
                            {badge_markup}
                        </div>
                        <div style="font-size: 1.15rem; font-weight: 800; color: #0a0a0a; font-family: 'JetBrains Mono', monospace; margin: 4px 0;">
                            {ev.value:,.0f} <span style="font-size: 0.8rem; font-weight: 600; color: #6b7280;">{ev.unit}</span>
                        </div>
                        <div style="font-size: 0.75rem; color: #6b7280; line-height: 1.4;">
                            • <strong>Raw:</strong> <code>{ev.raw_value}</code><br/>
                            • <strong>Provenance:</strong> Page {ev.page_number} ({ev.entity})
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

    elif extracted_claim is not None:
        b_year = audit_result.baseline_year or "FY23"
        t_year = audit_result.target_year or "FY24"
        b_val = audit_result.baseline_value if audit_result.baseline_value is not None else 0.0
        t_val = audit_result.target_value if audit_result.target_value is not None else 0.0

        if b_val > 0 or t_val > 0:
            st.markdown('<div class="cg-stage-header">Evidence</div>', unsafe_allow_html=True)
            ev_cols = st.columns(4)
            with ev_cols[0]:
                st.markdown(f"**Baseline ({b_year})**<br/>{b_val:,.2f}", unsafe_allow_html=True)
            with ev_cols[1]:
                st.markdown(f"**Target ({t_year})**<br/>{t_val:,.2f}", unsafe_allow_html=True)
            with ev_cols[2]:
                st.markdown(f"**Formula**<br/>`(({b_year} - {t_year}) / {b_year}) * 100`", unsafe_allow_html=True)
            with ev_cols[3]:
                st.markdown(f"**Calculated Reduction**<br/>{audit_result.calculated_delta:.2f}%", unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)

    # 6. Rule Summary
    summary = getattr(audit_result, "summary", None)
    if summary:
        st.markdown('<div class="cg-stage-header">Rule Summary</div>', unsafe_allow_html=True)
        s_cols = st.columns(4)
        s_cols[0].metric("Rules Evaluated", summary.total_rules)
        s_cols[1].metric("Passed", summary.passed)
        s_cols[2].metric("Flagged", summary.flagged)
        s_cols[3].metric("Not Applicable", summary.not_applicable)
        st.markdown("<br>", unsafe_allow_html=True)

    # 7. Detailed Rule Breakdown with expanders
    if rule_results:
        st.markdown('<div class="cg-stage-header">Rule Breakdown</div>', unsafe_allow_html=True)
        for r in rule_results:
            val = r.status.value
            if val == "PASS":
                r_color, r_icon = "#15803d", "✅"
            elif val == "FLAGGED":
                r_color, r_icon = "#b91c1c", "🚨"
            elif val == "NOT_APPLICABLE":
                r_color, r_icon = "#6b7280", "➖"
            else:
                r_color, r_icon = "#92400e", "⚠️"

            with st.expander(f"{r_icon}  {r.rule_id}  |  {r.domain}  |  {r.rule_name}"):
                st.markdown(f"**Status:** <span style='color:{r_color}; font-weight:600;'>{val.replace('_', ' ')}</span>", unsafe_allow_html=True)
                st.markdown(f"**Message:** {r.message}")

                ev = getattr(r, "evidence", None)
                if ev and (ev.baseline_value is not None or r.actual_value is not None or ev.raw_formula):
                    st.markdown("---")
                    st.markdown("**Evidence Data:**")
                    if ev.metric_name: st.markdown(f"- **Metric:** {ev.metric_name}")
                    if ev.baseline_year and ev.baseline_value is not None: st.markdown(f"- **Baseline ({ev.baseline_year}):** {ev.baseline_value:,.2f}")
                    if ev.target_year and ev.target_value is not None: st.markdown(f"- **Target ({ev.target_year}):** {ev.target_value:,.2f}")
                    if r.actual_value is not None: st.markdown(f"- **Actual:** {r.actual_value:,.2f}")
                    if r.expected_value is not None: st.markdown(f"- **Expected:** {r.expected_value:,.2f}")
                    if r.variance is not None: st.markdown(f"- **Variance:** {r.variance:,.2f}")
                    if ev.raw_formula: st.markdown(f"- **Formula:** `{ev.raw_formula}`")

        st.markdown("<br>", unsafe_allow_html=True)

    # 8. Audit Traceability (Metadata)
    st.markdown('<div class="cg-stage-header" style="color: #6b7280; font-size: 0.8rem;">Audit Traceability</div>', unsafe_allow_html=True)
    claim_text_disp = (
        pdf_audit.claim.claim_text
        if pdf_audit is not None
        else (extracted_claim.claim_text if extracted_claim else "N/A")
    )
    b_yr = audit_result.baseline_year or "FY24"
    t_yr = audit_result.target_year or "FY25"
    st.markdown(f'''
    <div style="background: #f9fafb; padding: 16px; border-radius: 8px; border: 1px solid #e5e7eb; font-size: 0.85rem; color: #4b5563; line-height: 1.6;">
        <strong>Narrative Claim:</strong> {claim_text_disp}<br/>
        <strong>Matched Metric:</strong> {audit_result.matched_metric or "N/A"}<br/>
        <strong>Period Range:</strong> {b_yr} → {t_yr}<br/>
        <strong>Execution Status:</strong> {exec_val} ({dec_val})
    </div>
    ''', unsafe_allow_html=True)

    # 9. Result Actions
    st.markdown("<br>", unsafe_allow_html=True)
    nav1, nav2 = st.columns([1, 4])
    with nav1:
        st.markdown('<a href="?view=audit_preset" target="_self" class="cg-btn-primary" style="width:100%; text-align:center;">Run Another</a>', unsafe_allow_html=True)
    with nav2:
        st.markdown('<a href="?view=landing" target="_self" class="cg-btn-secondary">← Back to Home</a>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# VIEW 2: AUDIT ENGINE (PRESET / CUSTOM / PDF AUTO-AUDIT)
# ──────────────────────────────────────────────────────────────────────
def render_audit_view(selected_mode=0):
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
        "Custom Input Upload",
        "PDF Auto-Audit (Real BRSR Document)",
    ]
    default_index = min(max(selected_mode, 0), len(case_options) - 1)

    ctrl_col1, ctrl_col2 = st.columns([3, 2], gap="large")
    with ctrl_col1:
        preset_choice = st.radio(
            "Evaluation Case Selection:",
            case_options,
            index=default_index,
            horizontal=False,
            label_visibility="collapsed",
            key="audit_case_selector",
        )
    with ctrl_col2:
        user_groq_key = st.text_input(
            "Groq API Key",
            type="password",
            help="Optional • Used for LLM claim extraction (falls back to local .env or offline parser)",
            key="audit_groq_key_input",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Reset active audit if mode changed
    if st.session_state.get("last_selected_mode") != preset_choice:
        st.session_state["last_selected_mode"] = preset_choice
        st.session_state.pop("active_pdf_audit_res", None)
        st.session_state.pop("active_csv_audit_res", None)

    # ──────────────────────────────────────────────────────────────────
    # MODE 4: PDF AUTO-AUDIT (REAL BRSR DOCUMENT)
    # ──────────────────────────────────────────────────────────────────
    if preset_choice == "PDF Auto-Audit (Real BRSR Document)":
        st.markdown('<div class="cg-stage-header">02 — Upload & Analyze BRSR PDF</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="color: #6b7280; font-size: 0.92rem; margin-bottom: 1rem;">'
            'Upload a SEBI BRSR or corporate sustainability report to automatically discover quantitative claims '
            'and verify them against source disclosures with complete page-level provenance.'
            '</p>',
            unsafe_allow_html=True
        )

        pdf_col1, pdf_col2 = st.columns([1, 1], gap="large")

        with pdf_col1:
            st.markdown('<div class="cg-section-tag">1. Upload Report PDF</div>', unsafe_allow_html=True)
            uploaded_pdf = st.file_uploader(
                "Upload Sustainability Report PDF (BRSR)",
                type=["pdf"],
                key="pdf_auto_audit_uploader",
                help="Upload any BRSR or sustainability PDF report (e.g. Tata Motors FY2024-25 BRSR)."
            )

        with pdf_col2:
            st.markdown('<div class="cg-section-tag">2. Document Status & Controls</div>', unsafe_allow_html=True)

            if not uploaded_pdf:
                st.info("📄 Upload a PDF document on the left to begin automated claim discovery and evidence extraction.")

        if uploaded_pdf:
            import tempfile, hashlib

            pdf_bytes = uploaded_pdf.getvalue()
            pdf_hash = hashlib.md5(pdf_bytes).hexdigest()
            doc_cache_key = f"parsed_doc_{pdf_hash}"

            temp_dir = tempfile.gettempdir()
            temp_pdf_path = os.path.join(temp_dir, f"claimguard_{pdf_hash}_{uploaded_pdf.name}")
            if not os.path.exists(temp_pdf_path):
                with open(temp_pdf_path, "wb") as f:
                    f.write(pdf_bytes)

            # Parse document with caching
            if doc_cache_key not in st.session_state:
                with st.spinner("Parsing document structure, text, and tables..."):
                    st.session_state[doc_cache_key] = parse_pdf(temp_pdf_path)

            parsed_doc = st.session_state[doc_cache_key]

            # Index emissions evidence
            ev_cache_key = f"ev_{pdf_hash}"
            if ev_cache_key not in st.session_state:
                extractor = EvidenceExtractor(parsed_doc)
                st.session_state[ev_cache_key] = extractor.extract_emissions_evidence()
            evidence_list = st.session_state[ev_cache_key]

            ev_pages = sorted(list(set(e.page_number for e in evidence_list)))
            pages_preview = ", ".join(map(str, ev_pages[:6]))
            if len(ev_pages) > 6:
                pages_preview += f" (+{len(ev_pages)-6} more)"

            with pdf_col2:
                st.markdown(f'''
                <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                    <div style="font-weight: 700; color: #0a0a0a; font-size: 0.95rem; margin-bottom: 6px;">📄 {uploaded_pdf.name}</div>
                    <div style="font-size: 0.84rem; color: #6b7280; line-height: 1.6;">
                        • <strong>Size:</strong> {uploaded_pdf.size / (1024*1024):.2f} MB<br/>
                        • <strong>Pages:</strong> {parsed_doc.total_pages} pages parsed ({parsed_doc.parse_time_seconds:.2f}s)<br/>
                        • <strong>Indexed Evidence:</strong> {len(evidence_list)} emissions disclosures on pages {pages_preview}
                    </div>
                </div>
                ''', unsafe_allow_html=True)

                analyze_btn = st.button("🔍 Analyze Report & Discover Claims", type="primary", key="btn_analyze_pdf")

            # ──────────────────────────────────────────────────────────
            # CLAIM DISCOVERY & AUDIT SELECTION
            # ──────────────────────────────────────────────────────────
            effective_key = user_groq_key.strip() if user_groq_key and user_groq_key.strip() else os.getenv("GROQ_API_KEY")
            has_groq = bool(effective_key and not effective_key.startswith("your_"))
            claims_cache_key = f"claims_{pdf_hash}_{has_groq}"

            selected_candidate_to_audit: Optional[ClaimCandidate] = None

            if analyze_btn or claims_cache_key in st.session_state:
                if analyze_btn:
                    with st.spinner("Analyzing document with LLM semantic claim discovery..."):
                        discovery_report = discover_claims_in_document(parsed_doc, api_key=effective_key if has_groq else None)
                        st.session_state[claims_cache_key] = discovery_report

                discovery_report = st.session_state.get(claims_cache_key, {})
                discovered_claims = discovery_report.get("claims", [])

                is_groq_used = any(c.extraction_method == ExtractionMethod.GROQ_LLM.value for c in discovered_claims)
                extraction_label = "Groq / Llama-3" if is_groq_used else "Offline Fallback Extractor"
                extraction_color = "#15803d" if is_groq_used else "#6b7280"

                supported_count = sum(1 for c in discovered_claims if is_candidate_auditable(c)[0])

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(f'''
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <div class="cg-stage-header" style="margin-bottom: 0;">
                        Report Analysis Complete &nbsp;•&nbsp; <span style="color: #15803d;">{len(discovered_claims)} Claims Detected</span> ({supported_count} Auditable)
                    </div>
                    <span style="font-size: 0.8rem; font-weight: 600; background: #f3f4f6; color: {extraction_color}; padding: 4px 12px; border-radius: 9999px; border: 1px solid #e5e7eb;">
                        Extraction: {extraction_label}
                    </span>
                </div>
                ''', unsafe_allow_html=True)

                if discovered_claims:
                    st.markdown('<p style="font-size: 0.88rem; color: #6b7280; margin-bottom: 10px;">Select a supported quantitative claim to audit against source disclosures:</p>', unsafe_allow_html=True)
                    for idx, c in enumerate(discovered_claims):
                        is_auditable, audit_reason = is_candidate_auditable(c)
                        c_card_col1, c_card_col2 = st.columns([4, 1], gap="medium")

                        status_badge = (
                            '<span class="cg-badge-source" style="font-size: 0.7rem; padding: 2px 8px;">SUPPORTED FOR AUDIT</span>'
                            if is_auditable
                            else '<span style="font-size: 0.7rem; font-weight: 600; background: #f3f4f6; color: #4b5563; padding: 2px 8px; border-radius: 9999px; border: 1px solid #e5e7eb;">NEEDS EVIDENCE</span>'
                        )

                        with c_card_col1:
                            metric_display = c.metric or "Quantitative Claim"
                            entity_display = c.entity if c.entity != "UNKNOWN" else "Entity Unspecified"
                            years_display = f"{c.baseline_year or 'N/A'} → {c.target_year or 'N/A'}"
                            pct_display = f"{c.claimed_percentage:.2f}%" if c.claimed_percentage is not None else "N/A"
                            page_display = f"p. {c.source_page}" if c.source_page else "Document text"
                            ext_method = "Groq / Llama" if c.extraction_method == ExtractionMethod.GROQ_LLM.value else "Fallback Regex"

                            reason_note = ""
                            if not is_auditable:
                                reason_note = f'<div style="font-size: 0.78rem; color: #6b7280; margin-top: 4px;">ℹ️ <em>{audit_reason}</em></div>'

                            st.markdown(f'''
                            <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 18px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                                    <span style="font-weight: 700; color: #0a0a0a; font-size: 0.95rem;">{metric_display}</span>
                                    <div style="display: flex; align-items: center; gap: 6px;">
                                        {status_badge}
                                        <span style="font-size: 0.74rem; background: #f9fafb; color: #4b5563; padding: 2px 8px; border-radius: 6px; border: 1px solid #e5e7eb;">{entity_display} • {years_display}</span>
                                    </div>
                                </div>
                                <div style="font-size: 0.88rem; color: #374151; margin-bottom: 6px;">
                                    "{c.claim_text}"
                                </div>
                                <div style="font-size: 0.78rem; color: #6b7280;">
                                    <strong>Claimed:</strong> {pct_display} &nbsp;•&nbsp; <strong>Source:</strong> {page_display} &nbsp;•&nbsp; <strong>Method:</strong> {ext_method}
                                </div>
                                {reason_note}
                            </div>
                            ''', unsafe_allow_html=True)
                        with c_card_col2:
                            if is_auditable:
                                if st.button(f"Verify Claim →", key=f"btn_verify_c_{idx}", use_container_width=True):
                                    selected_candidate_to_audit = c
                            else:
                                st.markdown('<div style="height: 100%; display: flex; align-items: center; justify-content: center; font-size: 0.78rem; color: #9ca3af; text-align: center; padding-top: 14px;">Not Currently<br/>Auditable</div>', unsafe_allow_html=True)

            # ──────────────────────────────────────────────────────────
            # CONTROLLED VERIFICATION SCENARIOS ON DOCUMENT
            # ──────────────────────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="cg-stage-header">Controlled Verification Scenarios (Tested Against Uploaded BRSR)</div>', unsafe_allow_html=True)
            st.markdown('<p style="font-size: 0.88rem; color: #6b7280; margin-bottom: 12px;">Test verified, discrepant, and unit-boundary verification scenarios against the real uploaded disclosures:</p>', unsafe_allow_html=True)

            p_col1, p_col2, p_col3 = st.columns(3, gap="medium")

            with p_col1:
                st.markdown('''
                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 12px; margin-bottom: 8px;">
                    <div style="font-weight: 700; color: #166534; font-size: 0.88rem;">Case A — Controlled Scope 1</div>
                    <div style="font-size: 0.78rem; color: #15803d; margin-top: 4px;">Claimed: 10.22% (FY24 → FY25)<br/>Expected: <strong>PASS (Verified)</strong></div>
                </div>
                ''', unsafe_allow_html=True)
                if st.button("Audit Scope 1 (PASS)", key="btn_preset_pass", use_container_width=True):
                    selected_candidate_to_audit = ClaimCandidate(
                        claim_text="Tata Motors Limited reduced Scope 1 emissions by 10.22% between FY24 and FY25.",
                        metric="Scope 1 Emissions",
                        claimed_percentage=10.22,
                        baseline_year="FY24",
                        target_year="FY25",
                        entity=EntityBoundary.TML.value,
                        source_page=88,
                    )

            with p_col2:
                st.markdown('''
                <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 12px; margin-bottom: 8px;">
                    <div style="font-weight: 700; color: #991b1b; font-size: 0.88rem;">Case B — Controlled Discrepancy</div>
                    <div style="font-size: 0.78rem; color: #b91c1c; margin-top: 4px;">Claimed: 25.00% (FY24 → FY25)<br/>Expected: <strong>FLAGGED (Discrepancy)</strong></div>
                </div>
                ''', unsafe_allow_html=True)
                if st.button("Audit Discrepancy (FLAG)", key="btn_preset_flag", use_container_width=True):
                    selected_candidate_to_audit = ClaimCandidate(
                        claim_text="Tata Motors Limited reduced Scope 1 emissions by 25.00% between FY24 and FY25.",
                        metric="Scope 1 Emissions",
                        claimed_percentage=25.00,
                        baseline_year="FY24",
                        target_year="FY25",
                        entity=EntityBoundary.TML.value,
                        source_page=88,
                    )

            with p_col3:
                st.markdown('''
                <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 12px; margin-bottom: 8px;">
                    <div style="font-weight: 700; color: #92400e; font-size: 0.88rem;">Case C — Controlled Combined Scope 1+2</div>
                    <div style="font-size: 0.78rem; color: #b45309; margin-top: 4px;">Claimed: 20.80% (tCO2e + tCO2)<br/>Expected: <strong>AUDIT UNVERIFIED</strong></div>
                </div>
                ''', unsafe_allow_html=True)
                if st.button("Audit Combined (UNVERIFIED)", key="btn_preset_unverified", use_container_width=True):
                    selected_candidate_to_audit = ClaimCandidate(
                        claim_text="Tata Motors Limited reduced its combined Scope 1 and Scope 2 greenhouse gas emissions by approximately 20.8% between FY24 and FY25.",
                        metric="Total Scope 1 & 2 Emissions",
                        claimed_percentage=20.80,
                        baseline_year="FY24",
                        target_year="FY25",
                        entity=EntityBoundary.TML.value,
                        source_page=88,
                    )

            # Execute audit if a candidate was selected
            if selected_candidate_to_audit is not None:
                # Check if candidate is auditable before executing audit
                is_auditable, audit_reason = is_candidate_auditable(selected_candidate_to_audit)
                if not is_auditable:
                    # Construct controlled unverified result directly without fabricating evidence or math
                    unverified_audit = AuditResult(
                        status="FLAGGED",
                        claimed_percentage=round(selected_candidate_to_audit.claimed_percentage or 0.0, 2),
                        calculated_delta=0.0,
                        variance=0.0,
                        discrepancy_reason=f"PDF Audit Unverified: {audit_reason}",
                        matched_metric=selected_candidate_to_audit.metric,
                        baseline_year=selected_candidate_to_audit.baseline_year or "FY24",
                        target_year=selected_candidate_to_audit.target_year or "FY25",
                        audit_decision=AuditDecision.UNVERIFIED,
                        execution_status=ExecutionStatus.MISSING_DATA,
                        summary=RuleSummaryCounts(total_rules=1, missing_data=1),
                    )
                    st.session_state["active_pdf_audit_res"] = PDFAuditResult(
                        audit_result=unverified_audit,
                        claim=selected_candidate_to_audit,
                        evidence=[],
                        derived_evidence=[],
                        is_derived=False,
                        evidence_type=EvidenceType.SOURCE_REPORTED.value,
                        derivation_basis=None,
                        source_file=uploaded_pdf.name,
                        source_pages=[selected_candidate_to_audit.source_page] if selected_candidate_to_audit.source_page else [],
                        entity=selected_candidate_to_audit.entity,
                        match_status=audit_reason,
                    )
                else:
                    with st.spinner("Auditing claim against extracted BRSR evidence..."):
                        pdf_audit_res = audit_pdf_claim(
                            claim=selected_candidate_to_audit,
                            document=parsed_doc,
                            evidence_list=evidence_list,
                            tolerance=0.05,
                        )
                        st.session_state["active_pdf_audit_res"] = pdf_audit_res

            # Display active PDF audit result
            if "active_pdf_audit_res" in st.session_state:
                pdf_res = st.session_state["active_pdf_audit_res"]
                render_audit_findings(audit_result=pdf_res.audit_result, pdf_audit=pdf_res)

        return

    # ──────────────────────────────────────────────────────────────────
    # MODES 1-3: CSV / PRESET AUDIT FLOWS (PRESERVED 100%)
    # ──────────────────────────────────────────────────────────────────
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
            uploaded_csv = st.file_uploader("Upload Ground-Truth Metrics CSV", type=["csv"], key="csv_metrics_uploader")
            if uploaded_csv:
                metrics_df = pd.read_csv(uploaded_csv)
                st.success(f"✓ `{uploaded_csv.name}` loaded successfully ({len(metrics_df)} rows).")
                st.dataframe(metrics_df, use_container_width=True, height=170)
            else:
                st.info("Upload a `metrics.csv` file containing ground-truth FY columns to complete the audit setup.")

    # Stage 03: Run Verification
    st.markdown('<div class="cg-action-area"><div class="cg-stage-header">03 — Execute Verification</div></div>', unsafe_allow_html=True)

    action_col1, action_col2 = st.columns([2, 1])
    with action_col1:
        run_audit_pressed = st.button("Run Deterministic Audit →", type="primary", key="run_audit_pipeline_btn")

    if run_audit_pressed:
        if not narrative_content or metrics_df is None:
            st.error("Please ensure both narrative text and metrics CSV data are loaded before running the audit.")
        else:
            with st.spinner("Extracting structured claim via LLM & executing pure Python mathematical verification..."):
                effective_key = user_groq_key.strip() if user_groq_key and user_groq_key.strip() else None
                extracted_claim = extract_claim_from_narrative(
                    narrative_text=narrative_content,
                    api_key=effective_key
                )
                audit_result = verify_claim(
                    claim=extracted_claim,
                    metrics_source=metrics_df
                )
                st.session_state["active_csv_audit_res"] = (audit_result, extracted_claim)

    if "active_csv_audit_res" in st.session_state:
        res, claim = st.session_state["active_csv_audit_res"]
        render_audit_findings(audit_result=res, extracted_claim=claim)


# ──────────────────────────────────────────────────────────────────────
# SPA DISPATCHER
# ──────────────────────────────────────────────────────────────────────
if st.session_state.current_view == "landing":
    render_landing_view()
elif st.session_state.current_view == "audit_custom":
    render_audit_view(selected_mode=2)
elif st.session_state.current_view == "audit_pdf":
    render_audit_view(selected_mode=3)
else:  # audit_preset
    render_audit_view(selected_mode=0)
