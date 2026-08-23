"""
ClaimGuard — Phase 6B: PDF Claim Discovery Models
Defines ClaimCandidate: the structured output of LLM-based claim extraction
from PDF document text. Completely separate from ExtractedClaim / verify_claim().
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExtractionMethod(str, Enum):
    """How the claim was extracted."""
    GROQ_LLM = "groq_llm"
    FALLBACK_REGEX = "fallback_regex"


class EntityBoundary(str, Enum):
    """Reporting boundary / entity scope."""
    TML = "TML"                             # Tata Motors Limited standalone
    TMPVL_TPEML = "TMPVL_TPEML"           # TMPVL and TPEML standalone
    CONSOLIDATED = "CONSOLIDATED"           # TML + TMPVL + TPEML combined
    UNKNOWN = "UNKNOWN"                     # Cannot be determined safely


@dataclass
class ClaimCandidate:
    """
    Structured output of semantic claim extraction from a PDF text chunk.

    This is the Phase 6B artifact. It is NOT connected to the rules engine,
    NOT a replacement for ExtractedClaim, and NOT a verification decision.

    It represents ONE structured claim extracted from ONE location in the document.
    """
    # Core claim content
    claim_text: str                          # Verbatim or near-verbatim claim sentence
    metric: Optional[str] = None            # e.g. "Total Scope 1 & 2 Emissions"
    claimed_percentage: Optional[float] = None  # e.g. 20.8 — explicitly stated, never calculated
    baseline_year: Optional[str] = None     # e.g. "FY24"
    target_year: Optional[str] = None       # e.g. "FY25"

    # Provenance
    source_page: Optional[int] = None       # Page number from ParsedDocument (1-indexed)
    source_pages: List[int] = field(default_factory=list)  # If claim spans multiple pages

    # Entity / boundary
    entity: str = EntityBoundary.UNKNOWN.value     # Reporting entity/boundary
    entity_raw: Optional[str] = None               # Raw text used to infer entity

    # Extraction metadata
    confidence: Optional[float] = None             # 0.0–1.0 extraction confidence only
    extraction_method: str = ExtractionMethod.FALLBACK_REGEX.value

    # Optional context
    context_text: Optional[str] = None     # Surrounding paragraph context
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_text": self.claim_text,
            "metric": self.metric,
            "claimed_percentage": self.claimed_percentage,
            "baseline_year": self.baseline_year,
            "target_year": self.target_year,
            "source_page": self.source_page,
            "source_pages": self.source_pages,
            "entity": self.entity,
            "entity_raw": self.entity_raw,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "context_text": self.context_text,
            "metadata": self.metadata,
        }
