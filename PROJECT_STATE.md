# ClaimGuard MVP — Complete Technical Reference & Project State

> **Official Technical Specification & Codebase Reference**  
> *Built for Prasunethon 2.0 Hackathon | Repository: `Adityaa10101/ClaimGuard`*

---

## Executive System Context

**ClaimGuard** is an enterprise-grade, deterministic ESG (Environmental, Social, and Governance) & BRSR (Business Responsibility and Sustainability Reporting) claim verification engine engineered to detect corporate greenwashing and mathematical discrepancies in corporate sustainability filings.

### 🛡️ The Immutable Core Rule
**We strictly separate semantic parsing from mathematical validation.**  
LLMs (Large Language Models) are non-deterministic and prone to arithmetic hallucination. Therefore, LLMs are **explicitly forbidden** from calculating reductions, variances, or compliance decisions. 

* **The LLM Layer (Semantic Extractor):** Employs Groq API (`llama-3.3-70b-versatile`) in strict JSON mode strictly to parse unstructured narrative text into structured Pydantic schemas (`ExtractedClaim`).
* **The Offline Fallback (Regex Extractor):** A multi-pattern regex parsing engine that activates when the API is unavailable, unconfigured, or invalid, ensuring 100% offline resilience.
* **The Deterministic Layer (Audit Engine):** Uses pure Python and Pandas to read ground-truth CSV metrics, dynamically map fiscal year columns (e.g., `fy23_value`, `fy24_value`, `fy25_value`), compute exact percentage deltas, and execute tolerance verification against claimed values.
* **The Multi-Page UI Layer:** A modern Streamlit web application with a responsive overview landing page (`app.py`) and a dedicated real-time interactive audit engine dashboard (`pages/Audit_Dashboard.py`).

---

## 1. System Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                 1. USER INTERFACE LAYER                                   │
│   • Landing & Architecture Page (app.py): Hero, Greenwashing Trap, Architecture Roadmap   │
│   • Audit Engine Dashboard (pages/Audit_Dashboard.py): Presets & Custom File Upload       │
└─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                               2. SEMANTIC EXTRACTION LAYER                                │
│   • src/extractor.py                                                                      │
│   • Primary: Groq API (llama-3.3-70b-versatile) with strict JSON mode                     │
│   • Offline Fallback: Multi-pattern Regex Sentence & Number Scanner                       │
│   • Output: ExtractedClaim Pydantic object (Metric, Claimed %, Baseline/Target Years)     │
└─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                             3. DETERMINISTIC AUDIT LAYER                                  │
│   • src/rules_engine.py                                                                   │
│   • Pure Python & Pandas (metrics.csv)                                                    │
│   • Dynamic Column Matcher: Maps baseline_year/target_year to arbitrary fiscal headers    │
│   • Math Formula:                                                                         │
│        Calculated Delta % = ((Baseline Value - Target Value) / Baseline Value) * 100      │
│        Variance % = | Claimed % - Calculated Delta % |                                    │
│   • Tolerance Check: Threshold = 0.05%                                                    │
│   • Output: AuditResult object (PASS vs FLAGGED, Evidence Log, Delta Breakdown)          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Directory Structure

```
ClaimGuard/
├── .env                                       # Local environment variables (GROQ_API_KEY)
├── .gitignore                                 # Git exclusion rules (pycache, env, build)
├── PROJECT_STATE.md                           # Master technical reference & architecture log
├── PROJECT_STATUS.md                          # Live operational status, test validation & health report
├── README.md                                  # Project landing documentation & quickstart guide
├── requirements.txt                           # Python package dependency definitions
├── app.py                                     # Consolidated Single-Page Application (SPA) with routing
│
├── assets/
│   └── hero-illustration.jpg                  # Custom high-resolution hero illustration
│
├── data/                                      # Ground-truth corporate filing presets
│   ├── preset_clean/                          # Verified Clean Preset
│   │   ├── metrics.csv                        # Scope 1 & 2 CSV metrics (FY23: 10,500 -> FY24: 10,228.05 = -2.59%)
│   │   └── narrative.txt                      # Verified PR claim narrative (2.59%)
│   └── preset_flagged/                        # Flagged Greenwashing Preset
│       ├── metrics.csv                        # Ground-truth metrics CSV (FY23: 10,500 -> FY24: 10,228.05 = -2.59%)
│       └── narrative.txt                      # Exaggerated PR claim narrative (20.00% claim)
│
├── src/                                       # Core ClaimGuard Python Package
│   ├── __init__.py                            # Module exports
│   ├── extractor.py                           # LLM + Regex hybrid claim extraction engine
│   ├── rules_engine.py                        # Deterministic YoY % calculation & tolerance check
│   └── schemas.py                             # Pydantic data models (ExtractedClaim & AuditResult)
│
├── test_audit.py                              # Automated unit tests (Clean & Flagged presets)
└── test_dynamic_years.py                      # Dynamic fiscal year handling unit tests
```

---

## 3. Core Module Deep Dive

### 3.1 `src/schemas.py` — Data Models & Schemas
* **`ExtractedClaim` (Pydantic BaseModel):**
  * `metric` (str): Identified target metric (e.g., `"Total Scope 1 & 2 Emissions"`).
  * `claimed_percentage` (float): Stated percentage reduction extracted from text.
  * `baseline_year` (str): Stated baseline period (e.g., `"FY23"`, `"FY24"`).
  * `target_year` (str): Stated target period (e.g., `"FY24"`, `"FY25"`).
  * `claim_text` (str): Verbatim text snippet from narrative.

* **`AuditResult` (Pydantic BaseModel):**
  * `status` (str): `"PASS"` or `"FLAGGED"`.
  * `claimed_percentage` (float): Stated reduction from claim.
  * `calculated_delta` (float): Exact calculated reduction from CSV metrics.
  * `variance` (float): Absolute difference `|claimed - calculated|`.
  * `discrepancy_reason` (str): Detailed text explanation of audit finding.
  * `matched_metric` (str): Matched metric row name in CSV.
  * `baseline_year` & `target_year` (str): Matched fiscal years.
  * `baseline_value` & `target_value` (float): Raw metric values from CSV.
  * `fy23_value` & `fy24_value` (float, optional): Historic values for backwards compatibility.

---

### 3.2 `src/extractor.py` — Extraction Layer
* **`extract_claims_from_text(text: str) -> ExtractedClaim`**:
  1. Checks for `GROQ_API_KEY` in environment.
  2. If key is present: Invokes `_extract_via_llm()` using Groq `llama-3.3-70b-versatile` with strict JSON mode.
  3. System Prompt explicitly forbids calculation: *"You are a JSON-only extraction engine. DO NOT calculate or verify math. Simply extract what is stated."*
  4. If API key is missing, invalid, or fails: Automatically triggers `_extract_via_regex()` for offline fallback parsing.

---

### 3.3 `src/rules_engine.py` — Deterministic Audit Engine
* **`verify_claim(claim: ExtractedClaim, df: pd.DataFrame, tolerance: float = 0.05) -> AuditResult`**:
  1. Normalizes metric names and column headers in the input DataFrame.
  2. Dynamically locates metric row (e.g. matching `"Scope 1"`, `"Emissions"`, `"Renewable"`).
  3. Dynamically identifies baseline and target year columns (e.g., `fy23_value`, `fy24_value`, `fy25_value`).
  4. Performs pure Python mathematical verification:
     $$\text{Calculated Delta \%} = \frac{\text{Baseline Value} - \text{Target Value}}{\text{Baseline Value}} \times 100.0$$
     $$\text{Variance \%} = |\text{Claimed \%} - \text{Calculated Delta \%}|$$
  5. Compares `Variance` against `tolerance` (`0.05%`):
     * If $\text{Variance} \le 0.05\%$, returns status `"PASS"`.
     * Otherwise returns status `"FLAGGED"` with exact discrepancy explanation.

---

### 3.4 Consolidated SPA UI Architecture
* **`app.py`**:
  * Acts as the single-page application entry point, completely eliminating the Streamlit sidebar page list.
  * Controls view rendering using `st.session_state.current_view` and `st.query_params["view"]` (supporting views: `landing`, `audit_preset`, and `audit_custom`).
  * Injects a persistent, viewport-fixed navigation bar wrapper (`.cg-navbar-wrapper`) with a high z-index and blur overlays to float over scrolled contents.
  * Standardizes scrolling margins (`scroll-margin-top: 130px`) to prevent headers from slipping beneath the persistent navbar.

---

## 4. Verification & Testing

The codebase includes automated unit tests:

```bash
# Run core audit test suite
python test_audit.py

# Run dynamic fiscal year tests
python test_dynamic_years.py
```

### Verified Test Cases:
1. **Clean Preset Test**: Validates 2.59% claimed reduction against `10,500.00 -> 10,228.05` CSV metrics $\rightarrow$ **PASS** ($\text{Variance} = 0.00\%$).
2. **Flagged Preset Test**: Validates 20.00% claimed reduction against `10,500.00 -> 10,228.05` CSV metrics $\rightarrow$ **FLAGGED** ($\text{Variance} = 17.41\%$).
3. **Dynamic Year Mapping Test**: Validates arbitrary fiscal year pairs (e.g., FY24 $\rightarrow$ FY25, `20,000.00 -> 17,000.00` = 15.00%) with Clean (15.00% claim) and Flagged (30.00% claim) scenarios $\rightarrow$ **PASS**.
