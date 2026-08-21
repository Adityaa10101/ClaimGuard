from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

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
        description="The numerical percentage reduction or change claimed in the narrative text (e.g. 2.59 or 20.0)"
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

class AuditResult(BaseModel):
    """
    Pydantic schema representing the deterministic audit output.
    All calculations are executed in pure Python/Pandas dynamically based on claim years.
    """
    status: str = Field(
        ...,
        description="Audit status: 'PASS' if math matches claim within tolerance, else 'FLAGGED'"
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
