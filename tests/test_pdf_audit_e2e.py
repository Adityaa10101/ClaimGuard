"""
ClaimGuard — Phase 6C: PDF Audit End-to-End Integration Tests (Unit-Semantics Hardened)
Tests the full vertical slice:
  ParsedDocument (Tata Motors BRSR) + ClaimCandidate → EvidenceMatcher → verify_claim() → PDFAuditResult

Unit-Semantics & Correctness Rules:
1. Direct Scope 1 claims match 100% SOURCE_REPORTED evidence (Page 88: 48,736 -> 43,754 tCO2e) -> PASS (10.22%) / FLAGGED.
2. Direct Scope 2 claims match 100% SOURCE_REPORTED evidence (Page 88: 172,409 -> 131,407 tCO2) -> PASS (23.78%) / FLAGGED.
3. Combined Scope 1 + Scope 2 claims refuse to assume 1:1 unit equivalence between 'tCO2e' and 'tCO2'
   without an explicit document-provided normalization basis, returning controlled UNVERIFIED.
4. Strict source provenance: source-reported values remain SOURCE_REPORTED.
5. Entity safety (TML vs TMPVL/TPEML vs Consolidated vs Ambiguous UNKNOWN).
6. Year safety (FY24 -> FY25 vs missing year combinations).
7. Integration layer performs zero math; all verification delta computed by verify_claim().
8. Real Groq end-to-end smoke test (skipped if API key not available).
"""

import os
from pathlib import Path
import pytest
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from src.pdf.models import ParsedDocument, ExtractedEvidence, EvidenceType
from src.pdf.parser import parse_pdf
from src.pdf.evidence_extractor import EvidenceExtractor
from src.pdf.claim_models import ClaimCandidate, EntityBoundary, ExtractionMethod
from src.pdf.claim_discovery import discover_claims_from_text
from src.pdf.evidence_matcher import EvidenceMatcher, claim_candidate_to_extracted_claim
from src.pdf.audit_runner import PDFAuditResult, audit_pdf_claim
from src.schemas import AuditDecision, ExecutionStatus, RuleStatus


def get_test_pdf_path() -> Path:
    """Dynamically locates the Tata Motors FY2024-25 BRSR PDF."""
    env_path = os.getenv("TATA_BRSR_PDF_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    candidates = [
        Path(__file__).parent.parent / "data" / "Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf",
        Path(__file__).parent.parent / "data" / "fixtures" / "Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf",
        Path(__file__).parent.parent.parent / "Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf",
        Path(__file__).parent.parent.parent / "Tata-Motors-BRSR_r3-Only-Web-Link-1.pdf",
        Path(r"C:\Users\Lenovo\Desktop\CLAIMGUARD\Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf"),
        Path(r"C:\Users\Lenovo\Desktop\CLAIMGUARD\Tata-Motors-BRSR_r3-Only-Web-Link-1.pdf"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    pytest.skip("Tata Motors BRSR PDF fixture not found in workspace or parent directory.")


@pytest.fixture(scope="module")
def tata_doc() -> ParsedDocument:
    """Fixture parsing the Tata Motors BRSR document once for E2E tests."""
    pdf_path = get_test_pdf_path()
    return parse_pdf(pdf_path)


@pytest.fixture(scope="module")
def tata_evidence(tata_doc: ParsedDocument):
    """Fixture extracting emissions evidence once for all E2E tests."""
    extractor = EvidenceExtractor(tata_doc)
    return extractor.extract_emissions_evidence()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Direct Source-Reported Scope 1 End-to-End Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDirectScope1E2E:

    def test_tml_scope1_direct_pass(self, tata_doc: ParsedDocument, tata_evidence):
        """
        Direct Scope 1 Claim:
        Tata Motors Limited reduced Scope 1 emissions by 10.22% between FY24 and FY25.
        Ground truth (Page 88):
          Scope 1: 48,736 tCO2e (FY24) -> 43,754 tCO2e (FY25)
          Calculated Delta: ((48736 - 43754) / 48736) * 100 = 10.2224% -> 10.22%
        Expected Result: PASS
        """
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 1 emissions by 10.22% between FY24 and FY25.",
            metric="Scope 1 Emissions",
            claimed_percentage=10.22,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
            source_page=88,
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence, tolerance=0.05)

        # 1. Audit Outcome
        assert pdf_audit.status == "PASS"
        assert pdf_audit.audit_decision == AuditDecision.PASS
        assert pdf_audit.calculated_delta == pytest.approx(10.22, abs=0.01)
        assert pdf_audit.variance <= 0.05

        # 2. Source-Reported Provenance
        assert pdf_audit.source_file == tata_doc.filename
        assert pdf_audit.source_pages == [88]
        assert pdf_audit.is_derived is False
        assert pdf_audit.evidence_type == EvidenceType.SOURCE_REPORTED.value
        assert len(pdf_audit.evidence) == 2
        assert all(e.metric == "Scope 1" and e.unit == "tCO2e" for e in pdf_audit.evidence)

    def test_tml_scope1_direct_flagged(self, tata_doc: ParsedDocument, tata_evidence):
        """
        Discrepant Scope 1 Claim:
        Tata Motors Limited claimed a 25.0% Scope 1 reduction, but ground truth is 10.22%.
        Expected Result: FLAGGED
        """
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 1 emissions by 25.0% between FY24 and FY25.",
            metric="Scope 1 Emissions",
            claimed_percentage=25.0,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
            source_page=88,
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence, tolerance=0.05)

        assert pdf_audit.status == "FLAGGED"
        assert pdf_audit.audit_decision == AuditDecision.FLAGGED
        assert pdf_audit.calculated_delta == pytest.approx(10.22, abs=0.01)
        assert pdf_audit.variance == pytest.approx(14.78, abs=0.05)
        assert "MATHEMATICAL DISCREPANCY DETECTED" in pdf_audit.discrepancy_reason


# ─────────────────────────────────────────────────────────────────────────────
# 2. Direct Source-Reported Scope 2 End-to-End Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDirectScope2E2E:

    def test_tml_scope2_direct_pass(self, tata_doc: ParsedDocument, tata_evidence):
        """
        Direct Scope 2 Claim:
        Tata Motors Limited reduced Scope 2 emissions by 23.78% between FY24 and FY25.
        Ground truth (Page 88):
          Scope 2: 172,409 tCO2 (FY24) -> 131,407 tCO2 (FY25)
          Calculated Delta: ((172409 - 131407) / 172409) * 100 = 23.7818% -> 23.78%
        Expected Result: PASS
        """
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 2 emissions by 23.78% between FY24 and FY25.",
            metric="Scope 2 Emissions",
            claimed_percentage=23.78,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
            source_page=88,
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence, tolerance=0.05)

        # 1. Audit Outcome
        assert pdf_audit.status == "PASS"
        assert pdf_audit.audit_decision == AuditDecision.PASS
        assert pdf_audit.calculated_delta == pytest.approx(23.78, abs=0.01)
        assert pdf_audit.variance <= 0.05

        # 2. Source-Reported Provenance
        assert pdf_audit.source_file == tata_doc.filename
        assert pdf_audit.source_pages == [88]
        assert pdf_audit.is_derived is False
        assert pdf_audit.evidence_type == EvidenceType.SOURCE_REPORTED.value
        assert len(pdf_audit.evidence) == 2
        assert all(e.metric == "Scope 2" and e.unit == "tCO2" for e in pdf_audit.evidence)

    def test_tml_scope2_direct_flagged(self, tata_doc: ParsedDocument, tata_evidence):
        """
        Discrepant Scope 2 Claim:
        Tata Motors Limited claimed a 35.0% Scope 2 reduction, but ground truth is 23.78%.
        Expected Result: FLAGGED
        """
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 2 emissions by 35.0% between FY24 and FY25.",
            metric="Scope 2 Emissions",
            claimed_percentage=35.0,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
            source_page=88,
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence, tolerance=0.05)

        assert pdf_audit.status == "FLAGGED"
        assert pdf_audit.audit_decision == AuditDecision.FLAGGED
        assert pdf_audit.calculated_delta == pytest.approx(23.78, abs=0.01)
        assert pdf_audit.variance == pytest.approx(11.22, abs=0.05)
        assert "MATHEMATICAL DISCREPANCY DETECTED" in pdf_audit.discrepancy_reason


# ─────────────────────────────────────────────────────────────────────────────
# 3. Combined Scope 1 + 2 Claim (Strict Unit Semantics: UNVERIFIED)
# ─────────────────────────────────────────────────────────────────────────────

class TestCombinedScopeUnitSemantics:

    def test_combined_claim_refuses_unit_assumption_and_returns_unverified(self, tata_doc: ParsedDocument, tata_evidence):
        """
        Combined Scope 1 + Scope 2 Claim:
        The Tata Motors BRSR separately reports Scope 1 in 'tCO2e' and Scope 2 in 'tCO2'.
        Because the document does NOT provide an explicit unit normalization basis,
        the system strictly refuses to assume 1:1 carbon mass equivalence and returns UNVERIFIED.
        """
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced its combined Scope 1 and Scope 2 greenhouse gas emissions by approximately 20.8% between FY24 and FY25.",
            metric="Total Scope 1 & 2 Emissions",
            claimed_percentage=20.8,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
            source_page=88,
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence, tolerance=0.05)

        # 1. Audit Outcome is controlled UNVERIFIED
        assert pdf_audit.audit_decision == AuditDecision.UNVERIFIED
        assert pdf_audit.audit_result.execution_status == ExecutionStatus.INVALID_DATA

        # 2. Clear Discrepancy Reason Explaining Unit Difference
        assert "Unit mismatch" in pdf_audit.discrepancy_reason
        assert "tCO2e" in pdf_audit.discrepancy_reason
        assert "tCO2" in pdf_audit.discrepancy_reason
        assert "audited independently" in pdf_audit.discrepancy_reason

        # 3. Provenance is Still Retained
        assert pdf_audit.source_file == tata_doc.filename
        assert 88 in pdf_audit.source_pages
        assert len(pdf_audit.evidence) == 4  # The 4 constituent disclosures are preserved


# ─────────────────────────────────────────────────────────────────────────────
# 4. Source Provenance & Raw Disclosures
# ─────────────────────────────────────────────────────────────────────────────

class TestSourceProvenanceAndSemantics:

    def test_source_reported_evidence_integrity(self, tata_doc: ParsedDocument, tata_evidence):
        """Verifies raw strings, page numbers, units, and evidence types are strictly preserved."""
        extractor = EvidenceExtractor(tata_doc)
        s1_ev = extractor.find_evidence_by_metric("Scope 1", year="FY24")
        s2_ev = extractor.find_evidence_by_metric("Scope 2", year="FY24")

        # TML Page 88
        tml_s1 = next(e for e in s1_ev if e.entity == "TML")
        tml_s2 = next(e for e in s2_ev if e.entity == "TML")

        assert tml_s1.page_number == 88
        assert tml_s1.raw_value == "48,736*"
        assert tml_s1.unit == "tCO2e"
        assert tml_s1.evidence_type == EvidenceType.SOURCE_REPORTED.value

        assert tml_s2.page_number == 88
        assert tml_s2.raw_value == "1,72,409*"
        assert tml_s2.unit == "tCO2"
        assert tml_s2.evidence_type == EvidenceType.SOURCE_REPORTED.value


# ─────────────────────────────────────────────────────────────────────────────
# 5. Entity Safety & Boundary Separation
# ─────────────────────────────────────────────────────────────────────────────

class TestEntitySafety:

    def test_tml_claim_matches_only_tml_evidence(self, tata_evidence):
        """TML Scope 1 claim must match ONLY TML evidence (Page 88), not Consolidated (Page 89)."""
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 1 emissions by 10.22% in FY25.",
            metric="Scope 1 Emissions",
            claimed_percentage=10.22,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
        )

        matcher = EvidenceMatcher(tata_evidence)
        match_res = matcher.match_claim(claim)

        assert match_res.is_matched is True
        assert match_res.entity == "TML"
        assert all(e.entity == "TML" for e in match_res.matched_evidence)
        assert match_res.source_pages == [88]

    def test_consolidated_claim_matches_consolidated_evidence(self, tata_evidence):
        """Consolidated Scope 1 claim must match Consolidated evidence (Page 89), not TML."""
        claim = ClaimCandidate(
            claim_text="Consolidated operations reduced Scope 1 emissions in FY25.",
            metric="Scope 1 Emissions",
            claimed_percentage=0.75,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.CONSOLIDATED.value,
        )

        matcher = EvidenceMatcher(tata_evidence)
        match_res = matcher.match_claim(claim)

        assert match_res.is_matched is True
        assert match_res.entity == EntityBoundary.CONSOLIDATED.value
        assert all("Consolidated" in (e.entity or "") for e in match_res.matched_evidence)
        assert match_res.source_pages == [89]

    def test_ambiguous_entity_returns_unverified(self, tata_doc: ParsedDocument, tata_evidence):
        """Claim with UNKNOWN / ambiguous entity must return UNVERIFIED without guessing."""
        claim = ClaimCandidate(
            claim_text="Tata Motors reduced Scope 1 emissions by 10.22%.",
            metric="Scope 1 Emissions",
            claimed_percentage=10.22,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.UNKNOWN.value,  # Ambiguous
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence)

        assert pdf_audit.audit_decision == AuditDecision.UNVERIFIED
        assert "Ambiguous entity boundary" in pdf_audit.discrepancy_reason


# ─────────────────────────────────────────────────────────────────────────────
# 6. Year Safety
# ─────────────────────────────────────────────────────────────────────────────

class TestYearSafety:

    def test_missing_year_returns_unverified(self, tata_doc: ParsedDocument, tata_evidence):
        """Requesting an unsupported year pair (e.g. FY22 -> FY23) returns controlled UNVERIFIED."""
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 1 emissions by 15% between FY22 and FY23.",
            metric="Scope 1 Emissions",
            claimed_percentage=15.0,
            baseline_year="FY22",
            target_year="FY23",
            entity=EntityBoundary.TML.value,
        )

        pdf_audit = audit_pdf_claim(claim, tata_doc, evidence_list=tata_evidence)

        assert pdf_audit.audit_decision == AuditDecision.UNVERIFIED
        assert pdf_audit.audit_result.execution_status == ExecutionStatus.MISSING_DATA
        assert "Missing required year disclosure" in pdf_audit.discrepancy_reason


# ─────────────────────────────────────────────────────────────────────────────
# 7. No Math in Integration Layer
# ─────────────────────────────────────────────────────────────────────────────

class TestNoMathInIntegration:

    def test_matcher_does_not_calculate_delta(self, tata_evidence):
        """Verifies EvidenceMatcher returns raw ground-truth columns without pre-computing delta."""
        claim = ClaimCandidate(
            claim_text="Tata Motors Limited reduced Scope 1 emissions by 10.22% in FY25.",
            metric="Scope 1 Emissions",
            claimed_percentage=10.22,
            baseline_year="FY24",
            target_year="FY25",
            entity=EntityBoundary.TML.value,
        )

        matcher = EvidenceMatcher(tata_evidence)
        match_res = matcher.match_claim(claim)

        # Matcher must NOT have added delta / percentage / variance columns
        df_cols = list(match_res.metrics_df.columns)
        for forbidden in ["delta", "calculated_delta", "variance", "percentage_change", "audit_result"]:
            assert forbidden not in df_cols, f"Forbidden math column '{forbidden}' found in matcher DataFrame!"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Real Groq End-to-End Smoke Test on Direct Scope 1 Disclosure
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "").startswith("your_"),
    reason="Live GROQ_API_KEY not set — skipping live Groq E2E smoke test"
)
class TestRealGroqE2E:

    def test_live_groq_direct_scope1_pass(self, tata_doc: ParsedDocument, tata_evidence):
        """
        Full live pipeline:
        Controlled Scope 1 Text → Groq/LLM → ClaimCandidate → EvidenceMatcher → verify_claim() → PDFAuditResult (PASS)
        """
        text = (
            "Tata Motors Limited reduced its Scope 1 direct greenhouse gas emissions "
            "by approximately 10.22% between FY24 and FY25."
        )

        # 1. Semantic extraction via Groq
        candidates = discover_claims_from_text(text, source_page=88, source_file=tata_doc.filename)
        assert len(candidates) >= 1
        candidate = candidates[0]
        assert candidate.extraction_method == ExtractionMethod.GROQ_LLM.value
        assert candidate.entity == EntityBoundary.TML.value

        # 2. Audit against real Tata PDF Scope 1 evidence
        pdf_audit = audit_pdf_claim(candidate, tata_doc, evidence_list=tata_evidence, tolerance=0.05)

        assert pdf_audit.status == "PASS"
        assert pdf_audit.audit_decision == AuditDecision.PASS
        assert pdf_audit.calculated_delta == pytest.approx(10.22, abs=0.01)
        assert pdf_audit.source_pages == [88]
        assert pdf_audit.is_derived is False
        print(f"\n[LIVE GROQ SCOPE 1 E2E PASS] Status={pdf_audit.status}, Delta={pdf_audit.calculated_delta}%, Entity={pdf_audit.entity}")
