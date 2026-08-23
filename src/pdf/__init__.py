"""
ClaimGuard PDF Ingestion and Evidence Extraction Module
"""

from .models import (
    DocumentPage,
    DocumentTable,
    ExtractedEvidence,
    EvidenceType,
    ParsedDocument,
)
from .parser import PDFParser, parse_pdf
from .evidence_extractor import EvidenceExtractor
from .claim_models import ClaimCandidate, EntityBoundary, ExtractionMethod
from .claim_discovery import (
    PDFClaimDiscovery,
    discover_claims_in_document,
    discover_claims_from_text,
    extract_claims_from_text_fallback,
)
from .evidence_matcher import (
    EvidenceMatcher,
    MatchResult,
    claim_candidate_to_extracted_claim,
)
from .audit_runner import (
    PDFAuditResult,
    audit_pdf_claim,
)

__all__ = [
    "DocumentPage",
    "DocumentTable",
    "ExtractedEvidence",
    "ParsedDocument",
    "PDFParser",
    "parse_pdf",
    "EvidenceExtractor",
    # Phase 6B
    "ClaimCandidate",
    "EntityBoundary",
    "ExtractionMethod",
    "PDFClaimDiscovery",
    "discover_claims_in_document",
    "discover_claims_from_text",
    "extract_claims_from_text_fallback",
    # Phase 6C
    "EvidenceMatcher",
    "MatchResult",
    "claim_candidate_to_extracted_claim",
    "PDFAuditResult",
    "audit_pdf_claim",
]
