"""
ClaimGuard — Enterprise Streamlit Dashboard

Production-grade ESG consistency validator interface.
Upload a BRSR filing → Extract claims → Run 15 deterministic rules → See results.

The AI does NOT decide compliance. It only extracts.
The deterministic rules engine makes all PASS/FAIL decisions.
"""

import os
import time
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.schemas import (
    Claim, ClaimCategory, ValidationStatus, Severity, Authority,
    AuditReport, ProcessingTime, detect_category,
)
from src.extractor import extract_claims_from_narrative, extract_claim_from_narrative
from src.rules import create_default_engine
from src.rules_engine import verify_claim
from src.audit_trail import save_audit_report, export_report_json

load_dotenv()

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ClaimGuard — ESG Consistency Validator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.main { background-color: #0f172a; }
.stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); }

/* Header */
.cg-header {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.cg-title {
    font-family: 'Inter', sans-serif;
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 6px 0;
    letter-spacing: -0.5px;
}
.cg-subtitle {
    color: #94a3b8;
    font-size: 1.0rem;
    font-family: 'Inter', sans-serif;
}
.cg-filing-info {
    color: #e2e8f0;
    font-size: 1.1rem;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    margin-top: 8px;
}

/* Summary Stats */
.stat-bar {
    display: flex;
    gap: 12px;
    margin: 16px 0 24px 0;
}
.stat-item {
    flex: 1;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    padding: 16px 20px;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.stat-num {
    font-size: 2rem;
    font-weight: 800;
    color: #f1f5f9;
    line-height: 1.2;
}
.stat-lbl {
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}

/* Finding Cards */
.finding-card {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 12px;
    font-family: 'Inter', sans-serif;
    transition: all 0.2s ease;
}
.finding-card:hover {
    border-color: rgba(255, 255, 255, 0.12);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}
.finding-card.fail-high {
    border-left: 4px solid #ef4444;
}
.finding-card.fail-medium {
    border-left: 4px solid #f97316;
}
.finding-card.fail-low {
    border-left: 4px solid #eab308;
}
.finding-card.pass {
    border-left: 4px solid #22c55e;
}
.finding-card.unsupported {
    border-left: 4px solid #6b7280;
}

.finding-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.finding-title {
    font-weight: 700;
    font-size: 1.0rem;
    color: #e2e8f0;
}
.finding-badge {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-fail { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
.badge-pass { background: rgba(34, 197, 94, 0.2); color: #86efac; }
.badge-unsupported { background: rgba(107, 114, 128, 0.2); color: #d1d5db; }
.badge-deterministic { background: rgba(56, 189, 248, 0.15); color: #7dd3fc; }
.badge-heuristic { background: rgba(251, 191, 36, 0.15); color: #fcd34d; }

.finding-detail {
    font-size: 0.9rem;
    color: #94a3b8;
    line-height: 1.6;
}
.finding-metric {
    display: flex;
    gap: 24px;
    margin-top: 8px;
}
.finding-metric-item {
    font-size: 0.85rem;
    color: #cbd5e1;
}
.finding-metric-item strong {
    color: #f1f5f9;
}

/* Timing bar */
.timing-bar {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    padding: 16px 24px;
    font-family: 'Inter', sans-serif;
    margin-top: 16px;
}
.timing-title {
    font-size: 0.8rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
}
.timing-items {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}
.timing-item {
    font-size: 0.9rem;
    color: #cbd5e1;
}
.timing-item strong {
    color: #38bdf8;
}
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.markdown("### 🛡️ ClaimGuard")
st.sidebar.markdown("**ESG Consistency Validator**")
st.sidebar.markdown("---")

# Data source selection
st.sidebar.subheader("📁 Filing Source")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPANIES_DIR = os.path.join(BASE_DIR, "data", "companies")
PRESET_CLEAN = os.path.join(BASE_DIR, "data", "preset_clean")
PRESET_FLAGGED = os.path.join(BASE_DIR, "data", "preset_flagged")

# Build company list
company_options = ["Custom Upload"]
company_filings = {}

# Add demo companies
if os.path.exists(COMPANIES_DIR):
    for company_dir in sorted(os.listdir(COMPANIES_DIR)):
        company_path = os.path.join(COMPANIES_DIR, company_dir)
        if os.path.isdir(company_path):
            filings_path = os.path.join(company_path, "filings")
            if os.path.exists(filings_path):
                for filing_dir in sorted(os.listdir(filings_path)):
                    filing_path = os.path.join(filings_path, filing_dir)
                    if os.path.isdir(filing_path):
                        label = f"{company_dir.replace('_', ' ').title()} — {filing_dir.upper()}"
                        company_options.append(label)
                        company_filings[label] = filing_path

# Add legacy presets
if os.path.exists(PRESET_CLEAN):
    company_options.append("Preset: Clean Case (2.59%)")
    company_filings["Preset: Clean Case (2.59%)"] = PRESET_CLEAN
if os.path.exists(PRESET_FLAGGED):
    company_options.append("Preset: Flagged Case (20%)")
    company_filings["Preset: Flagged Case (20%)"] = PRESET_FLAGGED

selected_source = st.sidebar.selectbox("Select Filing", company_options)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")
user_api_key = st.sidebar.text_input(
    "Groq API Key (Optional)",
    type="password",
    help="Leave blank to use offline regex extractor.",
)
tolerance = st.sidebar.slider(
    "Tolerance (% points)", 0.0, 5.0, 0.05, 0.01,
    help="Maximum allowed variance before flagging."
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**Engine:** 15 deterministic rules  \n"
    f"**Authority:** Deterministic (no LLM math)  \n"
    f"**Version:** 2.0 (Round 2)"
)


# ─── Data Loading ────────────────────────────────────────────────────────────

narrative_content = ""
metrics_df = None
company_name = ""
filing_period = ""

if selected_source == "Custom Upload":
    company_name = "Custom Filing"
    filing_period = "N/A"
else:
    filing_path = company_filings.get(selected_source, "")
    if filing_path:
        # Parse company name and period from path
        parts = selected_source.split(" — ")
        company_name = parts[0].replace("Preset: ", "") if parts else "Unknown"
        filing_period = parts[1] if len(parts) > 1 else ""

        narrative_path = os.path.join(filing_path, "narrative.txt")
        metrics_path = os.path.join(filing_path, "metrics.csv")

        if os.path.exists(narrative_path):
            with open(narrative_path, "r", encoding="utf-8") as f:
                narrative_content = f.read()
        if os.path.exists(metrics_path):
            metrics_df = pd.read_csv(metrics_path)


# ─── Header ──────────────────────────────────────────────────────────────────

header_info = ""
if company_name and company_name != "Custom Filing":
    header_info = f'<div class="cg-filing-info">{company_name} • {filing_period}</div>'

st.markdown(f"""
<div class="cg-header">
    <div class="cg-title">🛡️ ClaimGuard</div>
    <div class="cg-subtitle">
        Deterministic ESG Consistency Validator — AI extracts, Python validates, math decides.
    </div>
    {header_info}
</div>
""", unsafe_allow_html=True)


# ─── Input Section ───────────────────────────────────────────────────────────

col_input, col_data = st.columns([1, 1], gap="medium")

with col_input:
    st.markdown("#### 📝 Narrative Text")
    if selected_source == "Custom Upload":
        narrative_content = st.text_area(
            "Paste BRSR / ESG narrative text",
            value="",
            height=280,
            placeholder="Paste sustainability PR claim or BRSR narrative text here...",
            label_visibility="collapsed",
        )
    else:
        st.text_area(
            "Narrative text (read-only)",
            value=narrative_content,
            height=280,
            disabled=True,
            label_visibility="collapsed",
        )

with col_data:
    st.markdown("#### 📊 Source Metrics (CSV)")
    if selected_source == "Custom Upload":
        uploaded_csv = st.file_uploader(
            "Upload metrics CSV",
            type=["csv"],
            label_visibility="collapsed",
        )
        if uploaded_csv:
            metrics_df = pd.read_csv(uploaded_csv)
            st.dataframe(metrics_df, use_container_width=True, height=240)
        else:
            st.info("Upload a `metrics.csv` file with ground-truth data.")
    else:
        if metrics_df is not None:
            st.dataframe(metrics_df, use_container_width=True, height=240)
        else:
            st.warning("No metrics CSV found for this filing.")


# ─── Execution ───────────────────────────────────────────────────────────────

st.markdown("---")

run_col, _, info_col = st.columns([2, 4, 2])
with run_col:
    run_clicked = st.button(
        "🚀 Run Audit Pipeline",
        use_container_width=True,
        type="primary",
    )
with info_col:
    st.caption("15 rules • Deterministic • Auditable")

if run_clicked:
    if not narrative_content or metrics_df is None:
        st.error("⚠️ Please provide both narrative text and metrics CSV.")
    else:
        # ── Step 1: Extract Claims ──
        with st.spinner("🔍 Extracting claims from narrative..."):
            t0 = time.time()
            claims = extract_claims_from_narrative(
                narrative_text=narrative_content,
                company=company_name,
                api_key=user_api_key if user_api_key else None,
            )
            extraction_time = time.time() - t0

        # ── Step 2: Run Rules Engine ──
        with st.spinner("⚡ Running 15 deterministic validation rules..."):
            engine = create_default_engine()
            pt = ProcessingTime(ai_extraction_s=round(extraction_time, 3))
            report = engine.evaluate_all(
                claims=claims,
                source_data=metrics_df,
                company=company_name,
                filing_period=filing_period,
                processing_time=pt,
            )

        # ── Step 3: Save Audit Trail ──
        save_path = save_audit_report(report)

        # ── Step 4: Display Results ──
        st.markdown("---")

        # Summary Stats Bar
        s = report.summary
        fail_color = "#ef4444" if s.failed > 0 else "#22c55e"

        st.markdown(f"""
        <div class="stat-bar">
            <div class="stat-item">
                <div class="stat-num">{s.total_claims}</div>
                <div class="stat-lbl">Claims Analyzed</div>
            </div>
            <div class="stat-item">
                <div class="stat-num" style="color: #22c55e;">{s.passed}</div>
                <div class="stat-lbl">Passed</div>
            </div>
            <div class="stat-item">
                <div class="stat-num" style="color: {fail_color};">{s.failed}</div>
                <div class="stat-lbl">Failed</div>
            </div>
            <div class="stat-item">
                <div class="stat-num" style="color: #6b7280;">{s.unsupported}</div>
                <div class="stat-lbl">Unsupported</div>
            </div>
            <div class="stat-item">
                <div class="stat-num" style="color: #ef4444;">{s.high_severity_failures}</div>
                <div class="stat-lbl">🔴 High Severity</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Findings (sorted by severity) ──
        st.markdown("#### 📋 Validation Findings")

        # Sort: FAIL-HIGH first, then FAIL-MEDIUM, FAIL-LOW, UNSUPPORTED, PASS
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
        status_order = {"FAIL": 0, "UNSUPPORTED": 1, "PASS": 2}

        sorted_results = sorted(
            report.results,
            key=lambda r: (
                status_order.get(r.status.value if hasattr(r.status, 'value') else r.status, 9),
                severity_order.get(r.severity.value if hasattr(r.severity, 'value') else r.severity, 9),
            ),
        )

        for i, result in enumerate(sorted_results):
            status_val = result.status.value if hasattr(result.status, 'value') else result.status
            severity_val = result.severity.value if hasattr(result.severity, 'value') else result.severity
            authority_val = result.authority.value if hasattr(result.authority, 'value') else result.authority

            # Card class
            if status_val == "FAIL":
                card_class = f"fail-{severity_val.lower()}"
                severity_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}.get(severity_val, "⚪")
                badge_class = "badge-fail"
                badge_text = f"{severity_icon} {severity_val} — FAIL"
            elif status_val == "PASS":
                card_class = "pass"
                severity_icon = "🟢"
                badge_class = "badge-pass"
                badge_text = "✓ PASS"
            else:
                card_class = "unsupported"
                severity_icon = "⚪"
                badge_class = "badge-unsupported"
                badge_text = "— UNSUPPORTED"

            # Authority badge
            auth_badge = ""
            if authority_val == "HEURISTIC":
                auth_badge = '<span class="finding-badge badge-heuristic">⚠ HEURISTIC</span>'
            else:
                auth_badge = '<span class="finding-badge badge-deterministic">✓ DETERMINISTIC</span>'

            # Metrics display
            metrics_html = ""
            if result.reported_value is not None and result.calculated_value is not None:
                metrics_html = f"""
                <div class="finding-metric">
                    <div class="finding-metric-item"><strong>Reported:</strong> {result.reported_value}</div>
                    <div class="finding-metric-item"><strong>Calculated:</strong> {result.calculated_value}</div>
                    <div class="finding-metric-item"><strong>Variance:</strong> {result.variance if result.variance else 'N/A'}</div>
                </div>
                """

            st.markdown(f"""
            <div class="finding-card {card_class}">
                <div class="finding-header">
                    <div class="finding-title">{result.rule_name}</div>
                    <div>
                        <span class="finding-badge {badge_class}">{badge_text}</span>
                        {auth_badge}
                    </div>
                </div>
                <div class="finding-detail">{result.explanation}</div>
                {metrics_html}
            </div>
            """, unsafe_allow_html=True)

            # Expandable evidence
            with st.expander(f"🔍 Evidence & Formula — {result.rule_id}", expanded=False):
                ev_col1, ev_col2 = st.columns(2)
                with ev_col1:
                    st.markdown("**Rule ID:**")
                    st.code(result.rule_id)
                    st.markdown("**Formula:**")
                    st.code(result.formula if result.formula else "N/A")
                with ev_col2:
                    st.markdown("**Source Evidence:**")
                    st.code(result.source_evidence if result.source_evidence else "N/A")
                    st.markdown("**Claim ID:**")
                    st.code(result.claim_id if result.claim_id else "N/A")

        # ── Processing Time ──
        pt = report.processing_time
        st.markdown(f"""
        <div class="timing-bar">
            <div class="timing-title">⏱️ Processing Time</div>
            <div class="timing-items">
                <div class="timing-item">AI Extraction: <strong>{pt.ai_extraction_s:.2f}s</strong></div>
                <div class="timing-item">Validation: <strong>{pt.validation_s:.3f}s</strong></div>
                <div class="timing-item">Total: <strong>{pt.total_s:.2f}s</strong></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Extracted Claims & Audit Report ──
        st.markdown("---")
        tab1, tab2, tab3 = st.tabs([
            "📋 Extracted Claims",
            "📊 Full Audit Report (JSON)",
            "📁 Audit Trail",
        ])

        with tab1:
            for c in report.claims:
                cat_val = c.category.value if hasattr(c.category, 'value') else c.category
                st.markdown(f"**{c.claim_id}** — {c.metric} ({cat_val})")
                st.json({
                    "claim_id": c.claim_id,
                    "metric": c.metric,
                    "category": cat_val,
                    "reported_value": c.reported_value,
                    "reported_unit": c.reported_unit,
                    "previous_period": c.previous_period,
                    "current_period": c.current_period,
                    "source_text": c.source_text[:200],
                    "confidence": c.confidence,
                })

        with tab2:
            report_json = export_report_json(report)
            st.download_button(
                "⬇️ Download Audit Report JSON",
                data=report_json,
                file_name=f"{report.report_id}.json",
                mime="application/json",
            )
            st.json(report.model_dump())

        with tab3:
            st.success(f"✅ Audit report saved: `{save_path}`")
            st.markdown(
                f"**Report ID:** `{report.report_id}`  \n"
                f"**Timestamp:** `{report.timestamp}`  \n"
                f"**Company:** `{report.company}`  \n"
                f"**Filing:** `{report.filing_period}`"
            )
            st.markdown(
                "The complete evidence chain for every decision is stored in "
                "the audit report JSON. Each finding traces back to: "
                "**Claim → Source Text → Rule → Formula → Calculation → Decision.**"
            )
