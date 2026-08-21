"""
ClaimGuard Deterministic Rules — Water Category

2 rules for validating water-related ESG claims:
- WATER_CONSUMPTION_CHANGE_V1: Water consumption YoY change verification
- WATER_RECYCLING_PCT_V1: Water recycling percentage verification
"""

import pandas as pd
from src.schemas import Claim, RuleResult, Severity
from src.rules import BaseRule, find_metric_row, find_row_by_keyword, get_period_value


class WaterConsumptionChangeRule(BaseRule):
    """
    Verify the claimed year-over-year water consumption change.

    Example:
        FY23 water = 15,200 kGal
        FY24 water = 14,900 kGal
        Claimed reduction = 5%

        Calculated: ((15200 - 14900) / 15200) × 100 = 1.97%
        5% ≠ 1.97% → FAIL
    """

    rule_id = "WATER_CONSUMPTION_CHANGE_V1"
    rule_name = "Water Consumption YoY Change"
    category = "water"
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
                "Baseline water value is 0; cannot compute percentage change."
            )

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

        if variance <= 0.1:
            return self._pass(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Water consumption change {actual_pct}% matches "
                    f"claimed {reported}%."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Claimed {reported}% water consumption change, but "
                    f"calculated {actual_pct}%. Variance: {variance} pp."
                ),
                evidence=evidence,
            )


class WaterRecyclingPctRule(BaseRule):
    """
    Verify that the claimed water recycling percentage matches source data.

    Example:
        Water recycled = 3,000 kGal
        Total water    = 15,000 kGal
        Claimed recycled % = 25%

        Calculated: (3,000 / 15,000) × 100 = 20%
        25% ≠ 20% → FAIL
    """

    rule_id = "WATER_RECYCLING_PCT_V1"
    rule_name = "Water Recycling Percentage"
    category = "water"
    severity = Severity.MEDIUM

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        if claim.reported_unit != "percent":
            return self._unsupported(
                "Claim does not report a percentage value."
            )

        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        recycled_row = find_row_by_keyword(
            df, ["recycl", "reuse", "reclaim"]
        )
        total_row = find_row_by_keyword(
            df, ["total water", "water consumption", "water usage",
                 "facility water"]
        )

        if recycled_row is None or total_row is None:
            return self._unsupported(
                "Could not find water recycled and total water rows "
                "in source data."
            )

        recycled_val = get_period_value(recycled_row, claim.current_period)
        total_val = get_period_value(total_row, claim.current_period)

        if recycled_val is None or total_val is None:
            return self._unsupported(
                f"Missing water values for {claim.current_period}."
            )

        if total_val == 0:
            return self._unsupported(
                "Total water is 0; cannot compute recycling percentage."
            )

        actual_pct = round((recycled_val / total_val) * 100, 2)
        reported = round(claim.reported_value, 2)
        variance = round(abs(actual_pct - reported), 2)

        formula = (
            f"(Recycled / Total) × 100 = "
            f"({recycled_val:,.2f} / {total_val:,.2f}) × 100 = {actual_pct}%"
        )
        evidence = (
            f"Recycled: {recycled_val:,.2f}, Total: {total_val:,.2f}"
        )

        if variance <= 0.5:
            return self._pass(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Water recycling {actual_pct}% matches claimed {reported}%."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Claimed {reported}% water recycling, calculated "
                    f"{actual_pct}%. Variance: {variance} pp."
                ),
                evidence=evidence,
            )
