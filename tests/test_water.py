"""
ClaimGuard Test Suite — Water Rules

Tests for:
- WATER_CONSUMPTION_CHANGE_V1
- WATER_RECYCLING_PCT_V1
"""

import pytest
import pandas as pd
from src.schemas import Claim, ClaimCategory, ValidationStatus
from src.rules.water import (
    WaterConsumptionChangeRule,
    WaterRecyclingPctRule,
)


class TestWaterConsumptionChange:
    """Test water consumption YoY change verification."""

    def setup_method(self):
        self.rule = WaterConsumptionChangeRule()

    def test_correct_water_change(self, water_df, correct_water_claim):
        result = self.rule.evaluate(correct_water_claim, water_df)
        assert result.status == ValidationStatus.PASS
        assert result.calculated_value == pytest.approx(1.97, abs=0.01)

    def test_incorrect_water_change(self, water_df):
        claim = Claim(
            metric="Facility Water Usage",
            category=ClaimCategory.WATER,
            reported_value=10.0,  # Actually 1.97%
            reported_unit="percent",
            previous_period="FY23",
            current_period="FY24",
        )
        result = self.rule.evaluate(claim, water_df)
        assert result.status == ValidationStatus.FAIL
        assert result.variance > 7.0

    def test_missing_water_data(self, correct_water_claim):
        empty_df = pd.DataFrame(columns=["metric_name", "fy23_value", "fy24_value"])
        result = self.rule.evaluate(correct_water_claim, empty_df)
        assert result.status == ValidationStatus.UNSUPPORTED


class TestWaterRecyclingPct:
    """Test water recycling percentage verification."""

    def setup_method(self):
        self.rule = WaterRecyclingPctRule()

    def test_correct_recycling_pct(self, water_df):
        # Recycled: 3200, Total: 14900 → 21.48%
        claim = Claim(
            metric="Water Recycled",
            category=ClaimCategory.WATER,
            reported_value=21.48,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, water_df)
        assert result.status == ValidationStatus.PASS

    def test_incorrect_recycling_pct(self, water_df):
        claim = Claim(
            metric="Water Recycled",
            category=ClaimCategory.WATER,
            reported_value=40.0,  # Actually ~21.48%
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, water_df)
        assert result.status == ValidationStatus.FAIL

    def test_missing_recycling_data(self):
        partial_df = pd.DataFrame([{
            "metric_name": "Facility Water Usage",
            "fy24_value": 14900.0,
        }])
        claim = Claim(
            metric="Water Recycled",
            category=ClaimCategory.WATER,
            reported_value=20.0,
            reported_unit="percent",
            current_period="FY24",
            previous_period="FY23",
        )
        result = self.rule.evaluate(claim, partial_df)
        assert result.status == ValidationStatus.UNSUPPORTED
