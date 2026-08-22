import pandas as pd
from typing import Union, Optional, Dict, Any, List

from src.schemas import (
    ExtractedClaim,
    AuditResult,
    AuditDecision,
    ExecutionStatus,
    RuleResult,
    RuleStatus,
    RuleEvidence,
    RuleSummaryCounts,
)
from src.rules.base import RuleEvaluationContext
from src.rules.registry import RuleRegistry
from src.rules.metric_resolver import resolve_metric, MetricResolutionStatus
from src.rules.year_resolver import (
    normalize_fiscal_year,
    resolve_year_column,
    extract_numeric_value,
)
from src.rules.aggregator import ResultAggregator

# Floating-point representation noise tolerance epsilon
FLOAT_EPSILON = 1e-9


def verify_claim(
    claim: ExtractedClaim,
    metrics_source: Union[str, pd.DataFrame],
    tolerance: float = 0.05
) -> AuditResult:
    """
    Pure Python & Pandas deterministic rules engine.
    
    1. Normalizes and validates tabular metrics data.
    2. Conservatively resolves claimed metric without silent fallbacks.
    3. Normalizes and maps baseline and target fiscal years.
    4. Evaluates YoY percentage reduction with full floating-point precision.
    5. Dispatches context to registered domain validation rules.
    6. Aggregates multi-rule outcomes into a backward-compatible AuditResult.
    """
    # 1. Ingest metrics data source
    if isinstance(metrics_source, str):
        try:
            df = pd.read_csv(metrics_source)
        except Exception as e:
            return _create_error_result(
                claim=claim,
                reason=f"Failed to read CSV metrics source: {str(e)}",
                decision=AuditDecision.UNVERIFIED,
                status=ExecutionStatus.ERROR
            )
    elif isinstance(metrics_source, pd.DataFrame):
        df = metrics_source.copy()
    else:
        return _create_error_result(
            claim=claim,
            reason="Invalid metrics source provided. Expected CSV file path or pandas DataFrame.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.INVALID_DATA
        )

    if df.empty:
        return _create_error_result(
            claim=claim,
            reason="Metrics table is empty. Cannot perform audit verification.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.MISSING_DATA
        )

    # Clean column names (strip whitespace and convert to lowercase for resolution)
    df.columns = [col.strip().lower() for col in df.columns]

    # 2. Normalize baseline and target fiscal years
    b_year = normalize_fiscal_year(claim.baseline_year) or "FY23"
    t_year = normalize_fiscal_year(claim.target_year) or "FY24"

    if b_year == t_year:
        return _create_error_result(
            claim=claim,
            reason=f"Invalid year alignment: Baseline year ({b_year}) and target year ({t_year}) cannot be identical.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.INVALID_DATA,
            b_year=b_year,
            t_year=t_year
        )

    # 3. Deterministic metric resolution
    res_status, matched_row, metric_msg, candidate_matches = resolve_metric(claim.metric, df)

    if res_status == MetricResolutionStatus.AMBIGUOUS_MATCH:
        return _create_error_result(
            claim=claim,
            reason=f"Ambiguous metric query: '{claim.metric}' matched multiple candidate CSV records: {candidate_matches}. Specify exact metric.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.INVALID_DATA,
            b_year=b_year,
            t_year=t_year
        )

    if res_status == MetricResolutionStatus.NO_MATCH or matched_row is None:
        return _create_error_result(
            claim=claim,
            reason=f"Unable to locate matching CSV metric record for '{claim.metric}'.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.MISSING_DATA,
            b_year=b_year,
            t_year=t_year
        )

    metric_name = matched_row.get("metric_name", matched_row.get("metric_id", claim.metric))
    metric_id = matched_row.get("metric_id")

    # 4. Strict fiscal year column resolution
    baseline_col = resolve_year_column(list(df.columns), b_year)
    target_col = resolve_year_column(list(df.columns), t_year)

    if not baseline_col or not target_col:
        missing_cols = []
        if not baseline_col:
            missing_cols.append(f"{b_year.lower()}_value")
        if not target_col:
            missing_cols.append(f"{t_year.lower()}_value")
        return _create_error_result(
            claim=claim,
            reason=f"CSV metrics table is missing required year column(s): {', '.join(missing_cols)}.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.MISSING_DATA,
            b_year=b_year,
            t_year=t_year,
            matched_metric=str(metric_name)
        )

    # 5. Extract numeric values safely
    baseline_val, err_b = extract_numeric_value(matched_row, baseline_col)
    target_val, err_t = extract_numeric_value(matched_row, target_col)

    if baseline_val is None or target_val is None:
        err_details = err_b or err_t or "Invalid numerical data."
        return _create_error_result(
            claim=claim,
            reason=f"Failed to extract numeric values for {b_year} -> {t_year}: {err_details}",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.INVALID_DATA,
            b_year=b_year,
            t_year=t_year,
            matched_metric=str(metric_name),
            baseline_val=baseline_val,
            target_val=target_val
        )

    # Zero-division boundary check
    if baseline_val == 0.0:
        return _create_error_result(
            claim=claim,
            reason=f"Baseline year ({b_year}) value is 0. Cannot compute percentage delta.",
            decision=AuditDecision.UNVERIFIED,
            status=ExecutionStatus.INVALID_DATA,
            b_year=b_year,
            t_year=t_year,
            matched_metric=str(metric_name),
            baseline_val=baseline_val,
            target_val=target_val
        )

    # 6. PURE PYTHON DETERMINISTIC MATH (Full IEEE-754 Precision)
    # Reduction % = ((Baseline - Target) / Baseline) * 100
    raw_delta = ((baseline_val - target_val) / baseline_val) * 100.0
    raw_variance = abs(claim.claimed_percentage - raw_delta)

    # Precision tolerance comparison (with float epsilon guard against representation noise)
    variance_passes = raw_variance <= (tolerance + FLOAT_EPSILON)

    # Display / Stored rounded metrics
    calculated_delta = round(raw_delta, 2)
    claimed_pct = round(claim.claimed_percentage, 2)
    display_variance = round(raw_variance, 2)

    # Discrepancy reasoning
    if variance_passes:
        primary_status = RuleStatus.PASS
        discrepancy_reason = (
            f"VERIFIED: The claimed {claimed_pct}% reduction matches the ground truth CSV data "
            f"exactly ({b_year}: {baseline_val:,.2f} -> {t_year}: {target_val:,.2f}, actual reduction: {calculated_delta:.2f}%)."
        )
    else:
        primary_status = RuleStatus.FLAGGED
        discrepancy_reason = (
            f"MATHEMATICAL DISCREPANCY DETECTED: PR narrative claims a {claimed_pct:.2f}% reduction, "
            f"but pure Python audit of metrics.csv calculates only a {calculated_delta:.2f}% reduction "
            f"({b_year}: {baseline_val:,.2f} -> {t_year}: {target_val:,.2f}). Variance: {display_variance:.2f}%."
        )

    # Primary YoY Rule Result
    primary_rule_result = RuleResult(
        rule_id="EM-02",
        domain="Emissions",
        rule_name="YoY Percentage Delta Verification",
        status=primary_status,
        actual_value=calculated_delta,
        expected_value=claimed_pct,
        variance=display_variance,
        tolerance=tolerance,
        message=discrepancy_reason,
        evidence=RuleEvidence(
            metric_id=str(metric_id) if metric_id else None,
            metric_name=str(metric_name),
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=baseline_val,
            target_value=target_val,
            raw_formula=f"(({baseline_val} - {target_val}) / {baseline_val}) * 100.0",
            additional_context={
                "unrounded_delta": raw_delta,
                "unrounded_variance": raw_variance,
                "tolerance": tolerance
            }
        )
    )

    all_rule_results: List[RuleResult] = [primary_rule_result]

    # 7. Evaluate any additional registered domain rules in RuleRegistry
    RuleRegistry.auto_discover()
    context = RuleEvaluationContext(
        claim=claim,
        metrics_df=df,
        resolved_metric_row=matched_row,
        canonical_baseline_year=b_year,
        canonical_target_year=t_year,
        baseline_col=baseline_col,
        target_col=target_col,
        baseline_value=baseline_val,
        target_value=target_val,
        tolerance=tolerance,
        all_metric_rows=df.to_dict(orient="records")
    )

    for rule in RuleRegistry.get_all_rules():
        # Avoid duplicate EM-02 execution if registered
        if rule.rule_id == "EM-02":
            continue
        try:
            if rule.is_applicable(context):
                res = rule.evaluate(context)
                all_rule_results.append(res)
            else:
                all_rule_results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        domain=rule.domain.value if hasattr(rule.domain, 'value') else str(rule.domain),
                        rule_name=rule.rule_name,
                        status=RuleStatus.NOT_APPLICABLE,
                        message=f"Rule not applicable to claim for metric '{claim.metric}'."
                    )
                )
        except Exception as e:
            all_rule_results.append(
                RuleResult(
                    rule_id=rule.rule_id,
                    domain=rule.domain.value if hasattr(rule.domain, 'value') else str(rule.domain),
                    rule_name=rule.rule_name,
                    status=RuleStatus.ERROR,
                    message=f"Internal rule execution error: {str(e)}"
                )
            )

    # 8. Consolidate and aggregate outputs
    return ResultAggregator.aggregate(
        claim=claim,
        rule_results=all_rule_results,
        matched_metric_name=str(metric_name),
        baseline_year=b_year,
        target_year=t_year,
        baseline_val=baseline_val,
        target_val=target_val,
        primary_claimed_pct=claimed_pct,
        primary_calculated_delta=calculated_delta,
        primary_variance=display_variance,
        primary_discrepancy_reason=discrepancy_reason
    )


def _create_error_result(
    claim: ExtractedClaim,
    reason: str,
    decision: AuditDecision,
    status: ExecutionStatus,
    b_year: str = "FY23",
    t_year: str = "FY24",
    matched_metric: Optional[str] = None,
    baseline_val: Optional[float] = None,
    target_val: Optional[float] = None
) -> AuditResult:
    """Helper to construct structured unverified / error AuditResult objects."""
    claimed_pct = round(claim.claimed_percentage, 2)
    return AuditResult(
        status="FLAGGED",  # Preserves legacy app.py display
        claimed_percentage=claimed_pct,
        calculated_delta=0.0,
        variance=claimed_pct,
        discrepancy_reason=reason,
        matched_metric=matched_metric,
        baseline_year=b_year,
        target_year=t_year,
        baseline_value=baseline_val,
        target_value=target_val,
        fy23_value=baseline_val,
        fy24_value=target_val,
        audit_decision=decision,
        execution_status=status,
        summary=RuleSummaryCounts(
            total_rules=1,
            missing_data=1 if status == ExecutionStatus.MISSING_DATA else 0,
            invalid_data=1 if status == ExecutionStatus.INVALID_DATA else 0,
            error=1 if status == ExecutionStatus.ERROR else 0
        ),
        rule_results=[
            RuleResult(
                rule_id="EM-02",
                domain="Emissions",
                rule_name="YoY Percentage Delta Verification",
                status=RuleStatus.MISSING_DATA if status == ExecutionStatus.MISSING_DATA else (
                    RuleStatus.INVALID_DATA if status == ExecutionStatus.INVALID_DATA else RuleStatus.ERROR
                ),
                message=reason
            )
        ]
    )


# Backward-compatible helper aliases for any existing tests
def _extract_year_value(row: dict, col_name: str, year_str_lower: str) -> Optional[float]:
    val, _ = extract_numeric_value(row, col_name)
    return val


def _find_matching_metric_row(df: pd.DataFrame, claim_metric: str) -> Optional[dict]:
    _, row, _, _ = resolve_metric(claim_metric, df)
    return row
