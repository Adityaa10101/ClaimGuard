"""
ClaimGuard Deterministic Rules — Energy Category

3 rules for validating energy-related ESG claims:
- ENERGY_RENEWABLE_PCT_V1: Renewable energy percentage verification
- ENERGY_TOTAL_CHANGE_V1: Total energy YoY change verification
- ENERGY_RENEWABLE_CROSSCHECK_V1: Renewable ≤ Total energy check
"""

import pandas as pd
from src.schemas import Claim, RuleResult, Severity
from src.rules import BaseRule, find_row_by_keyword, get_period_value


class EnergyRenewablePctRule(BaseRule):
    """
    Verify that the claimed renewable energy percentage matches source data.

    Example:
        Renewable energy = 45,000 MWh
        Total energy     = 120,000 MWh
        Claimed renewable % = 50%

        Calculated: (45,000 / 120,000) × 100 = 37.5%
        50% ≠ 37.5% → FAIL
    """

    rule_id = "ENERGY_RENEWABLE_PCT_V1"
    rule_name = "Renewable Energy Percentage"
    category = "energy"
    severity = Severity.HIGH

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        if claim.reported_unit != "percent":
            return self._unsupported(
                "Claim does not report a percentage value."
            )

        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        renewable_row = find_row_by_keyword(
            df, ["renewable"], exclude_keywords=["non-renewable", "nonrenewable"]
        )
        total_row = find_row_by_keyword(
            df, ["total energy", "total consumption", "total electricity"]
        )

        if renewable_row is None or total_row is None:
            return self._unsupported(
                "Could not find renewable and total energy rows in source data."
            )

        renewable_val = get_period_value(renewable_row, claim.current_period)
        total_val = get_period_value(total_row, claim.current_period)

        if renewable_val is None or total_val is None:
            return self._unsupported(
                f"Missing energy values for {claim.current_period}."
            )

        if total_val == 0:
            return self._unsupported("Total energy is 0; cannot compute percentage.")

        actual_pct = round((renewable_val / total_val) * 100, 2)
        reported = round(claim.reported_value, 2)
        variance = round(abs(actual_pct - reported), 2)

        formula = (
            f"(Renewable / Total) × 100 = "
            f"({renewable_val:,.2f} / {total_val:,.2f}) × 100 = {actual_pct}%"
        )
        evidence = (
            f"Renewable: {renewable_val:,.2f}, Total: {total_val:,.2f}"
        )

        if variance <= 0.5:
            return self._pass(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Renewable energy {actual_pct}% matches claimed {reported}%."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Claimed {reported}% renewable energy, calculated "
                    f"{actual_pct}%. Variance: {variance} percentage points."
                ),
                evidence=evidence,
            )


class EnergyTotalChangeRule(BaseRule):
    """
    Verify the claimed year-over-year total energy change.

    Uses the same percentage reduction formula as emissions.
    """

    rule_id = "ENERGY_TOTAL_CHANGE_V1"
    rule_name = "Total Energy YoY Change"
    category = "energy"
    severity = Severity.MEDIUM

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        if claim.reported_unit != "percent":
            return self._unsupported(
                "Claim does not report a percentage value."
            )

        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        # Find the total energy row, or match by metric name
        row = find_row_by_keyword(
            df, ["total energy", "total consumption", "total electricity"]
        )
        if row is None:
            # Try matching by claim metric name
            from src.rules import find_metric_row
            row = find_metric_row(source_data, claim.metric)

        if row is None:
            return self._unsupported(
                f"Could not find energy metric '{claim.metric}' in source data."
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
                "Baseline energy value is 0; cannot compute percentage change."
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
                    f"Energy change {actual_pct}% matches claimed {reported}%."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=reported,
                calculated=actual_pct,
                formula=formula,
                explanation=(
                    f"Claimed {reported}% energy change, but calculated "
                    f"{actual_pct}%. Variance: {variance} pp."
                ),
                evidence=evidence,
            )


class EnergyRenewableCrosscheckRule(BaseRule):
    """
    Verify that renewable energy ≤ total energy.

    If renewable exceeds total, the data is internally inconsistent.
    """

    rule_id = "ENERGY_RENEWABLE_CROSSCHECK_V1"
    rule_name = "Renewable ≤ Total Energy"
    category = "energy"
    severity = Severity.MEDIUM

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        renewable_row = find_row_by_keyword(
            df, ["renewable"], exclude_keywords=["non-renewable", "nonrenewable"]
        )
        total_row = find_row_by_keyword(
            df, ["total energy", "total consumption", "total electricity"]
        )

        if renewable_row is None or total_row is None:
            return self._unsupported(
                "Could not find renewable and total energy rows for cross-check."
            )

        renewable_val = get_period_value(renewable_row, claim.current_period)
        total_val = get_period_value(total_row, claim.current_period)

        if renewable_val is None or total_val is None:
            return self._unsupported(
                f"Missing energy values for {claim.current_period}."
            )

        formula = (
            f"Renewable ({renewable_val:,.2f}) ≤ Total ({total_val:,.2f})"
        )
        evidence = (
            f"Renewable: {renewable_val:,.2f}, Total: {total_val:,.2f}"
        )

        if renewable_val <= total_val:
            return self._pass(
                reported=renewable_val,
                calculated=total_val,
                formula=formula,
                explanation=(
                    f"Renewable energy ({renewable_val:,.2f}) does not exceed "
                    f"total energy ({total_val:,.2f}). Data is consistent."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=renewable_val,
                calculated=total_val,
                formula=formula,
                explanation=(
                    f"Renewable energy ({renewable_val:,.2f}) EXCEEDS total "
                    f"energy ({total_val:,.2f}). This is physically impossible "
                    f"— source data is internally inconsistent."
                ),
                evidence=evidence,
            )
