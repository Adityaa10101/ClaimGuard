from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AuditDecision(str, Enum):
    PASS = "PASS"
    FLAGGED = "FLAGGED"
    UNVERIFIED = "UNVERIFIED"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    MISSING_DATA = "MISSING_DATA"
    INVALID_DATA = "INVALID_DATA"
    ERROR = "ERROR"


class RuleStatus(str, Enum):
    PASS = "PASS"
    FLAGGED = "FLAGGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING_DATA = "MISSING_DATA"
    INVALID_DATA = "INVALID_DATA"
    ERROR = "ERROR"


class ExtractedClaim(BaseModel):
    """
    Pydantic schema for PR narrative claim extraction.
    Note: The LLM is strictly used for extraction of claimed entities/values,
    and is FORBIDDEN from performing mathematical validation.
    """
    metric: str = Field(
        ...,
        description="The ESG or operational metric mentioned in the claim (e.g. Total Scope 1 & 2 Emissions)"
    )
    claimed_percentage: float = Field(
        ...,
        description="The numerical percentage reduction or change claimed in narrative text (e.g. 2.59 or 20.0)"
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


class RuleEvidence(BaseModel):
    """Structured audit evidence trail for an individual rule execution."""
    metric_id: Optional[str] = None
    metric_name: Optional[str] = None
    baseline_year: Optional[str] = None
    target_year: Optional[str] = None
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    raw_formula: Optional[str] = None
    additional_context: Dict[str, Any] = Field(default_factory=dict)


class RuleResult(BaseModel):
    """
    Standardized result contract for all deterministic validation rules.
    Non-numeric rules may convey findings via status, message, and evidence.
    """
    rule_id: str = Field(..., description="Unique rule code (e.g., 'EM-01', 'GEN-01')")
    domain: str = Field(..., description="Rule domain: 'Emissions', 'Energy', 'Water', 'General'")
    rule_name: str = Field(..., description="Human-readable rule title")
    status: RuleStatus = Field(..., description="Evaluation outcome status")
    actual_value: Optional[float] = Field(None, description="Calculated value from ground-truth CSV")
    expected_value: Optional[float] = Field(None, description="Claimed value or theoretical requirement")
    variance: Optional[float] = Field(None, description="Absolute mathematical variance (|actual - expected|)")
    tolerance: float = Field(0.05, description="Allowed variance threshold")
    message: str = Field(..., description="Auditor narrative detailing finding")
    evidence: RuleEvidence = Field(default_factory=RuleEvidence, description="Structured audit trail")


class RuleSummaryCounts(BaseModel):
    total_rules: int = 0
    passed: int = 0
    flagged: int = 0
    not_applicable: int = 0
    missing_data: int = 0
    invalid_data: int = 0
    error: int = 0


class AuditResult(BaseModel):
    """
    Pydantic schema representing the deterministic audit output.
    Maintains 100% backward compatibility with app.py while carrying
    extended rule execution diagnostics.
    """
    # Core legacy fields (Preserved for app.py UI binding)
    status: str = Field(
        ...,
        description="Audit status string: 'PASS' if math verified, else 'FLAGGED' or 'UNVERIFIED'"
    )
    claimed_percentage: float = Field(
        ...,
        description="The percentage reduction claimed in narrative"
    )
    calculated_delta: float = Field(
        ...,
        description="The actual percentage change calculated mathematically from tabular CSV data"
    )
    variance: float = Field(
        ...,
        description="Absolute difference between claimed and calculated percentages"
    )
    discrepancy_reason: str = Field(
        ...,
        description="Human-readable audit explanation and findings summary"
    )
    matched_metric: Optional[str] = Field(
        None,
        description="Name of the matching metric row found in CSV metrics"
    )
    baseline_year: Optional[str] = Field(
        "FY23",
        description="Dynamic baseline year from claim (e.g. FY23, FY24)"
    )
    target_year: Optional[str] = Field(
        "FY24",
        description="Dynamic target year from claim (e.g. FY24, FY25)"
    )
    baseline_value: Optional[float] = Field(
        None,
        description="Ground truth baseline year value from CSV"
    )
    target_value: Optional[float] = Field(
        None,
        description="Ground truth target year value from CSV"
    )
    fy23_value: Optional[float] = Field(
        None,
        description="Backward compatible alias for baseline_value"
    )
    fy24_value: Optional[float] = Field(
        None,
        description="Backward compatible alias for target_value"
    )

    # Extended deterministic engine diagnostic fields
    audit_decision: AuditDecision = Field(
        AuditDecision.PASS,
        description="Formal audit decision: PASS, FLAGGED, or UNVERIFIED"
    )
    execution_status: ExecutionStatus = Field(
        ExecutionStatus.SUCCESS,
        description="Engine execution status: SUCCESS, PARTIAL, MISSING_DATA, INVALID_DATA, ERROR"
    )
    summary: RuleSummaryCounts = Field(
        default_factory=RuleSummaryCounts,
        description="Rollup counts across all evaluated rules"
    )
    rule_results: List[RuleResult] = Field(
        default_factory=list,
        description="Complete list of all individual rule execution outputs"
    )
