"""
ClaimGuard Test Suite — Shared fixtures and sample data.

Provides reusable pytest fixtures with realistic ESG data for testing
all 15 deterministic rules.
"""

import pytest
import pandas as pd
from src.schemas import Claim, ClaimCategory


# ─── Source Data Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def emissions_df():
    """Realistic emissions source data with Scope 1, Scope 2, and Total."""
    return pd.DataFrame([
        {
            "metric_id": "MTR-001",
            "category": "Emissions",
            "metric_name": "Scope 1 Direct Emissions",
            "unit": "MT CO2e",
            "fy23_value": 4200.00,
            "fy24_value": 4100.00,
            "yoy_change_pct": -2.38,
        },
        {
            "metric_id": "MTR-002",
            "category": "Emissions",
            "metric_name": "Scope 2 Indirect Emissions",
            "unit": "MT CO2e",
            "fy23_value": 6300.00,
            "fy24_value": 6128.05,
            "yoy_change_pct": -2.73,
        },
        {
            "metric_id": "MTR-TOTAL",
            "category": "Emissions",
            "metric_name": "Total Scope 1 & 2 Emissions",
            "unit": "MT CO2e",
            "fy23_value": 10500.00,
            "fy24_value": 10228.05,
            "yoy_change_pct": -2.59,
        },
    ])


@pytest.fixture
def energy_df():
    """Realistic energy source data with renewable, non-renewable, and total."""
    return pd.DataFrame([
        {
            "metric_id": "ENG-001",
            "category": "Energy",
            "metric_name": "Renewable Energy",
            "unit": "MWh",
            "fy23_value": 45000.0,
            "fy24_value": 52000.0,
            "yoy_change_pct": 15.56,
        },
        {
            "metric_id": "ENG-002",
            "category": "Energy",
            "metric_name": "Non-Renewable Energy",
            "unit": "MWh",
            "fy23_value": 75000.0,
            "fy24_value": 68000.0,
            "yoy_change_pct": -9.33,
        },
        {
            "metric_id": "ENG-TOTAL",
            "category": "Energy",
            "metric_name": "Total Energy Consumption",
            "unit": "MWh",
            "fy23_value": 120000.0,
            "fy24_value": 120000.0,
            "yoy_change_pct": 0.0,
        },
    ])


@pytest.fixture
def water_df():
    """Realistic water source data with consumption and recycling."""
    return pd.DataFrame([
        {
            "metric_id": "WTR-001",
            "category": "Water",
            "metric_name": "Facility Water Usage",
            "unit": "kGal",
            "fy23_value": 15200.00,
            "fy24_value": 14900.00,
            "yoy_change_pct": -1.97,
        },
        {
            "metric_id": "WTR-002",
            "category": "Water",
            "metric_name": "Water Recycled",
            "unit": "kGal",
            "fy23_value": 2800.00,
            "fy24_value": 3200.00,
            "yoy_change_pct": 14.29,
        },
    ])


@pytest.fixture
def full_df(emissions_df, energy_df, water_df):
    """Combined DataFrame with all categories."""
    waste_df = pd.DataFrame([
        {
            "metric_id": "WST-001",
            "category": "Waste",
            "metric_name": "Solid Waste Generated",
            "unit": "Tons",
            "fy23_value": 850.00,
            "fy24_value": 830.00,
            "yoy_change_pct": -2.35,
        },
    ])
    return pd.concat(
        [emissions_df, energy_df, water_df, waste_df],
        ignore_index=True,
    )


# ─── Claim Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def correct_emissions_claim():
    """A claim that matches the source data exactly (2.59% reduction)."""
    return Claim(
        company="Test Corp",
        metric="Total Scope 1 & 2 Emissions",
        category=ClaimCategory.EMISSIONS,
        reported_value=2.59,
        reported_unit="percent",
        previous_period="FY23",
        current_period="FY24",
        source_text="Achieved a 2.59% reduction in total emissions.",
    )


@pytest.fixture
def incorrect_emissions_claim():
    """A claim that contradicts source data (claims 20% but actual is 2.59%)."""
    return Claim(
        company="Test Corp",
        metric="Total Scope 1 & 2 Emissions",
        category=ClaimCategory.EMISSIONS,
        reported_value=20.0,
        reported_unit="percent",
        previous_period="FY23",
        current_period="FY24",
        source_text="Achieved a 20.00% reduction in total emissions.",
    )


@pytest.fixture
def correct_water_claim():
    """A water claim that matches source data (1.97% reduction)."""
    return Claim(
        company="Test Corp",
        metric="Facility Water Usage",
        category=ClaimCategory.WATER,
        reported_value=1.97,
        reported_unit="percent",
        previous_period="FY23",
        current_period="FY24",
        source_text="Water consumption reduced by 1.97%.",
    )


@pytest.fixture
def missing_metric_claim():
    """A claim referencing a metric not in the source data."""
    return Claim(
        company="Test Corp",
        metric="Biodiversity Index Score",
        category=ClaimCategory.GENERAL,
        reported_value=15.0,
        reported_unit="percent",
        previous_period="FY23",
        current_period="FY24",
        source_text="Improved biodiversity index by 15%.",
    )


@pytest.fixture
def impossible_pct_claim():
    """A claim with a percentage > 100% (physically impossible)."""
    return Claim(
        company="Test Corp",
        metric="Total Scope 1 & 2 Emissions",
        category=ClaimCategory.EMISSIONS,
        reported_value=150.0,
        reported_unit="percent",
        previous_period="FY23",
        current_period="FY24",
        source_text="Achieved a 150% reduction in emissions.",
    )
