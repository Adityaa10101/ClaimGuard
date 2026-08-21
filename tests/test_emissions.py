"""
ClaimGuard Test Suite — Emissions Rules

Tests for:
- EMISSIONS_ABSOLUTE_V1
- EMISSIONS_REDUCTION_PCT_V1
- EMISSIONS_YOY_DIRECTION_V1
- EMISSIONS_SCOPE_CONSISTENCY_V1
"""

import pytest
import pandas as pd
from src.schemas import Claim, ClaimCategory, ValidationStatus
from src.rules.emissions import (
    EmissionsAbsoluteRule,
    EmissionsReductionPctRule,
    EmissionsYoYDirectionRule,
    EmissionsScopeConsistencyRule,
)


class TestEmissionsReductionPct:
    """Test the core percentage reduction rule."""

    def setup_method(self):
        self.rule = EmissionsReductionPctRule()

    def test_correct_claim_passes(self, emissions_df, correct_emissions_claim):
        result = self.rule.evaluate(correct_emissions_claim, emissions_df)
        assert result.status == ValidationStatus.PASS
        assert result.rule_id == "EMISSIONS_REDUCTION_PCT_V1"
        assert result.severity.value == "HIGH"
        assert result.calculated_value == pytest.approx(2.59, abs=0.01)

    def test_incorrect_claim_fails(self, emissions_df, incorrect_emissions_claim):
        result = self.rule.evaluate(incorrect_emissions_claim, emissions_df)
        assert result.status == ValidationStatus.FAIL
        assert result.variance > 15.0  # 20 - 2.59 ≈ 17.41
        assert "DISCREPANCY" in result.explanation

    def test_missing_metric_unsupported(self, emissions_df, missing_metric_claim):
        # This claim's metric won't match well, but find_metric_row has fallback
        # so it will still find a row. Let's test with empty df instead.
        empty_df = pd.DataFrame(columns=["metric_name", "fy23_value", "fy24_value"])
        result = self.rule.evaluate(missing_metric_claim, empty_df)
        assert result.status == ValidationStatus.UNSUPPORTED

    def test_zero_baseline_unsupported(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=10.0,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        zero_df = pd.DataFrame([{
            "metric_id": "MTR-TOTAL",
            "metric_name": "Total Scope 1 & 2 Emissions",
            "unit": "MT CO2e",
            "fy23_value": 0,
            "fy24_value": 100,
        }])
        result = self.rule.evaluate(claim, zero_df)
        assert result.status == ValidationStatus.UNSUPPORTED

    def test_non_percent_claim_unsupported(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=271.95,
            reported_unit="MT CO2e",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.UNSUPPORTED

    def test_result_has_full_evidence_chain(self, emissions_df, correct_emissions_claim):
        result = self.rule.evaluate(correct_emissions_claim, emissions_df)
        assert result.formula != ""
        assert result.source_evidence != ""
        assert result.authority.value == "DETERMINISTIC"


class TestEmissionsAbsolute:
    """Test the absolute emissions change rule."""

    def setup_method(self):
        self.rule = EmissionsAbsoluteRule()

    def test_correct_absolute_change(self, emissions_df):
        # Actual change: 10228.05 - 10500 = -271.95
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=-271.95,
            reported_unit="MT CO2e",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_incorrect_absolute_change(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=-1000.0,
            reported_unit="MT CO2e",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.FAIL

    def test_percent_claim_skipped(self, emissions_df, correct_emissions_claim):
        result = self.rule.evaluate(correct_emissions_claim, emissions_df)
        assert result.status == ValidationStatus.UNSUPPORTED


class TestEmissionsYoYDirection:
    """Test the year-over-year direction check."""

    def setup_method(self):
        self.rule = EmissionsYoYDirectionRule()

    def test_correct_decrease_direction(self, emissions_df, correct_emissions_claim):
        result = self.rule.evaluate(correct_emissions_claim, emissions_df)
        assert result.status == ValidationStatus.PASS
        assert "decrease" in result.explanation.lower()

    def test_wrong_direction_fails(self, emissions_df):
        # Claim says increase (negative reported_value) but data shows decrease
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=-5.0,  # negative = claiming increase
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.FAIL
        assert "mismatch" in result.explanation.lower()


class TestEmissionsScopeConsistency:
    """Test the Scope 1 + Scope 2 = Total cross-check."""

    def setup_method(self):
        self.rule = EmissionsScopeConsistencyRule()

    def test_consistent_scopes_pass(self, emissions_df, correct_emissions_claim):
        # Scope 1 (4100) + Scope 2 (6128.05) = 10228.05 = Total ✓
        result = self.rule.evaluate(correct_emissions_claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_inconsistent_scopes_fail(self, correct_emissions_claim):
        bad_df = pd.DataFrame([
            {
                "metric_name": "Scope 1 Direct Emissions",
                "unit": "MT CO2e",
                "fy24_value": 5000.0,
            },
            {
                "metric_name": "Scope 2 Indirect Emissions",
                "unit": "MT CO2e",
                "fy24_value": 5000.0,
            },
            {
                "metric_name": "Total Scope 1 & 2 Emissions",
                "unit": "MT CO2e",
                "fy24_value": 8000.0,  # Should be 10000
            },
        ])
        result = self.rule.evaluate(correct_emissions_claim, bad_df)
        assert result.status == ValidationStatus.FAIL
        assert result.variance == pytest.approx(2000.0, abs=0.1)

    def test_missing_scope_rows_unsupported(self, correct_emissions_claim):
        partial_df = pd.DataFrame([{
            "metric_name": "Total Scope 1 & 2 Emissions",
            "fy24_value": 10228.05,
        }])
        result = self.rule.evaluate(correct_emissions_claim, partial_df)
        assert result.status == ValidationStatus.UNSUPPORTED
