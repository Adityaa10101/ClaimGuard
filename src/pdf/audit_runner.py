"""
ClaimGuard — Phase 6C: PDF Audit Runner
Coordinates PDF Claim Candidate matching with the existing deterministic rules engine.
Produces a PDFAuditResult carrying the engine's AuditResult alongside complete
source page provenance and extracted evidence trails.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .claim_models import ClaimCandidate, EntityBoundary
from .evidence_extractor import EvidenceExtractor
from .evidence_matcher import EvidenceMatcher, MatchResult, claim_candidate_to_extracted_claim
from .models import ExtractedEvidence, EvidenceType, ParsedDocument
from ..rules_engine import verify_claim
from ..schemas import AuditDecision, AuditResult, ExecutionStatus, RuleEvidence, RuleResult, RuleStatus, RuleSummaryCounts

logger = logging.getLogger("claimguard.pdf.audit_runner")


@dataclass
class PDFAuditResult:
    """
    Structured outcome of auditing a ClaimCandidate against a ParsedDocument.
    Carries the engine's deterministic AuditResult along with source page provenance.
    Explicitly distinguishes SOURCE_REPORTED disclosures from DERIVED metrics.
    """
    audit_result: AuditResult
    claim: ClaimCandidate
    evidence: List[ExtractedEvidence] = field(default_factory=list)  # Source-reported disclosures
    derived_evidence: List[ExtractedEvidence] = field(default_factory=list)  # Derived aggregations
    is_derived: bool = False
    evidence_type: str = EvidenceType.SOURCE_REPORTED.value
    derivation_basis: Optional[str] = None
    source_file: str = ""
    source_pages: List[int] = field(default_factory=list)
    entity: str = EntityBoundary.UNKNOWN.value
    match_status: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        """Forward status string: 'PASS', 'FLAGGED', etc."""
        return self.audit_result.status

    @property
    def audit_decision(self) -> AuditDecision:
        return self.audit_result.audit_decision

    @property
    def calculated_delta(self) -> float:
        return self.audit_result.calculated_delta

    @property
    def variance(self) -> float:
        return self.audit_result.variance

    @property
    def discrepancy_reason(self) -> str:
        return self.audit_result.discrepancy_reason


def audit_pdf_claim(
    claim: ClaimCandidate,
    document: ParsedDocument,
    evidence_list: Optional[List[ExtractedEvidence]] = None,
    tolerance: float = 0.05,
) -> PDFAuditResult:
    """
    End-to-end vertical slice auditing a single ClaimCandidate against a ParsedDocument.
    
    1. Extracts emissions evidence from document if not already provided.
    2. Matches ClaimCandidate against ExtractedEvidence via EvidenceMatcher.
    3. If matched, delegates 100% of mathematical validation to verify_claim().
    4. Wraps and returns PDFAuditResult retaining complete page-level provenance.
    """
    # 1. Extract evidence if not pre-provided
    if evidence_list is None:
        extractor = EvidenceExtractor(document)
        evidence_list = extractor.extract_emissions_evidence()

    # 2. Match claim against evidence pool
    matcher = EvidenceMatcher(evidence_list)
    match_res = matcher.match_claim(claim)

    if not match_res.is_matched or match_res.metrics_df is None:
        # Construct controlled unverified AuditResult via schemas
        claimed_pct = claim.claimed_percentage if claim.claimed_percentage is not None else 0.0
        reason_msg = f"PDF Audit Unverified: {match_res.status_message}"
        
        status_decision = AuditDecision.UNVERIFIED
        exec_status = ExecutionStatus.INVALID_DATA if match_res.error_code in ["AMBIGUOUS_ENTITY", "INCOMPATIBLE_UNITS", "UNIT_MISMATCH_UNVERIFIED"] else ExecutionStatus.MISSING_DATA
        
        unverified_audit_result = AuditResult(
            status="FLAGGED",
            claimed_percentage=round(claimed_pct, 2),
            calculated_delta=0.0,
            variance=round(claimed_pct, 2),
            discrepancy_reason=reason_msg,
            matched_metric=claim.metric,
            baseline_year=claim.baseline_year or "FY24",
            target_year=claim.target_year or "FY25",
            audit_decision=status_decision,
            execution_status=exec_status,
            summary=RuleSummaryCounts(
                total_rules=1,
                missing_data=1 if exec_status == ExecutionStatus.MISSING_DATA else 0,
                invalid_data=1 if exec_status == ExecutionStatus.INVALID_DATA else 0,
            ),
            rule_results=[
                RuleResult(
                    rule_id="EM-02",
                    domain="Emissions",
                    rule_name="YoY Percentage Delta Verification",
                    status=RuleStatus.MISSING_DATA if exec_status == ExecutionStatus.MISSING_DATA else RuleStatus.INVALID_DATA,
                    message=reason_msg,
                )
            ]
        )
        
        return PDFAuditResult(
            audit_result=unverified_audit_result,
            claim=claim,
            evidence=match_res.matched_evidence,
            derived_evidence=[],
            is_derived=False,
            evidence_type=EvidenceType.SOURCE_REPORTED.value,
            derivation_basis=None,
            source_file=match_res.source_file or document.filename,
            source_pages=match_res.source_pages,
            entity=claim.entity,
            match_status=match_res.status_message,
            metadata={"error_code": match_res.error_code},
        )

    # 3. Call EXISTING verify_claim() with matched DataFrame
    extracted_claim = match_res.extracted_claim or claim_candidate_to_extracted_claim(claim)
    engine_result = verify_claim(
        claim=extracted_claim,
        metrics_source=match_res.metrics_df,
        tolerance=tolerance,
    )

    # 4. Wrap and return PDFAuditResult with explicit derivation provenance
    return PDFAuditResult(
        audit_result=engine_result,
        claim=claim,
        evidence=match_res.matched_evidence,
        derived_evidence=match_res.derived_evidence,
        is_derived=match_res.is_derived,
        evidence_type=match_res.evidence_type,
        derivation_basis=match_res.derivation_basis,
        source_file=match_res.source_file or document.filename,
        source_pages=match_res.source_pages,
        entity=match_res.entity,
        match_status=match_res.status_message,
        metadata={
            "document_total_pages": document.total_pages,
            "matched_rows_count": len(match_res.metrics_df),
        },
    )
