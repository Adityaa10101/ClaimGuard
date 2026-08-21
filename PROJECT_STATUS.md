# ClaimGuard — Current System Status & Technical Architecture Report

> **Document Purpose:** Complete codebase assessment, feature inventory, working components, known bugs, and technical roadmap for AI agents & developers.  
> **Date:** August 2026 | **Repository:** `Adityaa10101/ClaimGuard`

---

## 1. Executive Summary: What is ClaimGuard?

**ClaimGuard** is a hybrid ESG & BRSR audit engine built to eliminate **corporate greenwashing and LLM arithmetic hallucinations**.

### The Core Principle:
* **LLMs** (via Groq API / Llama-3) are **strictly restricted to semantic JSON extraction** (extracting metric names, stated percentages, baseline/target years). **LLMs are forbidden from doing math.**
* **Pure Python & Pandas** execute **100% deterministic mathematical calculations**, dynamic year mapping, and tolerance checks against ground-truth CSV metrics.

---

## 2. Is there only a Hero Page? (Clarification)

**No, there is both a Landing Page and an Interactive Audit Dashboard:**

1. **Landing Page (`app.py`)**:
   - A full-width, modern landing page rendered via `st.components.v1.html`.
   - Contains:
     - **Hero Section** with custom graphic illustration.
     - **The AI Greenwashing Trap** breakdown.
     - **Architecture Timeline** (Step 1 to Step 4).
     - **Domain Cards** (Emissions, Energy, Water, General Logic).
     - **Roadmap Section** (PDF RAG, Microservices, 5-Year Trend Analysis).
   - Navbar contains buttons linking to `/Audit_Dashboard`.

2. **Audit Dashboard (`pages/Audit_Dashboard.py`)**:
   - The multi-page Streamlit dashboard view.
   - Allows users to test:
     - **Preset 1: Clean Case** (2.59% PR claim vs 2.59% actual CSV delta $\rightarrow$ **PASS**).
     - **Preset 2: Flagged Case** (20.00% fake PR claim vs 2.59% actual CSV delta $\rightarrow$ **FLAGGED**).
     - **Custom Input Upload** (Type custom narrative + upload custom `metrics.csv`).
   - Displays real-time **PASS** / **FLAGGED** status badges, mathematical variance cards, and extracted JSON inspection tabs.

---

## 3. Detailed Component Inventory & Working Status

| Component / File | Status | Description & Mechanics |
| :--- | :---: | :--- |
| **`src/schemas.py`** | ✅ Working | Pydantic v2 data contracts: `ExtractedClaim` (claim extraction schema) and `AuditResult` (deterministic calculation output). |
| **`src/extractor.py`** | ✅ Working | Hybrid semantic extractor. Primary: Groq API (`llama-3.3-70b-versatile`) in strict JSON mode. Fallback: Offline regex scanner if API key is missing. |
| **`src/rules_engine.py`** | ✅ Working | Pure Python / Pandas calculation engine. Dynamically matches `fyXX_value` columns, calculates YoY % change, and computes variance against a 0.05% tolerance threshold. |
| **`test_audit.py`** | ✅ Working | Automated unit tests validating Preset 1 (PASS) and Preset 2 (FLAGGED). Fully passing. |
| **`test_dynamic_years.py`** | ✅ Working | Tests dynamic year mapping for various fiscal year headers (FY22, FY23, FY24, etc.). |
| **`data/preset_clean/`** | ✅ Working | Ground truth CSV (`10,500.00 -> 10,228.05`) + narrative (2.59% claim). |
| **`data/preset_flagged/`** | ✅ Working | Ground truth CSV (`10,500.00 -> 10,228.05`) + narrative (20.00% claim). |
| **`app.py`** | ✅ Working | Streamlit landing page with responsive CSS and navigation links. |
| **`pages/Audit_Dashboard.py`** | ✅ Working | Streamlit audit dashboard. Supports Preset 1, Preset 2, and custom uploads with real-time audit report generation. |

---

## 4. Identified Bugs & Required Fixes

### ⚠️ Bug 1: Preset File Path in `pages/Audit_Dashboard.py`
* **Issue**: Lines 126–128 use:
  ```python
  BASE_DIR = os.path.dirname(os.path.abspath(__file__))
  PRESET_CLEAN_DIR = os.path.join(BASE_DIR, "data", "preset_clean")
  ```
  Because `Audit_Dashboard.py` is inside `pages/`, `BASE_DIR` resolves to `ClaimGuard/pages/`, causing preset file loading to look for `ClaimGuard/pages/data/...` instead of `ClaimGuard/data/...`.
* **Fix**: Change to parent directory:
  ```python
  BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  ```

### ⚠️ Bug 2: Streamlit Sidebar Hidden on Landing Page
* **Issue**: `app.py` injects CSS `display: none !important` for `[data-testid="stSidebar"]`. This hides the default Streamlit page navigation menu.
* **Workaround / Fix**: Users navigate via the top right navbar buttons (`/Audit_Dashboard`), or sidebar can be re-enabled for seamless page toggling.

---

## 5. End-to-End Execution Flow

```
[User Input: Narrative Text & CSV]
               │
               ▼
   [src/extractor.py]
   • Groq Llama-3 API (Strict JSON mode)
   • Offline Regex Scanner (Fallback)
               │
               ▼ ExtractedClaim JSON
   [src/rules_engine.py]
   • Pandas dynamic column detection (e.g. fy23_value, fy24_value)
   • Pure Python Formula: ((Baseline - Target) / Baseline) * 100
   • Variance Calculation: |Claimed% - Calculated%|
   • Tolerance: <= 0.05%
               │
               ▼ AuditResult Object
   [pages/Audit_Dashboard.py]
   • Green "PASS" or Red "FLAGGED" badge
   • Metric breakdown cards & JSON inspection tabs
```

---

## 6. Recommended Next Steps for Development / AI Collaborators

1. **Fix Preset Pathing in `pages/Audit_Dashboard.py`**: Update `BASE_DIR` to point to root directory so preset buttons load CSVs and narratives immediately.
2. **Expand Multi-Claim Support**: Currently, `src/extractor.py` extracts a single main claim. Upgrade to extract a list of claims (`List[ExtractedClaim]`) from a single multi-paragraph narrative.
3. **Add Additional Domain Rules**:
   - Renewable energy percentage cross-check (`Renewable / Total Energy * 100`).
   - Water recycling ratio verification.
   - Scope 1 + Scope 2 = Total Scope 1 & 2 subtotal validation.
4. **Export Capabilities**: Add a "Download Audit Report (PDF/JSON)" button in `pages/Audit_Dashboard.py`.
