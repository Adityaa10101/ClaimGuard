"""
ClaimGuard Schema Definitions — Production-grade Pydantic models.

Defines the data structures for:
- Claims extracted from ESG filings
- Rule execution results with full evidence chains
- Complete audit reports with processing metrics

All validation decisions are made by deterministic rules, not LLMs.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
import uuid


# ─── Enums ────────────────────────────────────────────────────────────────────

class ClaimCategory(str, Enum):
    """ESG filing claim categories."""
    EMISSIONS = "emissions"
    ENERGY = "energy"
    WATER = "water"
    WASTE = "waste"
    GENERAL = "general"


class ValidationStatus(str, Enum):
    """Deterministic validation outcome."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNSUPPORTED = "UNSUPPORTED"


class Severity(str, Enum):
    """Finding severity level."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Authority(str, Enum):
    """Whether the finding is deterministic (authoritative) or heuristic."""
    DETERMINISTIC = "DETERMINISTIC"
    HEURISTIC = "HEURISTIC"


# ─── Core Models ──────────────────────────────────────────────────────────────

class Claim(BaseModel):
    """
    Production-grade ESG claim extracted from a filing.

    The LLM extracts these fields from narrative text.
    Mathematical validation is NEVER performed by the LLM.
    """
    claim_id: str = Field(
        default_factory=lambda: f"CLM-{uuid.uuid4().hex[:6].upper()}",
        description="Unique claim identifier"
    )
    company: str = Field(
        default="",
        description="Company name from the filing"
    )
    metric: str = Field(
        ...,
        description="The ESG metric (e.g. 'Total Scope 1 & 2 Emissions')"
    )
    category: ClaimCategory = Field(
        default=ClaimCategory.GENERAL,
        description="Claim category: emissions, energy, water, waste, general"
    )
    reported_value: float = Field(
        ...,
        description="The numerical value claimed in the narrative"
    )
    reported_unit: str = Field(
        default="percent",
        description="Unit of the reported value (percent, MT CO2e, kWh, kGal)"
    )
    previous_value: Optional[float] = Field(
        default=None,
        description="Baseline period value mentioned in narrative"
    )
    current_value: Optional[float] = Field(
        default=None,
        description="Current period value mentioned in narrative"
    )
    previous_period: str = Field(
        default="FY23",
        description="Baseline comparison period (e.g. FY23)"
    )
    current_period: str = Field(
        default="FY24",
        description="Current evaluation period (e.g. FY24)"
    )
    source_page: Optional[int] = Field(
        default=None,
        description="PDF page number where claim was found"
    )
    source_text: str = Field(
        default="",
        description="Verbatim text containing the claim"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0, le=1.0,
        description="LLM extraction confidence (0.0 to 1.0)"
    )


class RuleResult(BaseModel):
    """
    Output of a single deterministic rule execution.

    Contains the complete evidence chain:
    Rule → Formula → Calculated Value → Reported Value → Variance → Decision
    """
    rule_id: str = Field(
        ...,
        description="Unique rule identifier (e.g. EMISSIONS_REDUCTION_PCT_V1)"
    )
    rule_name: str = Field(
        ...,
        description="Human-readable rule name"
    )
    claim_id: str = Field(
        default="",
        description="ID of the claim this result belongs to"
    )
    status: ValidationStatus = Field(
        ...,
        description="PASS / FAIL / UNSUPPORTED"
    )
    severity: Severity = Field(
        default=Severity.MEDIUM,
        description="HIGH / MEDIUM / LOW / INFO"
    )
    reported_value: Optional[float] = Field(
        default=None,
        description="The value claimed in the filing"
    )
    calculated_value: Optional[float] = Field(
        default=None,
        description="The value calculated from source data"
    )
    variance: Optional[float] = Field(
        default=None,
        description="Absolute difference between reported and calculated"
    )
    formula: str = Field(
        default="",
        description="The mathematical formula used for verification"
    )
    explanation: str = Field(
        ...,
        description="Human-readable explanation of the finding"
    )
    source_evidence: str = Field(
        default="",
        description="Verbatim source text or data used for verification"
    )
    authority: Authority = Field(
        default=Authority.DETERMINISTIC,
        description="DETERMINISTIC (authoritative) or HEURISTIC (review recommended)"
    )


class ProcessingTime(BaseModel):
    """Per-stage timing breakdown for the audit pipeline."""
    pdf_extraction_s: float = 0.0
    ai_extraction_s: float = 0.0
    validation_s: float = 0.0
    total_s: float = 0.0


class AuditSummary(BaseModel):
    """Aggregate statistics for an audit report."""
    total_claims: int = 0
    total_rules_executed: int = 0
    passed: int = 0
    failed: int = 0
    unsupported: int = 0
    high_severity_failures: int = 0


class AuditReport(BaseModel):
    """
    Complete audit report for a filing.

    Contains all claims, rule results, summary statistics,
    and processing time — the full evidence chain for every decision.
    """
    report_id: str = Field(
        default_factory=lambda: f"RPT-{uuid.uuid4().hex[:8].upper()}"
    )
    company: str = ""
    filing_period: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    claims: List[Claim] = Field(default_factory=list)
    results: List[RuleResult] = Field(default_factory=list)
    summary: AuditSummary = Field(default_factory=AuditSummary)
    processing_time: ProcessingTime = Field(default_factory=ProcessingTime)


# ─── Backward Compatibility (Round 1) ────────────────────────────────────────

class ExtractedClaim(BaseModel):
    """
    Legacy schema for PR narrative claim extraction (Round 1 compatibility).
    Use Claim for new code.
    """
    metric: str = Field(
        ...,
        description="The ESG or operational metric mentioned in the claim"
    )
    claimed_percentage: float = Field(
        ...,
        description="The numerical percentage claimed in the narrative text"
    )
    baseline_year: str = Field(
        ...,
        description="The baseline comparison year (e.g. FY23)"
    )
    target_year: str = Field(
        ...,
        description="The target evaluation year (e.g. FY24)"
    )
    claim_text: Optional[str] = Field(
        None,
        description="The verbatim claim sentence extracted from the narrative text"
    )

    def to_claim(
        self,
        company: str = "",
        category: Optional[ClaimCategory] = None
    ) -> Claim:
        """Convert legacy ExtractedClaim to production Claim."""
        cat = category or detect_category(self.metric)
        return Claim(
            company=company,
            metric=self.metric,
            category=cat,
            reported_value=self.claimed_percentage,
            reported_unit="percent",
            previous_period=self.baseline_year,
            current_period=self.target_year,
            source_text=self.claim_text or ""
        )


class AuditResult(BaseModel):
    """
    Legacy schema for deterministic audit output (Round 1 compatibility).
    Use RuleResult for new code.
    """
    status: str = Field(
        ...,
        description="Audit status: 'PASS' if math matches, else 'FLAGGED'"
    )
    claimed_percentage: float = Field(
        ...,
        description="The percentage reduction claimed in narrative"
    )
    calculated_delta: float = Field(
        ...,
        description="The actual percentage change calculated from CSV data"
    )
    variance: float = Field(
        ...,
        description="Absolute difference between claimed and calculated"
    )
    discrepancy_reason: str = Field(
        ...,
        description="Human-readable audit explanation"
    )
    matched_metric: Optional[str] = None
    baseline_year: Optional[str] = "FY23"
    target_year: Optional[str] = "FY24"
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    fy23_value: Optional[float] = None
    fy24_value: Optional[float] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def detect_category(metric_name: str) -> ClaimCategory:
    """Auto-detect claim category from metric name keywords."""
    name_lower = metric_name.lower()
    if any(kw in name_lower for kw in [
        "emission", "scope", "co2", "ghg", "carbon", "greenhouse"
    ]):
        return ClaimCategory.EMISSIONS
    elif any(kw in name_lower for kw in [
        "energy", "electricity", "renewable", "solar", "wind", "kwh", "mwh"
    ]):
        return ClaimCategory.ENERGY
    elif any(kw in name_lower for kw in [
        "water", "kgal", "water consumption", "water recycl"
    ]):
        return ClaimCategory.WATER
    elif any(kw in name_lower for kw in [
        "waste", "landfill", "recycl", "solid waste"
    ]):
        return ClaimCategory.WASTE
    return ClaimCategory.GENERAL
