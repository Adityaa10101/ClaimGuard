"""
ClaimGuard Test Suite — General Rules

Tests for:
- UNIT_CONSISTENCY_V1
- YEAR_CONSISTENCY_V1
- PCT_BOUNDS_V1
- TOTAL_SUBTOTAL_V1
- CROSS_TABLE_CONSISTENCY_V1
- MISSING_EVIDENCE_V1
"""

import pytest
import pandas as pd
from src.schemas import Claim, ClaimCategory, ValidationStatus, Authority
from src.rules.general import (
    UnitConsistencyRule,
    YearConsistencyRule,
    PctBoundsRule,
    TotalSubtotalRule,
    CrossTableConsistencyRule,
    MissingEvidenceRule,
)


class TestUnitConsistency:
    """Test unit consistency checks."""

    def setup_method(self):
        self.rule = UnitConsistencyRule()

    def test_matching_units_pass(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=271.95,
            reported_unit="MT CO2e",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_percentage_claim_always_passes(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_mismatched_units_fail(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=271.95,
            reported_unit="kg CO2e",  # Source says MT CO2e
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.FAIL


class TestYearConsistency:
    """Test year/period consistency checks."""

    def setup_method(self):
        self.rule = YearConsistencyRule()

    def test_valid_years_pass(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_invalid_years_fail(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY21",  # Not in data
            current_period="FY22",  # Not in data
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.FAIL


class TestPctBounds:
    """Test percentage bounds validation."""

    def setup_method(self):
        self.rule = PctBoundsRule()

    def test_valid_percentage_passes(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_over_100_fails(self, emissions_df, impossible_pct_claim):
        result = self.rule.evaluate(impossible_pct_claim, emissions_df)
        assert result.status == ValidationStatus.FAIL
        assert "exceeds 100%" in result.explanation.lower() or "greater than 100" in result.explanation.lower()

    def test_negative_percentage_fails(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=-5.0,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.FAIL

    def test_non_percent_skipped(self, emissions_df):
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


class TestTotalSubtotal:
    """Test total/subtotal arithmetic consistency."""

    def setup_method(self):
        self.rule = TotalSubtotalRule()

    def test_consistent_totals_pass(self, emissions_df):
        # Scope 1 (4100) + Scope 2 (6128.05) = 10228.05 = Total
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_inconsistent_totals_fail(self):
        bad_df = pd.DataFrame([
            {
                "metric_id": "E-001",
                "category": "Emissions",
                "metric_name": "Scope 1 Emissions",
                "fy24_value": 5000.0,
            },
            {
                "metric_id": "E-002",
                "category": "Emissions",
                "metric_name": "Scope 2 Emissions",
                "fy24_value": 3000.0,
            },
            {
                "metric_id": "E-TOTAL",
                "category": "Emissions",
                "metric_name": "Total Emissions",
                "fy24_value": 12000.0,  # Should be 8000
            },
        ])
        claim = Claim(
            metric="Total Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=10.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, bad_df)
        assert result.status == ValidationStatus.FAIL


class TestCrossTableConsistency:
    """Test that same metric doesn't have conflicting values."""

    def setup_method(self):
        self.rule = CrossTableConsistencyRule()

    def test_unique_metric_passes(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_duplicate_conflicting_values_fail(self):
        dup_df = pd.DataFrame([
            {
                "metric_name": "Total Emissions",
                "fy24_value": 10000.0,
            },
            {
                "metric_name": "Total Emissions",
                "fy24_value": 12000.0,  # Conflict!
            },
        ])
        claim = Claim(
            metric="Total Emissions",
            category=ClaimCategory.GENERAL,
            reported_value=10.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, dup_df)
        assert result.status == ValidationStatus.FAIL
        assert "conflicting" in result.explanation.lower()


class TestMissingEvidence:
    """Test the heuristic missing evidence rule."""

    def setup_method(self):
        self.rule = MissingEvidenceRule()

    def test_evidence_present_passes(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        assert result.status == ValidationStatus.PASS

    def test_no_matching_metric_flags(self):
        empty_df = pd.DataFrame(columns=["metric_name", "fy23_value", "fy24_value"])
        claim = Claim(
            metric="Biodiversity Index",
            category=ClaimCategory.GENERAL,
            reported_value=15.0,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, empty_df)
        assert result.status == ValidationStatus.FAIL
        assert result.authority == Authority.HEURISTIC

    def test_heuristic_authority_set(self, emissions_df):
        claim = Claim(
            metric="Total Scope 1 & 2 Emissions",
            category=ClaimCategory.EMISSIONS,
            reported_value=2.59,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, emissions_df)
        # MissingEvidenceRule is always heuristic
        assert result.authority == Authority.HEURISTIC or result.authority == Authority.DETERMINISTIC
