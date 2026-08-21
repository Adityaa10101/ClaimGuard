import streamlit as st
import base64
import os

# ──────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClaimGuard — Deterministic ESG Auditing",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ──────────────────────────────────────────────────────────────────────
# LOAD HERO IMAGE AS BASE64
# ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load_image_b64(path):
    """Load a local image and encode it as base64 for HTML embedding."""
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
hero_b64 = load_image_b64(os.path.join(BASE_DIR, "assets", "hero-illustration.jpg"))


# ──────────────────────────────────────────────────────────────────────
# HIDE STREAMLIT DEFAULT CHROME
# ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    #MainMenu, header[data-testid="stHeader"], footer,
    [data-testid="stToolbar"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebar"] {
        display: none !important;
        visibility: hidden !important;
    }
    .stMainBlockContainer, .block-container,
    [data-testid="stMainBlockContainer"] {
        padding: 0 !important;
        max-width: 100% !important;
    }
    .stApp {
        background-color: #F3F4F6 !important;
    }
    iframe {
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# FULL LANDING PAGE (via st.components.v1.html for full HTML support)
# ──────────────────────────────────────────────────────────────────────

LANDING_PAGE_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">

<style>
/* ===== RESET ===== */
*, *::before, *::after {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

html {{
    scroll-behavior: smooth;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1F2937;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background: #F3F4F6;
    overflow-x: hidden;
}}

a {{ text-decoration: none; }}

.cg-container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 40px;
}}

/* ===== NAVBAR ===== */
.cg-navbar {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    background: rgba(255, 255, 255, 0.97);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid #E5E7EB;
    height: 64px;
}}

.cg-nav-inner {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 40px;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}

.cg-nav-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
}}

.cg-nav-brand svg {{
    width: 30px;
    height: 30px;
    flex-shrink: 0;
}}

.cg-brand-text {{
    font-size: 1.2rem;
    font-weight: 700;
    color: #111827;
    letter-spacing: -0.02em;
}}

.cg-nav-actions {{
    display: flex;
    align-items: center;
    gap: 12px;
}}

.cg-btn-ghost {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 18px;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    background: transparent;
    color: #374151;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
}}

.cg-btn-ghost:hover {{
    background: #F3F4F6;
    border-color: #9CA3AF;
    color: #111827;
}}

.cg-btn-ghost svg {{
    width: 15px;
    height: 15px;
    stroke: currentColor;
}}

.cg-btn-primary {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 22px;
    border: none;
    border-radius: 8px;
    background: #2563EB;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s ease;
    box-shadow: 0 1px 3px rgba(37, 99, 235, 0.25);
}}

.cg-btn-primary:hover {{
    background: #1D4ED8;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35);
    transform: translateY(-1px);
    color: #FFFFFF;
}}

/* ===== HERO ===== */
.cg-hero {{
    padding: 130px 0 90px;
    background: #F3F4F6;
    position: relative;
    overflow: hidden;
}}

.cg-hero::before {{
    content: '';
    position: absolute;
    top: -200px;
    right: -150px;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(37, 99, 235, 0.05) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}}

.cg-hero-grid {{
    display: grid;
    grid-template-columns: 1.1fr 0.9fr;
    gap: 60px;
    align-items: center;
}}

.cg-hero-content {{
    animation: heroFadeUp 0.9s cubic-bezier(0.16, 1, 0.3, 1) both;
}}

.cg-hero h1 {{
    font-size: 3.1rem;
    font-weight: 800;
    line-height: 1.1;
    color: #111827;
    letter-spacing: -0.03em;
    margin-bottom: 22px;
}}

.cg-hero-sub {{
    font-size: 1.1rem;
    color: #4B5563;
    line-height: 1.75;
    max-width: 540px;
}}

.cg-hero-illustration {{
    display: flex;
    justify-content: center;
    animation: heroFadeUp 0.9s cubic-bezier(0.16, 1, 0.3, 1) 0.15s both;
}}

.cg-hero-img {{
    width: 100%;
    max-width: 500px;
    border-radius: 16px;
    filter: drop-shadow(0 20px 40px rgba(0, 0, 0, 0.08));
}}

/* ===== PROBLEM SECTION (DARK) ===== */
.cg-problem {{
    padding: 100px 0;
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
    color: #FFFFFF;
    position: relative;
    overflow: hidden;
}}

.cg-problem::before {{
    content: '';
    position: absolute;
    top: -40%;
    right: -15%;
    width: 550px;
    height: 550px;
    background: radial-gradient(circle, rgba(37, 99, 235, 0.1) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}}

.cg-problem h2 {{
    font-size: 2.6rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    margin-bottom: 12px;
    position: relative;
}}

.cg-problem-sub {{
    font-size: 1.2rem;
    color: #94A3B8;
    font-weight: 500;
    margin-bottom: 32px;
    font-style: italic;
    position: relative;
}}

.cg-problem-body {{
    font-size: 1.0625rem;
    color: #CBD5E1;
    line-height: 1.85;
    max-width: 820px;
    position: relative;
}}

/* ===== ARCHITECTURE TIMELINE ===== */
.cg-architecture {{
    padding: 100px 0;
    background: #F3F4F6;
}}

.cg-architecture h2 {{
    font-size: 2.3rem;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.025em;
    margin-bottom: 64px;
    text-align: center;
}}

.cg-timeline {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    position: relative;
    padding: 0 10px;
}}

.cg-timeline::before {{
    content: '';
    position: absolute;
    top: 32px;
    left: 12%;
    right: 12%;
    height: 3px;
    background: linear-gradient(90deg, #2563EB 0%, #06B6D4 33%, #10B981 66%, #8B5CF6 100%);
    border-radius: 4px;
    z-index: 0;
}}

.cg-timeline-step {{
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    flex: 1;
    position: relative;
    z-index: 1;
    cursor: pointer;
    padding: 0 12px;
}}

.cg-step-icon {{
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: #FFFFFF;
    border: 2.5px solid #E5E7EB;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 18px;
    transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}}

.cg-step-icon svg {{
    width: 26px;
    height: 26px;
    stroke: #6B7280;
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: stroke 0.3s ease;
}}

.cg-timeline-step:hover .cg-step-icon {{
    border-color: #2563EB;
    background: #EFF6FF;
    box-shadow: 0 6px 24px rgba(37, 99, 235, 0.2);
    transform: scale(1.12);
}}

.cg-timeline-step:hover .cg-step-icon svg {{
    stroke: #2563EB;
}}

.cg-step-label {{
    font-size: 0.7rem;
    font-weight: 700;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 6px;
}}

.cg-step-title {{
    font-size: 1rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 6px;
    transition: color 0.3s ease;
}}

.cg-timeline-step:hover .cg-step-title {{
    color: #2563EB;
}}

.cg-step-detail {{
    font-size: 0.85rem;
    color: #6B7280;
    line-height: 1.6;
    max-height: 0;
    overflow: hidden;
    opacity: 0;
    transition: max-height 0.45s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.35s ease 0.05s;
    max-width: 220px;
}}

.cg-timeline-step:hover .cg-step-detail {{
    max-height: 160px;
    opacity: 1;
}}

/* ===== VERIFICATION CARDS ===== */
.cg-verification {{
    padding: 100px 0;
    background: #FFFFFF;
}}

.cg-verification h2 {{
    font-size: 2.3rem;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.025em;
    margin-bottom: 52px;
    text-align: center;
}}

.cg-cards-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 24px;
}}

.cg-card {{
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 28px 24px;
    cursor: default;
    transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
                box-shadow 0.35s ease;
}}

.cg-card:hover {{
    transform: translateY(-6px);
    box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.12),
                0 4px 12px rgba(0, 0, 0, 0.04);
}}

.cg-card-icon {{
    width: 48px;
    height: 48px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 18px;
}}

.cg-card-icon svg {{
    width: 24px;
    height: 24px;
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}}

.cg-emissions {{ background: #FEE2E2; }}
.cg-emissions svg {{ stroke: #DC2626; }}
.cg-energy {{ background: #FEF3C7; }}
.cg-energy svg {{ stroke: #D97706; }}
.cg-water {{ background: #DBEAFE; }}
.cg-water svg {{ stroke: #2563EB; }}
.cg-logic {{ background: #E0E7FF; }}
.cg-logic svg {{ stroke: #4F46E5; }}

.cg-card h3 {{
    font-size: 1.1rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 10px;
}}

.cg-card p {{
    font-size: 0.875rem;
    color: #6B7280;
    line-height: 1.65;
}}

/* ===== ROADMAP ===== */
.cg-roadmap {{
    padding: 100px 0;
    background: #F3F4F6;
}}

.cg-roadmap h2 {{
    font-size: 2.3rem;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.025em;
    margin-bottom: 52px;
    text-align: center;
}}

.cg-roadmap-list {{
    max-width: 740px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
}}

.cg-roadmap-item {{
    display: flex;
    align-items: flex-start;
    gap: 20px;
    padding: 28px;
    background: #FFFFFF;
    border-radius: 12px;
    border: 1px solid #E5E7EB;
    transition: all 0.35s ease;
    opacity: 0;
    transform: translateX(-24px);
    animation: staggerSlideIn 0.65s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}}

.cg-roadmap-item:nth-child(1) {{ animation-delay: 0.1s; }}
.cg-roadmap-item:nth-child(2) {{ animation-delay: 0.28s; }}
.cg-roadmap-item:nth-child(3) {{ animation-delay: 0.46s; }}

.cg-roadmap-item:hover {{
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.07);
    transform: translateX(6px);
}}

.cg-roadmap-icon {{
    width: 50px;
    height: 50px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}

.cg-roadmap-icon svg {{
    width: 24px;
    height: 24px;
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}}

.cg-pdf {{ background: #DBEAFE; }}
.cg-pdf svg {{ stroke: #2563EB; }}
.cg-api {{ background: #D1FAE5; }}
.cg-api svg {{ stroke: #059669; }}
.cg-trend {{ background: #EDE9FE; }}
.cg-trend svg {{ stroke: #7C3AED; }}

.cg-roadmap-content h3 {{
    font-size: 1.05rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 6px;
}}

.cg-roadmap-content p {{
    font-size: 0.9rem;
    color: #6B7280;
    line-height: 1.7;
}}

/* ===== FOOTER ===== */
.cg-footer {{
    padding: 36px 0;
    background: #FFFFFF;
    border-top: 1px solid #E5E7EB;
    text-align: center;
}}

.cg-footer p {{
    font-size: 0.875rem;
    color: #9CA3AF;
    font-weight: 400;
}}

/* ===== ANIMATIONS ===== */
@keyframes heroFadeUp {{
    from {{ opacity: 0; transform: translateY(32px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

@keyframes staggerSlideIn {{
    from {{ opacity: 0; transform: translateX(-24px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}

/* ===== SCROLL ANIMATIONS ===== */
.cg-animate {{
    opacity: 0;
    transform: translateY(30px);
    transition: opacity 0.7s ease, transform 0.7s ease;
}}

.cg-animate.cg-visible {{
    opacity: 1;
    transform: translateY(0);
}}

/* ===== RESPONSIVE ===== */
@media (max-width: 1024px) {{
    .cg-hero-grid {{ grid-template-columns: 1fr; gap: 40px; }}
    .cg-hero h1 {{ font-size: 2.5rem; }}
    .cg-cards-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .cg-timeline {{ flex-direction: column; align-items: center; gap: 32px; }}
    .cg-timeline::before {{ display: none; }}
    .cg-step-detail {{ max-height: none; opacity: 1; }}
    .cg-container {{ padding: 0 24px; }}
}}

@media (max-width: 640px) {{
    .cg-hero {{ padding: 110px 0 60px; }}
    .cg-hero h1 {{ font-size: 2rem; }}
    .cg-problem h2, .cg-architecture h2,
    .cg-verification h2, .cg-roadmap h2 {{ font-size: 1.8rem; }}
    .cg-cards-grid {{ grid-template-columns: 1fr; }}
    .cg-nav-inner {{ padding: 0 16px; }}
    .cg-container {{ padding: 0 18px; }}
    .cg-problem, .cg-architecture,
    .cg-verification, .cg-roadmap {{ padding: 70px 0; }}
}}
</style>
</head>

<body>

    <!-- ═══════════ NAVBAR ═══════════ -->
    <nav class="cg-navbar">
        <div class="cg-nav-inner">
            <div class="cg-nav-brand">
                <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M16 2L4 7v8c0 7.18 5.12 13.84 12 15 6.88-1.16 12-7.82 12-15V7L16 2z" fill="#2563EB" fill-opacity="0.12" stroke="#2563EB" stroke-width="2"/>
                    <path d="M11.5 16l3 3 6-6" stroke="#2563EB" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                </svg>
                <span class="cg-brand-text">ClaimGuard</span>
            </div>
            <div class="cg-nav-actions">
                <a href="/Audit_Dashboard" class="cg-btn-ghost" target="_parent">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
                        <path d="M8 12V3M8 3L4.5 6.5M8 3l3.5 3.5M2 14h12"/>
                    </svg>
                    Upload
                </a>
                <a href="/Audit_Dashboard" class="cg-btn-primary" target="_parent">View Results</a>
            </div>
        </div>
    </nav>

    <!-- ═══════════ SECTION 1: HERO ═══════════ -->
    <section class="cg-hero" id="hero">
        <div class="cg-container cg-hero-grid">
            <div class="cg-hero-content">
                <h1>Welcome to ClaimGuard: Deterministic ESG Auditing</h1>
                <p class="cg-hero-sub">
                    Eliminating the ESG greenwashing trap by pairing LLM semantic claim extraction
                    with pure Python deterministic mathematical verification. Never trust an AI
                    to do the math &mdash; verify it deterministically.
                </p>
            </div>
            <div class="cg-hero-illustration">
                <img class="cg-hero-img" src="data:image/jpeg;base64,{hero_b64}" alt="ClaimGuard illustration">
            </div>
        </div>
    </section>

    <!-- ═══════════ SECTION 2: THE PROBLEM (DARK) ═══════════ -->
    <section class="cg-problem cg-animate" id="problem">
        <div class="cg-container">
            <h2>The AI Greenwashing Trap</h2>
            <p class="cg-problem-sub">Why standard LLMs fail at compliance auditing.</p>
            <p class="cg-problem-body">
                Corporate sustainability reports are filled with qualitative PR narratives that
                often mask the actual tabular data. While GenAI is incredible at reading these
                narratives, standard LLMs hallucinate arithmetic. You cannot trust an LLM to
                calculate a Year-over-Year emissions delta. ClaimGuard solves this by bridging
                the gap between semantic understanding and deterministic truth.
            </p>
        </div>
    </section>

    <!-- ═══════════ SECTION 3: ARCHITECTURE TIMELINE ═══════════ -->
    <section class="cg-architecture cg-animate" id="architecture">
        <div class="cg-container">
            <h2>Semantic Extraction meets Deterministic Math.</h2>
            <div class="cg-timeline">
                <div class="cg-timeline-step">
                    <div class="cg-step-icon">
                        <svg viewBox="0 0 24 24"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 13H8"/><path d="M16 17H8"/><path d="M16 13h-2"/></svg>
                    </div>
                    <span class="cg-step-label">Step 1</span>
                    <span class="cg-step-title">Unstructured Ingestion</span>
                    <p class="cg-step-detail">Feed in PR narratives and ground-truth tabular CSVs (like SEBI BRSR filings).</p>
                </div>
                <div class="cg-timeline-step">
                    <div class="cg-step-icon">
                        <svg viewBox="0 0 24 24"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/></svg>
                    </div>
                    <span class="cg-step-label">Step 2</span>
                    <span class="cg-step-title">LLM JSON Extraction</span>
                    <p class="cg-step-detail">Llama-3 via Groq parses the text into strict schemas, isolating the metric, baseline, and claimed reduction percentage. Zero math is performed here.</p>
                </div>
                <div class="cg-timeline-step">
                    <div class="cg-step-icon">
                        <svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M8 6h8"/><path d="M8 10h2"/><path d="M14 10h2"/><path d="M8 14h2"/><path d="M14 14h2"/><path d="M8 18h8"/></svg>
                    </div>
                    <span class="cg-step-label">Step 3</span>
                    <span class="cg-step-title">Dynamic Pandas Verification</span>
                    <p class="cg-step-detail">Our pure Python engine maps the extracted years to the CSV headers and calculates the exact formulas dynamically.</p>
                </div>
                <div class="cg-timeline-step">
                    <div class="cg-step-icon">
                        <svg viewBox="0 0 24 24"><rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/></svg>
                    </div>
                    <span class="cg-step-label">Step 4</span>
                    <span class="cg-step-title">Evidence &amp; Audit Trails</span>
                    <p class="cg-step-detail">Generates an immutable, JSON-backed audit report highlighting the exact mathematical variance.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- ═══════════ SECTION 4: VERIFICATION CARDS ═══════════ -->
    <section class="cg-verification cg-animate" id="verification">
        <div class="cg-container">
            <h2>Comprehensive ESG Validation Domains</h2>
            <div class="cg-cards-grid">
                <div class="cg-card">
                    <div class="cg-card-icon cg-emissions">
                        <svg viewBox="0 0 24 24"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>
                    </div>
                    <h3>Emissions Engine</h3>
                    <p>Validates absolute change, percentage drops, and Scope 1 &amp; 2 subtotal consistency against ground-truth CSV data.</p>
                </div>
                <div class="cg-card">
                    <div class="cg-card-icon cg-energy">
                        <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                    </div>
                    <h3>Energy Engine</h3>
                    <p>Cross-checks renewable energy ratios against total energy consumption limits and validates percentage bounds.</p>
                </div>
                <div class="cg-card">
                    <div class="cg-card-icon cg-water">
                        <svg viewBox="0 0 24 24"><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/></svg>
                    </div>
                    <h3>Water Engine</h3>
                    <p>Audits withdrawal variances and facility water recycling percentages to ensure metric integrity.</p>
                </div>
                <div class="cg-card">
                    <div class="cg-card-icon cg-logic">
                        <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
                    </div>
                    <h3>General Logic</h3>
                    <p>Enforces period alignment, unit consistency, and absolute mathematical bounds (e.g., flagging &gt;100% reductions).</p>
                </div>
            </div>
        </div>
    </section>

    <!-- ═══════════ SECTION 5: ROADMAP ═══════════ -->
    <section class="cg-roadmap cg-animate" id="roadmap">
        <div class="cg-container">
            <h2>Built for Enterprise Scale</h2>
            <div class="cg-roadmap-list">
                <div class="cg-roadmap-item">
                    <div class="cg-roadmap-icon cg-pdf">
                        <svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                    </div>
                    <div class="cg-roadmap-content">
                        <h3>Full PDF RAG Pipelines</h3>
                        <p>Transitioning from text snippets to ingesting 150-page SEBI reports autonomously using Retrieval-Augmented Generation and OCR extraction pipelines.</p>
                    </div>
                </div>
                <div class="cg-roadmap-item">
                    <div class="cg-roadmap-icon cg-api">
                        <svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>
                    </div>
                    <div class="cg-roadmap-content">
                        <h3>Headless Microservices</h3>
                        <p>Decoupling the rules engine into a standalone FastAPI endpoint for seamless ERP integration by banks, rating agencies, and ESG auditors.</p>
                    </div>
                </div>
                <div class="cg-roadmap-item">
                    <div class="cg-roadmap-icon cg-trend">
                        <svg viewBox="0 0 24 24"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                    </div>
                    <div class="cg-roadmap-content">
                        <h3>Multi-Year Trend Analysis</h3>
                        <p>Moving beyond Year-over-Year checks to 5-year rolling averages to catch systemic data manipulation and long-term greenwashing patterns.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- ═══════════ FOOTER ═══════════ -->
    <footer class="cg-footer">
        <div class="cg-container">
            <p>Built for Prasunethon 2.0 Hackathon (Round 2)</p>
        </div>
    </footer>

    <!-- ═══════════ SCROLL ANIMATION JS ═══════════ -->
    <script>
        const observer = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    entry.target.classList.add('cg-visible');
                }}
            }});
        }}, {{ threshold: 0.15 }});

        document.querySelectorAll('.cg-animate').forEach(el => observer.observe(el));
    </script>

</body>
</html>
"""

# Render the full landing page using st.components.v1.html
# This supports full HTML/CSS/JS without Streamlit stripping tags
st.components.v1.html(LANDING_PAGE_HTML, height=3200, scrolling=True)
