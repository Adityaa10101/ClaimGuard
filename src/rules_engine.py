"""
ClaimGuard Rules Engine — Backward-compatible wrapper.

This module maintains the Round 1 API (verify_claim) while delegating
to the new production RuleEngine with 15 deterministic rules.

For new code, use:
    from src.rules import create_default_engine
    engine = create_default_engine()
    report = engine.evaluate_all(claims, source_data)
"""

import pandas as pd
from typing import Union

from src.schemas import (
    ExtractedClaim, AuditResult, Claim, RuleResult,
    ClaimCategory, ValidationStatus, detect_category,
)
from src.rules import create_default_engine, find_metric_row, get_period_value


def verify_claim(
    claim: ExtractedClaim,
    metrics_source: Union[str, pd.DataFrame],
    tolerance: float = 0.05,
) -> AuditResult:
    """
    Legacy API: verify a single ExtractedClaim against metrics CSV.

    Internally uses the new production RuleEngine but returns
    the Round 1 AuditResult format for backward compatibility.
    """
    # Load source data
    if isinstance(metrics_source, str):
        df = pd.read_csv(metrics_source)
    else:
        df = metrics_source.copy()

    df.columns = [col.strip().lower() for col in df.columns]

    # Convert legacy claim to production Claim
    production_claim = claim.to_claim()

    # Use the production engine
    engine = create_default_engine()
    results = engine.evaluate_claim(production_claim, df)

    # Find the core percentage reduction result for backward compat
    pct_result = None
    for r in results:
        if r.rule_id == "EMISSIONS_REDUCTION_PCT_V1":
            pct_result = r
            break

    # If no percentage result found, use the original logic
    if pct_result is None:
        return _legacy_verify(claim, df, tolerance)

    # Map back to legacy AuditResult
    b_year = claim.baseline_year.strip().upper() if claim.baseline_year else "FY23"
    t_year = claim.target_year.strip().upper() if claim.target_year else "FY24"

    # Get source values for display
    row = find_metric_row(df, claim.metric)
    baseline_val = get_period_value(row, claim.baseline_year) if row else None
    target_val = get_period_value(row, claim.target_year) if row else None

    status = "PASS" if pct_result.status == ValidationStatus.PASS else "FLAGGED"

    return AuditResult(
        status=status,
        claimed_percentage=round(claim.claimed_percentage, 2),
        calculated_delta=pct_result.calculated_value or 0.0,
        variance=pct_result.variance or 0.0,
        discrepancy_reason=pct_result.explanation,
        matched_metric=row.get("metric_name") if row else None,
        baseline_year=b_year,
        target_year=t_year,
        baseline_value=baseline_val,
        target_value=target_val,
        fy23_value=baseline_val,
        fy24_value=target_val,
    )


def _legacy_verify(
    claim: ExtractedClaim,
    df: pd.DataFrame,
    tolerance: float,
) -> AuditResult:
    """Fallback to original pure-Python verification if new engine can't run."""
    b_year = claim.baseline_year.strip().upper() if claim.baseline_year else "FY23"
    t_year = claim.target_year.strip().upper() if claim.target_year else "FY24"

    row = find_metric_row(df, claim.metric)
    if row is None:
        return AuditResult(
            status="FLAGGED",
            claimed_percentage=claim.claimed_percentage,
            calculated_delta=0.0,
            variance=claim.claimed_percentage,
            discrepancy_reason=f"Unable to locate matching CSV metric for '{claim.metric}'.",
            matched_metric=None,
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=None,
            target_value=None,
            fy23_value=None,
            fy24_value=None,
        )

    metric_name = row.get("metric_name", "Unknown Metric")
    baseline_val = get_period_value(row, claim.baseline_year)
    target_val = get_period_value(row, claim.target_year)

    if baseline_val is None or target_val is None:
        return AuditResult(
            status="FLAGGED",
            claimed_percentage=claim.claimed_percentage,
            calculated_delta=0.0,
            variance=claim.claimed_percentage,
            discrepancy_reason="Missing year column(s) in metrics table.",
            matched_metric=str(metric_name),
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=baseline_val,
            target_value=target_val,
            fy23_value=baseline_val,
            fy24_value=target_val,
        )

    if baseline_val == 0:
        return AuditResult(
            status="FLAGGED",
            claimed_percentage=claim.claimed_percentage,
            calculated_delta=0.0,
            variance=claim.claimed_percentage,
            discrepancy_reason=f"Baseline ({b_year}) value is 0.",
            matched_metric=str(metric_name),
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=baseline_val,
            target_value=target_val,
            fy23_value=baseline_val,
            fy24_value=target_val,
        )

    raw_delta = ((baseline_val - target_val) / baseline_val) * 100.0
    calculated_delta = round(raw_delta, 2)
    claimed_pct = round(claim.claimed_percentage, 2)
    variance = round(abs(claimed_pct - calculated_delta), 2)

    if variance <= tolerance:
        status = "PASS"
        reason = (
            f"VERIFIED: {claimed_pct}% matches {calculated_delta}% "
            f"({b_year}: {baseline_val:,.2f} → {t_year}: {target_val:,.2f})."
        )
    else:
        status = "FLAGGED"
        reason = (
            f"DISCREPANCY: Claims {claimed_pct}% but calculated "
            f"{calculated_delta}% ({b_year}: {baseline_val:,.2f} → "
            f"{t_year}: {target_val:,.2f}). Variance: {variance}%."
        )

    return AuditResult(
        status=status,
        claimed_percentage=claimed_pct,
        calculated_delta=calculated_delta,
        variance=variance,
        discrepancy_reason=reason,
        matched_metric=str(metric_name),
        baseline_year=b_year,
        target_year=t_year,
        baseline_value=baseline_val,
        target_value=target_val,
        fy23_value=baseline_val,
        fy24_value=target_val,
    )
