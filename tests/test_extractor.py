import pytest
from src.extractor import extract_claim_from_narrative

def test_extractor_recycling():
    # TEST A - Recycling
    narrative = "Our facility achieved a 35% recycling rate."
    claim = extract_claim_from_narrative(narrative)
    assert claim.claimed_recycling_rate == 35.0
    assert claim.claimed_percentage == 0.0
    
def test_extractor_recycling_alternate():
    # TEST B - Recycling alternate wording
    narrative = "The facility recycled 42% of its water."
    claim = extract_claim_from_narrative(narrative)
    assert claim.claimed_recycling_rate == 42.0
    assert claim.claimed_percentage == 0.0

def test_extractor_water_intensity():
    # TEST C - Water intensity
    narrative = "Our water consumption intensity was 2.4 KL per crore of revenue."
    claim = extract_claim_from_narrative(narrative)
    assert claim.claimed_water_intensity == 2.4
    assert claim.claimed_percentage == 0.0

def test_extractor_emissions_regression():
    # TEST D - Emissions regression
    narrative = "Achieved a 20% reduction in Scope 1 and Scope 2 emissions in FY24."
    claim = extract_claim_from_narrative(narrative)
    assert claim.claimed_percentage == 20.0
    assert claim.claimed_recycling_rate is None
    assert claim.claimed_water_intensity is None

def test_extractor_no_false_extraction():
    # TEST E - No false extraction
    narrative = "Our company improved energy efficiency by 15%."
    claim = extract_claim_from_narrative(narrative)
    assert claim.claimed_percentage == 15.0
    assert claim.claimed_recycling_rate is None
    assert claim.claimed_water_intensity is None
