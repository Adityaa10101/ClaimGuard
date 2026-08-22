"""
Track 2 Test Suite: Emissions Rules (EM-01 -> EM-05)
Covers: PASS, FLAGGED, MISSING_DATA, INVALID_DATA, NOT_APPLICABLE per rule,
including explicit tests for specification gap behaviors on EM-03 and EM-05.
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

# Ensure emissions rules are imported/registered
import src.rules.emissions  # noqa: F401

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


def _get_emissions_fixture_df():
    return pd.read_csv(os.path.join(FIXTURES_DIR, "emissions_full.csv"))


# ═══════════════════════════════════════════════════════════════
# EM-01: Scope 1 & 2 Subtotal Summation
# ═══════════════════════════════════════════════════════════════

def test_em01_pass():
    """Scope 1 (4100) + Scope 2 (6128.05) = Total (10228.05) -> PASS"""
    df = _get_emissions_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    total_row = next(r for r in rows if r.get("metric_id") == "MTR-TOTAL")
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-01")
    assert rule.is_applicable(ctx), "EM-01 should be applicable when all three rows exist"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    assert result.actual_value == 10228.05
    assert result.expected_value == 10228.05
    print("[PASS] EM-01: Subtotal summation PASS")


def test_em01_flagged():
    """Tampered total: Scope 1 + Scope 2 != manipulated Total -> FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions", "fy23_value": 4200, "fy24_value": 4100},
        {"metric_id": "MTR-002", "category": "Emissions", "metric_name": "Scope 2 Indirect Emissions", "fy23_value": 6300, "fy24_value": 6128.05},
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10500, "fy24_value": 9000.00},
    ])
    rows = df.to_dict(orient="records")
    total_row = rows[2]
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    assert result.variance > 0.05
    print("[PASS] EM-01: Subtotal mismatch FLAGGED")


def test_em01_missing_scope2():
    """Missing Scope 2 row -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions", "fy23_value": 4200, "fy24_value": 4100},
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10500, "fy24_value": 10228.05},
    ])
    rows = df.to_dict(orient="records")
    total_row = rows[1]
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-01")
    assert not rule.is_applicable(ctx), "EM-01 should not be applicable when Scope 2 is missing"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EM-01: Missing Scope 2 -> MISSING_DATA")


def test_em01_invalid_data():
    """Non-numeric values -> INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions", "fy23_value": 4200, "fy24_value": "N/A"},
        {"metric_id": "MTR-002", "category": "Emissions", "metric_name": "Scope 2 Indirect Emissions", "fy23_value": 6300, "fy24_value": 6128.05},
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10500, "fy24_value": 10228.05},
    ])
    rows = df.to_dict(orient="records")
    total_row = rows[2]
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] EM-01: Non-numeric values -> INVALID_DATA")


def test_em01_not_applicable_water():
    """Water domain claim -> NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-W01", "category": "Water", "metric_name": "Facility Water Usage", "fy23_value": 15200, "fy24_value": 14900},
    ])
    rows = df.to_dict(orient="records")
    water_row = rows[0]
    ctx = _make_context(
        claim=ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=water_row, all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EM-01")
    assert not rule.is_applicable(ctx), "EM-01 should NOT be applicable to Water domain"
    print("[PASS] EM-01: Water claim -> NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# EM-02: YoY Percentage Delta (Stub Registration Check)
# ═══════════════════════════════════════════════════════════════

def test_em02_registered():
    """EM-02 must be in the registry."""
    rule = RuleRegistry.get_rule("EM-02")
    assert rule is not None, "EM-02 must be registered"
    assert rule.rule_id == "EM-02"
    assert rule.domain == RuleDomain.EMISSIONS
    print("[PASS] EM-02: Registered in RuleRegistry")


# ═══════════════════════════════════════════════════════════════
# EM-03: Base-Year Restatement Matching (Specification Gap)
# ═══════════════════════════════════════════════════════════════

def test_em03_specification_gap_not_applicable():
    """EM-03 safely returns NOT_APPLICABLE due to lack of restatement specification/claim schema."""
    df = _get_emissions_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    total_row = next(r for r in rows if r.get("metric_id") == "MTR-TOTAL")
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-03")

    # Applicability check
    assert not rule.is_applicable(ctx), "EM-03 should return is_applicable=False until explicit spec exists"

    # Direct evaluate check
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.NOT_APPLICABLE, f"Expected NOT_APPLICABLE, got {result.status}"
    assert "SPECIFICATION GAP" in result.message
    print("[PASS] EM-03: Specification gap safely returns NOT_APPLICABLE")


def test_em03_not_applicable_energy():
    """Energy domain -> NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "fy23_value": 50000, "fy24_value": 48000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Purchased Grid Electricity", claimed_percentage=4.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EM-03")
    assert not rule.is_applicable(ctx), "EM-03 should NOT be applicable to Energy domain"
    print("[PASS] EM-03: Energy claim -> NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# EM-04: Scope 3 Upstream / Downstream Consistency
# ═══════════════════════════════════════════════════════════════

def test_em04_pass():
    """Upstream (20000) + Downstream (24100) = Total (44100) -> PASS"""
    df = _get_emissions_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    total_row = next(r for r in rows if r.get("metric_id") == "MTR-TOTAL")
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-04")
    assert rule.is_applicable(ctx), "EM-04 should be applicable when Scope 3 disaggregation columns exist"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] EM-04: Scope 3 upstream + downstream = total -> PASS")


def test_em04_flagged():
    """Tampered Scope 3 total -> FLAGGED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions",
         "fy23_value": 10500, "fy24_value": 10228.05},
        {"metric_id": "MTR-005", "category": "Emissions", "metric_name": "Scope 3 Value Chain Emissions",
         "fy23_value": 45000, "fy24_value": 44100,
         "scope3_upstream_fy24": 20000, "scope3_downstream_fy24": 24100, "scope3_total_fy24": 50000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-04")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED, f"Expected FLAGGED, got {result.status}: {result.message}"
    print("[PASS] EM-04: Tampered Scope 3 total -> FLAGGED")


def test_em04_missing_scope3_row():
    """No Scope 3 row -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions",
         "fy23_value": 10500, "fy24_value": 10228.05},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-04")
    assert not rule.is_applicable(ctx), "EM-04 should not be applicable when Scope 3 row is missing"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EM-04: No Scope 3 row -> MISSING_DATA")


def test_em04_missing_disaggregation_cols():
    """Scope 3 row exists but no upstream/downstream columns -> MISSING_DATA when evaluated"""
    df = pd.DataFrame([
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions",
         "fy23_value": 10500, "fy24_value": 10228.05},
        {"metric_id": "MTR-005", "category": "Emissions", "metric_name": "Scope 3 Value Chain Emissions",
         "fy23_value": 45000, "fy24_value": 44100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-04")
    assert not rule.is_applicable(ctx), "EM-04 should not be applicable when disaggregation cols are missing"
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.MISSING_DATA, f"Expected MISSING_DATA, got {result.status}"
    print("[PASS] EM-04: Missing disaggregation columns -> MISSING_DATA")


def test_em04_invalid_numeric():
    """Non-numeric Scope 3 values -> INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions",
         "fy23_value": 10500, "fy24_value": 10228.05},
        {"metric_id": "MTR-005", "category": "Emissions", "metric_name": "Scope 3 Value Chain Emissions",
         "fy23_value": 45000, "fy24_value": 44100,
         "scope3_upstream_fy24": "bad", "scope3_downstream_fy24": 24100, "scope3_total_fy24": 44100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-04")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] EM-04: Non-numeric Scope 3 -> INVALID_DATA")


# ═══════════════════════════════════════════════════════════════
# EM-05: Absolute Metric-Ton Variance Check (Specification Gap)
# ═══════════════════════════════════════════════════════════════

def test_em05_specification_gap_not_applicable():
    """EM-05 safely returns NOT_APPLICABLE because ExtractedClaim has no claimed_absolute_value."""
    df = _get_emissions_fixture_df()
    df.columns = [c.strip().lower() for c in df.columns]
    rows = df.to_dict(orient="records")
    total_row = next(r for r in rows if r.get("metric_id") == "MTR-TOTAL")
    ctx = _make_context(df=df, resolved_row=total_row, all_rows=rows)
    rule = RuleRegistry.get_rule("EM-05")

    # Applicability check
    assert not rule.is_applicable(ctx), "EM-05 should return is_applicable=False until schema supports absolute claims"

    # Direct evaluate check
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.NOT_APPLICABLE, f"Expected NOT_APPLICABLE, got {result.status}"
    assert "SPECIFICATION GAP" in result.message
    print("[PASS] EM-05: Specification gap safely returns NOT_APPLICABLE")


def test_em05_not_applicable_water():
    """Water domain -> NOT_APPLICABLE"""
    df = pd.DataFrame([
        {"metric_id": "MTR-W01", "category": "Water", "metric_name": "Facility Water Usage",
         "fy23_value": 15200, "fy24_value": 14900},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    rule = RuleRegistry.get_rule("EM-05")
    assert not rule.is_applicable(ctx), "EM-05 should NOT be applicable to Water domain"
    print("[PASS] EM-05: Water claim -> NOT_APPLICABLE")


# ═══════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════

def test_em01_nan_values():
    """NaN values in scope data -> INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions", "fy23_value": 4200, "fy24_value": float("nan")},
        {"metric_id": "MTR-002", "category": "Emissions", "metric_name": "Scope 2 Indirect Emissions", "fy23_value": 6300, "fy24_value": 6128.05},
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10500, "fy24_value": 10228.05},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[2], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA, f"Expected INVALID_DATA, got {result.status}"
    print("[PASS] EM-01 Edge: NaN values -> INVALID_DATA")


def test_em01_negative_values():
    """Negative values should still compute correctly"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions", "fy23_value": 4200, "fy24_value": -100},
        {"metric_id": "MTR-002", "category": "Emissions", "metric_name": "Scope 2 Indirect Emissions", "fy23_value": 6300, "fy24_value": 6128.05},
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10500, "fy24_value": 6028.05},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[2], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] EM-01 Edge: Negative values compute correctly")


def test_em01_exact_tolerance_boundary():
    """Variance exactly at tolerance -> PASS"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions", "fy23_value": 4200, "fy24_value": 4100.00},
        {"metric_id": "MTR-002", "category": "Emissions", "metric_name": "Scope 2 Indirect Emissions", "fy23_value": 6300, "fy24_value": 6128.00},
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10500, "fy24_value": 10228.05},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[2], all_rows=rows, tolerance=0.05)
    rule = RuleRegistry.get_rule("EM-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS at exact tolerance, got {result.status}: {result.message}"
    print("[PASS] EM-01 Edge: Exact tolerance boundary -> PASS")


def test_em04_zero_upstream():
    """Zero upstream value should compute correctly"""
    df = pd.DataFrame([
        {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions",
         "fy23_value": 10500, "fy24_value": 10228.05},
        {"metric_id": "MTR-005", "category": "Emissions", "metric_name": "Scope 3 Value Chain Emissions",
         "fy23_value": 45000, "fy24_value": 44100,
         "scope3_upstream_fy24": 0, "scope3_downstream_fy24": 44100, "scope3_total_fy24": 44100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("EM-04")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS, f"Expected PASS, got {result.status}: {result.message}"
    print("[PASS] EM-04 Edge: Zero upstream -> PASS")


# ═══════════════════════════════════════════════════════════════
# REGISTRY VERIFICATION
# ═══════════════════════════════════════════════════════════════

def test_registry_contains_all_emissions():
    """All 5 emissions rules must be registered."""
    for rule_id in ["EM-01", "EM-02", "EM-03", "EM-04", "EM-05"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert rule is not None, f"{rule_id} not found in registry"
        assert rule.domain == RuleDomain.EMISSIONS, f"{rule_id} has wrong domain: {rule.domain}"
    print("[PASS] Registry: All 5 emissions rules registered")


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    print("==================================================")
    print("RUNNING TRACK 2 EMISSIONS TEST SUITE")
    print("==================================================")

    # EM-01
    test_em01_pass()
    test_em01_flagged()
    test_em01_missing_scope2()
    test_em01_invalid_data()
    test_em01_not_applicable_water()

    # EM-02
    test_em02_registered()

    # EM-03 (Specification Gap)
    test_em03_specification_gap_not_applicable()
    test_em03_not_applicable_energy()

    # EM-04
    test_em04_pass()
    test_em04_flagged()
    test_em04_missing_scope3_row()
    test_em04_missing_disaggregation_cols()
    test_em04_invalid_numeric()

    # EM-05 (Specification Gap)
    test_em05_specification_gap_not_applicable()
    test_em05_not_applicable_water()

    # Edge cases
    test_em01_nan_values()
    test_em01_negative_values()
    test_em01_exact_tolerance_boundary()
    test_em04_zero_upstream()

    # Registry
    test_registry_contains_all_emissions()

    print("==================================================")
    print("ALL TRACK 2 EMISSIONS TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
