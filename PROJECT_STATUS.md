# ClaimGuard — Operational Status & System Health Report

> **Document Purpose:** Complete codebase health status, verified test outputs, component directory, resolved issues, and active roadmap.  
> **Last Verified:** August 2026 | **Repository:** `Adityaa10101/ClaimGuard`

---

## 1. Executive Summary

**ClaimGuard** is fully operational across all architectural layers. The system separates non-deterministic LLM semantic extraction from 100% deterministic Python/Pandas mathematical verification to prevent greenwashing and hallucinated reporting.

* **Deterministic Rule:** All math operations, YoY delta calculations, and tolerance checks are strictly executed in pure Python/Pandas.
* **Resilience:** If the Groq API key is unavailable or fails, ClaimGuard automatically falls back to its offline regex extraction engine with zero system downtime.
* **Architecture Consolidation:** The entire app is consolidated into a Single-Page Application (SPA) in `app.py`, completely eliminating the multi-page Streamlit sidebar and achieving a premium Web3 monochrome design.
* **Sticky Navigation Bar:** Implemented a unified, persistent navigation bar that floats at the top of both the Landing and Audit views with smooth anchor navigation targeting.

---

## 2. SPA Architecture Status

| View | Access Path | Status | Features & Controls |
| :--- | :--- | :---: | :--- |
| **Overview Landing** | `?view=landing` | 🟢 **Healthy** | Centered layout, hero section with system status pulse dot, greenwashing trap analysis, workflow stages, concrete example verification case comparisons (Demo Case A vs B), 15 rules matrix, system architecture diagrams, and dashed roadmap elements. |
| **Audit Engine** | `?view=audit_preset` / `?view=audit_custom` | 🟢 **Healthy** | Full audit dashboard workflow. Step 1 selects case (Preset 1 PASS, Preset 2 FLAGGED, or Custom Upload). Step 2 reviews narrative text and metrics dataframe. Step 3 triggers the pure Python audit, rendering mathematical breakdown, absolute variance, tolerance comparison, extracted JSON outputs, and formula descriptions. |

---

## 3. Component Inventory & Health

| Component | File Path | Status | Description |
| :--- | :--- | :---: | :--- |
| **Core SPA App** | [`app.py`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/app.py) | 🟢 **Healthy** | Ingests CSS rules, initializes state variables, dispatches views, renders the unified sticky top navbar and responsive content. |
| **Data Schemas** | [`src/schemas.py`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/src/schemas.py) | 🟢 **Passing** | Pydantic v2 data models for `ExtractedClaim` and `AuditResult`. |
| **Semantic Extractor** | [`src/extractor.py`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/src/extractor.py) | 🟢 **Passing** | Hybrid LLM (`llama-3.3-70b-versatile` via Groq) + Offline Regex fallback scanner. |
| **Audit Engine** | [`src/rules_engine.py`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/src/rules_engine.py) | 🟢 **Passing** | Pure Python/Pandas deterministic calculator with dynamic fiscal year column matching and 0.05% tolerance threshold. |
| **Preset Clean Data** | [`data/preset_clean/`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/data/preset_clean/) | 🟢 **Passing** | Clean test dataset (2.59% PR claim vs 2.59% CSV delta). |
| **Preset Flagged Data** | [`data/preset_flagged/`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/data/preset_flagged/) | 🟢 **Passing** | Flagged greenwashing test dataset (20.00% PR claim vs 2.59% CSV delta). |
| **Core Test Suite** | [`test_audit.py`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/test_audit.py) | 🟢 **Passing** | Automated validation of Preset 1 and Preset 2 scenarios. |
| **Dynamic Years Suite**| [`test_dynamic_years.py`](file:///c:/Users/Lenovo/Desktop/CLAIMGUARD/ClaimGuard/test_dynamic_years.py) | 🟢 **Passing** | Automated validation of arbitrary fiscal year headers (FY24 $\rightarrow$ FY25). |

---

## 4. Test Suite Execution Results

All automated test suites pass with 100% success rate:

```
$ python test_audit.py
--- Testing Preset 1: Clean ---
Extracted Claim: {'metric': 'Total Scope 1 & 2 Emissions', 'claimed_percentage': 2.59, 'baseline_year': 'FY23', 'target_year': 'FY24'}
Audit Result: {'status': 'PASS', 'claimed_percentage': 2.59, 'calculated_delta': 2.59, 'variance': 0.0, 'discrepancy_reason': 'VERIFIED: The claimed 2.59% reduction matches the ground truth CSV data exactly...'}
Preset 1 Test PASSED!

--- Testing Preset 2: Flagged ---
Extracted Claim: {'metric': 'Total Scope 1 & 2 Emissions', 'claimed_percentage': 20.0, 'baseline_year': 'FY23', 'target_year': 'FY24'}
Audit Result: {'status': 'FLAGGED', 'claimed_percentage': 20.0, 'calculated_delta': 2.59, 'variance': 17.41, 'discrepancy_reason': 'MATHEMATICAL DISCREPANCY DETECTED: PR narrative claims a 20.00% reduction, but pure Python audit calculates only a 2.59% reduction...'}
Preset 2 Test PASSED!

ALL UNIT TESTS PASSED SUCCESSFULLY!

$ python test_dynamic_years.py
Clean FY24->FY25 Audit Result: {'status': 'PASS', 'variance': 0.0}
Flagged FY24->FY25 Audit Result: {'status': 'FLAGGED', 'variance': 15.0}
DYNAMIC YEARS TEST PASSED PERFECTLY!
```

---

## 5. Resolved Fixes & Improvements

1. **SPA Router Integration**: Leveraged `st.session_state` and `st.query_params` to switch between landing, preset audit, and custom audit views seamlessly without forcing page reloads or revealing Streamlit's default navigation sidebar.
2. **Sticky Navigation Bar (Fixed Wrapper)**: Solved Streamlit element scroll bounding issues by targeting `position: fixed` on a dedicated `.cg-navbar-wrapper` element with `z-index: 999999` and wrapping navigation markup, ensuring consistent visibility while scrolling.
3. **Anchor Headings Scroll Offset**: Applied `scroll-margin-top: 130px` to all landing page sections so that clicking top links smoothly scrolls headings right below the fixed navbar header.
4. **Resilient Offline Fallback**: Confirmed that offline regex extraction immediately handles claims when Groq API keys are absent or invalid without throwing exceptions.

---

## 6. Active Roadmap & Future Enhancements

1. **Multi-Claim Batch Extraction**: Extend `src/extractor.py` to parse multiple claims per narrative document (`List[ExtractedClaim]`).
2. **Domain-Specific Rules Expansion**:
   - Scope 1 + Scope 2 total summation cross-validation.
   - Renewable energy ratio verification ($\text{Renewable} / \text{Total Energy} \times 100$).
   - Water recycling & reuse percentage checks.
3. **Audit Report Export**: Add PDF / CSV / JSON report export buttons to the Audit Dashboard.
4. **PDF / BRSR Document Parser**: Ingestion pipeline for full PDF sustainability reports with automated table extraction.
