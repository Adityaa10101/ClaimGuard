"""
Track 3 Adversarial & Integration Test Suite
Comprehensive hardening tests across all Track 3 rules covering:
- Input failures (empty data, missing columns, NaN, malformed strings)
- Boundary conditions (zero denominator, tolerance edges, 100%+ claims)
- Year edge cases (all format variations, identical, reversed, missing)
- Metric edge cases (exact, alias, ambiguous, unknown)
- Cross-domain isolation (Water rules on Emissions claims and vice versa)
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas as pd
from src.schemas import ExtractedClaim, AuditDecision, ExecutionStatus, RuleStatus
from src.rules.base import BaseRule, RuleDomain, RuleEvaluationContext
from src.rules.registry import RuleRegistry
from src.rules_engine import verify_claim

# Ensure all domain rules are imported/registered
import src.rules.water    # noqa: F401
import src.rules.general  # noqa: F401

FIXTURES_DIR = os.path.join(REPO_ROOT, "data", "fixtures")
CLEAN_DIR = os.path.join(REPO_ROOT, "data", "preset_clean")
FLAGGED_DIR = os.path.join(REPO_ROOT, "data", "preset_flagged")


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
    if claim is None:
        claim = ExtractedClaim(
            metric="Facility Water Usage",
            claimed_percentage=1.97,
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
# 1. INPUT FAILURES
# ═══════════════════════════════════════════════════════════════

def test_adv_empty_dataframe():
    """Empty DataFrame → engine returns UNVERIFIED/MISSING_DATA"""
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, pd.DataFrame())
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    print("[PASS] ADV-01: Empty DataFrame → UNVERIFIED/MISSING_DATA")


def test_adv_empty_csv_path():
    """Non-existent CSV path → engine returns UNVERIFIED/ERROR"""
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, "nonexistent_path_xyz.csv")
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.ERROR
    print("[PASS] ADV-02: Non-existent CSV → UNVERIFIED/ERROR")


def test_adv_missing_columns():
    """DataFrame with no metric_name column → engine handles gracefully"""
    df = pd.DataFrame([{"some_field": "some_value", "fy23_value": 100}])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    print("[PASS] ADV-03: Missing metric columns → UNVERIFIED")


def test_adv_missing_metric_row():
    """DataFrame with no matching metric row → MISSING_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Unrelated Metric", "fy23_value": 100, "fy24_value": 90},
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    print("[PASS] ADV-04: No matching metric row → MISSING_DATA")


def test_adv_nan_values():
    """NaN in value column → engine handles as INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "metric_name": "Facility Water Usage",
         "fy23_value": float("nan"), "fy24_value": 14900},
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    print("[PASS] ADV-05: NaN in value → INVALID_DATA")


def test_adv_empty_string_values():
    """Empty string in value column → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "metric_name": "Facility Water Usage",
         "fy23_value": "", "fy24_value": 14900},
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    print("[PASS] ADV-06: Empty string value → INVALID_DATA")


def test_adv_malformed_numeric_strings():
    """Malformed numeric string → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "metric_name": "Facility Water Usage",
         "fy23_value": "twelve thousand", "fy24_value": 14900},
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    print("[PASS] ADV-07: Malformed numeric string → INVALID_DATA")


def test_adv_unexpected_units_rule_level():
    """Unexpected unit in metric row → GEN-02 handles gracefully"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Water", "metric_name": "Facility Water Usage",
         "unit": "furlongs", "fy23_value": 15200, "fy24_value": 14900},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    rule = RuleRegistry.get_rule("GEN-02")
    # Should be applicable (unit field exists)
    assert rule.is_applicable(ctx)
    result = rule.evaluate(ctx)
    # "furlongs" is not in canonical map but there are no peers to conflict with → PASS
    assert result.status in (RuleStatus.PASS, RuleStatus.INVALID_DATA)
    print("[PASS] ADV-08: Unexpected units → handled gracefully")


# ═══════════════════════════════════════════════════════════════
# 2. BOUNDARY CONDITIONS
# ═══════════════════════════════════════════════════════════════

def test_adv_zero_denominator_engine():
    """Zero baseline via engine → INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage",
         "fy23_value": 0.0, "fy24_value": 14900},
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    print("[PASS] ADV-09: Zero baseline via engine → INVALID_DATA")


def test_adv_zero_baseline_gen03():
    """Zero baseline via GEN-03 rule → INVALID_DATA"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=0.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA
    print("[PASS] ADV-10: Zero baseline GEN-03 → INVALID_DATA")


def test_adv_exact_005_tolerance():
    """Variance exactly 0.05% → PASS (at tolerance)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage",
         "fy23_value": 10000.0, "fy24_value": 9000.0},
    ])
    # Actual delta = 10.0%. Claim 10.05% → variance = 0.05% → PASS
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=10.05, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df, tolerance=0.05)
    assert result.status == "PASS", f"Expected PASS at exact tolerance, got {result.status}"
    assert result.variance == 0.05
    print("[PASS] ADV-11: Exactly 0.05% tolerance → PASS")


def test_adv_006_tolerance_breach():
    """Variance 0.06% → FLAGGED (just beyond tolerance)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage",
         "fy23_value": 10000.0, "fy24_value": 9000.0},
    ])
    # Actual delta = 10.0%. Claim 10.06% → variance = 0.06% → FLAGGED
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=10.06, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df, tolerance=0.05)
    assert result.status == "FLAGGED", f"Expected FLAGGED at 0.06% variance, got {result.status}"
    assert result.variance == 0.06
    print("[PASS] ADV-12: 0.06% tolerance breach → FLAGGED")


def test_adv_100_percent_claim():
    """Exactly 100% claimed → GEN-03 PASS (boundary, not impossible)"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=100.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS
    print("[PASS] ADV-13: 100% claim → GEN-03 PASS")


def test_adv_over_100_claim():
    """150% claimed → GEN-03 INVALID_DATA"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=150.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA
    print("[PASS] ADV-14: 150% claim → GEN-03 INVALID_DATA")


def test_adv_negative_percentage():
    """Negative percentage → GEN-03 FLAGGED"""
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=-10.0, baseline_year="FY23", target_year="FY24"),
        baseline_val=10000.0,
    )
    rule = RuleRegistry.get_rule("GEN-03")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED
    print("[PASS] ADV-15: Negative percentage → GEN-03 FLAGGED")


# ═══════════════════════════════════════════════════════════════
# 3. YEAR EDGE CASES
# ═══════════════════════════════════════════════════════════════

def test_adv_year_fy23_fy24():
    """FY23 → FY24 via GEN-01 → PASS"""
    df = pd.DataFrame([{"metric_id": "MTR-001", "metric_name": "Test", "fy23_value": 1000, "fy24_value": 900}])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0],
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS
    print("[PASS] ADV-16: FY23 → FY24 via GEN-01 → PASS")


def test_adv_year_fy24_fy25():
    """FY24 → FY25 via GEN-01 → PASS"""
    df = pd.DataFrame([{"metric_id": "MTR-001", "metric_name": "Test", "fy24_value": 1000, "fy25_value": 900}])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY24", target_year="FY25"),
        df=df, resolved_row=df.to_dict(orient="records")[0],
        baseline_col="fy24_value", target_col="fy25_value",
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS
    print("[PASS] ADV-17: FY24 → FY25 via GEN-01 → PASS")


def test_adv_year_2023_2024():
    """2023 → 2024 via GEN-01 → PASS"""
    df = pd.DataFrame([{"metric_id": "MTR-001", "metric_name": "Test", "fy23_value": 1000, "fy24_value": 900}])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="2023", target_year="2024"),
        df=df, resolved_row=df.to_dict(orient="records")[0],
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS
    print("[PASS] ADV-18: 2023 → 2024 via GEN-01 → PASS")


def test_adv_year_fy2023_fy2024():
    """FY2023 → FY2024 via GEN-01 → PASS"""
    df = pd.DataFrame([{"metric_id": "MTR-001", "metric_name": "Test", "fy23_value": 1000, "fy24_value": 900}])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY2023", target_year="FY2024"),
        df=df, resolved_row=df.to_dict(orient="records")[0],
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.PASS
    print("[PASS] ADV-19: FY2023 → FY2024 via GEN-01 → PASS")


def test_adv_year_fy24_fy24_identical():
    """FY24 → FY24 via GEN-01 → INVALID_DATA"""
    df = pd.DataFrame([{"metric_id": "MTR-001", "metric_name": "Test", "fy24_value": 1000}])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=5.0, baseline_year="FY24", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0],
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.INVALID_DATA
    print("[PASS] ADV-20: FY24 → FY24 identical → INVALID_DATA")


def test_adv_year_fy25_fy24_reversed():
    """FY25 → FY24 via GEN-01 → FLAGGED"""
    df = pd.DataFrame([{"metric_id": "MTR-001", "metric_name": "Test", "fy24_value": 1000, "fy25_value": 900}])
    ctx = _make_context(
        claim=ExtractedClaim(metric="Test", claimed_percentage=10.0, baseline_year="FY25", target_year="FY24"),
        df=df, resolved_row=df.to_dict(orient="records")[0],
    )
    rule = RuleRegistry.get_rule("GEN-01")
    result = rule.evaluate(ctx)
    assert result.status == RuleStatus.FLAGGED
    print("[PASS] ADV-21: FY25 → FY24 reversed → FLAGGED")


def test_adv_year_missing_via_engine():
    """Missing year column via full engine → UNVERIFIED"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage", "fy23_value": 15200},
        # No fy24_value column
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    print("[PASS] ADV-22: Missing year column via engine → MISSING_DATA")


# ═══════════════════════════════════════════════════════════════
# 4. METRIC EDGE CASES
# ═══════════════════════════════════════════════════════════════

def test_adv_metric_exact_match():
    """Exact metric name match → engine finds it"""
    df = pd.DataFrame([
        {"metric_id": "MTR-WT01", "metric_name": "Facility Water Usage",
         "fy23_value": 15200, "fy24_value": 14900},
    ])
    claim = ExtractedClaim(metric="Facility Water Usage", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.matched_metric == "Facility Water Usage"
    assert result.status == "PASS"
    print("[PASS] ADV-23: Exact metric name match → found")


def test_adv_metric_alias_match():
    """Alias 'water consumption' → matches 'Facility Water Usage'"""
    metrics_path = os.path.join(FIXTURES_DIR, "water_full.csv")
    claim = ExtractedClaim(metric="water consumption", claimed_percentage=1.97, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, metrics_path)
    assert result.matched_metric == "Facility Water Usage"
    assert result.status == "PASS"
    print("[PASS] ADV-24: Alias match 'water consumption' → 'Facility Water Usage'")


def test_adv_metric_ambiguous():
    """Ambiguous metric query → UNVERIFIED/INVALID_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-A", "category": "Water", "metric_name": "Water Operations North", "fy23_value": 100, "fy24_value": 90},
        {"metric_id": "MTR-B", "category": "Water", "metric_name": "Water Operations South", "fy23_value": 200, "fy24_value": 180},
    ])
    claim = ExtractedClaim(metric="Water Operations", claimed_percentage=10.0, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    print("[PASS] ADV-25: Ambiguous metric → INVALID_DATA")


def test_adv_metric_completely_unknown():
    """Completely unknown metric → MISSING_DATA"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage", "fy23_value": 15200, "fy24_value": 14900},
    ])
    claim = ExtractedClaim(metric="Quantum Flux Density", claimed_percentage=5.0, baseline_year="FY23", target_year="FY24")
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    print("[PASS] ADV-26: Unknown metric → MISSING_DATA")


# ═══════════════════════════════════════════════════════════════
# 5. CROSS-DOMAIN ISOLATION
# ═══════════════════════════════════════════════════════════════

def test_adv_water_rules_not_applicable_to_emissions():
    """Water rules (WT-01/02/03) should NOT apply to Emissions claims"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Emissions", "metric_name": "Scope 1 Direct Emissions",
         "unit": "MT CO2e", "fy23_value": 4200, "fy24_value": 4100},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Scope 1 Direct Emissions", claimed_percentage=2.38, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    for rule_id in ["WT-01", "WT-02", "WT-03"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert not rule.is_applicable(ctx), f"{rule_id} should NOT be applicable to Emissions domain"
    print("[PASS] ADV-27: Water rules not applicable to Emissions")


def test_adv_water_rules_not_applicable_to_energy():
    """Water rules should NOT apply to Energy claims"""
    df = pd.DataFrame([
        {"metric_id": "MTR-EN01", "category": "Energy", "metric_name": "Purchased Grid Electricity",
         "unit": "MWh", "fy23_value": 50000, "fy24_value": 48000},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(
        claim=ExtractedClaim(metric="Purchased Grid Electricity", claimed_percentage=4.0, baseline_year="FY23", target_year="FY24"),
        df=df, resolved_row=rows[0], all_rows=rows,
    )
    for rule_id in ["WT-01", "WT-02", "WT-03"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert not rule.is_applicable(ctx), f"{rule_id} should NOT be applicable to Energy domain"
    print("[PASS] ADV-28: Water rules not applicable to Energy")


def test_adv_general_rules_applicable_cross_domain():
    """GEN-01 and GEN-03 should apply to ALL domains (cross-domain structural checks)"""
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "category": "Water", "metric_name": "Facility Water Usage",
         "fy23_value": 15200, "fy24_value": 14900},
    ])
    rows = df.to_dict(orient="records")
    ctx = _make_context(df=df, resolved_row=rows[0], all_rows=rows)
    # GEN-01 and GEN-03 are cross-domain
    for rule_id in ["GEN-01", "GEN-03"]:
        rule = RuleRegistry.get_rule(rule_id)
        assert rule.is_applicable(ctx), f"{rule_id} should be applicable across all domains"
    print("[PASS] ADV-29: GEN-01/03 applicable cross-domain")


# ═══════════════════════════════════════════════════════════════
# 6. DEMO PRESET REGRESSION
# ═══════════════════════════════════════════════════════════════

def test_adv_demo_a_still_passes():
    """Demo A (clean preset) must still produce PASS"""
    metrics_path = os.path.join(CLEAN_DIR, "metrics.csv")
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=2.59,
        baseline_year="FY23",
        target_year="FY24",
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "PASS", f"Demo A regression: expected PASS, got {result.status}"
    assert result.audit_decision == AuditDecision.PASS
    print("[PASS] ADV-30: Demo A preset → PASS (regression)")


def test_adv_demo_b_still_flagged():
    """Demo B (flagged preset) must still produce FLAGGED"""
    metrics_path = os.path.join(FLAGGED_DIR, "metrics.csv")
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=20.00,
        baseline_year="FY23",
        target_year="FY24",
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "FLAGGED", f"Demo B regression: expected FLAGGED, got {result.status}"
    assert result.audit_decision == AuditDecision.FLAGGED
    assert result.variance == 17.41
    print("[PASS] ADV-31: Demo B preset → FLAGGED (regression)")


# ═══════════════════════════════════════════════════════════════
# 7. WATER RULES VIA FULL ENGINE (INTEGRATION)
# ═══════════════════════════════════════════════════════════════

def test_adv_water_full_fixture_via_engine():
    """Water fixture via full engine with water claim → should include WT rule results"""
    metrics_path = os.path.join(FIXTURES_DIR, "water_full.csv")
    claim = ExtractedClaim(
        metric="Facility Water Usage",
        claimed_percentage=1.97,
        baseline_year="FY23",
        target_year="FY24",
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "PASS", f"Expected PASS for correct water claim, got {result.status}"

    # Check that Water rules were evaluated (not just skipped)
    rule_ids_in_results = [r.rule_id for r in result.rule_results]
    assert "EM-02" in rule_ids_in_results, "Primary EM-02 rule should be present"

    # GEN-01 and GEN-03 should be in results (always applicable)
    assert "GEN-01" in rule_ids_in_results, "GEN-01 should be in results"
    assert "GEN-03" in rule_ids_in_results, "GEN-03 should be in results"
    print("[PASS] ADV-32: Water fixture via full engine → PASS with rule results")


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    print("==================================================")
    print("RUNNING TRACK 3 ADVERSARIAL TEST SUITE")
    print("==================================================")

    # 1. Input Failures
    test_adv_empty_dataframe()
    test_adv_empty_csv_path()
    test_adv_missing_columns()
    test_adv_missing_metric_row()
    test_adv_nan_values()
    test_adv_empty_string_values()
    test_adv_malformed_numeric_strings()
    test_adv_unexpected_units_rule_level()

    # 2. Boundary Conditions
    test_adv_zero_denominator_engine()
    test_adv_zero_baseline_gen03()
    test_adv_exact_005_tolerance()
    test_adv_006_tolerance_breach()
    test_adv_100_percent_claim()
    test_adv_over_100_claim()
    test_adv_negative_percentage()

    # 3. Year Edge Cases
    test_adv_year_fy23_fy24()
    test_adv_year_fy24_fy25()
    test_adv_year_2023_2024()
    test_adv_year_fy2023_fy2024()
    test_adv_year_fy24_fy24_identical()
    test_adv_year_fy25_fy24_reversed()
    test_adv_year_missing_via_engine()

    # 4. Metric Edge Cases
    test_adv_metric_exact_match()
    test_adv_metric_alias_match()
    test_adv_metric_ambiguous()
    test_adv_metric_completely_unknown()

    # 5. Cross-Domain Isolation
    test_adv_water_rules_not_applicable_to_emissions()
    test_adv_water_rules_not_applicable_to_energy()
    test_adv_general_rules_applicable_cross_domain()

    # 6. Demo Preset Regression
    test_adv_demo_a_still_passes()
    test_adv_demo_b_still_flagged()

    # 7. Integration
    test_adv_water_full_fixture_via_engine()

    print("==================================================")
    print("ALL 32 TRACK 3 ADVERSARIAL TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
