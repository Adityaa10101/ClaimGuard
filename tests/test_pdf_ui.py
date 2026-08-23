"""
ClaimGuard — Phase 6D: PDF Auto-Audit UI & Helper Tests
Verifies that app.py compiles cleanly, imports Phase 6C backend symbols,
validates candidate auditability rules, and handles PDFAuditResult rendering structures.
"""

import ast
from pathlib import Path
import pytest
from src.pdf.models import ExtractedEvidence, EvidenceType
from src.pdf.claim_models import ClaimCandidate, EntityBoundary
from src.pdf.audit_runner import PDFAuditResult
from src.rules_engine import verify_claim
from src.schemas import AuditDecision, AuditResult, ExecutionStatus, RuleResult, RuleStatus, RuleSummaryCounts


def test_app_syntax_and_imports():
    """Verify that app.py compiles with zero syntax errors."""
    app_path = Path(__file__).parent.parent / "app.py"
    assert app_path.exists()
    content = app_path.read_text(encoding="utf-8")
    parsed = ast.parse(content, filename="app.py")
    assert isinstance(parsed, ast.Module)


def test_candidate_auditability_filter():
    """Verify candidate auditability classification logic."""
    import importlib.util
    app_path = Path(__file__).parent.parent / "app.py"
    spec = importlib.util.spec_from_file_location("app_module", app_path)
    # We can test the helper directly or duplicate-test the deterministic logic
    from app import is_candidate_auditable

    # Supported: Scope 1
    c1 = ClaimCandidate(
        claim_text="TML reduced Scope 1 emissions by 10.22% between FY24 and FY25.",
        metric="Scope 1 Emissions",
        claimed_percentage=10.22,
        baseline_year="FY24",
        target_year="FY25",
        entity="TML",
    )
    is_aud, _ = is_candidate_auditable(c1)
    assert is_aud is True

    # Supported: Scope 2
    c2 = ClaimCandidate(
        claim_text="TML reduced Scope 2 emissions by 23.78% between FY24 and FY25.",
        metric="Scope 2 Emissions",
        claimed_percentage=23.78,
        baseline_year="FY24",
        target_year="FY25",
        entity="TML",
    )
    is_aud, _ = is_candidate_auditable(c2)
    assert is_aud is True

    # Supported: Combined Scope 1+2
    c3 = ClaimCandidate(
        claim_text="TML reduced combined Scope 1 and Scope 2 emissions by 20.80% between FY24 and FY25.",
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=20.80,
        baseline_year="FY24",
        target_year="FY25",
        entity="TML",
    )
    is_aud, _ = is_candidate_auditable(c3)
    assert is_aud is True

    # Unsupported: Plastic packaging
    c_pkg = ClaimCandidate(
        claim_text="100% of plastic packaging is recyclable.",
        metric="Plastic Packaging",
        claimed_percentage=100.0,
        baseline_year="FY24",
        target_year="FY25",
        entity="TML",
    )
    is_aud, reason = is_candidate_auditable(c_pkg)
    assert is_aud is False
    assert "not currently indexed" in reason.lower()

    # Unsupported: Affirmative Action procurement
    c_proc = ClaimCandidate(
        claim_text="0.21% of procurement spent on affirmative action suppliers.",
        metric="Procurement Spent",
        claimed_percentage=0.21,
        baseline_year="FY24",
        target_year="FY25",
        entity="TML",
    )
    is_aud, reason = is_candidate_auditable(c_proc)
    assert is_aud is False

    # Unsupported: Missing percentage
    c_no_pct = ClaimCandidate(
        claim_text="TML significantly reduced Scope 1 emissions.",
        metric="Scope 1 Emissions",
        claimed_percentage=None,
        baseline_year="FY24",
        target_year="FY25",
        entity="TML",
    )
    is_aud, reason = is_candidate_auditable(c_no_pct)
    assert is_aud is False


def test_pdf_audit_result_rendering_structure():
    """Verifies that a PDFAuditResult contains all fields expected by the UI."""
    claim = ClaimCandidate(
        claim_text="Tata Motors Limited reduced Scope 1 emissions by 10.22% between FY24 and FY25.",
        metric="Scope 1 Emissions",
        claimed_percentage=10.22,
        baseline_year="FY24",
        target_year="FY25",
        entity=EntityBoundary.TML.value,
        source_page=88,
    )

    ev_fy24 = ExtractedEvidence(
        source_file="test_brsr.pdf",
        page_number=88,
        metric="Scope 1",
        reporting_year="FY24",
        value=48736.0,
        raw_value="48,736*",
        unit="tCO2e",
        entity="TML",
        evidence_type=EvidenceType.SOURCE_REPORTED.value,
    )
    ev_fy25 = ExtractedEvidence(
        source_file="test_brsr.pdf",
        page_number=88,
        metric="Scope 1",
        reporting_year="FY25",
        value=43754.0,
        raw_value="43,754",
        unit="tCO2e",
        entity="TML",
        evidence_type=EvidenceType.SOURCE_REPORTED.value,
    )

    audit_res = AuditResult(
        status="PASS",
        claimed_percentage=10.22,
        calculated_delta=10.22,
        variance=0.0,
        discrepancy_reason="Disclosed reduction matches independent calculation.",
        matched_metric="Scope 1 Emissions",
        baseline_year="FY24",
        target_year="FY25",
        baseline_value=48736.0,
        target_value=43754.0,
        audit_decision=AuditDecision.PASS,
        execution_status=ExecutionStatus.SUCCESS,
        summary=RuleSummaryCounts(total_rules=15, passed=4, flagged=0, not_applicable=11),
    )

    pdf_audit = PDFAuditResult(
        audit_result=audit_res,
        claim=claim,
        evidence=[ev_fy24, ev_fy25],
        source_file="test_brsr.pdf",
        source_pages=[88],
        entity="TML",
        match_status="Matched",
        is_derived=False,
        evidence_type=EvidenceType.SOURCE_REPORTED.value,
    )

    assert pdf_audit.status == "PASS"
    assert pdf_audit.audit_decision == AuditDecision.PASS
    assert pdf_audit.calculated_delta == 10.22
    assert pdf_audit.variance == 0.0
    assert len(pdf_audit.evidence) == 2
    assert pdf_audit.evidence[0].evidence_type == "SOURCE_REPORTED"
    assert pdf_audit.source_pages == [88]
