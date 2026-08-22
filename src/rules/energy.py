"""
Track 2: Energy Validation Rules Domain Module
Rules:
- EN-01: Renewable Mix Percentage Check
- EN-02: Grid Electricity & Fuel Totals (with unit compatibility validation)
- EN-03: Captive Generation Balance
- EN-04: Energy Intensity Per Revenue Ratio (specification gap — returns NOT_APPLICABLE)
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

def _is_energy_domain(context: RuleEvaluationContext) -> bool:
    """Check if the claim's resolved metric row belongs to the Energy category."""
    if context.resolved_metric_row is None:
        return False
    category = str(context.resolved_metric_row.get("category", "")).strip().lower()
    return category == "energy"


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
# EN-01: Renewable Mix Percentage Check
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EnergyRenewableMixRule(BaseRule):
    rule_id = "EN-01"
    domain = RuleDomain.ENERGY
    rule_name = "Renewable Mix Percentage Check"
    description = (
        "Verifies that the claimed renewable energy percentage matches "
        "the ground-truth CSV value within tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_energy_domain(context) or not context.all_metric_rows:
            return False
        # Applicable when the claim specifically targets renewable energy / mix
        claim_norm = normalize_metric_text(context.claim.metric)
        row_norm = normalize_metric_text(str(context.resolved_metric_row.get("metric_name", ""))) if context.resolved_metric_row else ""
        return "renewable" in claim_norm or "renewable" in row_norm

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            renewable_row = _find_row_by_metric_name(rows, "Renewable Energy Percentage")
            if renewable_row is None:
                return self._missing(
                    "Renewable Energy Percentage row not found in CSV."
                )

            actual_pct = _safe_float(renewable_row.get(target_col))
            if actual_pct is None:
                return self._invalid(
                    f"Non-numeric renewable energy percentage in column '{target_col}': "
                    f"'{renewable_row.get(target_col)}'."
                )

            claimed_pct = context.claim.claimed_percentage
            variance = abs(claimed_pct - actual_pct)

            evidence = RuleEvidence(
                metric_name="Renewable Energy Percentage",
                target_year=context.canonical_target_year,
                target_value=actual_pct,
                raw_formula=f"|Claimed({claimed_pct}%) - Actual({actual_pct}%)| = {variance}%",
                additional_context={
                    "claimed_percentage": claimed_pct,
                    "actual_percentage": actual_pct,
                    "variance": round(variance, 4),
                    "unit": str(renewable_row.get("unit", "%")),
                }
            )

            if variance <= context.tolerance:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.PASS,
                    actual_value=round(actual_pct, 2),
                    expected_value=round(claimed_pct, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"VERIFIED: Claimed renewable mix ({claimed_pct:.2f}%) matches "
                        f"CSV value ({actual_pct:.2f}%). Variance: {variance:.4f}%."
                    ),
                    evidence=evidence,
                )
            else:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.FLAGGED,
                    actual_value=round(actual_pct, 2),
                    expected_value=round(claimed_pct, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"RENEWABLE MIX DISCREPANCY: Claimed {claimed_pct:.2f}% but "
                        f"CSV shows {actual_pct:.2f}%. Variance: {variance:.4f}%."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"EN-01 internal error: {e}")
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
# EN-02: Grid Electricity & Fuel Totals
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EnergyGridFuelTotalsRule(BaseRule):
    rule_id = "EN-02"
    domain = RuleDomain.ENERGY
    rule_name = "Grid Electricity & Fuel Totals"
    description = (
        "Verifies that Grid Electricity + Fuel Energy = Total Energy Consumption "
        "within tolerance when units are compatible."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_energy_domain(context) or not context.all_metric_rows or not context.target_col:
            return False
        year_suffix = context.target_col.replace("_value", "")
        fuel_col = f"fuel_energy_{year_suffix}"
        return any(fuel_col in row for row in context.all_metric_rows)

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            grid_row = _find_row_by_metric_name(rows, "Purchased Grid Electricity")
            total_row = _find_row_by_metric_name(rows, "Total Energy Consumption")

            if grid_row is None:
                return self._missing("Purchased Grid Electricity row not found in CSV.")
            if total_row is None:
                return self._missing("Total Energy Consumption row not found in CSV.")

            year_suffix = target_col.replace("_value", "")
            fuel_col = f"fuel_energy_{year_suffix}"

            if fuel_col not in total_row:
                return self._missing(
                    f"Fuel energy column '{fuel_col}' not found in CSV. "
                    f"Cannot verify grid + fuel = total reconciliation."
                )

            # Unit compatibility check
            grid_unit = str(grid_row.get("unit", "")).strip().lower()
            total_unit = str(total_row.get("unit", "")).strip().lower()

            if grid_unit and total_unit and grid_unit != total_unit:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.INVALID_DATA,
                    message="Incompatible units; deterministic reconciliation requires compatible units.",
                    evidence=RuleEvidence(
                        metric_name="Total Energy Consumption",
                        target_year=context.canonical_target_year,
                        additional_context={
                            "grid_unit": grid_row.get("unit"),
                            "total_unit": total_row.get("unit"),
                            "reason": "Unit mismatch between component and total rows."
                        }
                    )
                )

            grid_val = _safe_float(grid_row.get(target_col))
            fuel_val = _safe_float(total_row.get(fuel_col))
            total_val = _safe_float(total_row.get(target_col))

            if grid_val is None:
                return self._invalid(f"Non-numeric grid electricity value: '{grid_row.get(target_col)}'.")
            if fuel_val is None:
                return self._invalid(f"Non-numeric fuel energy value: '{total_row.get(fuel_col)}'.")
            if total_val is None:
                return self._invalid(f"Non-numeric total energy value: '{total_row.get(target_col)}'.")

            calculated_total = grid_val + fuel_val
            variance = abs(calculated_total - total_val)

            evidence = RuleEvidence(
                metric_name="Total Energy Consumption",
                target_year=context.canonical_target_year,
                raw_formula=f"Grid({grid_val}) + Fuel({fuel_val}) = {calculated_total} vs Total({total_val})",
                additional_context={
                    "grid_electricity": grid_val,
                    "grid_unit": str(grid_row.get("unit", "")),
                    "fuel_energy": fuel_val,
                    "calculated_total": calculated_total,
                    "reported_total": total_val,
                    "total_unit": str(total_row.get("unit", "")),
                    "variance": round(variance, 4),
                }
            )

            if variance <= context.tolerance:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.PASS,
                    actual_value=round(calculated_total, 2),
                    expected_value=round(total_val, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"VERIFIED: Grid ({grid_val:,.2f}) + Fuel ({fuel_val:,.2f}) "
                        f"= {calculated_total:,.2f}, matching reported Total ({total_val:,.2f}). "
                        f"Variance: {variance:.4f}."
                    ),
                    evidence=evidence,
                )
            else:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.FLAGGED,
                    actual_value=round(calculated_total, 2),
                    expected_value=round(total_val, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"ENERGY TOTALS MISMATCH: Grid ({grid_val:,.2f}) + Fuel ({fuel_val:,.2f}) "
                        f"= {calculated_total:,.2f}, but reported Total is {total_val:,.2f}. "
                        f"Variance: {variance:.4f}."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"EN-02 internal error: {e}")
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
# EN-03: Captive Generation Balance
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EnergyCaptiveBalanceRule(BaseRule):
    rule_id = "EN-03"
    domain = RuleDomain.ENERGY
    rule_name = "Captive Generation Balance"
    description = (
        "Verifies that Captive Generation = Captive Consumed + Captive Exported "
        "within tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_energy_domain(context) or not context.all_metric_rows or not context.target_col:
            return False
        captive_row = _find_row_by_metric_name(context.all_metric_rows, "Renewable Energy Generation")
        if captive_row is None:
            return False
        year_suffix = context.target_col.replace("_value", "")
        gen_col = f"captive_generation_{year_suffix}"
        return gen_col in captive_row

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            captive_row = _find_row_by_metric_name(rows, "Renewable Energy Generation")
            if captive_row is None:
                return self._missing(
                    "Renewable Energy Generation (captive) row not found in CSV."
                )

            year_suffix = target_col.replace("_value", "")
            gen_col = f"captive_generation_{year_suffix}"
            consumed_col = f"captive_consumed_{year_suffix}"
            exported_col = f"captive_exported_{year_suffix}"

            missing_cols = []
            if gen_col not in captive_row:
                missing_cols.append(gen_col)
            if consumed_col not in captive_row:
                missing_cols.append(consumed_col)
            if exported_col not in captive_row:
                missing_cols.append(exported_col)

            if missing_cols:
                return self._missing(
                    f"Captive generation balance columns not found: {', '.join(missing_cols)}."
                )

            gen_val = _safe_float(captive_row.get(gen_col))
            consumed_val = _safe_float(captive_row.get(consumed_col))
            exported_val = _safe_float(captive_row.get(exported_col))

            if gen_val is None or consumed_val is None or exported_val is None:
                return self._invalid(
                    f"Non-numeric captive generation values: "
                    f"generation={captive_row.get(gen_col)}, "
                    f"consumed={captive_row.get(consumed_col)}, "
                    f"exported={captive_row.get(exported_col)}."
                )

            calculated_gen = consumed_val + exported_val
            variance = abs(gen_val - calculated_gen)

            evidence = RuleEvidence(
                metric_name="Renewable Energy Generation",
                target_year=context.canonical_target_year,
                raw_formula=f"Consumed({consumed_val}) + Exported({exported_val}) = {calculated_gen} vs Generation({gen_val})",
                additional_context={
                    "captive_generation": gen_val,
                    "captive_consumed": consumed_val,
                    "captive_exported": exported_val,
                    "calculated_total": calculated_gen,
                    "variance": round(variance, 4),
                }
            )

            if variance <= context.tolerance:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.PASS,
                    actual_value=round(calculated_gen, 2),
                    expected_value=round(gen_val, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"VERIFIED: Consumed ({consumed_val:,.2f}) + Exported ({exported_val:,.2f}) "
                        f"= {calculated_gen:,.2f}, matching Generation ({gen_val:,.2f}). "
                        f"Variance: {variance:.4f}."
                    ),
                    evidence=evidence,
                )
            else:
                return RuleResult(
                    rule_id=self.rule_id, domain=self.domain.value,
                    rule_name=self.rule_name, status=RuleStatus.FLAGGED,
                    actual_value=round(calculated_gen, 2),
                    expected_value=round(gen_val, 2),
                    variance=round(variance, 4),
                    tolerance=context.tolerance,
                    message=(
                        f"CAPTIVE BALANCE MISMATCH: Consumed ({consumed_val:,.2f}) + Exported ({exported_val:,.2f}) "
                        f"= {calculated_gen:,.2f}, but Generation is {gen_val:,.2f}. "
                        f"Variance: {variance:.4f}."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"EN-03 internal error: {e}")
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
# EN-04: Energy Intensity per Revenue Ratio
# Specification Gap: ExtractedClaim does not currently carry a claimed
# intensity value/ratio. Until the extraction schema supports claimed
# intensity, this rule returns NOT_APPLICABLE while preserving the
# calculated intensity in evidence where computable.
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EnergyIntensityRule(BaseRule):
    rule_id = "EN-04"
    domain = RuleDomain.ENERGY
    rule_name = "Energy Intensity per Revenue Ratio"
    description = (
        "Calculates energy intensity = energy_consumption / revenue and "
        "verifies against claimed intensity. Requires claimed intensity in schema."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        # ExtractedClaim does not currently support a claimed intensity value/ratio.
        # Until the extraction schema supports claimed intensity, this rule is NOT_APPLICABLE.
        return False

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            total_row = _find_row_by_metric_name(rows, "Total Energy Consumption") if rows else None
            evidence = None

            if total_row and target_col:
                year_suffix = target_col.replace("_value", "")
                revenue_col = f"revenue_{year_suffix}"
                energy_val = _safe_float(total_row.get(target_col))
                revenue_val = _safe_float(total_row.get(revenue_col)) if revenue_col in total_row else None
                if energy_val is not None and revenue_val is not None and revenue_val > 0:
                    intensity = energy_val / revenue_val
                    evidence = RuleEvidence(
                        metric_name="Total Energy Consumption",
                        target_year=context.canonical_target_year,
                        raw_formula=f"Energy({energy_val}) / Revenue({revenue_val}) = {intensity}",
                        additional_context={
                            "energy_consumption": energy_val,
                            "energy_unit": str(total_row.get("unit", "GJ")),
                            "revenue": revenue_val,
                            "calculated_intensity": round(intensity, 8),
                            "intensity_unit": f"{total_row.get('unit', 'GJ')}/revenue_unit",
                        }
                    )

            return RuleResult(
                rule_id=self.rule_id,
                domain=self.domain.value,
                rule_name=self.rule_name,
                status=RuleStatus.NOT_APPLICABLE,
                actual_value=evidence.additional_context.get("calculated_intensity") if evidence else None,
                expected_value=None,
                variance=None,
                tolerance=context.tolerance,
                message=(
                    "SPECIFICATION GAP: Energy intensity verification requires an extracted "
                    "claimed intensity ratio. ExtractedClaim currently only supports percentage "
                    "reductions. Informational intensity calculation preserved in evidence where computable."
                ),
                evidence=evidence
            )
        except Exception as e:
            logger.exception(f"EN-04 internal error: {e}")
            return RuleResult(
                rule_id=self.rule_id, domain=self.domain.value,
                rule_name=self.rule_name, status=RuleStatus.ERROR,
                message=f"Internal rule execution error: {str(e)}"
            )
