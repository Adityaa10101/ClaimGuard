# ClaimGuard MVP — Complete Technical Reference & Project State

> **Original Baseline Technical Specification & Codebase Reference**  
> *Built for Prasunethon 2.0 Hackathon*

---

## Executive System Context

**ClaimGuard** is a production-grade, deterministic ESG (Environmental, Social, and Governance) & BRSR (Business Responsibility and Sustainability Reporting) claim verification engine engineered to detect corporate greenwashing and mathematical discrepancies in corporate sustainability filings.

### 🛡️ The Immutable Core Rule
**We strictly separate semantic parsing from mathematical validation.**  
LLMs (Large Language Models) are non-deterministic and prone to arithmetic hallucination. Therefore, LLMs are **explicitly forbidden** from calculating reductions, variances, or compliance decisions. 

* **The LLM Layer (Semantic Extractor):** Employs the Groq API (`llama-3.3-70b-versatile`) strictly to parse unstructured narrative text into structured Pydantic JSON schemas (`ExtractedClaim`).
* **The Offline Fallback (Regex Extractor):** A multi-pattern regex parsing engine that activates when the API is unavailable or unconfigured, ensuring 100% offline resilience.
* **The Deterministic Layer (Audit Engine):** Uses pure Python and Pandas to read ground-truth CSV metrics, dynamically map fiscal year columns (e.g., `fy23_value`, `fy24_value`), compute exact percentage deltas, and execute tolerance verification against claimed values.
* **The UI Layer:** An enterprise Streamlit dashboard (`app.py`) supporting filing presets, custom raw CSV/narrative inputs, interactive metric cards, evidence accordions, and metric variance visual badges.

---

## 1. Architecture Overview

The ClaimGuard pipeline flows through three distinct, decoupled stages:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          1. INPUT LAYER (UI)                            │
│   • Streamlit Dashboard (app.py)                                        │
│   • Accepts Narrative Text (narrative.txt / custom st.text_area)        │
│   • Accepts Ground-Truth Table (metrics.csv / custom file upload)       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      2. SEMANTIC EXTRACTION LAYER                       │
│   • src/extractor.py                                                    │
│   • Primary: Groq API (llama-3.3-70b-versatile)                         │
│     System Prompt + response_format={"type": "json_object"}             │
│   • Fallback: Regex Multi-Pattern Sentence & Number Scanner            │
│   • Output: ExtractedClaim Pydantic object (Metric, Claimed %, Years)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    3. DETERMINISTIC AUDIT LAYER                         │
│   • src/rules_engine.py                                                 │
│   • Reads Pandas DataFrame (metrics.csv)                                │
│   • Dynamic Column Matcher: Maps baseline_year/target_year to cols      │
│   • Math Execution:                                                     │
│        Calculated Delta % = ((Baseline - Target) / Baseline) * 100      │
│        Variance % = | Claimed % - Calculated Delta % |                  │
│   • Tolerance Check: Threshold = 0.05%                                  │
│   • Output: AuditResult object (PASS vs FLAGGED, Evidence Log)          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Directory Structure

```
ClaimGuard/
├── .env                                       # Local environment variables (GROQ_API_KEY)
├── .gitignore                                 # Git exclusion rules (pycache, env, build)
├── PROJECT_STATE.md                           # Ultimate technical reference & architecture log
├── README.md                                  # Project landing documentation & quickstart guide
├── app.py                                     # Production Streamlit Enterprise Dashboard
├── requirements.txt                           # Python package dependency definitions
├── test_audit.py                              # Automated unit tests (Clean & Flagged presets)
├── test_dynamic_years.py                      # Dynamic year handling unit tests
│
├── claimguard/                                # Package root directory
│   └── data/
│       └── preset_flagged/
│           └── metrics.csv
│
├── data/                                      # Ground-truth corporate filing presets
│   ├── preset_clean/                          # Verified Clean Preset
│   │   ├── metrics.csv                        # Scope 1 & 2 CSV metrics (FY23: 10,500 -> FY24: 10,228.05 = -2.59%)
│   │   └── narrative.txt                      # Verified PR claim narrative (2.59%)
│   └── preset_flagged/                        # Flagged Greenwashing Preset
│       ├── metrics.csv                        # Ground-truth metrics CSV (FY23: 10,500 -> FY24: 10,228.05 = -2.59%)
│       └── narrative.txt                      # Exaggerated PR claim narrative (20.00% claim)
│
└── src/                                       # Core ClaimGuard Python Package
    ├── __init__.py                            # Module exports
    ├── extractor.py                           # LLM + Regex hybrid claim extraction engine
    ├── rules_engine.py                        # Deterministic YoY % calculation & tolerance check
    └── schemas.py                             # Pydantic data models (ExtractedClaim & AuditResult)
```

---

## 3. Core Module Deep Dive

### 3.1 `src/schemas.py` — Data Models & Schemas

* **`ExtractedClaim` (Pydantic BaseModel):**
  * `metric` (str): Identified target metric (e.g., `"Total Scope 1 & 2 Emissions"`).
  * `claimed_percentage` (float): Stated percentage reduction extracted from text.
  * `baseline_year` (str): Stated baseline period (e.g., `"FY23"`).
  * `target_year` (str): Stated target period (e.g., `"FY24"`).
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
  * `fy23_value` & `fy24_value` (float, optional): Historic values.

---

### 3.2 `src/extractor.py` — Extraction Layer

* **`extract_claims_from_text(text: str) -> ExtractedClaim`**:
  1. Checks for `GROQ_API_KEY` in environment.
  2. If key is present: Invokes `_extract_via_llm()` using Groq `llama-3.3-70b-versatile` with strict JSON mode.
  3. System Prompt explicitly forbids calculation: *"You are a JSON-only extraction engine. DO NOT calculate or verify math. Simply extract what is stated."*
  4. If API key is missing or call fails: Automatically triggers `_extract_via_regex()` for offline fallback parsing.

---

### 3.3 `src/rules_engine.py` — Deterministic Audit Engine

* **`verify_claim(claim: ExtractedClaim, df: pd.DataFrame, tolerance: float = 0.05) -> AuditResult`**:
  1. Normalizes metric names and column headers in the input DataFrame.
  2. Dynamically locates metric row (e.g. matching `"Scope 1"`, `"Emissions"`).
  3. Dynamically identifies baseline and target year columns (e.g. `fy23_value`, `fy24_value`).
  4. Performs pure Python mathematical verification:
     $$\text{Calculated Delta \%} = \frac{\text{Baseline Value} - \text{Target Value}}{\text{Baseline Value}} \times 100.0$$
     $$\text{Variance \%} = |\text{Claimed \%} - \text{Calculated Delta \%}|$$
  5. Compares `Variance` against `tolerance` (`0.05%`).
     * If $\text{Variance} \le 0.05\%$, returns status `"PASS"`.
     * Otherwise returns status `"FLAGGED"` with exact discrepancy explanation.

---

### 3.4 `app.py` — Streamlit Dashboard

* Provides interactive visual dashboard for claim verification.
* Features:
  * Preset selection: **Preset 1 (Clean)**, **Preset 2 (Flagged)**, or **Custom Input Mode**.
  * Custom text area for raw narrative PR input and file uploader for ground-truth `metrics.csv`.
  * Visual audit badges (**PASS** green card vs **FLAGGED** red warning card).
  * Ground-truth metric data tables and detailed JSON breakdown.

---

## 4. Verification & Testing

The codebase includes zero-dependency automated unit tests:

```bash
python test_audit.py
```

### Test Scenarios:
1. **Clean Preset Test**: Validates 2.59% claimed reduction against `10,500.00 -> 10,228.05` CSV metrics $\rightarrow$ **PASS**.
2. **Flagged Preset Test**: Validates 20.00% claimed reduction against `10,500.00 -> 10,228.05` CSV metrics $\rightarrow$ **FLAGGED** (17.41% variance).
3. **Dynamic Year Mapping Test** (`test_dynamic_years.py`): Verifies flexible column detection for various fiscal year formats.

---
