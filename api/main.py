"""
ClaimGuard API — FastAPI Application

Thin API boundary around the existing deterministic audit engine.

Architecture:
    FastAPI  →  src/extractor.py  →  src/rules_engine.py  →  15-rule registry  →  AuditResult

This module does NOT contain business logic, rule calculations, or
extraction algorithms. It converts HTTP requests into the data
structures expected by the existing engine and serializes results back.

Run:
    uvicorn api.main:app --reload --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import List

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    AuditRequest,
    HealthResponse,
    RuleInfo,
    RulesResponse,
)
from src.extractor import extract_claim_from_narrative
from src.rules.registry import RuleRegistry
from src.rules_engine import verify_claim
from src.schemas import AuditResult

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

load_dotenv()

API_VERSION = "1.0.0"
SERVICE_NAME = "ClaimGuard API"

logger = logging.getLogger("claimguard.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


# ──────────────────────────────────────────────
# Application Lifespan — one-time initialization
# ──────────────────────────────────────────────

_registry_initialized: bool = False


def _ensure_registry():
    """Discover and register all rules once. Idempotent."""
    global _registry_initialized
    if not _registry_initialized:
        RuleRegistry.auto_discover()
        _registry_initialized = True
        logger.info(
            f"ClaimGuard rule registry initialized — "
            f"{len(RuleRegistry.get_all_rules())} rules loaded"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run rule discovery once at application startup."""
    _ensure_registry()
    yield


# Also run discovery at module-import time so that TestClient
# (which may not always trigger lifespan) has rules available.
_ensure_registry()


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

app = FastAPI(
    title=SERVICE_NAME,
    version=API_VERSION,
    description=(
        "Deterministic ESG / BRSR claim verification API. "
        "Validates corporate sustainability narratives against ground-truth metrics "
        "using a 15-rule deterministic engine."
    ),
    lifespan=lifespan,
)

# CORS — configurable via environment, safe localhost default
_allowed_origins = os.getenv(
    "CLAIMGUARD_ALLOWED_ORIGINS",
    "http://localhost:8501,http://localhost:3000,http://localhost:8000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns service status and number of loaded deterministic rules.",
    tags=["Status"],
)
async def health_check():
    rules_count = len(RuleRegistry.get_all_rules())
    if rules_count == 0:
        logger.warning("Health check failed — no rules loaded")
        raise HTTPException(
            status_code=503,
            detail="Rule registry failed to initialize. No deterministic rules loaded.",
        )
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=API_VERSION,
        rules_loaded=rules_count,
    )



# ──────────────────────────────────────────────
# GET /rules
# ──────────────────────────────────────────────

@app.get(
    "/rules",
    response_model=RulesResponse,
    summary="List registered rules",
    description="Returns all currently registered deterministic validation rules, dynamically derived from the RuleRegistry.",
    tags=["Status"],
)
async def list_rules():
    rules = RuleRegistry.get_all_rules()
    rule_list: List[RuleInfo] = [
        RuleInfo(
            rule_id=r.rule_id,
            domain=r.domain.value if hasattr(r.domain, "value") else str(r.domain),
            name=r.rule_name,
            description=getattr(r, "description", ""),
        )
        for r in rules
    ]
    return RulesResponse(total=len(rule_list), rules=rule_list)


# ──────────────────────────────────────────────
# POST /audit
# ──────────────────────────────────────────────

@app.post(
    "/audit",
    response_model=AuditResult,
    summary="Run deterministic audit",
    description=(
        "Accepts a sustainability narrative and ground-truth metrics, "
        "then runs the full ClaimGuard extraction + 15-rule verification pipeline. "
        "Domain outcomes (PASS / FLAGGED / UNVERIFIED) are returned as HTTP 200 — "
        "they are valid audit results, not errors."
    ),
    tags=["Audit"],
)
async def run_audit(request: AuditRequest):
    logger.info(f"POST /audit — {len(request.metrics)} metric records received")

    try:
        # 1. Convert API metric records → pandas DataFrame
        df = _metrics_to_dataframe(request.metrics)

        # 2. Extract claim from narrative (uses existing extractor pipeline)
        claim = extract_claim_from_narrative(request.narrative)
        logger.info(
            f"Extracted claim — metric='{claim.metric}', "
            f"claimed_pct={claim.claimed_percentage}, "
            f"years={claim.baseline_year}→{claim.target_year}"
        )

        # 3. Run deterministic audit engine
        result = verify_claim(claim, df)
        logger.info(
            f"Audit complete — decision={result.audit_decision.value}, "
            f"execution={result.execution_status.value}, "
            f"rules_evaluated={result.summary.total_rules}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal audit engine error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal audit engine error. Please check server logs.",
        )


# ──────────────────────────────────────────────
# Helpers — DataFrame conversion boundary
# ──────────────────────────────────────────────

def _metrics_to_dataframe(metrics) -> pd.DataFrame:
    """
    Convert a list of MetricRecord Pydantic models into a pandas DataFrame.

    Uses model_dump() to capture both explicit and extra fields,
    ensuring extended columns (recycling_rate_fy24, fuel_energy_fy24, etc.)
    pass through to the engine intact.
    """
    records = [m.model_dump() for m in metrics]
    df = pd.DataFrame(records)
    return df
