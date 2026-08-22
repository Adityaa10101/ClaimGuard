"""
Track 3 Test Suite: General Rules (GEN-01 → GEN-03)
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

# Ensure general rules are imported/registered
import src.rules.general  # noqa: F401

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
            metric="Total Scope 1 & 2 Emissions",
            claimed_percentage=2.59,
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


# ═══════════════════════════════════════════════════════════════
# GEN-01: Baseline Year Period Alignment
# ═══════════════════════════════════════════════════════════════

def test_gen01_fy23_to_fy24_pass():
    """FY23 → FY24: Valid ordering → PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy23_value": 1000, "fy24_value": 900},
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
    )
    rule = RuleRegistry.get_rule("GEN-01")
    assert rule.is_applicable(ctx), "GEN-01 should always be applicable"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-01: FY23 → FY24 valid ordering → PASS")


def test_gen01_fy24_to_fy25_pass():
    """FY24 → FY25: Valid ordering → PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy24_value": 1000, "fy25_value": 900},
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=10.0, baseline_year="FY24", target_year="FY25"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
        baseline_col="fy24_value", target_col="fy25_value",
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-01: FY24 → FY25 valid ordering → PASS")


def test_gen01_four_digit_years_pass():
    """2023 → 2024: 4-digit year normalization → PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy23_value": 1000, "fy24_value": 900},
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=10.0, baseline_year="2023", target_year="2024"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-01: 2023 → 2024 (4-digit normalization) → PASS")


def test_gen01_fy2023_to_fy2024_pass():
    """FY2023 → FY2024: Full format normalization → PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy23_value": 1000, "fy24_value": 900},
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=10.0, baseline_year="FY2023", target_year="FY2024"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-01: FY2023 → FY2024 → PASS")


def test_gen01_identical_years_invalid():
    """FY24 → FY24: Identical years → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy24_value": 1000},
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=5.0, baseline_year="FY24", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}: {result.message}"
    assert "identical" in result.message.lower()
    print("[PASS] GEN-01: FY24 → FY24 identical → INVALID_DATA")


def test_gen01_reverse_order_flagged():
    """FY25 → FY24: Reverse ordering → FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy24_value": 1000, "fy25_value": 900},
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=10.0, baseline_year="FY25", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    print("[PASS] GEN-01: FY25 → FY24 reverse → FLAGGED")


def test_gen01_missing_year_column():
    """Missing year column → MISSING_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Test Metric", "fy23_value": 1000},
        # fy24_value column does not exist
    ])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test Metric", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0], all_rows=df.to_dict(orient="records"),
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}: {result.message}"
    print("[PASS] GEN-01: Missing year column → MISSING_DATA")


# ═══════════════════════════════════════════════════════════════
# GEN-02: Metric Unit Scale Consistency
# ═══════════════════════════════════════════════════════════════

def test_gen02_same_units_pass():
    """All emissions metrics use MT CO2e → PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "unit": "MT CO2e", "fy23_value": 4200, "fy24_value": 4100},
        {"metric_id": "MTR-002", "category": "Emissions", "metric_name": "Scope 2 Indirect Emissions",
         "unit": "MT CO2e", "fy23_value": 6300, "fy24_value": 6128.05},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("GEN-02")
    assert rule.is_applicable(ctx), "GEN-02 should be applicable when unit field exists"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-02: Same units → PASS")


def test_gen02_incompatible_units_invalid():
    """Duplicate metric_name rows with different units → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "unit": "MT CO2e", "fy23_value": 4200, "fy24_value": 4100},
        {"metric_id": "MTR-001-dup", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "unit": "kg", "fy23_value": 4200000, "fy24_value": 4100000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("GEN-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}: {result.message}"
    assert "UNIT SCALE INCONSISTENCY" in result.message
    print("[PASS] GEN-02: Duplicate metric with incompatible units -> INVALID_DATA")


def test_gen02_missing_unit_field():
    """No unit field → NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("GEN-02")
    assert not rule.is_applicable(ctx), "GEN-02 should NOT be applicable when unit field is missing"
    print("[PASS] GEN-02: Missing unit field → NOT_APPLICABLE")


def test_gen02_no_resolved_row():
    """No resolved metric row → NOT_APPLICABLE"""
    df = pd.DataFrame()
    ctx = _make_context(df=df, resolved_row=None, all_rows=[])
    rule = RuleRegistry.get_rule("GEN-02")
    assert not rule.is_applicable(ctx), "GEN-02 should NOT be applicable when no resolved row"
    print("[PASS] GEN-02: No resolved row → NOT_APPLICABLE")


def test_gen02_energy_duplicate_mwh_vs_kwh():
    """Same metric name but MWh vs kWh in duplicate rows → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Grid Electricity",
         "unit": "MWh", "fy23_value": 50000, "fy24_value": 48000},
        {"metric_id": "MTR-EN01-dup", "category": "Energy", "metric_name": "Grid Electricity",
         "unit": "kWh", "fy23_value": 50000000, "fy24_value": 48000000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Grid Electricity", claimed_percentage=4.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("GEN-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}: {result.message}"
    print("[PASS] GEN-02: Duplicate metric MWh vs kWh → INVALID_DATA")


def test_gen02_different_metrics_ok():
    """Different metric names with different units → PASS (no conflict)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "unit": "MT CO2e", "fy23_value": 4200, "fy24_value": 4100},
        {"metric_id": "MTR-W01", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "kGal", "fy23_value": 15200, "fy24_value": 14900},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("GEN-02")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-02: Different metric names, different units → PASS")


# ═══════════════════════════════════════════════════════════════
# GEN-03: >100% Impossibility & Zero-Division Guard
# ═══════════════════════════════════════════════════════════════

def test_gen03_normal_pass():
    """Valid claimed percentage (2.59%) → PASS"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=2.59, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    assert rule.is_applicable(ctx), "GEN-03 should always be applicable"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-03: Normal valid percentage → PASS")


def test_gen03_over_100_invalid():
    """>100% claimed reduction → INVALID_DATA"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=150.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}: {result.message}"
    assert "impossible" in result.message.lower() or "exceeds 100" in result.message.lower()
    print("[PASS] GEN-03: >100% → INVALID_DATA")


def test_gen03_exactly_100_pass():
    """Exactly 100% claimed reduction → PASS (boundary, not impossible)"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=100.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-03: Exactly 100% → PASS")


def test_gen03_negative_flagged():
    """Negative claimed percentage → FLAGGED"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=-5.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    assert "negative" in result.message.lower()
    print("[PASS] GEN-03: Negative percentage → FLAGGED")


def test_gen03_zero_baseline_invalid():
    """Zero baseline value → INVALID_DATA"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=0.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}: {result.message}"
    assert "zero baseline" in result.message.lower() or "baseline value is 0" in result.message.lower()
    print("[PASS] GEN-03: Zero baseline → INVALID_DATA")


def test_gen03_null_baseline_pass():
    """None baseline value (not yet resolved) → PASS (guard only fires on explicit 0)"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=None,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] GEN-03: None baseline → PASS (guard only fires on explicit 0)")


def test_gen03_101_invalid():
    """101% claimed reduction → INVALID_DATA"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=101.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}: {result.message}"
    print("[PASS] GEN-03: 101% → INVALID_DATA")


# ═══════════════════════════════════════════════════════════════
# REGISTRY VERIFICATION
# ═══════════════════════════════════════════════════════════════

def test_registry_contains_all_general():
    """All 3 general rules must be registered."""
    for rule_id in ["GEN-01", "GEN-02", "GEN-03"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert rule is not None, f"{rule_id} not found in registry"
        assert rule.domain == RuleDomain.GENERAL, f"{rule_id} has wrong domain: {rule.domain}"
    print("[PASS] Registry: All 3 general rules registered")


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    print("==================================================")
    print("RUNNING TRACK 3 GENERAL TEST SUITE")
    print("==================================================")

    # GEN-01
    test_gen01_fy23_to_fy24_pass()
    test_gen01_fy24_to_fy25_pass()
    test_gen01_four_digit_years_pass()
    test_gen01_fy2023_to_fy2024_pass()
    test_gen01_identical_years_invalid()
    test_gen01_reverse_order_flagged()
    test_gen01_missing_year_column()

    # GEN-02
    test_gen02_same_units_pass()
    test_gen02_incompatible_units_invalid()
    test_gen02_missing_unit_field()
    test_gen02_no_resolved_row()
    test_gen02_energy_duplicate_mwh_vs_kwh()
    test_gen02_different_metrics_ok()

    # GEN-03
    test_gen03_normal_pass()
    test_gen03_over_100_invalid()
    test_gen03_exactly_100_pass()
    test_gen03_negative_flagged()
    test_gen03_zero_baseline_invalid()
    test_gen03_null_baseline_pass()
    test_gen03_101_invalid()

    # Registry
    test_registry_contains_all_general()

    print("==================================================")
    print("ALL TRACK 3 GENERAL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
