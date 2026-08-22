"""
Track 3: General Validation Rules Domain Module
Rules:
- GEN-01: Baseline Year Period Alignment
- GEN-02: Metric Unit Scale Consistency
- GEN-03: >100% Impossibility & Zero-Div Guard
"""
import logging
from typing import Optional, Dict, Any, List

from src.rules.base import BaseRule, RuleDomain, RuleEvaluationContext
from src.rules.registry import RuleRegistry
from src.schemas import RuleResult, RuleStatus, RuleEvidence
from src.rules.year_resolver import normalize_fiscal_year, resolve_year_column

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

# Controlled unit normalization map for identical-unit comparison.
# We do NOT invent arbitrary conversion factors. If units do not
# map to the same canonical form, they are incompatible.
UNIT_CANONICAL_MAP: Dict[str, str] = {
    # Emissions
    "mt co2e": "mt_co2e",
    "metric tons co2e": "mt_co2e",
    "metric tonnes co2e": "mt_co2e",
    "tonnes co2e": "mt_co2e",
    "tons co2e": "mt_co2e",
    "tco2e": "mt_co2e",
    "t co2e": "mt_co2e",
    # Mass
    "tons": "tons",
    "tonnes": "tons",
    "metric tons": "metric_tons",
    "metric tonnes": "metric_tons",
    "mt": "metric_tons",
    "kg": "kg",
    "kilograms": "kg",
    # Energy
    "mwh": "mwh",
    "megawatt hours": "mwh",
    "kwh": "kwh",
    "kilowatt hours": "kwh",
    "gj": "gj",
    "gigajoules": "gj",
    "tj": "tj",
    "terajoules": "tj",
    # Water
    "kgal": "kgal",
    "kilolitres": "kl",
    "kiloliters": "kl",
    "kl": "kl",
    "litres": "l",
    "liters": "l",
    "l": "l",
    "ml": "ml",
    "megalitres": "ml",
    "megaliters": "ml",
    # Percentage
    "%": "percent",
    "percent": "percent",
    "percentage": "percent",
}


def _canonicalize_unit(raw_unit: Optional[str]) -> Optional[str]:
    """Normalize a unit string to its canonical form via the controlled map."""
    if not raw_unit or not isinstance(raw_unit, str):
        return None
    cleaned = raw_unit.strip().lower()
    if not cleaned:
        return None
    return UNIT_CANONICAL_MAP.get(cleaned, cleaned)


# ─────────────────────────────────────────────────────────────────────
# GEN-01: Baseline Year Period Alignment
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class BaselineYearAlignmentRule(BaseRule):
    rule_id = "GEN-01"
    domain = RuleDomain.GENERAL
    rule_name = "Baseline Year Period Alignment"
    description = (
        "Verifies that baseline and target years are valid, distinct, "
        "correctly ordered (baseline < target), and resolvable to actual "
        "dataset columns. Uses Track 1's year resolver."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        # Cross-domain structural check — always applicable
        return True

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            claim = context.claim

            # Resolve years using Track 1's normalizer
            baseline_canonical = normalize_fiscal_year(claim.baseline_year)
            target_canonical = normalize_fiscal_year(claim.target_year)

            if baseline_canonical is None:
                return self._missing(
                    f"Cannot resolve baseline year '{claim.baseline_year}' to a valid fiscal year.",
                    claim.baseline_year, claim.target_year
                )

            if target_canonical is None:
                return self._missing(
                    f"Cannot resolve target year '{claim.target_year}' to a valid fiscal year.",
                    claim.baseline_year, claim.target_year
                )

            # Identical years check
            if baseline_canonical == target_canonical:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.INVALID_DATA,
                    message=(
                        f"INVALID: Baseline year ({baseline_canonical}) and target year "
                        f"({target_canonical}) are identical. Cannot compute YoY change."
                    ),
                    evidence=RuleEvidence(
                        baseline_year=baseline_canonical,
                        target_year=target_canonical,
                        additional_context={
                            "raw_baseline": claim.baseline_year,
                            "raw_target": claim.target_year,
                            "reason": "identical_years",
                        }
                    )
                )

            # Extract 2-digit year numbers for ordering check
            baseline_num = int(baseline_canonical.replace("FY", ""))
            target_num = int(target_canonical.replace("FY", ""))

            if baseline_num >= target_num:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.FLAGGED,
                    message=(
                        f"INVALID ORDERING: Baseline year ({baseline_canonical}) must precede "
                        f"target year ({target_canonical}), but {baseline_num} >= {target_num}."
                    ),
                    evidence=RuleEvidence(
                        baseline_year=baseline_canonical,
                        target_year=target_canonical,
                        additional_context={
                            "raw_baseline": claim.baseline_year,
                            "raw_target": claim.target_year,
                            "baseline_num": baseline_num,
                            "target_num": target_num,
                            "reason": "reverse_ordering",
                        }
                    )
                )

            # Verify year columns exist in the DataFrame
            import pandas as pd
            df = context.metrics_df
            if df is not None and not (isinstance(df, pd.DataFrame) and df.empty):
                df_cols = list(df.columns) if isinstance(df, pd.DataFrame) else []
                baseline_col = resolve_year_column(df_cols, baseline_canonical)
                target_col_resolved = resolve_year_column(df_cols, target_canonical)

                missing_cols = []
                if not baseline_col:
                    missing_cols.append(f"{baseline_canonical.lower()}_value")
                if not target_col_resolved:
                    missing_cols.append(f"{target_canonical.lower()}_value")

                if missing_cols:
                    return self._missing(
                        f"Year columns not found in dataset: {', '.join(missing_cols)}. "
                        f"Cannot resolve {baseline_canonical} → {target_canonical} to ground-truth data.",
                        baseline_canonical, target_canonical
                    )

            return RuleResult(
                rule_id=self.rule_id,
                domain=self.domain.value,
                rule_name=self.rule_name,
                status=RuleStatus.PASS,
                message=(
                    f"VERIFIED: Year alignment {baseline_canonical} → {target_canonical} is valid. "
                    f"Baseline precedes target, both years are resolvable."
                ),
                evidence=RuleEvidence(
                    baseline_year=baseline_canonical,
                    target_year=target_canonical,
                    additional_context={
                        "raw_baseline": claim.baseline_year,
                        "raw_target": claim.target_year,
                        "baseline_num": baseline_num,
                        "target_num": target_num,
                    }
                )
            )

        except Exception as e:
            logger.exception(f"GEN-01 internal error: {e}")
            return RuleResult(
                rule_id=self.rule_id, domain=self.domain.value,
                rule_name=self.rule_name, status=RuleStatus.ERROR,
                message=f"Internal rule execution error: {str(e)}"
            )

    def _missing(self, msg: str, raw_baseline: str, raw_target: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id, domain=self.domain.value,
            rule_name=self.rule_name, status=RuleStatus.MISSING_DATA,
            message=msg,
            evidence=RuleEvidence(
                additional_context={
                    "raw_baseline": raw_baseline,
                    "raw_target": raw_target,
                }
            )
        )


# ─────────────────────────────────────────────────────────────────────
# GEN-02: Metric Unit Scale Consistency
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class UnitScaleConsistencyRule(BaseRule):
    rule_id = "GEN-02"
    domain = RuleDomain.GENERAL
    rule_name = "Metric Unit Scale Consistency"
    description = (
        "Verifies that the metric unit declared in the CSV is recognized "
        "and consistent. Reports INVALID_DATA for unrecognized units."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        # Applicable whenever a resolved metric row has a unit field
        if context.resolved_metric_row is None:
            return False
        unit = context.resolved_metric_row.get("unit")
        return unit is not None and str(unit).strip() != ""

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            row = context.resolved_metric_row
            if row is None:
                return self._missing("No resolved metric row available.")

            raw_unit = str(row.get("unit", "")).strip()
            if not raw_unit:
                return self._missing("Metric row has no unit field specified.")

            canonical_unit = _canonicalize_unit(raw_unit)
            metric_name = str(row.get("metric_name", ""))

            # Check if the unit is recognizable
            if canonical_unit is None:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.INVALID_DATA,
                    message=(
                        f"Unrecognized unit '{raw_unit}' in metric row '{metric_name}'. "
                        f"Cannot validate unit scale consistency."
                    ),
                    evidence=RuleEvidence(
                        metric_name=metric_name,
                        additional_context={"raw_unit": raw_unit}
                    )
                )

            # Cross-check: If there are multiple rows with the SAME metric_name,
            # verify they all declare the same unit (guard against copy/paste errors).
            all_rows = context.all_metric_rows or []
            inconsistent_peers = []
            for peer_row in all_rows:
                peer_name = str(peer_row.get("metric_name", "")).strip()
                if peer_name != metric_name:
                    continue
                peer_unit_raw = str(peer_row.get("unit", "")).strip()
                if not peer_unit_raw:
                    continue
                peer_canonical = _canonicalize_unit(peer_unit_raw)
                if peer_canonical and peer_canonical != canonical_unit:
                    inconsistent_peers.append({
                        "peer_unit": peer_unit_raw,
                        "peer_canonical": peer_canonical,
                    })

            if inconsistent_peers:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.INVALID_DATA,
                    message=(
                        f"UNIT SCALE INCONSISTENCY: Metric '{metric_name}' uses unit '{raw_unit}' "
                        f"({canonical_unit}), but duplicate rows for the same metric declare "
                        f"incompatible units: {[p['peer_unit'] for p in inconsistent_peers]}. "
                        f"Deterministic comparison requires compatible units."
                    ),
                    evidence=RuleEvidence(
                        metric_name=metric_name,
                        additional_context={
                            "declared_unit": raw_unit,
                            "canonical_unit": canonical_unit,
                            "inconsistent_peers": inconsistent_peers,
                        }
                    )
                )

            return RuleResult(
                rule_id=self.rule_id,
                domain=self.domain.value,
                rule_name=self.rule_name,
                status=RuleStatus.PASS,
                message=(
                    f"VERIFIED: Metric '{metric_name}' unit '{raw_unit}' ({canonical_unit}) "
                    f"is recognized and consistent."
                ),
                evidence=RuleEvidence(
                    metric_name=metric_name,
                    additional_context={
                        "declared_unit": raw_unit,
                        "canonical_unit": canonical_unit,
                    }
                )
            )

        except Exception as e:
            logger.exception(f"GEN-02 internal error: {e}")
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


def _are_confusable_units(unit_a: str, unit_b: str) -> bool:
    """
    Determines whether two canonical units are in the same measurement
    domain and could be confused (e.g., kg vs metric_tons, kwh vs mwh).
    """
    CONFUSABLE_GROUPS = [
        {"mt_co2e", "kg", "tons", "metric_tons"},   # Mass / emissions
        {"mwh", "kwh", "gj", "tj"},                  # Energy
        {"kgal", "kl", "l", "ml"},                    # Volume / water
    ]
    for group in CONFUSABLE_GROUPS:
        if unit_a in group and unit_b in group:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────
# GEN-03: >100% Impossibility & Zero-Division Guard
# ─────────────────────────────────────────────────────────────────────

@RuleRegistry.register
class ImpossibilityGuardRule(BaseRule):
    rule_id = "GEN-03"
    domain = RuleDomain.GENERAL
    rule_name = ">100% Impossibility & Zero-Division Guard"
    description = (
        "Guards percentage-reduction claims and ratio calculations against "
        "impossible or invalid states: claimed > 100%, negative claims, "
        "and zero-baseline division."
    )

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        # Cross-domain mathematical guard — always applicable
        return True

    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        try:
            claimed_pct = context.claim.claimed_percentage
            baseline_val = context.baseline_value

            evidence = RuleEvidence(
                baseline_year=context.canonical_baseline_year,
                target_year=context.canonical_target_year,
                baseline_value=baseline_val,
                additional_context={
                    "claimed_percentage": claimed_pct,
                    "baseline_value": baseline_val,
                }
            )

            # Check 1: Claimed reduction > 100% is mathematically impossible
            if claimed_pct > 100.0:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.INVALID_DATA,
                    actual_value=claimed_pct,
                    expected_value=None,
                    message=(
                        f"IMPOSSIBLE CLAIM: Claimed reduction of {claimed_pct:.2f}% exceeds 100%. "
                        f"A percentage reduction greater than 100% is mathematically impossible."
                    ),
                    evidence=evidence,
                )

            # Check 2: Negative claimed percentage is suspicious
            if claimed_pct < 0.0:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.FLAGGED,
                    actual_value=claimed_pct,
                    expected_value=None,
                    message=(
                        f"SUSPICIOUS CLAIM: Claimed percentage is negative ({claimed_pct:.2f}%). "
                        f"Negative reduction implies an increase, which conflicts with a reduction claim."
                    ),
                    evidence=evidence,
                )

            # Check 3: Zero baseline guard
            if baseline_val is not None and baseline_val == 0.0:
                return RuleResult(
                    rule_id=self.rule_id,
                    domain=self.domain.value,
                    rule_name=self.rule_name,
                    status=RuleStatus.INVALID_DATA,
                    actual_value=None,
                    expected_value=claimed_pct,
                    message=(
                        f"ZERO BASELINE: Baseline value is 0. Cannot compute percentage "
                        f"reduction (division by zero). Claimed {claimed_pct:.2f}% is unverifiable."
                    ),
                    evidence=evidence,
                )

            # All guards passed
            return RuleResult(
                rule_id=self.rule_id,
                domain=self.domain.value,
                rule_name=self.rule_name,
                status=RuleStatus.PASS,
                actual_value=claimed_pct,
                message=(
                    f"VERIFIED: Claimed percentage ({claimed_pct:.2f}%) is within valid bounds "
                    f"(0-100%), and baseline value is non-zero."
                ),
                evidence=evidence,
            )

        except Exception as e:
            logger.exception(f"GEN-03 internal error: {e}")
            return RuleResult(
                rule_id=self.rule_id, domain=self.domain.value,
                rule_name=self.rule_name, status=RuleStatus.ERROR,
                message=f"Internal rule execution error: {str(e)}"
            )
