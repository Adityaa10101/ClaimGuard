import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from src.extractor import extract_claim_from_narrative
from src.rules_engine import verify_claim

# Load environment variables from .env file
load_dotenv()


st.set_page_config(
    page_title="ClaimGuard - ESG Audit Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern design aesthetics
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    }
    .header-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .title-text {
        font-family: 'Inter', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    .subtitle-text {
        color: #94a3b8;
        font-size: 1.05rem;
    }
    .badge-pass {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 1.5rem;
        display: inline-block;
        box-shadow: 0 4px 14px 0 rgba(16, 185, 129, 0.39);
        letter-spacing: 1px;
    }
    .badge-flagged {
        background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 1.5rem;
        display: inline-block;
        box-shadow: 0 4px 14px 0 rgba(239, 68, 68, 0.39);
        letter-spacing: 1px;
    }
    .metric-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f3f4f6;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .code-box {
        background-color: #020617;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #1e293b;
        font-family: monospace;
    }
    </style>
""", unsafe_allow_html=True)

# Application Header
st.markdown("""
    <div class="header-card">
        <div class="title-text">🛡️ ClaimGuard Audit Engine</div>
        <div class="subtitle-text">
            Deterministic ESG & BRSR verification engine. Combines LLM structured claim extraction with pure Python/Pandas mathematical verification to eliminate AI hallucinated math.
        </div>
    </div>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.image("https://img.icons8.com/isometric/100/shield-gradient.png", width=64)
st.sidebar.title("ClaimGuard Audit")
st.sidebar.page_link("app.py", label="🏠 Overview & Architecture", icon=None)
st.sidebar.page_link("pages/Audit_Dashboard.py", label="🚀 Audit Engine Dashboard", icon=None)
st.sidebar.markdown("---")

preset_choice = st.sidebar.radio(
    "Select Evaluation Case:",
    ["Preset 1: Clean Case (2.59% PR Claim)", "Preset 2: Flagged Case (20.00% Fake PR Claim)", "Custom Input Upload"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("API Settings (Optional)")
user_groq_key = st.sidebar.text_input("Groq API Key (Optional)", type="password", help="Leave blank to use zero-config offline rule extractor.")

# Paths setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESET_CLEAN_DIR = os.path.join(BASE_DIR, "data", "preset_clean")
PRESET_FLAGGED_DIR = os.path.join(BASE_DIR, "data", "preset_flagged")

# Load data based on selection
narrative_content = ""
metrics_df = None

col1, col2 = st.columns([1, 1], gap="medium")

if preset_choice == "Preset 1: Clean Case (2.59% PR Claim)":
    narrative_path = os.path.join(PRESET_CLEAN_DIR, "narrative.txt")
    metrics_path = os.path.join(PRESET_CLEAN_DIR, "metrics.csv")
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            narrative_content = f.read()
    if os.path.exists(metrics_path):
        metrics_df = pd.read_csv(metrics_path)

    with col1:
        st.subheader("1. Narrative PR Text & Claim Extraction")
        st.text_area("Raw Narrative Text (BRSR / PR Statement)", value=narrative_content, height=300, disabled=True)

    with col2:
        st.subheader("2. Ground-Truth Tabular Metrics (CSV)")
        st.dataframe(metrics_df, use_container_width=True, height=300)

elif preset_choice == "Preset 2: Flagged Case (20.00% Fake PR Claim)":
    narrative_path = os.path.join(PRESET_FLAGGED_DIR, "narrative.txt")
    metrics_path = os.path.join(PRESET_FLAGGED_DIR, "metrics.csv")
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            narrative_content = f.read()
    if os.path.exists(metrics_path):
        metrics_df = pd.read_csv(metrics_path)

    with col1:
        st.subheader("1. Narrative PR Text & Claim Extraction")
        st.text_area("Raw Narrative Text (BRSR / PR Statement)", value=narrative_content, height=300, disabled=True)

    with col2:
        st.subheader("2. Ground-Truth Tabular Metrics (CSV)")
        st.dataframe(metrics_df, use_container_width=True, height=300)

else:  # Custom Input Upload
    with col1:
        st.subheader("1. Narrative PR Text & Claim Extraction")
        narrative_content = st.text_area(
            "Paste or Type Narrative Text (BRSR / PR Statement)",
            value="",
            height=300,
            placeholder="Paste or type your sustainability PR claim or BRSR narrative text here...",
            help="Type or paste the narrative text containing the PR claim to be audited."
        )

    with col2:
        st.subheader("2. Ground-Truth Tabular Metrics (CSV)")
        uploaded_csv = st.file_uploader("Upload Ground-truth Metrics CSV (metrics.csv)", type=["csv"])
        if uploaded_csv:
            metrics_df = pd.read_csv(uploaded_csv)
            st.dataframe(metrics_df, use_container_width=True, height=200)
        else:
            st.info("Upload a `metrics.csv` file containing ground-truth FY data to complete the audit setup.")


st.markdown("---")

# Execution trigger
if st.button("🚀 Run Deterministic Audit Pipeline", use_container_width=True, type="primary"):
    if not narrative_content or metrics_df is None:
        st.error("Please ensure both narrative text and metrics CSV data are loaded before running the audit.")
    else:
        with st.spinner("Extracting structured claim via LLM & executing pure Python mathematical verification..."):
            # Step 1: Extraction via LLM (or fallback)
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
        st.subheader("3. Deterministic Audit Findings & Verification Report")

        # Top Badge
        status_col, info_col = st.columns([1, 3])
        with status_col:
            if audit_result.status == "PASS":
                st.markdown('<div class="badge-pass">✅ PASS</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="badge-flagged">🚨 FLAGGED</div>', unsafe_allow_html=True)

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
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Claimed Reduction</div>
                    <div class="metric-val">{audit_result.claimed_percentage:.2f}%</div>
                </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Calculated Python Delta</div>
                    <div class="metric-val">{audit_result.calculated_delta:.2f}%</div>
                </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Mathematical Variance</div>
                    <div class="metric-val">{audit_result.variance:.2f}%</div>
                </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Ground Truth ({b_year} → {t_year})</div>
                    <div class="metric-val">{b_val:,.0f} → {t_val:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)

        # Detailed Inspection Tabs
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

