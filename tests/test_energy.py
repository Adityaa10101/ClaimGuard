"""
ClaimGuard Test Suite — Energy Rules

Tests for:
- ENERGY_RENEWABLE_PCT_V1
- ENERGY_TOTAL_CHANGE_V1
- ENERGY_RENEWABLE_CROSSCHECK_V1
"""

import pytest
import pandas as pd
from src.schemas import Claim, ClaimCategory, ValidationStatus
from src.rules.energy import (
    EnergyRenewablePctRule,
    EnergyTotalChangeRule,
    EnergyRenewableCrosscheckRule,
)


class TestEnergyRenewablePct:
    """Test renewable energy percentage verification."""

    def setup_method(self):
        self.rule = EnergyRenewablePctRule()

    def test_correct_renewable_pct(self, energy_df):
        # Renewable: 52000, Total: 120000 → 43.33%
        claim = Claim(
            metric="Renewable Energy",
            category=ClaimCategory.ENERGY,
            reported_value=43.33,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, energy_df)
        assert result.status == ValidationStatus.PASS

    def test_incorrect_renewable_pct(self, energy_df):
        claim = Claim(
            metric="Renewable Energy",
            category=ClaimCategory.ENERGY,
            reported_value=60.0,  # Actually 43.33%
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, energy_df)
        assert result.status == ValidationStatus.FAIL
        assert result.variance > 15.0

    def test_missing_energy_data(self):
        claim = Claim(
            metric="Renewable Energy",
            category=ClaimCategory.ENERGY,
            reported_value=50.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        empty_df = pd.DataFrame(columns=["metric_name", "fy24_value"])
        result = self.rule.evaluate(claim, empty_df)
        assert result.status == ValidationStatus.UNSUPPORTED


class TestEnergyTotalChange:
    """Test total energy YoY change verification."""

    def setup_method(self):
        self.rule = EnergyTotalChangeRule()

    def test_zero_change_passes(self, energy_df):
        # Total: FY23=120000, FY24=120000 → 0% change
        claim = Claim(
            metric="Total Energy Consumption",
            category=ClaimCategory.ENERGY,
            reported_value=0.0,
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, energy_df)
        assert result.status == ValidationStatus.PASS

    def test_incorrect_change_fails(self, energy_df):
        claim = Claim(
            metric="Total Energy Consumption",
            category=ClaimCategory.ENERGY,
            reported_value=10.0,  # Actually 0%
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, energy_df)
        assert result.status == ValidationStatus.FAIL


class TestEnergyRenewableCrosscheck:
    """Test that renewable ≤ total energy."""

    def setup_method(self):
        self.rule = EnergyRenewableCrosscheckRule()

    def test_valid_renewable_total_passes(self, energy_df):
        claim = Claim(
            metric="Total Energy Consumption",
            category=ClaimCategory.ENERGY,
            reported_value=0.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, energy_df)
        assert result.status == ValidationStatus.PASS

    def test_renewable_exceeds_total_fails(self):
        bad_df = pd.DataFrame([
            {
                "metric_name": "Renewable Energy",
                "unit": "MWh",
                "fy24_value": 150000.0,
            },
            {
                "metric_name": "Total Energy Consumption",
                "unit": "MWh",
                "fy24_value": 120000.0,
            },
        ])
        claim = Claim(
            metric="Total Energy Consumption",
            category=ClaimCategory.ENERGY,
            reported_value=0.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, bad_df)
        assert result.status == ValidationStatus.FAIL
        assert "EXCEEDS" in result.explanation

    def test_missing_renewable_data_unsupported(self):
        partial_df = pd.DataFrame([{
            "metric_name": "Total Energy Consumption",
            "fy24_value": 120000.0,
        }])
        claim = Claim(
            metric="Total Energy Consumption",
            category=ClaimCategory.ENERGY,
            reported_value=0.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, partial_df)
        assert result.status == ValidationStatus.UNSUPPORTED
