"""
ClaimGuard Deterministic Rules — Emissions Category

4 rules for validating emissions-related ESG claims:
- EMISSIONS_ABSOLUTE_V1: Absolute emissions change verification
- EMISSIONS_REDUCTION_PCT_V1: Percentage reduction verification (core rule)
- EMISSIONS_YOY_DIRECTION_V1: Year-over-year direction check
- EMISSIONS_SCOPE_CONSISTENCY_V1: Scope 1 + Scope 2 = Total cross-check
"""

import pandas as pd
from src.schemas import Claim, RuleResult, Severity, ValidationStatus
from src.rules import BaseRule, find_metric_row, find_row_by_keyword, get_period_value


class EmissionsAbsoluteRule(BaseRule):
    """
    Verify that the claimed absolute emissions change matches source data.

    Example: "Emissions dropped by 271.95 MT CO2e"
    → Calculate actual: target_val - baseline_val
    → Compare to claimed absolute change
    """

    rule_id = "EMISSIONS_ABSOLUTE_V1"
    rule_name = "Absolute Emissions Change"
    category = "emissions"
    severity = Severity.HIGH

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        # This rule checks absolute values, not percentages
        if claim.reported_unit == "percent":
            return self._unsupported(
                "Claim reports a percentage, not an absolute value. "
                "Skipping — use EMISSIONS_REDUCTION_PCT_V1 instead."
            )

        row = find_metric_row(source_data, claim.metric)
        if row is None:
            return self._unsupported(
                f"Could not find metric '{claim.metric}' in source data."
            )

        baseline_val = get_period_value(row, claim.previous_period)
        target_val = get_period_value(row, claim.current_period)

        if baseline_val is None or target_val is None:
            return self._unsupported(
                f"Missing period data for {claim.previous_period} "
                f"and/or {claim.current_period}."
            )

        actual_change = round(target_val - baseline_val, 2)
        reported = round(claim.reported_value, 2)

        formula = (
            f"{claim.current_period}_value - {claim.previous_period}_value "
            f"= {target_val:,.2f} - {baseline_val:,.2f} = {actual_change:,.2f}"
        )
        evidence = (
            f"{claim.previous_period}: {baseline_val:,.2f}, "
            f"{claim.current_period}: {target_val:,.2f}"
        )

        # Allow small tolerance for rounding
        if abs(actual_change - reported) <= 0.5:
            return self._pass(
                reported=reported,
                calculated=actual_change,
                formula=formula,
                explanation=(
                    f"Absolute change of {actual_change:,.2f} matches "
                    f"reported {reported:,.2f}."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=reported,
                calculated=actual_change,
                formula=formula,
                explanation=(
                    f"Reported absolute change {reported:,.2f} does not match "
                    f"calculated {actual_change:,.2f}. "
                    f"Variance: {abs(reported - actual_change):,.2f}."
                ),
                evidence=evidence,
            )


class EmissionsReductionPctRule(BaseRule):
    """
    Verify that the claimed percentage reduction matches source data.

    This is the CORE rule of ClaimGuard.

    Example:
        Previous emissions = 100,000 MT CO2e
        Current emissions  = 80,000 MT CO2e
        Reported reduction = 35%

        Calculated: ((100,000 - 80,000) / 100,000) × 100 = 20%
        35% ≠ 20% → FAIL
    """

    rule_id = "EMISSIONS_REDUCTION_PCT_V1"
    rule_name = "Percentage Emissions Reduction"
    category = "emissions"
    severity = Severity.HIGH

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        if claim.reported_unit != "percent":
            return self._unsupported(
                "Claim does not report a percentage value."
            )

        row = find_metric_row(source_data, claim.metric)
        if row is None:
            return self._unsupported(
                f"Could not find metric '{claim.metric}' in source data."
            )

        baseline_val = get_period_value(row, claim.previous_period)
        target_val = get_period_value(row, claim.current_period)

        if baseline_val is None or target_val is None:
            return self._unsupported(
                f"Missing period data for {claim.previous_period} "
                f"and/or {claim.current_period}."
            )

        if baseline_val == 0:
            return self._unsupported(
                f"Baseline value ({claim.previous_period}) is 0. "
                f"Cannot compute percentage change."
            )

        # PURE PYTHON DETERMINISTIC MATH
        # Reduction % = ((Baseline - Target) / Baseline) × 100
        actual_pct = round(((baseline_val - target_val) / baseline_val) * 100, 2)
        reported = round(claim.reported_value, 2)
        variance = round(abs(reported - actual_pct), 2)

        formula = (
            f"(({claim.previous_period} - {claim.current_period}) / "
            f"{claim.previous_period}) × 100 = "
            f"(({baseline_val:,.2f} - {target_val:,.2f}) / "
            f"{baseline_val:,.2f}) × 100 = {actual_pct}%"
        )
        evidence = (
            f"{claim.previous_period}: {baseline_val:,.2f}, "
            f"{claim.current_period}: {target_val:,.2f}"
        )

        # Tolerance: 0.05 percentage points
        tolerance = 0.05
        if variance <= tolerance:
            return self._pass(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"VERIFIED: Claimed {reported}% reduction matches calculated "
                    f"{actual_pct}% ({claim.previous_period}: {baseline_val:,.2f} → "
                    f"{claim.current_period}: {target_val:,.2f})."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"DISCREPANCY: Claimed {reported}% reduction, but calculated "
                    f"{actual_pct}% ({claim.previous_period}: {baseline_val:,.2f} → "
                    f"{claim.current_period}: {target_val:,.2f}). "
                    f"Variance: {variance} percentage points."
                ),
                evidence=evidence,
            )


class EmissionsYoYDirectionRule(BaseRule):
    """
    Verify that the claimed direction (increase/decrease) matches actual data.

    If a company claims emissions "decreased" but data shows an increase → FAIL.
    """

    rule_id = "EMISSIONS_YOY_DIRECTION_V1"
    rule_name = "Year-over-Year Direction"
    category = "emissions"
    severity = Severity.HIGH

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        row = find_metric_row(source_data, claim.metric)
        if row is None:
            return self._unsupported(
                f"Could not find metric '{claim.metric}' in source data."
            )

        baseline_val = get_period_value(row, claim.previous_period)
        target_val = get_period_value(row, claim.current_period)

        if baseline_val is None or target_val is None:
            return self._unsupported(
                "Missing period data for direction check."
            )

        actual_decreased = target_val < baseline_val
        # A positive reported_value with unit "percent" means a claimed reduction
        claimed_decrease = claim.reported_value > 0

        formula = (
            f"Direction: {claim.current_period} ({target_val:,.2f}) vs "
            f"{claim.previous_period} ({baseline_val:,.2f})"
        )
        evidence = (
            f"{claim.previous_period}: {baseline_val:,.2f}, "
            f"{claim.current_period}: {target_val:,.2f}"
        )

        if claimed_decrease == actual_decreased:
            direction = "decrease" if actual_decreased else "increase"
            return self._pass(
                reported=claim.reported_value,
                calculated=claim.reported_value,
                formula=formula,
                explanation=(
                    f"Direction confirmed: data shows {direction} as claimed."
                ),
                evidence=evidence,
            )
        else:
            actual_dir = "decrease" if actual_decreased else "increase"
            claimed_dir = "decrease" if claimed_decrease else "increase"
            return self._fail(
                reported=claim.reported_value,
                calculated=-claim.reported_value,
                formula=formula,
                explanation=(
                    f"Direction mismatch: claim states {claimed_dir} but data "
                    f"shows {actual_dir} ({claim.previous_period}: "
                    f"{baseline_val:,.2f} → {claim.current_period}: "
                    f"{target_val:,.2f})."
                ),
                evidence=evidence,
            )


class EmissionsScopeConsistencyRule(BaseRule):
    """
    Verify that Scope 1 + Scope 2 = Total Scope 1 & 2 in source data.

    This is a cross-reference check on the source data itself,
    not on a specific claim value.
    """

    rule_id = "EMISSIONS_SCOPE_CONSISTENCY_V1"
    rule_name = "Scope 1 + 2 = Total Consistency"
    category = "emissions"
    severity = Severity.MEDIUM

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        scope1_row = find_row_by_keyword(
            df, ["scope 1", "scope1"],
            exclude_keywords=["total", "scope 1 &", "scope 1 and"]
        )
        scope2_row = find_row_by_keyword(
            df, ["scope 2", "scope2"],
            exclude_keywords=["total", "scope 1 &", "scope 1 and"]
        )
        total_row = find_row_by_keyword(
            df, ["total scope", "scope 1 & 2", "scope 1 and 2", "combined"]
        )

        if scope1_row is None or scope2_row is None or total_row is None:
            return self._unsupported(
                "Could not find Scope 1, Scope 2, and Total rows in source "
                "data for cross-check."
            )

        # Check the current period
        s1_val = get_period_value(scope1_row, claim.current_period)
        s2_val = get_period_value(scope2_row, claim.current_period)
        total_val = get_period_value(total_row, claim.current_period)

        if s1_val is None or s2_val is None or total_val is None:
            return self._unsupported(
                f"Missing Scope 1/2/Total values for {claim.current_period}."
            )

        calculated_total = round(s1_val + s2_val, 2)
        variance = round(abs(total_val - calculated_total), 2)

        formula = (
            f"Scope1 + Scope2 = {s1_val:,.2f} + {s2_val:,.2f} "
            f"= {calculated_total:,.2f}"
        )
        evidence = (
            f"Scope 1: {s1_val:,.2f}, Scope 2: {s2_val:,.2f}, "
            f"Reported Total: {total_val:,.2f}"
        )

        if variance <= 0.05:
            return self._pass(
                reported=total_val,
                calculated=calculated_total,
                formula=formula,
                explanation=(
                    f"Scope 1 ({s1_val:,.2f}) + Scope 2 ({s2_val:,.2f}) = "
                    f"{calculated_total:,.2f}, matches reported total "
                    f"{total_val:,.2f}."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=total_val,
                calculated=calculated_total,
                formula=formula,
                explanation=(
                    f"Scope 1 ({s1_val:,.2f}) + Scope 2 ({s2_val:,.2f}) = "
                    f"{calculated_total:,.2f}, but reported total is "
                    f"{total_val:,.2f}. Variance: {variance:,.2f}."
                ),
                evidence=evidence,
            )
