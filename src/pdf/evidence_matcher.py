"""
ClaimGuard — Phase 6C: Evidence Matcher
Matches semantic ClaimCandidates against ExtractedEvidence from PDF documents.
Constructs engine-ready DataFrames for the deterministic rules engine without
performing any audit calculations or percentage verifications.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from .models import ExtractedEvidence, EvidenceType, ParsedDocument
from .claim_models import ClaimCandidate, EntityBoundary
from ..schemas import ExtractedClaim
from ..rules.year_resolver import normalize_fiscal_year

logger = logging.getLogger("claimguard.pdf.evidence_matcher")


@dataclass
class MatchResult:
    """
    Structured outcome of matching a ClaimCandidate against ExtractedEvidence.
    Explicitly distinguishes SOURCE_REPORTED disclosures from DERIVED aggregations.
    Contains engine-ready DataFrame and provenance metadata.
    """
    is_matched: bool
    extracted_claim: Optional[ExtractedClaim] = None
    metrics_df: Optional[pd.DataFrame] = None
    matched_evidence: List[ExtractedEvidence] = field(default_factory=list)  # Source-reported disclosures
    derived_evidence: List[ExtractedEvidence] = field(default_factory=list)  # Explicitly flagged derived evidence
    is_derived: bool = False
    evidence_type: str = EvidenceType.SOURCE_REPORTED.value
    derivation_basis: Optional[str] = None
    source_file: str = ""
    source_pages: List[int] = field(default_factory=list)
    entity: str = EntityBoundary.UNKNOWN.value
    status_message: str = ""
    error_code: Optional[str] = None  # e.g., "AMBIGUOUS_ENTITY", "MISSING_YEARS", "NO_MATCH"


def claim_candidate_to_extracted_claim(candidate: ClaimCandidate) -> ExtractedClaim:
    """
    Adapter converting Phase 6B ClaimCandidate to existing ExtractedClaim contract.
    Preserves 100% compatibility with src.schemas.ExtractedClaim without schema changes.
    """
    metric_str = candidate.metric or "Total Scope 1 & 2 Emissions"
    claimed_pct = candidate.claimed_percentage if candidate.claimed_percentage is not None else 0.0
    b_year = candidate.baseline_year or "FY24"
    t_year = candidate.target_year or "FY25"
    claim_text = candidate.claim_text or ""

    return ExtractedClaim(
        metric=metric_str,
        claimed_percentage=claimed_pct,
        baseline_year=b_year,
        target_year=t_year,
        claim_text=claim_text,
    )


class EvidenceMatcher:
    """
    Deterministic matcher connecting ClaimCandidate disclosures to extracted evidence.
    Prepares normalized DataFrame tables for verify_claim().
    """

    def __init__(self, evidence_list: List[ExtractedEvidence]):
        self.evidence_list = evidence_list

    def match_claim(self, claim: ClaimCandidate) -> MatchResult:
        """
        Matches a claim candidate to source evidence based on:
        1. Reporting boundary / entity
        2. Metric scope (Combined Scope 1+2 vs Scope 1 vs Scope 2)
        3. Fiscal baseline and target years
        """
        # 1. Entity Validation Guard
        entity_req = (claim.entity or EntityBoundary.UNKNOWN.value).upper()
        if entity_req == EntityBoundary.UNKNOWN.value:
            return MatchResult(
                is_matched=False,
                status_message=f"Ambiguous entity boundary in claim ('{claim.entity}'). Cannot safely match evidence.",
                error_code="AMBIGUOUS_ENTITY",
                entity=EntityBoundary.UNKNOWN.value,
            )

        # Map entity boundary to evidence entity labels
        entity_evidence: List[ExtractedEvidence] = []
        for ev in self.evidence_list:
            ev_ent = (ev.entity or "").upper()
            if entity_req == EntityBoundary.TML.value:
                if ev_ent == "TML":
                    entity_evidence.append(ev)
            elif entity_req == EntityBoundary.TMPVL_TPEML.value:
                if "TMPVL" in ev_ent and "TPEML" in ev_ent and "CONSOLIDATED" not in ev_ent:
                    entity_evidence.append(ev)
            elif entity_req == EntityBoundary.CONSOLIDATED.value:
                if "CONSOLIDATED" in ev_ent:
                    entity_evidence.append(ev)

        if not entity_evidence:
            return MatchResult(
                is_matched=False,
                status_message=f"No source evidence found for entity boundary: '{claim.entity}'",
                error_code="NO_ENTITY_EVIDENCE",
                entity=claim.entity,
            )

        # 2. Year Validation
        b_year = normalize_fiscal_year(claim.baseline_year) or "FY24"
        t_year = normalize_fiscal_year(claim.target_year) or "FY25"

        if b_year == t_year:
            return MatchResult(
                is_matched=False,
                status_message=f"Invalid year pair: baseline ({b_year}) and target ({t_year}) cannot be identical.",
                error_code="INVALID_YEAR_ALIGNMENT",
                entity=claim.entity,
            )

        # 3. Metric Scope Matching
        metric_norm = (claim.metric or "").lower()
        is_combined = any(k in metric_norm for k in ["total", "combined", "1 & 2", "1 and 2", "greenhouse gas", "ghg"])
        is_scope1_only = "scope 1" in metric_norm and not is_combined
        is_scope2_only = "scope 2" in metric_norm and not is_combined

        if is_scope1_only:
            return self._build_single_metric_match(
                claim=claim,
                evidence_pool=entity_evidence,
                target_metric="Scope 1",
                canonical_name="Scope 1 Direct Emissions",
                b_year=b_year,
                t_year=t_year,
            )
        elif is_scope2_only:
            return self._build_single_metric_match(
                claim=claim,
                evidence_pool=entity_evidence,
                target_metric="Scope 2",
                canonical_name="Scope 2 Indirect Emissions",
                b_year=b_year,
                t_year=t_year,
            )
        else:
            # Combined Total Scope 1 & 2
            return self._build_combined_emissions_match(
                claim=claim,
                evidence_pool=entity_evidence,
                b_year=b_year,
                t_year=t_year,
            )

    def _build_single_metric_match(
        self,
        claim: ClaimCandidate,
        evidence_pool: List[ExtractedEvidence],
        target_metric: str,
        canonical_name: str,
        b_year: str,
        t_year: str,
    ) -> MatchResult:
        """Matches a single direct metric (Scope 1 only or Scope 2 only). Evidence is 100% SOURCE_REPORTED."""
        ev_base = next((e for e in evidence_pool if e.metric == target_metric and e.reporting_year == b_year), None)
        ev_target = next((e for e in evidence_pool if e.metric == target_metric and e.reporting_year == t_year), None)

        if not ev_base or not ev_target:
            missing = []
            if not ev_base:
                missing.append(b_year)
            if not ev_target:
                missing.append(t_year)
            return MatchResult(
                is_matched=False,
                status_message=f"Missing required year disclosure(s) {missing} for {target_metric}.",
                error_code="MISSING_YEARS",
                entity=claim.entity,
            )

        matched_evs = [ev_base, ev_target]
        source_pages = sorted(list(set(e.page_number for e in matched_evs)))
        source_file = ev_base.source_file

        # Build engine DataFrame
        b_col = f"{b_year.lower()}_value"
        t_col = f"{t_year.lower()}_value"
        df = pd.DataFrame([{
            "metric_id": f"MTR-{target_metric.upper().replace(' ', '')}",
            "category": "Emissions",
            "metric_name": canonical_name,
            "unit": ev_base.unit or "tCO2e",
            b_col: ev_base.value,
            t_col: ev_target.value,
        }])

        extracted_claim = claim_candidate_to_extracted_claim(claim)
        return MatchResult(
            is_matched=True,
            extracted_claim=extracted_claim,
            metrics_df=df,
            matched_evidence=matched_evs,
            derived_evidence=[],
            is_derived=False,
            evidence_type=EvidenceType.SOURCE_REPORTED.value,
            derivation_basis=None,
            source_file=source_file,
            source_pages=source_pages,
            entity=claim.entity,
            status_message=f"Successfully matched source-reported {target_metric} evidence for {claim.entity} ({b_year} -> {t_year}).",
        )

    def _build_combined_emissions_match(
        self,
        claim: ClaimCandidate,
        evidence_pool: List[ExtractedEvidence],
        b_year: str,
        t_year: str,
    ) -> MatchResult:
        """
        Matches combined Scope 1 and Scope 2 emissions evidence.
        
        FINAL UNIT-SEMANTICS HARDENING:
        1. Checks for an explicitly source-reported absolute combined metric first.
        2. If none exists, checks whether constituent units are identical.
        3. In the Tata Motors BRSR, Scope 1 is reported in 'tCO2e' and Scope 2 in 'tCO2'.
           Because the document does not provide an explicit unit normalization basis,
           an absolute combined total is NOT silently assumed or manufactured.
           Returns controlled UNVERIFIED / UNIT_MISMATCH_UNVERIFIED.
        """
        # 1. Check for explicit source-reported combined metric first
        comb_base = next((e for e in evidence_pool if e.metric.lower() in ["total scope 1 and 2", "total scope 1 & 2", "combined scope 1 and 2"] and e.reporting_year == b_year), None)
        comb_target = next((e for e in evidence_pool if e.metric.lower() in ["total scope 1 and 2", "total scope 1 & 2", "combined scope 1 and 2"] and e.reporting_year == t_year), None)

        if comb_base and comb_target and comb_base.evidence_type == EvidenceType.SOURCE_REPORTED.value:
            # Direct source-reported combined metric exists in document
            matched_evs = [comb_base, comb_target]
            source_pages = sorted(list(set(e.page_number for e in matched_evs)))
            b_col = f"{b_year.lower()}_value"
            t_col = f"{t_year.lower()}_value"
            df = pd.DataFrame([{
                "metric_id": "MTR-GHG-01",
                "category": "Emissions",
                "metric_name": "Total Scope 1 & 2 Emissions",
                "unit": comb_base.unit or "tCO2e",
                b_col: comb_base.value,
                t_col: comb_target.value,
            }])
            return MatchResult(
                is_matched=True,
                extracted_claim=claim_candidate_to_extracted_claim(claim),
                metrics_df=df,
                matched_evidence=matched_evs,
                derived_evidence=[],
                is_derived=False,
                evidence_type=EvidenceType.SOURCE_REPORTED.value,
                derivation_basis=None,
                source_file=comb_base.source_file,
                source_pages=source_pages,
                entity=claim.entity,
                status_message=f"Successfully matched source-reported combined Scope 1 & 2 evidence for {claim.entity} ({b_year} -> {t_year}).",
            )

        # 2. Look for constituent Scope 1 and Scope 2 disclosures
        s1_base = next((e for e in evidence_pool if e.metric == "Scope 1" and e.reporting_year == b_year), None)
        s1_target = next((e for e in evidence_pool if e.metric == "Scope 1" and e.reporting_year == t_year), None)
        s2_base = next((e for e in evidence_pool if e.metric == "Scope 2" and e.reporting_year == b_year), None)
        s2_target = next((e for e in evidence_pool if e.metric == "Scope 2" and e.reporting_year == t_year), None)

        missing_disclosures = []
        if not s1_base:
            missing_disclosures.append(f"Scope 1 {b_year}")
        if not s1_target:
            missing_disclosures.append(f"Scope 1 {t_year}")
        if not s2_base:
            missing_disclosures.append(f"Scope 2 {b_year}")
        if not s2_target:
            missing_disclosures.append(f"Scope 2 {t_year}")

        if missing_disclosures:
            return MatchResult(
                is_matched=False,
                status_message=f"Incomplete emissions disclosures for {claim.entity}. Missing: {missing_disclosures}.",
                error_code="MISSING_COMBINED_DISCLOSURES",
                entity=claim.entity,
            )

        # 3. Unit Compatibility & Semantics Verification
        s1_unit = (s1_base.unit or "").strip().lower()
        s2_unit = (s2_base.unit or "").strip().lower()

        # If constituent units are not identical (e.g. tCO2e vs tCO2), do NOT silently sum them
        if s1_unit != s2_unit:
            return MatchResult(
                is_matched=False,
                status_message=(
                    f"Unit mismatch: Scope 1 is reported in '{s1_base.unit}' while Scope 2 is reported in '{s2_base.unit}'. "
                    f"The source document does not provide an explicit unit normalization basis between these distinct units. "
                    f"Direct Scope 1 ('{s1_base.unit}') and Scope 2 ('{s2_base.unit}') disclosures must be audited independently. "
                    f"Combined absolute claim is UNVERIFIED."
                ),
                error_code="UNIT_MISMATCH_UNVERIFIED",
                entity=claim.entity,
                matched_evidence=[s1_base, s1_target, s2_base, s2_target],
                source_file=s1_base.source_file,
                source_pages=sorted(list(set([s1_base.page_number, s2_base.page_number]))),
            )

        # 4. If units are identical, construct derived sum
        combined_b_val = s1_base.value + s2_base.value
        combined_t_val = s1_target.value + s2_target.value

        derivation_text = (
            f"Derived sum: Scope 1 ({s1_base.value:,.0f} {s1_base.unit}) + "
            f"Scope 2 ({s2_base.value:,.0f} {s2_base.unit}) = {combined_b_val:,.0f} ({b_year}); "
            f"Scope 1 ({s1_target.value:,.0f} {s1_target.unit}) + "
            f"Scope 2 ({s2_target.value:,.0f} {s2_target.unit}) = {combined_t_val:,.0f} ({t_year})."
        )

        matched_evs = [s1_base, s1_target, s2_base, s2_target]
        source_pages = sorted(list(set(e.page_number for e in matched_evs)))
        source_file = s1_base.source_file

        derived_evs = [
            ExtractedEvidence(
                source_file=source_file,
                page_number=source_pages[0] if source_pages else 0,
                metric="Total Scope 1 and 2",
                reporting_year=b_year,
                value=combined_b_val,
                raw_value=f"{combined_b_val:,.0f} (derived)",
                unit=s1_base.unit,
                entity=claim.entity,
                evidence_type=EvidenceType.DERIVED.value,
                derivation_notes=derivation_text,
            ),
            ExtractedEvidence(
                source_file=source_file,
                page_number=source_pages[0] if source_pages else 0,
                metric="Total Scope 1 and 2",
                reporting_year=t_year,
                value=combined_t_val,
                raw_value=f"{combined_t_val:,.0f} (derived)",
                unit=s1_base.unit,
                entity=claim.entity,
                evidence_type=EvidenceType.DERIVED.value,
                derivation_notes=derivation_text,
            ),
        ]

        b_col = f"{b_year.lower()}_value"
        t_col = f"{t_year.lower()}_value"

        df = pd.DataFrame([
            {
                "metric_id": "MTR-GHG-01",
                "category": "Emissions",
                "metric_name": "Total Scope 1 & 2 Emissions",
                "unit": s1_base.unit or "tCO2e",
                b_col: combined_b_val,
                t_col: combined_t_val,
            },
            {
                "metric_id": "MTR-S1-01",
                "category": "Emissions",
                "metric_name": "Scope 1 Direct Emissions",
                "unit": s1_base.unit or "tCO2e",
                b_col: s1_base.value,
                t_col: s1_target.value,
            },
            {
                "metric_id": "MTR-S2-01",
                "category": "Emissions",
                "metric_name": "Scope 2 Indirect Emissions",
                "unit": s2_base.unit or "tCO2e",
                b_col: s2_base.value,
                t_col: s2_target.value,
            },
        ])

        return MatchResult(
            is_matched=True,
            extracted_claim=claim_candidate_to_extracted_claim(claim),
            metrics_df=df,
            matched_evidence=matched_evs,
            derived_evidence=derived_evs,
            is_derived=True,
            evidence_type=EvidenceType.DERIVED.value,
            derivation_basis=derivation_text,
            source_file=source_file,
            source_pages=source_pages,
            entity=claim.entity,
            status_message=f"Successfully matched and derived Scope 1 & 2 disclosures for {claim.entity} ({b_year} -> {t_year}).",
        )
