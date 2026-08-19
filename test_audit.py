import os
import sys
import pandas as pd
from src.extractor import extract_claim_from_narrative
from src.rules_engine import verify_claim

def run_tests():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Test Preset 1: Clean
    clean_narrative_path = os.path.join(base_dir, "data", "preset_clean", "narrative.txt")
    clean_metrics_path = os.path.join(base_dir, "data", "preset_clean", "metrics.csv")
    
    with open(clean_narrative_path, "r", encoding="utf-8") as f:
        clean_text = f.read()
        
    print("--- Testing Preset 1: Clean ---")
    claim_clean = extract_claim_from_narrative(clean_text)
    print("Extracted Claim:", claim_clean.model_dump())
    result_clean = verify_claim(claim_clean, clean_metrics_path)
    print("Audit Result:", result_clean.model_dump())
    assert result_clean.status == "PASS", f"Expected PASS for clean preset, got {result_clean.status}"
    print("Preset 1 Test PASSED!\n")

    # Test Preset 2: Flagged
    flagged_narrative_path = os.path.join(base_dir, "data", "preset_flagged", "narrative.txt")
    flagged_metrics_path = os.path.join(base_dir, "data", "preset_flagged", "metrics.csv")
    
    with open(flagged_narrative_path, "r", encoding="utf-8") as f:
        flagged_text = f.read()
        
    print("--- Testing Preset 2: Flagged ---")
    claim_flagged = extract_claim_from_narrative(flagged_text)
    print("Extracted Claim:", claim_flagged.model_dump())
    result_flagged = verify_claim(claim_flagged, flagged_metrics_path)
    print("Audit Result:", result_flagged.model_dump())
    assert result_flagged.status == "FLAGGED", f"Expected FLAGGED for flagged preset, got {result_flagged.status}"
    print("Preset 2 Test PASSED!\n")

    print("ALL UNIT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
