import os
import sys

# Ensure repository root is in Python path for test discovery
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas as pd
from unittest.mock import patch

from src.schemas import (
    ExtractedClaim,
    AuditResult,
    AuditDecision,
    ExecutionStatus,
    RuleStatus,
    RuleResult,
    RuleEvidence,
)
from src.rules.base import BaseRule, RuleDomain, RuleEvaluationContext
from src.rules.registry import RuleRegistry
from src.rules_engine import verify_claim
from src.extractor import extract_claim_from_narrative, _fallback_rule_extraction
from src.rules.metric_resolver import resolve_metric, MetricResolutionStatus
from src.rules.year_resolver import normalize_fiscal_year, resolve_year_column, extract_numeric_value


FIXTURES_DIR = os.path.join(REPO_ROOT, "data", "fixtures")
CLEAN_DIR = os.path.join(REPO_ROOT, "data", "preset_clean")
FLAGGED_DIR = os.path.join(REPO_ROOT, "data", "preset_flagged")


# 1. Clean Claim (Demo Case A)
def test_demo_case_a_clean_pass():
    metrics_path = os.path.join(CLEAN_DIR, "metrics.csv")
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=2.59,
        baseline_year="FY23",
        target_year="FY24",
        claim_text="Achieved a 2.59% reduction in total Scope 1 & 2 emissions in FY24 vs FY23."
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "PASS"
    assert result.audit_decision == AuditDecision.PASS
    assert result.execution_status == ExecutionStatus.SUCCESS
    assert result.variance == 0.0
    assert result.calculated_delta == 2.59
    assert result.baseline_value == 10500.0
    assert result.target_value == 10228.05
    print("[PASS] Test 1: Clean Claim (Demo Case A)")


# 2. Mismatched Claim (Demo Case B)
def test_demo_case_b_flagged():
    metrics_path = os.path.join(FLAGGED_DIR, "metrics.csv")
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=20.00,
        baseline_year="FY23",
        target_year="FY24",
        claim_text="Achieved a 20.00% reduction in total Scope 1 & 2 emissions."
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "FLAGGED"
    assert result.audit_decision == AuditDecision.FLAGGED
    assert result.execution_status == ExecutionStatus.SUCCESS
    assert result.variance == 17.41
    assert result.calculated_delta == 2.59
    print("[PASS] Test 2: Mismatched Claim (Demo Case B)")


# 3. Wrong Metric Query (No Silent Fallback to MTR-TOTAL or First Row)
def test_wrong_metric_no_fallback():
    metrics_path = os.path.join(FIXTURES_DIR, "emissions_full.csv")
    claim = ExtractedClaim(
        metric="Biodiversity Habitat Restoration Acres",
        claimed_percentage=15.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, metrics_path)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    assert "Unable to locate matching CSV metric record" in result.discrepancy_reason
    assert result.matched_metric is None
    print("[PASS] Test 3: Wrong Metric Query")


# 4. Ambiguous Metric Query Detection
def test_ambiguous_metric_detection():
    df = pd.DataFrame([
        {"metric_id": "MTR-A", "category": "Emissions", "metric_name": "Scope Direct Operations", "fy23_value": 100.0, "fy24_value": 90.0},
        {"metric_id": "MTR-B", "category": "Emissions", "metric_name": "Scope Direct Logistics", "fy23_value": 200.0, "fy24_value": 180.0},
    ])
    claim = ExtractedClaim(
        metric="Scope Direct",
        claimed_percentage=10.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    assert "Ambiguous metric query" in result.discrepancy_reason
    print("[PASS] Test 4: Ambiguous Metric Detection")


# 5. Missing Metric in CSV
def test_missing_metric_in_csv():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Purchased Electricity", "fy23_value": 500.0, "fy24_value": 450.0}
    ])
    claim = ExtractedClaim(
        metric="Hazardous Chemical Waste",
        claimed_percentage=10.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    print("[PASS] Test 5: Missing Metric in CSV")


# 6. Missing Year Column
def test_missing_year_column():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 1000.0}
    ])
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=5.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.MISSING_DATA
    assert "missing required year column" in result.discrepancy_reason
    print("[PASS] Test 6: Missing Year Column")


# 7. Zero Baseline Value Guard (ZeroDivisionError Protection)
def test_zero_baseline_division_guard():
    metrics_path = os.path.join(FIXTURES_DIR, "general_edge_cases.csv")
    claim = ExtractedClaim(
        metric="Zero Baseline Metric",
        claimed_percentage=10.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, metrics_path)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    assert "Baseline year (FY23) value is 0" in result.discrepancy_reason
    print("[PASS] Test 7: Zero Baseline Division Guard")


# 8. Negative Claimed Percentage
def test_negative_claimed_percentage():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage", "fy23_value": 1000.0, "fy24_value": 900.0}
    ])
    claim = ExtractedClaim(
        metric="Facility Water Usage",
        claimed_percentage=-10.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    assert result.status == "FLAGGED"
    assert result.audit_decision == AuditDecision.FLAGGED
    assert result.variance == 20.0
    print("[PASS] Test 8: Negative Claimed Percentage")


# 9. >100% Claimed Percentage
def test_over_100_percent_claimed_percentage():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Facility Water Usage", "fy23_value": 1000.0, "fy24_value": 900.0}
    ])
    claim = ExtractedClaim(
        metric="Facility Water Usage",
        claimed_percentage=150.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    assert result.status == "FLAGGED"
    assert result.audit_decision == AuditDecision.FLAGGED
    assert result.variance == 140.0
    print("[PASS] Test 9: >100% Claimed Percentage")


# 10. Exact 0.05% Tolerance Delta Boundary (PASS)
def test_exact_tolerance_boundary_pass():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10000.0, "fy24_value": 9000.0}
    ])
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=10.05,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df, tolerance=0.05)
    assert result.status == "PASS"
    assert result.audit_decision == AuditDecision.PASS
    assert result.variance == 0.05
    print("[PASS] Test 10: Exact 0.05% Boundary (PASS)")


# 11. 0.06% Variance Threshold Boundary (FLAGGED)
def test_tolerance_breach_boundary_flag():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10000.0, "fy24_value": 9000.0}
    ])
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=10.06,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df, tolerance=0.05)
    assert result.status == "FLAGGED"
    assert result.audit_decision == AuditDecision.FLAGGED
    assert result.variance == 0.06
    print("[PASS] Test 11: 0.06% Boundary (FLAGGED)")


# 12. Dynamic FY24 -> FY25 Pair
def test_dynamic_fy24_to_fy25_years():
    metrics_path = os.path.join(FIXTURES_DIR, "energy_full.csv")
    claim = ExtractedClaim(
        metric="Total Energy Consumption",
        claimed_percentage=4.51,
        baseline_year="FY24",
        target_year="FY25"
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "PASS"
    assert result.audit_decision == AuditDecision.PASS
    assert result.baseline_year == "FY24"
    assert result.target_year == "FY25"
    assert result.calculated_delta == 4.51
    print("[PASS] Test 12: Dynamic FY24 -> FY25 Pair")


# 13. 4-Digit Year Normalization (2023 -> 2024 / FY2023 -> FY2024)
def test_four_digit_year_normalization():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Purchased Grid Electricity", "fy23_value": 50000.0, "fy24_value": 48000.0}
    ])
    claim = ExtractedClaim(
        metric="Purchased Grid Electricity",
        claimed_percentage=4.0,
        baseline_year="2023",
        target_year="FY2024"
    )
    result = verify_claim(claim, df)
    assert result.status == "PASS"
    assert result.baseline_year == "FY23"
    assert result.target_year == "FY24"
    assert result.calculated_delta == 4.0
    print("[PASS] Test 13: 4-Digit Year Normalization")


# 14. Malformed PR Narrative Offline Fallback
def test_malformed_narrative_offline_fallback():
    raw_text = "ClaimGuard had a busy year. We managed our facilities across regions."
    claim = _fallback_rule_extraction(raw_text)
    assert claim.metric is not None
    assert claim.claimed_percentage == 0.0
    assert claim.baseline_year == "FY23"
    assert claim.target_year == "FY24"
    print("[PASS] Test 14: Malformed PR Narrative Fallback")


# 15. Extractor API Failure Resilience
def test_extractor_api_failure_resilience():
    raw_text = "Achieved a 2.59% reduction in total Scope 1 & 2 emissions in FY24 compared to FY23."
    with patch("src.extractor.os.getenv", return_value="invalid_api_key_123"):
        claim = extract_claim_from_narrative(raw_text)
        assert claim.metric == "Total Scope 1 & 2 Emissions"
        assert claim.claimed_percentage == 2.59
        assert claim.baseline_year == "FY23"
        assert claim.target_year == "FY24"
    print("[PASS] Test 15: Extractor API Resilience")


# 16. Multiple Rules Aggregation with Flags
def test_multiple_rules_aggregation_with_flags():
    RuleRegistry.clear()

    @RuleRegistry.register
    class DummyFailingRule(BaseRule):
        rule_id = "TEST-FAIL-01"
        domain = RuleDomain.GENERAL
        rule_name = "Dummy Secondary Policy Check"
        def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
            return RuleResult(
                rule_id=self.rule_id,
                domain=self.domain.value,
                rule_name=self.rule_name,
                status=RuleStatus.FLAGGED,
                message="Secondary regulatory check violated."
            )

    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Total Scope 1 & 2 Emissions", "fy23_value": 10000.0, "fy24_value": 9000.0}
    ])
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=10.0,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    RuleRegistry.clear()

    assert result.status == "FLAGGED"
    assert result.audit_decision == AuditDecision.FLAGGED
    assert result.summary.flagged == 1
    assert result.summary.passed == 1
    assert "TEST-FAIL-01" in result.discrepancy_reason
    print("[PASS] Test 16: Multiple Rules Aggregation")


# 17. Empty & Corrupt CSV Input
def test_empty_and_corrupt_csv_handling():
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=2.59,
        baseline_year="FY23",
        target_year="FY24"
    )
    empty_df = pd.DataFrame()
    result_empty = verify_claim(claim, empty_df)
    assert result_empty.audit_decision == AuditDecision.UNVERIFIED
    assert result_empty.execution_status == ExecutionStatus.MISSING_DATA

    result_bad_path = verify_claim(claim, "non_existent_file.csv")
    assert result_bad_path.audit_decision == AuditDecision.UNVERIFIED
    assert result_bad_path.execution_status == ExecutionStatus.ERROR
    print("[PASS] Test 17: Empty & Corrupt CSV Handling")


# 18. Identical Baseline and Target Years
def test_identical_baseline_and_target_years():
    df = pd.DataFrame([
        {"metric_id": "MTR-001", "metric_name": "Total Scope 1 & 2 Emissions", "fy24_value": 10000.0}
    ])
    claim = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=5.0,
        baseline_year="FY24",
        target_year="FY24"
    )
    result = verify_claim(claim, df)
    assert result.audit_decision == AuditDecision.UNVERIFIED
    assert result.execution_status == ExecutionStatus.INVALID_DATA
    assert "cannot be identical" in result.discrepancy_reason
    print("[PASS] Test 18: Identical Baseline and Target Years")


# 19. Alias and Synonym Resolution
def test_alias_and_synonym_resolution():
    metrics_path = os.path.join(FIXTURES_DIR, "water_full.csv")
    claim = ExtractedClaim(
        metric="water consumption",
        claimed_percentage=1.97,
        baseline_year="FY23",
        target_year="FY24"
    )
    result = verify_claim(claim, metrics_path)
    assert result.status == "PASS"
    assert result.matched_metric == "Facility Water Usage"
    print("[PASS] Test 19: Alias and Synonym Resolution")


# 20. Non-Interference with Notes Columns
def test_non_interference_with_notes_columns():
    df = pd.DataFrame([
        {
            "metric_id": "MTR-001",
            "metric_name": "Scope 1 Direct Emissions",
            "fy23_value": 4200.0,
            "fy24_value": 4100.0,
            "fy24_notes": 99999.0,
            "yoy_change_pct": -2.38
        }
    ])
    col = resolve_year_column(list(df.columns), "FY24")
    assert col == "fy24_value"
    assert col != "fy24_notes"
    assert col != "yoy_change_pct"
    print("[PASS] Test 20: Non-Interference with Notes Columns")


def run_all_tests():
    print("==================================================")
    print("RUNNING TRACK 1 INTEGRATION TEST SUITE (20 SCENARIOS)")
    print("==================================================")
    test_demo_case_a_clean_pass()
    test_demo_case_b_flagged()
    test_wrong_metric_no_fallback()
    test_ambiguous_metric_detection()
    test_missing_metric_in_csv()
    test_missing_year_column()
    test_zero_baseline_division_guard()
    test_negative_claimed_percentage()
    test_over_100_percent_claimed_percentage()
    test_exact_tolerance_boundary_pass()
    test_tolerance_breach_boundary_flag()
    test_dynamic_fy24_to_fy25_years()
    test_four_digit_year_normalization()
    test_malformed_narrative_offline_fallback()
    test_extractor_api_failure_resilience()
    test_multiple_rules_aggregation_with_flags()
    test_empty_and_corrupt_csv_handling()
    test_identical_baseline_and_target_years()
    test_alias_and_synonym_resolution()
    test_non_interference_with_notes_columns()
    print("==================================================")
    print("ALL 20 TRACK 1 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
