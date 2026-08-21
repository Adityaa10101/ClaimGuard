"""
ClaimGuard Deterministic Rules — General Category

6 cross-cutting rules that apply to ALL claim categories:
- UNIT_CONSISTENCY_V1: Claimed unit matches source data unit
- YEAR_CONSISTENCY_V1: Claimed periods exist in source data
- PCT_BOUNDS_V1: Percentage values within reasonable bounds
- TOTAL_SUBTOTAL_V1: Sum of sub-items equals reported total
- CROSS_TABLE_CONSISTENCY_V1: Same metric has same value across rows
- MISSING_EVIDENCE_V1: Claim has no supporting numerical data (heuristic)
"""

import pandas as pd
from src.schemas import Claim, RuleResult, Severity, Authority
from src.rules import (
    BaseRule, find_metric_row, find_row_by_keyword,
    get_period_value, get_unit_for_row,
)


class UnitConsistencyRule(BaseRule):
    """
    Verify that the claimed unit matches the source data unit.

    Example: Claim says "MT CO2e" but source data says "kg CO2e" → FAIL
    """

    rule_id = "UNIT_CONSISTENCY_V1"
    rule_name = "Unit Consistency"
    category = "general"
    severity = Severity.MEDIUM

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        row = find_metric_row(source_data, claim.metric)
        if row is None:
            return self._unsupported(
                f"Could not find metric '{claim.metric}' in source data."
            )

        source_unit = get_unit_for_row(row)
        if source_unit is None:
            return self._unsupported(
                "No unit column found in source data."
            )

        claimed_unit = claim.reported_unit.strip().lower()
        source_unit_lower = source_unit.lower()

        # "percent" doesn't need to match the source unit column —
        # percentage claims compare against the underlying metric unit
        if claimed_unit == "percent":
            return self._pass(
                reported=0,
                calculated=0,
                formula="Percentage claim — unit comparison not applicable",
                explanation=(
                    f"Claim reports a percentage. Source metric unit is "
                    f"'{source_unit}', which is the base unit for the "
                    f"percentage calculation."
                ),
                evidence=f"Source unit: {source_unit}",
            )

        # Normalize common unit variations
        unit_aliases = {
            "mt co2e": ["mt co2e", "metric tons co2e", "tco2e", "tonnes co2e"],
            "kwh": ["kwh", "kilowatt-hours", "kilowatt hours"],
            "mwh": ["mwh", "megawatt-hours", "megawatt hours"],
            "kgal": ["kgal", "thousand gallons", "1000 gallons"],
            "tons": ["tons", "tonnes", "metric tons"],
        }

        def normalize(unit: str) -> str:
            u = unit.strip().lower()
            for canonical, aliases in unit_aliases.items():
                if u in aliases:
                    return canonical
            return u

        norm_claimed = normalize(claimed_unit)
        norm_source = normalize(source_unit_lower)

        formula = f"Unit check: claimed '{claim.reported_unit}' vs source '{source_unit}'"
        evidence = f"Source unit: {source_unit}, Claimed unit: {claim.reported_unit}"

        if norm_claimed == norm_source:
            return self._pass(
                reported=0,
                calculated=0,
                formula=formula,
                explanation=(
                    f"Units match: '{claim.reported_unit}' ≡ '{source_unit}'."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=0,
                calculated=0,
                formula=formula,
                explanation=(
                    f"Unit mismatch: claim uses '{claim.reported_unit}' but "
                    f"source data uses '{source_unit}'. Values may not be "
                    f"directly comparable."
                ),
                evidence=evidence,
            )


class YearConsistencyRule(BaseRule):
    """
    Verify that the claimed periods exist as columns in source data.

    If a claim references FY25 but the CSV only has FY23 and FY24 → FAIL.
    """

    rule_id = "YEAR_CONSISTENCY_V1"
    rule_name = "Year/Period Consistency"
    category = "general"
    severity = Severity.MEDIUM

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        prev_lower = claim.previous_period.strip().lower()
        curr_lower = claim.current_period.strip().lower()

        # Check if columns containing these periods exist
        prev_found = any(prev_lower in col for col in df.columns)
        curr_found = any(curr_lower in col for col in df.columns)

        formula = (
            f"Period check: '{claim.previous_period}' and "
            f"'{claim.current_period}' in columns {list(df.columns)}"
        )
        evidence = f"CSV columns: {', '.join(df.columns)}"

        missing = []
        if not prev_found:
            missing.append(claim.previous_period)
        if not curr_found:
            missing.append(claim.current_period)

        if not missing:
            return self._pass(
                reported=0,
                calculated=0,
                formula=formula,
                explanation=(
                    f"Both periods ({claim.previous_period}, "
                    f"{claim.current_period}) found in source data."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=0,
                calculated=0,
                formula=formula,
                explanation=(
                    f"Period(s) {', '.join(missing)} not found in source data "
                    f"columns. Available columns: {', '.join(df.columns)}."
                ),
                evidence=evidence,
            )


class PctBoundsRule(BaseRule):
    """
    Verify that percentage values are within physically reasonable bounds.

    A claimed reduction > 100% is physically impossible.
    A claimed reduction exactly 0% may be suspicious.
    """

    rule_id = "PCT_BOUNDS_V1"
    rule_name = "Percentage Bounds Check"
    category = "general"
    severity = Severity.LOW

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        if claim.reported_unit != "percent":
            return self._unsupported(
                "Claim does not report a percentage — bounds check skipped."
            )

        reported = claim.reported_value
        formula = f"Bounds check: 0 ≤ {reported} ≤ 100"

        if reported < 0:
            return self._fail(
                reported=reported,
                calculated=0,
                formula=formula,
                explanation=(
                    f"Reported percentage {reported}% is negative. "
                    f"This may indicate a data entry error or an increase "
                    f"being reported as a reduction."
                ),
            )
        elif reported > 100:
            return self._fail(
                reported=reported,
                calculated=100,
                formula=formula,
                explanation=(
                    f"Reported percentage {reported}% exceeds 100%. "
                    f"A reduction greater than 100% is physically impossible."
                ),
            )
        else:
            return self._pass(
                reported=reported,
                calculated=reported,
                formula=formula,
                explanation=(
                    f"Percentage {reported}% is within valid bounds (0–100%)."
                ),
            )


class TotalSubtotalRule(BaseRule):
    """
    Verify that the sum of sub-items equals the reported total.

    Looks for rows that have a 'Total' variant and checks if the
    sum of non-total rows in the same category equals the total row.
    """

    rule_id = "TOTAL_SUBTOTAL_V1"
    rule_name = "Total/Subtotal Consistency"
    category = "general"
    severity = Severity.HIGH

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        if "category" not in df.columns or "metric_name" not in df.columns:
            return self._unsupported(
                "Source data missing 'category' or 'metric_name' columns."
            )

        # Find the category of the claim's metric
        claim_row = find_metric_row(source_data, claim.metric)
        if claim_row is None:
            return self._unsupported(
                f"Could not find metric '{claim.metric}' in source data."
            )

        row_category = str(claim_row.get("category", "")).strip().lower()
        if not row_category:
            return self._unsupported("No category found for this metric.")

        # Get all rows in the same category
        cat_rows = df[df["category"].astype(str).str.strip().str.lower() == row_category]
        if len(cat_rows) < 2:
            return self._unsupported(
                f"Only {len(cat_rows)} row(s) in category '{row_category}'. "
                f"Need at least a total and one subtotal."
            )

        # Separate total row from subtotal rows
        total_mask = cat_rows["metric_name"].astype(str).str.contains(
            "Total", case=False, na=False
        )
        # Also check metric_id for 'TOTAL'
        if "metric_id" in cat_rows.columns:
            total_mask = total_mask | cat_rows["metric_id"].astype(str).str.contains(
                "TOTAL", case=False, na=False
            )

        total_rows = cat_rows[total_mask]
        subtotal_rows = cat_rows[~total_mask]

        if total_rows.empty or subtotal_rows.empty:
            return self._unsupported(
                f"Could not separate total/subtotal rows in '{row_category}'."
            )

        total_row = total_rows.iloc[0].to_dict()
        total_val = get_period_value(total_row, claim.current_period)

        if total_val is None:
            return self._unsupported(
                f"Missing total value for {claim.current_period}."
            )

        # Sum subtotal rows
        subtotal_sum = 0.0
        subtotal_details = []
        for _, sub_row in subtotal_rows.iterrows():
            sub_dict = sub_row.to_dict()
            val = get_period_value(sub_dict, claim.current_period)
            if val is not None:
                subtotal_sum += val
                name = sub_dict.get("metric_name", "Unknown")
                subtotal_details.append(f"{name}: {val:,.2f}")

        subtotal_sum = round(subtotal_sum, 2)
        variance = round(abs(total_val - subtotal_sum), 2)

        formula = f"Sum of subtotals = {' + '.join(str(v.split(': ')[1]) for v in subtotal_details)} = {subtotal_sum:,.2f}"
        evidence = f"Subtotals: {'; '.join(subtotal_details)}. Reported total: {total_val:,.2f}"

        if variance <= 0.05:
            return self._pass(
                reported=total_val,
                calculated=subtotal_sum,
                formula=formula,
                explanation=(
                    f"Sum of subtotals ({subtotal_sum:,.2f}) matches reported "
                    f"total ({total_val:,.2f})."
                ),
                evidence=evidence,
            )
        else:
            return self._fail(
                reported=total_val,
                calculated=subtotal_sum,
                formula=formula,
                explanation=(
                    f"Sum of subtotals ({subtotal_sum:,.2f}) does not match "
                    f"reported total ({total_val:,.2f}). "
                    f"Variance: {variance:,.2f}."
                ),
                evidence=evidence,
            )


class CrossTableConsistencyRule(BaseRule):
    """
    Check if the same metric appears multiple times with different values.

    If 'Total Emissions' appears in two rows with different FY24 values,
    the source data is internally inconsistent.
    """

    rule_id = "CROSS_TABLE_CONSISTENCY_V1"
    rule_name = "Cross-Table Consistency"
    category = "general"
    severity = Severity.HIGH

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        df = source_data.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        if "metric_name" not in df.columns:
            return self._unsupported("No 'metric_name' column in source data.")

        # Find all rows matching the claim metric
        claim_lower = claim.metric.strip().lower()
        matching = df[
            df["metric_name"].astype(str).str.strip().str.lower() == claim_lower
        ]

        if len(matching) <= 1:
            return self._pass(
                reported=0,
                calculated=0,
                formula=f"Uniqueness check for '{claim.metric}'",
                explanation=(
                    f"Metric '{claim.metric}' appears {len(matching)} time(s) "
                    f"in source data. No duplicate conflict."
                ),
            )

        # Multiple rows — check if values differ
        values = []
        for _, row in matching.iterrows():
            val = get_period_value(row.to_dict(), claim.current_period)
            if val is not None:
                values.append(val)

        if len(set(values)) <= 1:
            return self._pass(
                reported=0,
                calculated=0,
                formula=f"Cross-table check for '{claim.metric}'",
                explanation=(
                    f"Metric '{claim.metric}' appears {len(matching)} times "
                    f"but all values agree ({values[0] if values else 'N/A'})."
                ),
            )
        else:
            return self._fail(
                reported=values[0] if values else 0,
                calculated=values[1] if len(values) > 1 else 0,
                formula=f"Cross-table check: values = {values}",
                explanation=(
                    f"Metric '{claim.metric}' has conflicting values across "
                    f"rows: {values}. Source data is internally inconsistent."
                ),
            )


class MissingEvidenceRule(BaseRule):
    """
    Flag claims that have no supporting numerical evidence in source data.

    This is a HEURISTIC rule — it flags for human review but is
    not authoritative. The AI layer explicitly marks this as non-binding.
    """

    rule_id = "MISSING_EVIDENCE_V1"
    rule_name = "Missing Supporting Evidence"
    category = "general"
    severity = Severity.LOW
    authority = Authority.HEURISTIC

    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        row = find_metric_row(source_data, claim.metric)

        if row is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                claim_id=claim.claim_id,
                status="FAIL",
                severity=Severity.LOW,
                explanation=(
                    f"No supporting numerical data found for claim metric "
                    f"'{claim.metric}'. This claim cannot be verified against "
                    f"source data. Manual review recommended."
                ),
                authority=Authority.HEURISTIC,
            )

        baseline = get_period_value(row, claim.previous_period)
        current = get_period_value(row, claim.current_period)

        if baseline is None and current is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                claim_id=claim.claim_id,
                status="FAIL",
                severity=Severity.LOW,
                explanation=(
                    f"Metric '{claim.metric}' found but has no numerical "
                    f"values for periods {claim.previous_period} or "
                    f"{claim.current_period}. Cannot verify."
                ),
                source_evidence=f"Row found: {row.get('metric_name', 'N/A')}",
                authority=Authority.HEURISTIC,
            )

        return self._pass(
            reported=claim.reported_value,
            calculated=claim.reported_value,
            formula="Evidence presence check",
            explanation=(
                f"Supporting data found for '{claim.metric}' with values "
                f"in {claim.previous_period} and/or {claim.current_period}."
            ),
            evidence=(
                f"Baseline: {baseline}, Current: {current}"
            ),
        )
