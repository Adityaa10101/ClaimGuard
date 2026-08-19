import pandas as pd
from src.schemas import ExtractedClaim
from src.rules_engine import verify_claim

def test_dynamic_years():
    # Mock CSV with FY24 and FY25 columns
    df = pd.DataFrame([
        {
            "metric_id": "MTR-TOTAL",
            "category": "Emissions",
            "metric_name": "Total Scope 1 & 2 Emissions",
            "unit": "MT CO2e",
            "fy24_value": 20000.0,
            "fy25_value": 17000.0,
            "yoy_change_pct": -15.0
        }
    ])
    
    # Claim for FY24 -> FY25 (15% reduction)
    claim_clean = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=15.0,
        baseline_year="FY24",
        target_year="FY25",
        claim_text="Reduced emissions by 15% in FY25 compared to FY24."
    )
    
    res = verify_claim(claim_clean, df)
    print("Clean FY24->FY25 Audit Result:", res.model_dump())
    assert res.status == "PASS"
    assert res.baseline_year == "FY24"
    assert res.target_year == "FY25"
    assert res.baseline_value == 20000.0
    assert res.target_value == 17000.0
    assert res.calculated_delta == 15.0

    # Flagged Claim for FY24 -> FY25 (claiming 30% reduction)
    claim_flagged = ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=30.0,
        baseline_year="FY24",
        target_year="FY25",
        claim_text="Achieved a massive 30% reduction in FY25 compared to FY24."
    )
    
    res_flagged = verify_claim(claim_flagged, df)
    print("Flagged FY24->FY25 Audit Result:", res_flagged.model_dump())
    assert res_flagged.status == "FLAGGED"
    assert res_flagged.variance == 15.0

    print("DYNAMIC YEARS TEST PASSED PERFECTLY!")

if __name__ == "__main__":
    test_dynamic_years()
