import os
import io
import pandas as pd
from typing import Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.extractor import extract_claim_from_narrative
from src.rules_engine import verify_claim

app = FastAPI(title="ClaimGuard API")

# Allow all origins for the hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRESET_CLEAN_DIR = os.path.join(BASE_DIR, "data", "preset_clean")
PRESET_FLAGGED_DIR = os.path.join(BASE_DIR, "data", "preset_flagged")

def read_preset(preset_dir: str) -> Dict[str, Any]:
    narrative_path = os.path.join(preset_dir, "narrative.txt")
    metrics_path = os.path.join(preset_dir, "metrics.csv")
    
    narrative = ""
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            narrative = f.read()
            
    metrics_csv = ""
    if os.path.exists(metrics_path):
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_csv = f.read()
            
    return {
        "narrative": narrative,
        "metrics_csv": metrics_csv
    }

@app.get("/api/presets")
def get_presets():
    return {
        "clean": read_preset(PRESET_CLEAN_DIR),
        "flagged": read_preset(PRESET_FLAGGED_DIR)
    }

@app.post("/api/audit")
async def audit_claim(
    narrative: str = Form(...),
    metrics_file: UploadFile = File(...)
):
    try:
        # Read the uploaded CSV
        content = await metrics_file.read()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        
        # Step 1: Extract Claim
        extracted_claim = extract_claim_from_narrative(narrative_text=narrative)
        
        # Step 2: Verify Claim
        audit_result = verify_claim(claim=extracted_claim, metrics_source=df)
        
        return {
            "extracted_claim": extracted_claim.model_dump(),
            "audit_result": audit_result.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
