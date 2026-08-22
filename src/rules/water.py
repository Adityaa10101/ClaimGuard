"""
Track 3: Water Validation Rules Domain Module
Rules:
- WT-01: Surface vs Groundwater Variance
- WT-02: Facility Water Recycling Rate
- WT-03: Consumption Intensity Boundary
"""
import logging
from typing import Optional, Dict, Any, List

from src.rules.base import BaseRule, RuleDomain, RuleEvaluationContext
from src.rules.registry import RuleRegistry
from src.schemas import RuleResult, RuleStatus, RuleEvidence
from src.rules.metric_resolver import normalize_metric_text

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _is_water_domain(context: RuleEvaluationContext) -> bool:
    """Check if the claim's resolved metric row belongs to the Water category."""
    if context.resolved_metric_row is None:
        return False
    category = str(context.resolved_metric_row.get("category", "")).strip().lower()
    return category == "water"


def _find_row_by_metric_name(rows: List[Dict[str, Any]], target_name: str) -> Optional[Dict[str, Any]]:
    """Find a row in all_metric_rows by normalized metric_name match."""
    target_norm = normalize_metric_text(target_name)
    for row in rows:
        if normalize_metric_text(str(row.get("metric_name", ""))) == target_norm:
            return row
    return None


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, float) and str(value) == "nan":
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if cleaned == "" or cleaned.lower() in ("n/a", "na", "none", "null", "-"):
                return None
            return float(cleaned)
        return float(value)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────
# WT-01: Surface vs Groundwater Variance
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class WaterSourceVarianceRule(BaseRule):
    rule_id = "WT-01"
    domain = RuleDomain.WATER
    rule_name = "Surface vs Groundwater Variance"
    description = (
        "Verifies that Surface Water Withdrawal + Groundwater Withdrawal = "
        "Total Facility Water Withdrawal within allowed tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_water_domain(context) or not context.all_metric_rows:
            return False
        surface = _find_row_by_metric_name(context.all_metric_rows, "Surface Water Withdrawal")
        ground = _find_row_by_metric_name(context.all_metric_rows, "Groundwater Withdrawal")
        total = _find_row_by_metric_name(context.all_metric_rows, "Facility Water Withdrawal")
        return surface is not None and ground is not None and total is not None

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            surface_row = _find_row_by_metric_name(rows, "Surface Water Withdrawal")
            ground_row = _find_row_by_metric_name(rows, "Groundwater Withdrawal")
            total_row = _find_row_by_metric_name(rows, "Facility Water Withdrawal")

            if surface_row is None or ground_row is None or total_row is None:
                missing = []
                if surface_row is None:
                    missing.append("Surface Water Withdrawal")
                if ground_row is None:
                    missing.append("Groundwater Withdrawal")
                if total_row is None:
                    missing.append("Facility Water Withdrawal")
                return self._missing(
                    f"Required metric rows not found in CSV: {', '.join(missing)}."
                )

            surface_val = _safe_float(surface_row.get(target_col))
            ground_val = _safe_float(ground_row.get(target_col))
            total_val = _safe_float(total_row.get(target_col))

            if surface_val is None or ground_val is None or total_val is None:
                return self._invalid(
                    f"Non-numeric or missing values in target year column '{target_col}' "
                    f"for Surface Water ({surface_row.get(target_col)}), "
                    f"Groundwater ({ground_row.get(target_col)}), "
                    f"or Total Withdrawal ({total_row.get(target_col)})."
                )

            calculated_total = surface_val + ground_val
            variance = abs(calculated_total - total_val)

            evidence = RuleEvidence(
                metric_name="Facility Water Withdrawal",
                baseline_year=context.canonical_baseline_year,
                target_year=context.canonical_target_year,
                raw_formula=f"Surface({surface_val}) + Groundwater({ground_val}) = {calculated_total} vs Reported Total({total_val})",
                additional_context={
                    "surface_water_value": surface_val,
                    "groundwater_value": ground_val,
                    "calculated_total": calculated_total,
                    "reported_total": total_val,
                    "variance": round(variance, 4),
                    "target_col": target_col,
                }
            )

            if variance <= context.tolerance:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.PASS,
                    actual_value=round(calculated_total, 2),
                    expected_value=round(total_val, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"VERIFIED: Surface Water ({surface_val:,.2f}) + Groundwater ({ground_val:,.2f}) "
                        f"= {calculated_total:,.2f}, matching reported Total Withdrawal ({total_val:,.2f}). "
                        f"Variance: {variance:.4f} kGal (within tolerance {context.tolerance})."
                    ),
                    evidence=evidence,
                )
            else:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.FLAGGED,
                    actual_value=round(calculated_total, 2),
                    expected_value=round(total_val, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"WATER SOURCE MISMATCH: Surface Water ({surface_val:,.2f}) + Groundwater ({ground_val:,.2f}) "
                        f"= {calculated_total:,.2f}, but reported Total Withdrawal is {total_val:,.2f}. "
                        f"Variance: {variance:.4f} kGal (exceeds tolerance {context.tolerance})."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"WT-01 internal error: {e}")
            return RuleResult(
                rule_id=self.rule_id, domain=self.domain.value,
                rule_name=self.rule_name, status=RuleStatus.ERROR,
                message=f"Internal rule execution error: {str(e)}"
            )

    def _missing(self, msg: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.MISSING_DATA,
            message=msg
        )

    def _invalid(self, msg: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.INVALID_DATA,
            message=msg
        )


# ─────────────────────────────────────────────────────────────────────
# WT-02: Facility Water Recycling Rate
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class WaterRecyclingRateRule(BaseRule):
    rule_id = "WT-02"
    domain = RuleDomain.WATER
    rule_name = "Facility Water Recycling Rate"
    description = (
        "Calculates recycling rate = (Recycled Water Volume / Facility Water Usage) × 100 "
        "and verifies against the reported recycling rate within tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_water_domain(context) or not context.all_metric_rows or not context.target_col:
            return False
        usage_row = _find_row_by_metric_name(context.all_metric_rows, "Facility Water Usage")
        recycled_row = _find_row_by_metric_name(context.all_metric_rows, "Recycled Water Volume")
        if usage_row is None or recycled_row is None:
            return False
        # Check that recycling rate column exists
        year_suffix = context.target_col.replace("_value", "")
        rate_col = f"recycling_rate_{year_suffix}"
        return rate_col in usage_row

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            usage_row = _find_row_by_metric_name(rows, "Facility Water Usage")
            recycled_row = _find_row_by_metric_name(rows, "Recycled Water Volume")

            if usage_row is None:
                return self._missing("Facility Water Usage row not found in CSV.")
            if recycled_row is None:
                return self._missing("Recycled Water Volume row not found in CSV.")

            year_suffix = target_col.replace("_value", "")
            rate_col = f"recycling_rate_{year_suffix}"

            recycled_val = _safe_float(recycled_row.get(target_col))
            usage_val = _safe_float(usage_row.get(target_col))
            reported_rate = _safe_float(usage_row.get(rate_col))  # For context/evidence only

            if recycled_val is None or usage_val is None:
                return self._invalid(
                    f"Non-numeric water values: recycled={recycled_row.get(target_col)}, "
                    f"usage={usage_row.get(target_col)}."
                )

            claimed_rate = getattr(context.claim, "claimed_recycling_rate", None)
            if claimed_rate is None:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.NOT_APPLICABLE,
                    message="No qualitative claimed_recycling_rate provided in ExtractedClaim. Skipping rule."
                )

            # Zero denominator guard
            if usage_val == 0.0:
                return self._invalid(
                    f"Facility Water Usage is 0 in {target_col}. "
                    f"Cannot compute recycling rate (division by zero)."
                )

            calculated_rate = (recycled_val / usage_val) * 100.0
            variance = abs(calculated_rate - claimed_rate)

            evidence = RuleEvidence(
                metric_name="Facility Water Usage",
                target_year=context.canonical_target_year,
                raw_formula=f"({recycled_val} / {usage_val}) × 100 = {calculated_rate:.2f}% vs Claimed({claimed_rate:.2f}%)",
                additional_context={
                    "recycled_water_volume": recycled_val,
                    "facility_water_usage": usage_val,
                    "calculated_rate_pct": round(calculated_rate, 2),
                    "claimed_rate_pct": claimed_rate,
                    "reported_rate_csv": reported_rate,
                    "variance": round(variance, 4),
                }
            )

            if variance <= context.tolerance:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.PASS,
                    actual_value=round(calculated_rate, 2),
                    expected_value=round(claimed_rate, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"VERIFIED: Recycling rate ({recycled_val:,.2f} / {usage_val:,.2f}) × 100 "
                        f"= {calculated_rate:.2f}%, matching claimed rate ({claimed_rate:.2f}%). "
                        f"Variance: {variance:.4f}%."
                    ),
                    evidence=evidence,
                )
            else:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.FLAGGED,
                    actual_value=round(calculated_rate, 2),
                    expected_value=round(claimed_rate, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"RECYCLING RATE DISCREPANCY: Calculated rate ({recycled_val:,.2f} / {usage_val:,.2f}) × 100 "
                        f"= {calculated_rate:.2f}%, but claimed rate is {claimed_rate:.2f}%. "
                        f"Variance: {variance:.4f}% (exceeds tolerance {context.tolerance})."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"WT-02 internal error: {e}")
            return RuleResult(
                rule_id=self.rule_id, domain=self.domain.value,
                rule_name=self.rule_name, status=RuleStatus.ERROR,
                message=f"Internal rule execution error: {str(e)}"
            )

    def _missing(self, msg: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.MISSING_DATA,
            message=msg
        )

    def _invalid(self, msg: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.INVALID_DATA,
            message=msg
        )


# ─────────────────────────────────────────────────────────────────────
# WT-03: Consumption Intensity Boundary
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class WaterIntensityRule(BaseRule):
    rule_id = "WT-03"
    domain = RuleDomain.WATER
    rule_name = "Consumption Intensity Boundary"
    description = (
        "Calculates water consumption intensity = Facility Water Usage / Revenue "
        "and verifies against the reported intensity value within tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_water_domain(context) or not context.all_metric_rows or not context.target_col:
            return False
        usage_row = _find_row_by_metric_name(context.all_metric_rows, "Facility Water Usage")
        if usage_row is None:
            return False
        year_suffix = context.target_col.replace("_value", "")
        revenue_col = f"revenue_{year_suffix}"
        intensity_col = f"water_intensity_{year_suffix}"
        return revenue_col in usage_row and intensity_col in usage_row

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            usage_row = _find_row_by_metric_name(rows, "Facility Water Usage")
            if usage_row is None:
                return self._missing("Facility Water Usage row not found in CSV.")

            year_suffix = target_col.replace("_value", "")
            revenue_col = f"revenue_{year_suffix}"
            intensity_col = f"water_intensity_{year_suffix}"

            if revenue_col not in usage_row:
                return self._missing(
                    f"Revenue column '{revenue_col}' not found in CSV. "
                    f"Cannot compute water consumption intensity."
                )

            usage_val = _safe_float(usage_row.get(target_col))
            revenue_val = _safe_float(usage_row.get(revenue_col))
            reported_intensity = _safe_float(usage_row.get(intensity_col)) # For context only

            if usage_val is None:
                return self._invalid(
                    f"Non-numeric water usage value in column '{target_col}': "
                    f"'{usage_row.get(target_col)}'."
                )

            if revenue_val is None:
                return self._invalid(
                    f"Non-numeric or missing revenue value in column '{revenue_col}': "
                    f"'{usage_row.get(revenue_col)}'."
                )

            claimed_intensity = getattr(context.claim, "claimed_water_intensity", None)
            if claimed_intensity is None:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.NOT_APPLICABLE,
                    message="No qualitative claimed_water_intensity provided in ExtractedClaim. Skipping rule."
                )

            # Zero denominator guard
            if revenue_val == 0.0:
                return self._invalid(
                    f"Revenue is 0 in '{revenue_col}'. "
                    f"Cannot compute water intensity (division by zero)."
                )

            calculated_intensity = usage_val / revenue_val
            variance = abs(calculated_intensity - claimed_intensity)

            evidence = RuleEvidence(
                metric_name="Facility Water Usage",
                target_year=context.canonical_target_year,
                raw_formula=f"Usage({usage_val}) / Revenue({revenue_val}) = {calculated_intensity:.8f} vs Claimed({claimed_intensity})",
                additional_context={
                    "water_usage": usage_val,
                    "water_unit": str(usage_row.get("unit", "kGal")),
                    "revenue": revenue_val,
                    "calculated_intensity": round(calculated_intensity, 8),
                    "claimed_intensity": claimed_intensity,
                    "reported_intensity_csv": reported_intensity,
                    "variance": round(variance, 8),
                    "intensity_unit": f"{usage_row.get('unit', 'kGal')}/revenue_unit",
                }
            )

            if variance <= context.tolerance:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.PASS,
                    actual_value=round(calculated_intensity, 8),
                    expected_value=round(claimed_intensity, 8),
                    variance=round(variance, 8),
                    tolerance=context.tolerance,
                    message=(
                        f"VERIFIED: Water intensity ({usage_val:,.2f} / {revenue_val:,.2f}) "
                        f"= {calculated_intensity:.8f}, matching claimed intensity ({claimed_intensity}). "
                        f"Variance: {variance:.8f}."
                    ),
                    evidence=evidence,
                )
            else:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.FLAGGED,
                    actual_value=round(calculated_intensity, 8),
                    expected_value=round(claimed_intensity, 8),
                    variance=round(variance, 8),
                    tolerance=context.tolerance,
                    message=(
                        f"INTENSITY DISCREPANCY: Calculated intensity ({usage_val:,.2f} / {revenue_val:,.2f}) "
                        f"= {calculated_intensity:.8f}, but claimed intensity is {claimed_intensity}. "
                        f"Variance: {variance:.8f} (exceeds tolerance {context.tolerance})."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"WT-03 internal error: {e}")
            return RuleResult(
                rule_id=self.rule_id, domain=self.domain.value,
                rule_name=self.rule_name, status=RuleStatus.ERROR,
                message=f"Internal rule execution error: {str(e)}"
            )

    def _missing(self, msg: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.MISSING_DATA,
            message=msg
        )

    def _invalid(self, msg: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.INVALID_DATA,
            message=msg
        )
