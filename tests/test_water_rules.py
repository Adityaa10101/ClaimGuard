"""
Track 3 Test Suite: Water Rules (WT-01 → WT-03)
Covers: PASS, FLAGGED, MISSING_DATA, INVALID_DATA, NOT_APPLICABLE per rule.
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

# Ensure water rules are imported/registered
import src.rules.water  # noqa: F401
RuleRegistry.auto_discover()

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
    claimed_recycling_rate=None,
    claimed_water_intensity=None,
):
    """Helper to construct a RuleEvaluationContext for unit tests."""
    if claim is None:
        claim = ExtractedClaim(
            metric="Facility Water Usage",
            claimed_percentage=1.97,
            baseline_year="FY23",
            target_year="FY24",
            claimed_recycling_rate=claimed_recycling_rate,
            claimed_water_intensity=claimed_water_intensity,
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


def _get_water_fixture_df():
    return pd.read_csv(os.path.join(FIXTURES_DIR, "water_full.csv"))


# ═══════════════════════════════════════════════════════════════
# WT-01: Surface vs Groundwater Variance
# ═══════════════════════════════════════════════════════════════

def test_wt01_pass():
    """Surface (10500) + Groundwater (7000) = Total Withdrawal (17500) → PASS"""
    df = _get_water_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    water_row = next(r for r in rows if r.get("metric_id") == "MTR-WT01")
    ctx = _make_context(df=df, resolved_row=water_row, all_rows=rows)
    rule = RuleRegistry.get_rule("WT-01")
    assert rule.is_applicable(ctx), "WT-01 should be applicable when all three water rows exist"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    assert result.actual_value == 17500.0
    assert result.expected_value == 17500.0
    print("[PASS] WT-01: Surface + Groundwater = Total → PASS")


def test_wt01_flagged():
    """Tampered total: Surface + Groundwater != manipulated Total → FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT02", "category": "Water", "metric_name": "Facility Water Withdrawal",
         "unit": "kGal", "fy23_value": 18000, "fy24_value": 20000},  # Tampered total
        {"metric_id": "MTR-WT04", "category": "Water", "metric_name": "Surface Water Withdrawal",
         "unit": "kGal", "fy23_value": 11000, "fy24_value": 10500},
        {"metric_id": "MTR-WT05", "category": "Water", "metric_name": "Groundwater Withdrawal",
         "unit": "kGal", "fy23_value": 7000, "fy24_value": 7000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("WT-01")
    result = rule.evaluate(ctx)
    # 10500 + 7000 = 17500 != 20000
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    assert result.variance > 0.05
    print("[PASS] WT-01: Tampered total → FLAGGED")


def test_wt01_missing_surface_row():
    """Missing Surface Water row → NOT_APPLICABLE (is_applicable returns False)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT02", "category": "Water", "metric_name": "Facility Water Withdrawal",
         "unit": "kGal", "fy23_value": 18000, "fy24_value": 17500},
        {"metric_id": "MTR-WT05", "category": "Water", "metric_name": "Groundwater Withdrawal",
         "unit": "kGal", "fy23_value": 7000, "fy24_value": 7000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("WT-01")
    assert not rule.is_applicable(ctx), "WT-01 should NOT be applicable when Surface Water row is missing"
    # Direct evaluate should return MISSING_DATA
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] WT-01: Missing Surface Water → MISSING_DATA")


def test_wt01_invalid_data():
    """Non-numeric values → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT02", "category": "Water", "metric_name": "Facility Water Withdrawal",
         "unit": "kGal", "fy23_value": 18000, "fy24_value": 17500},
        {"metric_id": "MTR-WT04", "category": "Water", "metric_name": "Surface Water Withdrawal",
         "unit": "kGal", "fy23_value": 11000, "fy24_value": "N/A"},
        {"metric_id": "MTR-WT05", "category": "Water", "metric_name": "Groundwater Withdrawal",
         "unit": "kGal", "fy23_value": 7000, "fy24_value": 7000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("WT-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] WT-01: Non-numeric values → INVALID_DATA")


def test_wt01_not_applicable_emissions():
    """Emissions domain claim → NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Scope 1 Direct Emissions", claimed_percentage=2.38, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("WT-01")
    assert not rule.is_applicable(ctx), "WT-01 should NOT be applicable to Emissions domain"
    print("[PASS] WT-01: Emissions claim → NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# WT-02: Facility Water Recycling Rate
# ═══════════════════════════════════════════════════════════════

def test_wt02_pass():
    """Recycled (3200) / Usage (14900) × 100 ≈ 21.48% matches claimed → PASS"""
    df = _get_water_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    usage_row = next(r for r in rows if r.get("metric_id") == "MTR-WT01")
    ctx = _make_context(df=df, resolved_row=usage_row, all_rows=rows, claimed_recycling_rate=21.48)
    rule = RuleRegistry.get_rule("WT-02")
    assert rule.is_applicable(ctx), "WT-02 should be applicable when recycling rate column exists"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    assert abs(result.variance) <= ctx.tolerance
    print("[PASS] WT-02: Recycling rate matches claimed → PASS")


def test_wt02_flagged():
    """Claimed rate differs from calculated rate → FLAGGED"""
    df = _get_water_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    usage_row = next(r for r in rows if r.get("metric_id") == "MTR-WT01")
    # Claiming 25.00% but actual is 21.48%
    ctx = _make_context(df=df, resolved_row=usage_row, all_rows=rows, claimed_recycling_rate=25.0)
    rule = RuleRegistry.get_rule("WT-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    print("[PASS] WT-02: Wrong claimed rate → FLAGGED")


def test_wt02_missing_recycled_row():
    """Missing recycled row → MISSING_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900, "recycling_rate_fy24": 21.48},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows, claimed_recycling_rate=21.48)
    rule = RuleRegistry.get_rule("WT-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] WT-02: Missing recycled row → MISSING_DATA")


def test_wt02_zero_denominator():
    """Zero water usage → INVALID_DATA (division by zero guard)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 0,  # Zero
         "recycling_rate_fy24": 21.48},
        {"metric_id": "MTR-WT03", "category": "Water", "metric_name": "Recycled Water Volume",
         "unit": "kGal", "fy23_value": 2800, "fy24_value": 3200},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows, claimed_recycling_rate=10.0)
    rule = RuleRegistry.get_rule("WT-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    assert "division by zero" in result.message.lower()
    print("[PASS] WT-02: Zero denominator → INVALID_DATA")


def test_wt02_not_applicable_emissions():
    """Emissions claim → NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Scope 1 Direct Emissions", claimed_percentage=2.38, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("WT-02")
    assert not rule.is_applicable(ctx), "WT-02 should NOT be applicable to Emissions domain"
    print("[PASS] WT-02: Emissions claim → NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# WT-03: Consumption Intensity Boundary
# ═══════════════════════════════════════════════════════════════

def test_wt03_pass():
    """Usage (14900) / Revenue (50000000) = 0.000298 matches reported → PASS"""
    df = _get_water_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    usage_row = next(r for r in rows if r.get("metric_id") == "MTR-WT01")
    ctx = _make_context(df=df, resolved_row=usage_row, all_rows=rows, claimed_water_intensity=0.000298)
    rule = RuleRegistry.get_rule("WT-03")
    assert rule.is_applicable(ctx), "WT-03 should be applicable when revenue and intensity columns exist"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] WT-03: Water intensity matches → PASS")


def test_wt03_flagged():
    """Reported intensity differs from calculated → FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900,
         "revenue_fy24": 50000000, "water_intensity_fy24": 1.0},  # Wrong: actual is ~0.000298
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows, claimed_water_intensity=1.0)
    rule = RuleRegistry.get_rule("WT-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    print("[PASS] WT-03: Wrong reported intensity → FLAGGED")


def test_wt03_zero_revenue():
    """Zero revenue → INVALID_DATA (division by zero)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900,
         "revenue_fy24": 0, "water_intensity_fy24": 0.000298},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows, claimed_water_intensity=0.000298)
    rule = RuleRegistry.get_rule("WT-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    assert "division by zero" in result.message.lower()
    print("[PASS] WT-03: Zero revenue → INVALID_DATA")


def test_wt03_missing_revenue_col():
    """Missing revenue column → NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("WT-03")
    assert not rule.is_applicable(ctx), "WT-03 should NOT be applicable when revenue column is missing"
    print("[PASS] WT-03: Missing revenue → NOT_APPLICABLE")


def test_wt03_not_applicable_emissions():
    """Emissions claim → NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Scope 1 Direct Emissions", claimed_percentage=2.38, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("WT-03")
    assert not rule.is_applicable(ctx), "WT-03 should NOT be applicable to Emissions domain"
    print("[PASS] WT-03: Emissions claim → NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════

def test_wt01_nan_values():
    """NaN values in water data → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT02", "category": "Water", "metric_name": "Facility Water Withdrawal",
         "unit": "kGal", "fy23_value": 18000, "fy24_value": 17500},
        {"metric_id": "MTR-WT04", "category": "Water", "metric_name": "Surface Water Withdrawal",
         "unit": "kGal", "fy23_value": 11000, "fy24_value": float("nan")},
        {"metric_id": "MTR-WT05", "category": "Water", "metric_name": "Groundwater Withdrawal",
         "unit": "kGal", "fy23_value": 7000, "fy24_value": 7000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("WT-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] WT-01 Edge: NaN values → INVALID_DATA")


def test_wt02_nan_recycled():
    """NaN recycled value → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900,
         "recycling_rate_fy24": 21.48},
        {"metric_id": "MTR-WT03", "category": "Water", "metric_name": "Recycled Water Volume",
         "unit": "kGal", "fy23_value": 2800, "fy24_value": float("nan")},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows, claimed_recycling_rate=21.48)
    rule = RuleRegistry.get_rule("WT-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] WT-02 Edge: NaN recycled value → INVALID_DATA")


def test_wt03_non_numeric_revenue():
    """Non-numeric revenue → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900,
         "revenue_fy24": "not_a_number", "water_intensity_fy24": 0.000298},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows, claimed_water_intensity=0.000298)
    rule = RuleRegistry.get_rule("WT-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] WT-03 Edge: Non-numeric revenue → INVALID_DATA")


# ═══════════════════════════════════════════════════════════════
# REGISTRY VERIFICATION
# ═══════════════════════════════════════════════════════════════

def test_registry_contains_all_water():
    """All 3 water rules must be registered."""
    for rule_id in ["WT-01", "WT-02", "WT-03"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert rule is not None, f"{rule_id} not found in registry"
        assert rule.domain == RuleDomain.WATER, f"{rule_id} has wrong domain: {rule.domain}"
    print("[PASS] Registry: All 3 water rules registered")


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    print("==================================================")
    print("RUNNING TRACK 3 WATER TEST SUITE")
    print("==================================================")

    # WT-01
    test_wt01_pass()
    test_wt01_flagged()
    test_wt01_missing_surface_row()
    test_wt01_invalid_data()
    test_wt01_not_applicable_emissions()

    # WT-02
    test_wt02_pass()
    test_wt02_flagged()
    test_wt02_missing_recycled_row()
    test_wt02_zero_denominator()
    test_wt02_not_applicable_emissions()

    # WT-03
    test_wt03_pass()
    test_wt03_flagged()
    test_wt03_zero_revenue()
    test_wt03_missing_revenue_col()
    test_wt03_not_applicable_emissions()

    # Edge cases
    test_wt01_nan_values()
    test_wt02_nan_recycled()
    test_wt03_non_numeric_revenue()

    # Registry
    test_registry_contains_all_water()

    print("==================================================")
    print("ALL TRACK 3 WATER TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
