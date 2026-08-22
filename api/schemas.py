"""
ClaimGuard API — Request/Response Schemas

Thin Pydantic models for the FastAPI boundary layer.
Domain schemas (ExtractedClaim, AuditResult, RuleResult, etc.) are
reused directly from src.schemas — NOT duplicated here.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Request Models
# ──────────────────────────────────────────────

class MetricRecord(BaseModel):
    """
    Single metric row matching the ground-truth CSV schema.

    Core fields are explicitly validated. Additional domain-specific
    columns (e.g. recycling_rate_fy24, fuel_energy_fy24, scope3_*)
    are captured via model_config extra='allow' so that extended
    fixtures pass through to the DataFrame without rejection.
    """
    metric_id: str = Field(..., description="Unique metric identifier (e.g. MTR-001)")
    category: str = Field(..., description="Domain category (e.g. Emissions, Energy, Water)")
    metric_name: str = Field(..., description="Human-readable metric name")
    unit: str = Field(..., description="Unit of measurement (e.g. MT CO2e, MWh, kGal)")

    model_config = {"extra": "allow"}


class AuditRequest(BaseModel):
    """
    POST /audit request payload.

    Contains the PR narrative text and the ground-truth metrics
    that the deterministic engine will verify against.
    """
    narrative: str = Field(
        ...,
        min_length=1,
        description="PR / sustainability narrative text containing ESG claims"
    )
    metrics: List[MetricRecord] = Field(
        ...,
        min_length=1,
        description="Ground-truth metric records (matching CSV column schema)"
    )


# ──────────────────────────────────────────────
# Response Models (for OpenAPI docs only)
# ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    """GET /health response."""
    status: str = Field(..., description="Service status: 'ok'")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
    rules_loaded: int = Field(..., description="Number of deterministic rules loaded")


class RuleInfo(BaseModel):
    """Single rule descriptor for GET /rules."""
    rule_id: str = Field(..., description="Unique rule code (e.g. EM-01)")
    domain: str = Field(..., description="Rule domain (Emissions, Energy, Water, General)")
    name: str = Field(..., description="Human-readable rule name")
    description: str = Field("", description="Rule description")


class RulesResponse(BaseModel):
    """GET /rules response."""
    total: int = Field(..., description="Total number of registered rules")
    rules: List[RuleInfo] = Field(..., description="List of all registered rules")
