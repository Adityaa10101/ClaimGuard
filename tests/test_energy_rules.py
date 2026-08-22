"""
Track 2 Test Suite: Energy Rules (EN-01 -> EN-04)
Covers: PASS, FLAGGED, MISSING_DATA, INVALID_DATA, NOT_APPLICABLE per rule,
including explicit tests for EN-01 applicability guards, EN-02 unit mismatch validation,
and EN-04 specification gap handling.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas as pd
from src.schemas import ExtractedClaim, RuleResult, RuleStatus, RuleEvidence
from src.rules.base import BaseRule, RuleDomain, RuleEvaluationContext
from src.rules.registry import RuleRegistry

# Ensure energy rules are imported/registered
import src.rules.energy  # noqa: F401

FIXTURES_DIR = os.path.join(REPO_ROOT, "data", "fixtures")


def _make_context(
    claim=None,
    df=None,
    resolved_row=None,
    baseline_col="fy23_value",
    target_col="fy24_value",
    baseline_val=None,
    target_val=None,
    all_rows=None,
    tolerance=0.05,
):
    """Helper to construct a RuleEvaluationContext for unit tests."""
    if claim is None:
        claim = ExtractedClaim(
            metric="Total Energy Consumption",
            claimed_percentage=4.0,
            baseline_year="FY23",
            target_year="FY24",
        )
    if df is None:
        df = pd.DataFrame()
    if all_rows is None and not df.empty:
        all_rows = df.to_dict(orient="records")
    return RuleEvaluationContext(
        claim=claim,
        metrics_df=df,
        resolved_metric_row=resolved_row,
        canonical_baseline_year="FY23",
        canonical_target_year="FY24",
        baseline_col=baseline_col,
        target_col=target_col,
        baseline_value=baseline_val,
        target_value=target_val,
        tolerance=tolerance,
        all_metric_rows=all_rows,
    )


def _get_energy_fixture_df():
    return pd.read_csv(os.path.join(FIXTURES_DIR, "energy_full.csv"))


# ═══════════════════════════════════════════════════════════════
# EN-01: Renewable Mix Percentage Check
# ═══════════════════════════════════════════════════════════════

def test_en01_pass_with_applicability():
    """A. Renewable claim: is_applicable == True, then evaluate() -> PASS"""
    df = _get_energy_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    en02_row = next(r for r in rows if r.get("metric_id") == "MTR-EN02")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Renewable Energy Percentage", claimed_percentage=42.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=en02_row, all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EN-01")

    # Explicitly test applicability
    assert rule.is_applicable(ctx), "EN-01 should be applicable for renewable claims"

    # Evaluate
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    assert result.actual_value == 42.0
    print("[PASS] EN-01: Renewable claim is_applicable == True -> PASS")


def test_en01_non_renewable_claim_not_applicable():
    """B. Non-renewable claim: is_applicable == False -> NOT_APPLICABLE"""
    df = _get_energy_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    en01_row = next(r for r in rows if r.get("metric_id") == "MTR-EN01")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Purchased Grid Electricity", claimed_percentage=4.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=en01_row, all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EN-01")

    # Explicitly test applicability
    assert not rule.is_applicable(ctx), "EN-01 should NOT be applicable for non-renewable claims"
    print("[PASS] EN-01: Non-renewable claim is_applicable == False")


def test_en01_flagged():
    """Claimed 60% vs CSV 42% -> FLAGGED"""
    df = _get_energy_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    en02_row = next(r for r in rows if r.get("metric_id") == "MTR-EN02")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Renewable Energy Percentage", claimed_percentage=60.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=en02_row, all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EN-01")
    assert rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    assert result.variance == 18.0
    print("[PASS] EN-01: Claimed 60% vs CSV 42% -> FLAGGED")


def test_en01_missing_row():
    """No Renewable Energy Percentage row -> MISSING_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "fy23_value": 50000, "fy24_value": 48000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Renewable Energy Percentage", claimed_percentage=42.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows
    )
    rule = RuleRegistry.get_rule("EN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EN-01: Missing renewable % row -> MISSING_DATA")


def test_en01_invalid_data():
    """Non-numeric renewable percentage -> INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "fy23_value": 50000, "fy24_value": 48000},
        {"metric_id": "MTR-EN02", "category": "Energy", "metric_name": "Renewable Energy Percentage",
         "fy23_value": 35.0, "fy24_value": "N/A"},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Renewable Energy Percentage", claimed_percentage=42.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[1], all_rows=rows
    )
    rule = RuleRegistry.get_rule("EN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] EN-01: Non-numeric renewable % -> INVALID_DATA")


def test_en01_not_applicable_emissions():
    """Emissions domain -> NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Scope 1 Direct Emissions", claimed_percentage=2.38, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EN-01")
    assert not rule.is_applicable(ctx), "EN-01 should NOT be applicable to Emissions domain"
    print("[PASS] EN-01: Emissions claim -> NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# EN-02: Grid Electricity & Fuel Totals
# ═══════════════════════════════════════════════════════════════

def test_en02_same_units_pass():
    """Same units (GJ): Grid (120,000) + Fuel (52,800) = Total (172,800) -> PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "unit": "GJ", "fy23_value": 50000, "fy24_value": 120000},
        {"metric_id": "MTR-EN03", "category": "Energy", "metric_name": "Total Energy Consumption",
         "unit": "GJ", "fy23_value": 180000, "fy24_value": 172800, "fuel_energy_fy24": 52800},
    ])
    rows = df.to_dict(orient="records")
    total_row = rows[1]
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EN-02")
    assert rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] EN-02: Same-unit grid + fuel = total -> PASS")


def test_en02_incompatible_units_invalid_data():
    """Incompatible units (MWh vs GJ) -> INVALID_DATA with explicit message"""
    df = _get_energy_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    total_row = next(r for r in rows if r.get("metric_id") == "MTR-EN03")
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EN-02")
    assert rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA for incompatible units, got {result.status}"
    assert "Incompatible units; deterministic reconciliation requires compatible units." in result.message
    print("[PASS] EN-02: Incompatible units -> INVALID_DATA")


def test_en02_reconciliation_mismatch_flagged():
    """Same units (GJ) but values do not sum to total -> FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "unit": "GJ", "fy23_value": 50000, "fy24_value": 100000},
        {"metric_id": "MTR-EN03", "category": "Energy", "metric_name": "Total Energy Consumption",
         "unit": "GJ", "fy23_value": 180000, "fy24_value": 172800, "fuel_energy_fy24": 52800},
    ])
    rows = df.to_dict(orient="records")
    total_row = rows[1]
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EN-02")
    result = rule.evaluate(ctx)
    # 100000 + 52800 = 152800 != 172800 -> FLAGGED
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED for mismatch, got {result.status}"
    print("[PASS] EN-02: Reconciliation mismatch -> FLAGGED")


def test_en02_missing_fuel_col():
    """No fuel_energy column -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "unit": "GJ", "fy23_value": 50000, "fy24_value": 48000},
        {"metric_id": "MTR-EN03", "category": "Energy", "metric_name": "Total Energy Consumption",
         "unit": "GJ", "fy23_value": 180000, "fy24_value": 172800},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[1], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-02")
    assert not rule.is_applicable(ctx), "EN-02 should not be applicable when fuel column is missing"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EN-02: Missing fuel column -> MISSING_DATA")


def test_en02_missing_grid_row():
    """No Grid Electricity row -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN03", "category": "Energy", "metric_name": "Total Energy Consumption",
         "unit": "GJ", "fy23_value": 180000, "fy24_value": 172800, "fuel_energy_fy24": 52800},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EN-02: Missing grid row -> MISSING_DATA")


# ═══════════════════════════════════════════════════════════════
# EN-03: Captive Generation Balance
# ═══════════════════════════════════════════════════════════════

def test_en03_pass():
    """Consumed (7500) + Exported (500) = Generation (8000) -> PASS"""
    df = _get_energy_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    en03_row = next(r for r in rows if r.get("metric_id") == "MTR-EN03")
    ctx = _make_context(df=df, resolved_row=en03_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EN-03")
    assert rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] EN-03: Captive balance -> PASS")


def test_en03_flagged():
    """Consumed + Exported != Generation -> FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN04", "category": "Energy", "metric_name": "Renewable Energy Generation",
         "fy23_value": None, "fy24_value": None,
         "captive_generation_fy24": 8000, "captive_consumed_fy24": 6000, "captive_exported_fy24": 500},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    print("[PASS] EN-03: Consumed + Exported != Generation -> FLAGGED")


def test_en03_missing_row():
    """No Renewable Energy Generation row -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "fy23_value": 50000, "fy24_value": 48000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-03")
    assert not rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EN-03: Missing captive row -> MISSING_DATA")


def test_en03_missing_columns():
    """Captive row exists but missing balance columns -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN04", "category": "Energy", "metric_name": "Renewable Energy Generation",
         "fy23_value": None, "fy24_value": None},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-03")
    assert not rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EN-03: Missing balance columns -> MISSING_DATA")


def test_en03_invalid_data():
    """Non-numeric captive values -> INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN04", "category": "Energy", "metric_name": "Renewable Energy Generation",
         "fy23_value": None, "fy24_value": None,
         "captive_generation_fy24": "bad", "captive_consumed_fy24": 7500, "captive_exported_fy24": 500},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] EN-03: Non-numeric captive values -> INVALID_DATA")


def test_en03_zero_generation():
    """Zero generation with zero consumed+exported -> PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN04", "category": "Energy", "metric_name": "Renewable Energy Generation",
         "fy23_value": None, "fy24_value": None,
         "captive_generation_fy24": 0, "captive_consumed_fy24": 0, "captive_exported_fy24": 0},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}"
    print("[PASS] EN-03: All zeros -> PASS")


# ═══════════════════════════════════════════════════════════════
# EN-04: Energy Intensity per Revenue Ratio (Specification Gap)
# ═══════════════════════════════════════════════════════════════

def test_en04_specification_gap_not_applicable():
    """EN-04 safely returns NOT_APPLICABLE because ExtractedClaim has no claimed intensity."""
    df = _get_energy_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    total_row = next(r for r in rows if r.get("metric_id") == "MTR-EN03")
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EN-04")

    # Applicability check
    assert not rule.is_applicable(ctx), "EN-04 should return is_applicable=False until schema supports claimed intensity"

    # Direct evaluate check: returns NOT_APPLICABLE with evidence preserved
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.NOT_APPLICABLE, f"Expected NOT_APPLICABLE, got {result.status}"
    assert "SPECIFICATION GAP" in result.message
    # Preserved evidence check
    assert result.evidence is not None
    assert result.evidence.additional_context.get("calculated_intensity") is not None
    print("[PASS] EN-04: Specification gap safely returns NOT_APPLICABLE with evidence preserved")


def test_en04_not_applicable_emissions():
    """Emissions domain -> NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Scope 1 Direct Emissions", claimed_percentage=2.38, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EN-04")
    assert not rule.is_applicable(ctx), "EN-04 should NOT be applicable to Emissions domain"
    print("[PASS] EN-04: Emissions claim -> NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# REGISTRY VERIFICATION
# ═══════════════════════════════════════════════════════════════

def test_registry_contains_all_energy():
    """All 4 energy rules must be registered."""
    for rule_id in ["EN-01", "EN-02", "EN-03", "EN-04"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert rule is not None, f"{rule_id} not found in registry"
        assert rule.domain == RuleDomain.ENERGY, f"{rule_id} has wrong domain: {rule.domain}"
    print("[PASS] Registry: All 4 energy rules registered")


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    print("==================================================")
    print("RUNNING TRACK 2 ENERGY TEST SUITE")
    print("==================================================")

    # EN-01 (Explicit Applicability & Evaluation Tests)
    test_en01_pass_with_applicability()
    test_en01_non_renewable_claim_not_applicable()
    test_en01_flagged()
    test_en01_missing_row()
    test_en01_invalid_data()
    test_en01_not_applicable_emissions()

    # EN-02 (Unit Compatibility & Reconciliation Tests)
    test_en02_same_units_pass()
    test_en02_incompatible_units_invalid_data()
    test_en02_reconciliation_mismatch_flagged()
    test_en02_missing_fuel_col()
    test_en02_missing_grid_row()

    # EN-03
    test_en03_pass()
    test_en03_flagged()
    test_en03_missing_row()
    test_en03_missing_columns()
    test_en03_invalid_data()
    test_en03_zero_generation()

    # EN-04 (Specification Gap)
    test_en04_specification_gap_not_applicable()
    test_en04_not_applicable_emissions()

    # Registry
    test_registry_contains_all_energy()

    print("==================================================")
    print("ALL TRACK 2 ENERGY TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
