import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest
import pandas as pd
from src.extractor import extract_claim_from_narrative
from src.rules_engine import verify_claim

def create_mock_csv(tmp_path, recycled_val, usage_val, revenue_val):
    df = pd.DataFrame([
        {
            "metric_id": "MTR-W-002",
            "metric_name": "Facility Water Usage",
            "category": "Water",
            "fy23_value": usage_val,  # Required by engine
            "fy24_value": usage_val,
            "recycling_rate_fy24": (recycled_val/usage_val)*100,
            "revenue_fy24": revenue_val,
            "water_intensity_fy24": usage_val/revenue_val
        },
        {
            "metric_id": "MTR-W-003",
            "metric_name": "Recycled Water Volume",
            "category": "Water",
            "fy23_value": recycled_val, # Required by engine
            "fy24_value": recycled_val
        }
    ])
    csv_path = tmp_path / "metrics.csv"
    df.to_csv(csv_path, index=False)
    return str(csv_path)

def test_wt02_pass(tmp_path):
    csv_path = create_mock_csv(tmp_path, 35.0, 100.0, 10.0)
    narrative = "Our facility achieved a 35% recycling rate."
    claim = extract_claim_from_narrative(narrative)
    result = verify_claim(claim, csv_path)
    wt02_res = next((r for r in result.rule_results if r.rule_id == "WT-02"), None)
    assert wt02_res is not None
    assert wt02_res.status == "PASS"

def test_wt02_flag(tmp_path):
    csv_path = create_mock_csv(tmp_path, 25.0, 100.0, 10.0)
    narrative = "Our facility achieved a 35% recycling rate."
    claim = extract_claim_from_narrative(narrative)
    result = verify_claim(claim, csv_path)
    wt02_res = next((r for r in result.rule_results if r.rule_id == "WT-02"), None)
    assert wt02_res is not None
    assert wt02_res.status == "FLAGGED"

def test_wt03_pass(tmp_path):
    csv_path = create_mock_csv(tmp_path, 5.0, 24.0, 10.0)
    narrative = "Our water consumption intensity was 2.4 KL per crore of revenue."
    claim = extract_claim_from_narrative(narrative)
    result = verify_claim(claim, csv_path)
    wt03_res = next((r for r in result.rule_results if r.rule_id == "WT-03"), None)
    assert wt03_res is not None
    assert wt03_res.status == "PASS"

def test_wt03_flag(tmp_path):
    csv_path = create_mock_csv(tmp_path, 5.0, 31.0, 10.0)
    narrative = "Our water consumption intensity was 2.4 KL per crore of revenue."
    claim = extract_claim_from_narrative(narrative)
    result = verify_claim(claim, csv_path)
    wt03_res = next((r for r in result.rule_results if r.rule_id == "WT-03"), None)
    assert wt03_res is not None
    assert wt03_res.status == "FLAGGED"
