"""
Track 2: Emissions Validation Rules Domain Module
Rules:
- EM-01: Scope 1 & 2 Subtotal Summation
- EM-02: YoY Percentage Delta Verification (stub — engine handles inline)
- EM-03: Base-Year Restatement Matching (specification gap — returns NOT_APPLICABLE)
- EM-04: Scope 3 Upstream/Downstream Consistency
- EM-05: Absolute Metric Ton Variance Check (specification gap — returns NOT_APPLICABLE)
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

def _is_emissions_domain(context: RuleEvaluationContext) -> bool:
    """Check if the claim's resolved metric row belongs to the Emissions category."""
    if context.resolved_metric_row is None:
        return False
    category = str(context.resolved_metric_row.get("category", "")).strip().lower()
    return category == "emissions"


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
# EM-01: Scope 1 & 2 Subtotal Summation
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EmissionsSubtotalRule(BaseRule):
    rule_id = "EM-01"
    domain = RuleDomain.EMISSIONS
    rule_name = "Scope 1 & 2 Subtotal Summation"
    description = (
        "Verifies that Scope 1 Direct Emissions + Scope 2 Indirect Emissions = "
        "Total Scope 1 & 2 Emissions within allowed tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_emissions_domain(context) or not context.all_metric_rows:
            return False
        scope1 = _find_row_by_metric_name(context.all_metric_rows, "Scope 1 Direct Emissions")
        scope2 = _find_row_by_metric_name(context.all_metric_rows, "Scope 2 Indirect Emissions")
        total = _find_row_by_metric_name(context.all_metric_rows, "Total Scope 1 & 2 Emissions")
        return scope1 is not None and scope2 is not None and total is not None

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            scope1_row = _find_row_by_metric_name(rows, "Scope 1 Direct Emissions")
            scope2_row = _find_row_by_metric_name(rows, "Scope 2 Indirect Emissions")
            total_row = _find_row_by_metric_name(rows, "Total Scope 1 & 2 Emissions")

            if scope1_row is None or scope2_row is None or total_row is None:
                missing = []
                if scope1_row is None:
                    missing.append("Scope 1 Direct Emissions")
                if scope2_row is None:
                    missing.append("Scope 2 Indirect Emissions")
                if total_row is None:
                    missing.append("Total Scope 1 & 2 Emissions")
                return self._missing(
                    f"Required metric rows not found in CSV: {', '.join(missing)}."
                )

            scope1_val = _safe_float(scope1_row.get(target_col))
            scope2_val = _safe_float(scope2_row.get(target_col))
            total_val = _safe_float(total_row.get(target_col))

            if scope1_val is None or scope2_val is None or total_val is None:
                return self._invalid(
                    f"Non-numeric or missing values in target year column '{target_col}' "
                    f"for Scope 1 ({scope1_row.get(target_col)}), "
                    f"Scope 2 ({scope2_row.get(target_col)}), "
                    f"or Total ({total_row.get(target_col)})."
                )

            calculated_total = scope1_val + scope2_val
            variance = abs(calculated_total - total_val)

            evidence = RuleEvidence(
                metric_name="Total Scope 1 & 2 Emissions",
                baseline_year=context.canonical_baseline_year,
                target_year=context.canonical_target_year,
                raw_formula=f"Scope1({scope1_val}) + Scope2({scope2_val}) = {calculated_total} vs Reported Total({total_val})",
                additional_context={
                    "scope1_value": scope1_val,
                    "scope2_value": scope2_val,
                    "calculated_subtotal": calculated_total,
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
                        f"VERIFIED: Scope 1 ({scope1_val:,.2f}) + Scope 2 ({scope2_val:,.2f}) "
                        f"= {calculated_total:,.2f}, matching reported Total ({total_val:,.2f}). "
                        f"Variance: {variance:.4f} MT CO2e (within tolerance {context.tolerance})."
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
                        f"SUBTOTAL MISMATCH: Scope 1 ({scope1_val:,.2f}) + Scope 2 ({scope2_val:,.2f}) "
                        f"= {calculated_total:,.2f}, but reported Total is {total_val:,.2f}. "
                        f"Variance: {variance:.4f} MT CO2e (exceeds tolerance {context.tolerance})."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"EM-01 internal error: {e}")
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
# EM-02: YoY Percentage Delta Verification (Stub)
# The engine already computes EM-02 inline and skips registered EM-02.
# We register it so the registry contains the rule_id for discovery.
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EmissionsYoYDeltaRule(BaseRule):
    rule_id = "EM-02"
    domain = RuleDomain.EMISSIONS
    rule_name = "YoY Percentage Delta Verification"
    description = (
        "Verifies that ((Baseline - Target) / Baseline) × 100 matches "
        "the claimed percentage within tolerance. Handled inline by rules_engine.py."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        return _is_emissions_domain(context)

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            domain=self.domain.value,
            rule_name=self.rule_name,
            status=RuleStatus.NOT_APPLICABLE,
            message="EM-02 is evaluated inline by the core engine. This registered stub is intentionally skipped."
        )


# ─────────────────────────────────────────────────────────────────────
# EM-03: Base-Year Restatement Matching
# Specification Gap: Legitimate restatements intentionally change baseline
# numbers. Until an explicit restatement specification and claim representation
# exist, this rule safely returns NOT_APPLICABLE.
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EmissionsBaseYearRestatementRule(BaseRule):
    rule_id = "EM-03"
    domain = RuleDomain.EMISSIONS
    rule_name = "Base-Year Restatement Matching"
    description = (
        "Verifies base-year restatement disclosures. Requires an explicit "
        "restatement claim and accounting specification."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        # Until an explicit restatement specification and claim representation exist,
        # no valid restatement verification context exists.
        return False

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            domain=self.domain.value,
            rule_name=self.rule_name,
            status=RuleStatus.NOT_APPLICABLE,
            message=(
                "SPECIFICATION GAP: Base-year restatement verification requires an explicit "
                "specification and claim representation for restatement triggers/accounting. "
                "Rule remains safely non-evaluating."
            )
        )


# ─────────────────────────────────────────────────────────────────────
# EM-04: Scope 3 Upstream / Downstream Consistency
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EmissionsScope3ConsistencyRule(BaseRule):
    rule_id = "EM-04"
    domain = RuleDomain.EMISSIONS
    rule_name = "Scope 3 Upstream/Downstream Consistency"
    description = (
        "Verifies that Scope 3 Upstream + Downstream = Scope 3 Total "
        "within tolerance."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        if not _is_emissions_domain(context) or not context.all_metric_rows or not context.target_col:
            return False
        scope3_row = _find_row_by_metric_name(context.all_metric_rows, "Scope 3 Value Chain Emissions")
        if scope3_row is None:
            return False
        year_suffix = context.target_col.replace("_value", "")
        upstream_col = f"scope3_upstream_{year_suffix}"
        return upstream_col in scope3_row

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            rows = context.all_metric_rows or []
            target_col = context.target_col

            if not target_col:
                return self._missing("No target year column resolved.")

            scope3_row = _find_row_by_metric_name(rows, "Scope 3 Value Chain Emissions")
            if scope3_row is None:
                return self._missing("Scope 3 Value Chain Emissions row not found in CSV.")

            year_suffix = target_col.replace("_value", "")
            upstream_col = f"scope3_upstream_{year_suffix}"
            downstream_col = f"scope3_downstream_{year_suffix}"
            total_col = f"scope3_total_{year_suffix}"

            if upstream_col not in scope3_row or downstream_col not in scope3_row or total_col not in scope3_row:
                return self._missing(
                    f"Scope 3 disaggregation columns not found: "
                    f"requires '{upstream_col}', '{downstream_col}', '{total_col}'."
                )

            upstream_val = _safe_float(scope3_row.get(upstream_col))
            downstream_val = _safe_float(scope3_row.get(downstream_col))
            total_val = _safe_float(scope3_row.get(total_col))

            if upstream_val is None or downstream_val is None or total_val is None:
                return self._invalid(
                    f"Non-numeric Scope 3 values: upstream={scope3_row.get(upstream_col)}, "
                    f"downstream={scope3_row.get(downstream_col)}, total={scope3_row.get(total_col)}."
                )

            calculated_total = upstream_val + downstream_val
            variance = abs(calculated_total - total_val)

            evidence = RuleEvidence(
                metric_name="Scope 3 Value Chain Emissions",
                target_year=context.canonical_target_year,
                raw_formula=f"Upstream({upstream_val}) + Downstream({downstream_val}) = {calculated_total} vs Total({total_val})",
                additional_context={
                    "scope3_upstream": upstream_val,
                    "scope3_downstream": downstream_val,
                    "calculated_total": calculated_total,
                    "reported_total": total_val,
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
                        f"VERIFIED: Scope 3 Upstream ({upstream_val:,.2f}) + Downstream ({downstream_val:,.2f}) "
                        f"= {calculated_total:,.2f}, matching reported Total ({total_val:,.2f})."
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
                        f"SCOPE 3 INCONSISTENCY: Upstream ({upstream_val:,.2f}) + Downstream ({downstream_val:,.2f}) "
                        f"= {calculated_total:,.2f}, but reported Total is {total_val:,.2f}. "
                        f"Variance: {variance:.4f}."
                    ),
                    evidence=evidence,
                )

        except Exception as e:
            logger.exception(f"EM-04 internal error: {e}")
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
# EM-05: Absolute Metric-Ton Variance Check
# Specification Gap: ExtractedClaim only carries percentage reductions.
# Until the schema supports an absolute claimed quantity, this rule
# safely returns NOT_APPLICABLE rather than fabricating a claim from CSV.
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class EmissionsAbsoluteVarianceRule(BaseRule):
    rule_id = "EM-05"
    domain = RuleDomain.EMISSIONS
    rule_name = "Absolute Metric-Ton Variance Check"
    description = (
        "Verifies declared absolute target quantities against CSV ground truth. "
        "Requires extracted absolute claim representation in schema."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        # ExtractedClaim currently only supports percentage claims (claimed_percentage).
        # Until schema supports claimed_absolute_value, this rule is NOT_APPLICABLE.
        return False

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            domain=self.domain.value,
            rule_name=self.rule_name,
            status=RuleStatus.NOT_APPLICABLE,
            message=(
                "SPECIFICATION GAP: Absolute metric-ton target verification requires an "
                "extracted absolute quantity claim (claimed_absolute_value). ExtractedClaim "
                "currently only supports claimed_percentage. Rule remains safely non-evaluating."
            )
        )
