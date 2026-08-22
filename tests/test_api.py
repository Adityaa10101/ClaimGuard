"""
ClaimGuard API — Integration & Unit Tests

Tests the FastAPI /health, /rules, and /audit endpoints using TestClient.
Primary audit tests exercise the full pipeline (extractor → rules_engine → AuditResult)
to validate end-to-end behavior matches the existing verified engine.
"""

import os
import sys

# Ensure project root is importable
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ──────────────────────────────────────────────
# Fixture Helpers
# ──────────────────────────────────────────────

DEMO_A_NARRATIVE = (
    "ANNUAL SUSTAINABILITY & PERFORMANCE REPORT FY24 - CLAIMGUARD CORP\n\n"
    "EXECUTIVE SUMMARY & KEY CLAIMS:\n"
    "During Fiscal Year 2024 (FY24), ClaimGuard Corp continued its commitment "
    "to operational efficiency and environmental stewardship across all facilities.\n\n"
    "Key Achievement:\n"
    "- Achieved a 2.59% reduction in total Scope 1 & Scope 2 greenhouse gas emissions "
    "across operating regions in FY24 compared to FY23 baseline performance.\n\n"
    "Details:\n"
    "In FY23, aggregate emissions measured 10,500.00 metric tons CO2e across all data "
    "centers and corporate hub facilities. Through targeted energy efficiency retrofits, "
    "renewable energy purchases, and optimized server workload routing, total emissions "
    "for FY24 dropped to 10,228.05 metric tons CO2e. This represents a net reduction of "
    "271.95 metric tons CO2e, or exactly a 2.59% decrease year-over-year.\n\n"
    "We remain dedicated to transparent, verified reporting of all key performance indicators."
)

DEMO_A_METRICS = [
    {
        "metric_id": "MTR-001",
        "category": "Emissions",
        "metric_name": "Scope 1 Direct Emissions",
        "unit": "MT CO2e",
        "fy23_value": 4200.00,
        "fy24_value": 4100.00,
        "yoy_change_pct": -2.38,
        "notes": "Fuel and company vehicle fleet",
    },
    {
        "metric_id": "MTR-002",
        "category": "Emissions",
        "metric_name": "Scope 2 Indirect Emissions",
        "unit": "MT CO2e",
        "fy23_value": 6300.00,
        "fy24_value": 6128.05,
        "yoy_change_pct": -2.73,
        "notes": "Purchased electricity for facilities",
    },
    {
        "metric_id": "MTR-TOTAL",
        "category": "Emissions",
        "metric_name": "Total Scope 1 & 2 Emissions",
        "unit": "MT CO2e",
        "fy23_value": 10500.00,
        "fy24_value": 10228.05,
        "yoy_change_pct": -2.59,
        "notes": "Combined total emissions",
    },
    {
        "metric_id": "MTR-003",
        "category": "Water",
        "metric_name": "Facility Water Usage",
        "unit": "kGal",
        "fy23_value": 15200.00,
        "fy24_value": 14900.00,
        "yoy_change_pct": -1.97,
        "notes": "Cooling and domestic water consumption",
    },
    {
        "metric_id": "MTR-004",
        "category": "Waste",
        "metric_name": "Solid Waste Generated",
        "unit": "Tons",
        "fy23_value": 850.00,
        "fy24_value": 830.00,
        "yoy_change_pct": -2.35,
        "notes": "Recycled and landfilled waste",
    },
]

DEMO_B_NARRATIVE = (
    "ANNUAL SUSTAINABILITY & PERFORMANCE REPORT FY24 - CLAIMGUARD CORP\n\n"
    "EXECUTIVE SUMMARY & KEY CLAIMS:\n"
    "During Fiscal Year 2024 (FY24), ClaimGuard Corp achieved unprecedented "
    "sustainability milestones through aggressive decarbonization initiatives.\n\n"
    "Key Achievement:\n"
    "- Achieved a 20.00% reduction in total Scope 1 & Scope 2 greenhouse gas emissions "
    "across operating regions in FY24 compared to FY23 baseline performance.\n\n"
    "Details:\n"
    "Through aggressive facility automation and clean energy transitions, our "
    "operational emissions dropped significantly. We are proud to announce a headline "
    "reduction of 20% year-over-year, setting a new benchmark for industry sustainability "
    "leadership.\n\n"
    "We remain dedicated to transparent, verified reporting of all key performance indicators."
)

# Demo B uses same metrics as Demo A but with inflated narrative claim
DEMO_B_METRICS = [
    {
        "metric_id": "MTR-001",
        "category": "Emissions",
        "metric_name": "Scope 1 Direct Emissions",
        "unit": "MT CO2e",
        "fy23_value": 4200.00,
        "fy24_value": 4100.00,
        "yoy_change_pct": -2.38,
        "notes": "Fuel and company vehicle fleet",
    },
    {
        "metric_id": "MTR-002",
        "category": "Emissions",
        "metric_name": "Scope 2 Indirect Emissions",
        "unit": "MT CO2e",
        "fy23_value": 6300.00,
        "fy24_value": 6128.05,
        "yoy_change_pct": -2.73,
        "notes": "Purchased electricity for facilities",
    },
    {
        "metric_id": "MTR-TOTAL",
        "category": "Emissions",
        "metric_name": "Total Scope 1 & 2 Emissions",
        "unit": "MT CO2e",
        "fy23_value": 10500.00,
        "fy24_value": 10228.05,
        "yoy_change_pct": -2.59,
        "notes": "Combined total emissions",
    },
    {
        "metric_id": "MTR-003",
        "category": "Water",
        "metric_name": "Facility Water Usage",
        "unit": "kGal",
        "fy23_value": 15200.00,
        "fy24_value": 14900.00,
        "yoy_change_pct": -1.97,
        "notes": "Cooling and domestic water consumption",
    },
    {
        "metric_id": "MTR-004",
        "category": "Waste",
        "metric_name": "Solid Waste Generated",
        "unit": "Tons",
        "fy23_value": 850.00,
        "fy24_value": 830.00,
        "yoy_change_pct": -2.35,
        "notes": "Recycled and landfilled waste",
    },
]


# ──────────────────────────────────────────────
# 1. Health Check
# ──────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_correct_structure(self):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "ClaimGuard API"
        assert data["version"] == "1.0.0"
        assert data["rules_loaded"] == 15


# ──────────────────────────────────────────────
# 2. Rules Listing
# ──────────────────────────────────────────────

EXPECTED_RULE_IDS = [
    "EM-01", "EM-02", "EM-03", "EM-04", "EM-05",
    "EN-01", "EN-02", "EN-03", "EN-04",
    "GEN-01", "GEN-02", "GEN-03",
    "WT-01", "WT-02", "WT-03",
]


class TestRules:
    def test_rules_returns_200(self):
        resp = client.get("/rules")
        assert resp.status_code == 200

    def test_rules_total_is_15(self):
        resp = client.get("/rules")
        data = resp.json()
        assert data["total"] == 15

    def test_rules_all_ids_present(self):
        resp = client.get("/rules")
        data = resp.json()
        returned_ids = sorted([r["rule_id"] for r in data["rules"]])
        assert returned_ids == sorted(EXPECTED_RULE_IDS)

    def test_rules_have_required_fields(self):
        resp = client.get("/rules")
        data = resp.json()
        for rule in data["rules"]:
            assert "rule_id" in rule
            assert "domain" in rule
            assert "name" in rule
            assert rule["domain"] in ["Emissions", "Energy", "Water", "General"]


# ──────────────────────────────────────────────
# 3. Audit — Demo A (PASS)
# ──────────────────────────────────────────────

class TestAuditDemoA:
    def test_demo_a_returns_200(self):
        resp = client.post("/audit", json={
            "narrative": DEMO_A_NARRATIVE,
            "metrics": DEMO_A_METRICS,
        })
        assert resp.status_code == 200

    def test_demo_a_is_pass(self):
        resp = client.post("/audit", json={
            "narrative": DEMO_A_NARRATIVE,
            "metrics": DEMO_A_METRICS,
        })
        data = resp.json()
        assert data["status"] == "PASS"
        assert data["audit_decision"] == "PASS"

    def test_demo_a_variance_near_zero(self):
        resp = client.post("/audit", json={
            "narrative": DEMO_A_NARRATIVE,
            "metrics": DEMO_A_METRICS,
        })
        data = resp.json()
        assert abs(data["variance"]) < 0.1

    def test_demo_a_serialization_complete(self):
        """Verify all required fields serialize correctly."""
        resp = client.post("/audit", json={
            "narrative": DEMO_A_NARRATIVE,
            "metrics": DEMO_A_METRICS,
        })
        data = resp.json()
        # Core fields
        assert "status" in data
        assert "claimed_percentage" in data
        assert "calculated_delta" in data
        assert "variance" in data
        assert "discrepancy_reason" in data
        assert "matched_metric" in data
        assert "baseline_year" in data
        assert "target_year" in data
        assert "baseline_value" in data
        assert "target_value" in data
        assert "fy23_value" in data
        assert "fy24_value" in data
        # Extended fields
        assert "audit_decision" in data
        assert "execution_status" in data
        assert "summary" in data
        assert "rule_results" in data
        # Nested structure verification
        assert isinstance(data["summary"], dict)
        assert isinstance(data["rule_results"], list)
        assert len(data["rule_results"]) > 0
        # Verify evidence serialization in rule results
        for rr in data["rule_results"]:
            assert "rule_id" in rr
            assert "domain" in rr
            assert "status" in rr
            assert "message" in rr
            assert "evidence" in rr


# ──────────────────────────────────────────────
# 4. Audit — Demo B (FLAGGED)
# ──────────────────────────────────────────────

class TestAuditDemoB:
    def test_demo_b_returns_200(self):
        """FLAGGED is a valid audit result — HTTP 200, not an error."""
        resp = client.post("/audit", json={
            "narrative": DEMO_B_NARRATIVE,
            "metrics": DEMO_B_METRICS,
        })
        assert resp.status_code == 200

    def test_demo_b_is_flagged(self):
        resp = client.post("/audit", json={
            "narrative": DEMO_B_NARRATIVE,
            "metrics": DEMO_B_METRICS,
        })
        data = resp.json()
        assert data["status"] == "FLAGGED"
        assert data["audit_decision"] == "FLAGGED"

    def test_demo_b_variance_approximately_17_41(self):
        resp = client.post("/audit", json={
            "narrative": DEMO_B_NARRATIVE,
            "metrics": DEMO_B_METRICS,
        })
        data = resp.json()
        assert abs(data["variance"] - 17.41) < 0.1


# ──────────────────────────────────────────────
# 5. Audit — Dynamic FY24 → FY25
# ──────────────────────────────────────────────

class TestAuditDynamicYears:
    def test_fy24_fy25_pass(self):
        narrative = (
            "In FY25 compared to FY24 baseline, our company achieved a 15% reduction "
            "in total Scope 1 & Scope 2 emissions across all operating regions."
        )
        metrics = [
            {
                "metric_id": "MTR-TOTAL",
                "category": "Emissions",
                "metric_name": "Total Scope 1 & 2 Emissions",
                "unit": "MT CO2e",
                "fy24_value": 20000.0,
                "fy25_value": 17000.0,
                "yoy_change_pct": -15.0,
            }
        ]
        resp = client.post("/audit", json={
            "narrative": narrative,
            "metrics": metrics,
        })
        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "PASS"
        assert data["baseline_year"] == "FY24"
        assert data["target_year"] == "FY25"
        assert data["calculated_delta"] == 15.0


# ──────────────────────────────────────────────
# 6. Audit — Water Recycling (WT-02)
# ──────────────────────────────────────────────

class TestAuditWaterRecycling:
    def test_wt02_present_and_correct(self):
        """E2E: extractor parses recycling rate → engine runs WT-02."""
        narrative = "Our facility achieved a 35% recycling rate."
        metrics = [
            {
                "metric_id": "MTR-W-002",
                "category": "Water",
                "metric_name": "Facility Water Usage",
                "unit": "kGal",
                "fy23_value": 100.0,
                "fy24_value": 100.0,
                "recycling_rate_fy24": 35.0,
                "revenue_fy24": 10.0,
                "water_intensity_fy24": 10.0,
            },
            {
                "metric_id": "MTR-W-003",
                "category": "Water",
                "metric_name": "Recycled Water Volume",
                "unit": "kGal",
                "fy23_value": 35.0,
                "fy24_value": 35.0,
            },
        ]
        resp = client.post("/audit", json={
            "narrative": narrative,
            "metrics": metrics,
        })
        data = resp.json()
        assert resp.status_code == 200
        wt02 = next(
            (r for r in data["rule_results"] if r["rule_id"] == "WT-02"),
            None,
        )
        assert wt02 is not None, "WT-02 rule result missing from API response"


# ──────────────────────────────────────────────
# 7. Audit — Water Intensity (WT-03)
# ──────────────────────────────────────────────

class TestAuditWaterIntensity:
    def test_wt03_present_and_correct(self):
        """E2E: extractor parses water intensity → engine runs WT-03."""
        narrative = "Our water consumption intensity was 2.4 KL per crore of revenue."
        metrics = [
            {
                "metric_id": "MTR-W-002",
                "category": "Water",
                "metric_name": "Facility Water Usage",
                "unit": "kGal",
                "fy23_value": 24.0,
                "fy24_value": 24.0,
                "recycling_rate_fy24": 20.83,
                "revenue_fy24": 10.0,
                "water_intensity_fy24": 2.4,
            },
            {
                "metric_id": "MTR-W-003",
                "category": "Water",
                "metric_name": "Recycled Water Volume",
                "unit": "kGal",
                "fy23_value": 5.0,
                "fy24_value": 5.0,
            },
        ]
        resp = client.post("/audit", json={
            "narrative": narrative,
            "metrics": metrics,
        })
        data = resp.json()
        assert resp.status_code == 200
        wt03 = next(
            (r for r in data["rule_results"] if r["rule_id"] == "WT-03"),
            None,
        )
        assert wt03 is not None, "WT-03 rule result missing from API response"


# ──────────────────────────────────────────────
# 8. Audit — Extended 15-rule Fixture
# ──────────────────────────────────────────────

class TestAuditExtendedFixture:
    def test_accepts_extended_columns(self):
        """Verify MetricRecord extra='allow' passes extended columns through."""
        narrative = (
            "Achieved a 2.59% reduction in total Scope 1 & Scope 2 greenhouse gas "
            "emissions in FY24 compared to FY23."
        )
        metrics = [
            {
                "metric_id": "MTR-001",
                "category": "Emissions",
                "metric_name": "Scope 1 Direct Emissions",
                "unit": "MT CO2e",
                "fy23_value": 4200.00,
                "fy24_value": 4100.00,
                "fy25_value": 4000.00,
                "yoy_change_pct": -2.38,
                "notes": "Fuel and company fleet",
            },
            {
                "metric_id": "MTR-002",
                "category": "Emissions",
                "metric_name": "Scope 2 Indirect Emissions",
                "unit": "MT CO2e",
                "fy23_value": 6300.00,
                "fy24_value": 6128.05,
                "fy25_value": 6000.00,
                "yoy_change_pct": -2.73,
                "notes": "Purchased electricity",
            },
            {
                "metric_id": "MTR-TOTAL",
                "category": "Emissions",
                "metric_name": "Total Scope 1 & 2 Emissions",
                "unit": "MT CO2e",
                "fy23_value": 10500.00,
                "fy24_value": 10228.05,
                "fy25_value": 10000.00,
                "yoy_change_pct": -2.59,
                "notes": "Combined total emissions",
                "restated_fy23_value": 10500.00,
                "absolute_target_fy24": 10228.05,
            },
            {
                "metric_id": "MTR-005",
                "category": "Emissions",
                "metric_name": "Scope 3 Value Chain Emissions",
                "unit": "MT CO2e",
                "fy23_value": 45000.00,
                "fy24_value": 44100.00,
                "fy25_value": 43000.00,
                "yoy_change_pct": -2.00,
                "notes": "Supply chain and logistics",
                "scope3_upstream_fy24": 20000.00,
                "scope3_downstream_fy24": 24100.00,
                "scope3_total_fy24": 44100.00,
            },
        ]
        resp = client.post("/audit", json={
            "narrative": narrative,
            "metrics": metrics,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PASS"


# ──────────────────────────────────────────────
# 9. Missing Data → UNVERIFIED / MISSING_DATA
# ──────────────────────────────────────────────

class TestAuditMissingData:
    def test_missing_metric_returns_unverified(self):
        """Narrative claims metric not present in ground truth → UNVERIFIED."""
        narrative = (
            "Achieved a 10% reduction in total Scope 1 & Scope 2 greenhouse gas "
            "emissions in FY24 compared to FY23."
        )
        # Provide metrics that don't include emissions at all
        metrics = [
            {
                "metric_id": "MTR-WATER",
                "category": "Water",
                "metric_name": "Facility Water Usage",
                "unit": "kGal",
                "fy23_value": 100.0,
                "fy24_value": 90.0,
            },
        ]
        resp = client.post("/audit", json={
            "narrative": narrative,
            "metrics": metrics,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["audit_decision"] == "UNVERIFIED"
        assert data["execution_status"] == "MISSING_DATA"


# ──────────────────────────────────────────────
# 10. Invalid Data → UNVERIFIED / INVALID_DATA
# ──────────────────────────────────────────────

class TestAuditInvalidData:
    def test_zero_baseline_returns_unverified(self):
        """Zero baseline value → cannot compute delta → UNVERIFIED."""
        narrative = (
            "Achieved a 10% reduction in total Scope 1 & Scope 2 greenhouse gas "
            "emissions in FY24 compared to FY23."
        )
        metrics = [
            {
                "metric_id": "MTR-TOTAL",
                "category": "Emissions",
                "metric_name": "Total Scope 1 & 2 Emissions",
                "unit": "MT CO2e",
                "fy23_value": 0.0,
                "fy24_value": 500.0,
            },
        ]
        resp = client.post("/audit", json={
            "narrative": narrative,
            "metrics": metrics,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["audit_decision"] == "UNVERIFIED"
        assert data["execution_status"] == "INVALID_DATA"


# ──────────────────────────────────────────────
# 11. Malformed Request → HTTP 422
# ──────────────────────────────────────────────

class TestMalformedRequest:
    def test_missing_narrative_returns_422(self):
        resp = client.post("/audit", json={
            "metrics": DEMO_A_METRICS,
        })
        assert resp.status_code == 422

    def test_missing_metrics_returns_422(self):
        resp = client.post("/audit", json={
            "narrative": "Some claim text",
        })
        assert resp.status_code == 422

    def test_empty_narrative_returns_422(self):
        resp = client.post("/audit", json={
            "narrative": "",
            "metrics": DEMO_A_METRICS,
        })
        assert resp.status_code == 422

    def test_empty_metrics_returns_422(self):
        resp = client.post("/audit", json={
            "narrative": "Some claim text",
            "metrics": [],
        })
        assert resp.status_code == 422

    def test_malformed_metric_returns_422(self):
        resp = client.post("/audit", json={
            "narrative": "Some claim text",
            "metrics": [{"bad_field": "value"}],
        })
        assert resp.status_code == 422

    def test_no_body_returns_422(self):
        resp = client.post("/audit")
        assert resp.status_code == 422


# ──────────────────────────────────────────────
# 12. Internal Engine Failure → HTTP 500
# ──────────────────────────────────────────────

class TestInternalFailure:
    def test_engine_crash_returns_500(self):
        """Mock verify_claim to raise, confirm HTTP 500 with safe message."""
        with patch("api.main.verify_claim", side_effect=RuntimeError("simulated crash")):
            resp = client.post("/audit", json={
                "narrative": DEMO_A_NARRATIVE,
                "metrics": DEMO_A_METRICS,
            })
            assert resp.status_code == 500
            data = resp.json()
            assert "detail" in data
            # Must NOT contain stack traces or sensitive info
            assert "simulated crash" not in data["detail"]
            assert "Internal" in data["detail"]
