"""
ClaimGuard Test Suite — End-to-End Pipeline

Tests the full pipeline:
PDF/Text → Claim Extraction → Rules Engine → Audit Report
"""

import pytest
import pandas as pd
from src.schemas import (
    Claim, ClaimCategory, ValidationStatus,
    AuditReport, ExtractedClaim,
)
from src.rules import create_default_engine
from src.extractor import extract_claims_from_narrative, extract_claim_from_narrative
from src.rules_engine import verify_claim


class TestRuleEngineIntegration:
    """Test the full rule engine with multiple claims."""

    def test_engine_has_15_rules(self):
        engine = create_default_engine()
        assert engine.rule_count == 15

    def test_evaluate_all_produces_report(self, emissions_df, correct_emissions_claim):
        engine = create_default_engine()
        report = engine.evaluate_all(
            claims=[correct_emissions_claim],
            source_data=emissions_df,
            company="Test Corp",
            filing_period="FY24",
        )
        assert isinstance(report, AuditReport)
        assert report.company == "Test Corp"
        assert report.summary.total_claims == 1
        assert len(report.results) > 0
        assert report.processing_time.validation_s >= 0

    def test_correct_claim_mostly_passes(self, emissions_df, correct_emissions_claim):
        engine = create_default_engine()
        report = engine.evaluate_all(
            claims=[correct_emissions_claim],
            source_data=emissions_df,
        )
        # The correct claim should pass most rules
        assert report.summary.passed > 0
        assert report.summary.high_severity_failures == 0

    def test_incorrect_claim_has_failures(self, emissions_df, incorrect_emissions_claim):
        engine = create_default_engine()
        report = engine.evaluate_all(
            claims=[incorrect_emissions_claim],
            source_data=emissions_df,
        )
        assert report.summary.failed > 0
        assert report.summary.high_severity_failures > 0

    def test_multiple_claims_evaluated(self, full_df):
        claims = [
            Claim(
                company="Test Corp",
                metric="Total Scope 1 & 2 Emissions",
                category=ClaimCategory.EMISSIONS,
                reported_value=2.59,
                reported_unit="percent",
                previous_period="FY23",
                current_period="FY24",
            ),
            Claim(
                company="Test Corp",
                metric="Facility Water Usage",
                category=ClaimCategory.WATER,
                reported_value=1.97,
                reported_unit="percent",
                previous_period="FY23",
                current_period="FY24",
            ),
        ]
        engine = create_default_engine()
        report = engine.evaluate_all(
            claims=claims,
            source_data=full_df,
            company="Test Corp",
            filing_period="FY24",
        )
        assert report.summary.total_claims == 2
        assert len(report.results) > 2  # Multiple rules per claim

    def test_report_has_processing_time(self, emissions_df, correct_emissions_claim):
        engine = create_default_engine()
        report = engine.evaluate_all(
            claims=[correct_emissions_claim],
            source_data=emissions_df,
        )
        assert report.processing_time.validation_s > 0
        assert report.processing_time.total_s > 0


class TestExtractorIntegration:
    """Test the claim extractor with realistic narratives."""

    def test_extract_single_claim_from_clean_narrative(self):
        narrative = (
            "Achieved a 2.59% reduction in total Scope 1 & Scope 2 "
            "greenhouse gas emissions in FY24 compared to FY23 baseline."
        )
        claims = extract_claims_from_narrative(narrative, company="Test Corp")
        assert len(claims) >= 1
        assert claims[0].reported_value == pytest.approx(2.59, abs=0.01)
        assert claims[0].category == ClaimCategory.EMISSIONS

    def test_extract_claim_detects_years(self):
        narrative = "Emissions reduced by 15% in FY25 compared to FY24."
        claims = extract_claims_from_narrative(narrative)
        assert len(claims) >= 1
        assert claims[0].previous_period == "FY24"
        assert claims[0].current_period == "FY25"

    def test_extract_multiple_claims(self):
        narrative = (
            "Key achievements:\n"
            "- 2.59% reduction in Scope 1 & 2 emissions in FY24 vs FY23.\n"
            "- 1.97% decrease in water consumption year-over-year.\n"
            "- 2.35% reduction in solid waste generated.\n"
        )
        claims = extract_claims_from_narrative(narrative, company="Multi Corp")
        assert len(claims) >= 2  # Should find at least 2 claims

    def test_legacy_extract_claim_from_narrative(self):
        narrative = "Achieved a 20.00% reduction in total emissions in FY24 compared to FY23."
        claim = extract_claim_from_narrative(narrative)
        assert isinstance(claim, ExtractedClaim)
        assert claim.claimed_percentage == pytest.approx(20.0, abs=0.1)


class TestBackwardCompatibility:
    """Test that the legacy verify_claim API still works."""

    def test_legacy_clean_preset_passes(self):
        claim = ExtractedClaim(
            metric="Total Scope 1 & 2 Emissions",
            claimed_percentage=2.59,
            baseline_year="FY23",
            target_year="FY24",
            claim_text="Achieved a 2.59% reduction.",
        )
        df = pd.DataFrame([{
            "metric_id": "MTR-TOTAL",
            "category": "Emissions",
            "metric_name": "Total Scope 1 & 2 Emissions",
            "unit": "MT CO2e",
            "fy23_value": 10500.00,
            "fy24_value": 10228.05,
        }])
        result = verify_claim(claim, df)
        assert result.status == "PASS"
        assert result.calculated_delta == pytest.approx(2.59, abs=0.01)

    def test_legacy_flagged_preset_fails(self):
        claim = ExtractedClaim(
            metric="Total Scope 1 & 2 Emissions",
            claimed_percentage=20.0,
            baseline_year="FY23",
            target_year="FY24",
            claim_text="Achieved a 20% reduction.",
        )
        df = pd.DataFrame([{
            "metric_id": "MTR-TOTAL",
            "category": "Emissions",
            "metric_name": "Total Scope 1 & 2 Emissions",
            "unit": "MT CO2e",
            "fy23_value": 10500.00,
            "fy24_value": 10228.05,
        }])
        result = verify_claim(claim, df)
        assert result.status == "FLAGGED"
        assert result.variance > 15.0

    def test_legacy_to_claim_conversion(self):
        legacy = ExtractedClaim(
            metric="Total Scope 1 & 2 Emissions",
            claimed_percentage=2.59,
            baseline_year="FY23",
            target_year="FY24",
        )
        claim = legacy.to_claim(company="Test Corp")
        assert isinstance(claim, Claim)
        assert claim.reported_value == 2.59
        assert claim.company == "Test Corp"
        assert claim.category == ClaimCategory.EMISSIONS
