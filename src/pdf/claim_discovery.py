"""
ClaimGuard — Phase 6B: PDF Claim Discovery
Extracts structured quantitative ESG claims from PDF document text using Groq/Llama.

Architecture:
  ParsedDocument (Phase 6A) → page-aware text chunks → Groq/LLM → ClaimCandidate[]

Strict constraints:
  - LLM is ONLY responsible for semantic extraction (not calculation, not validation)
  - All arithmetic is FORBIDDEN in LLM prompt and results
  - Does NOT call verify_claim() or connect to the rules engine
  - Does NOT modify ExtractedClaim or any frozen schemas
  - ClaimCandidate is a separate Phase 6B artifact only
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .claim_models import ClaimCandidate, EntityBoundary, ExtractionMethod
from .models import ParsedDocument

logger = logging.getLogger("claimguard.pdf.claim_discovery")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MODEL_FALLBACKS = [
    GROQ_MODEL,
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
]

# Max characters per chunk sent to the LLM (≈ 2,000-3,000 tokens worth of text)
CHUNK_CHAR_LIMIT = 4000

# Pages to include as surrounding context window
CONTEXT_WINDOW_PAGES = 1

# Keywords that signal a page likely contains a quantitative sustainability claim
CLAIM_SIGNAL_KEYWORDS = [
    "scope 1", "scope 2", "greenhouse gas", "ghg", "emission",
    "carbon", "energy", "renewable", "water recycl", "waste",
    "reduced by", "reduction of", "decrease", "declined by", "improved by",
    "achieved a", "% reduction", "% decrease", "% improvement", "% lower",
    "per cent", "percent", "tco2", "intensity",
]

# Metric normalization map
METRIC_ALIASES = {
    "total scope 1 & 2": "Total Scope 1 & 2 Emissions",
    "total scope 1 and 2": "Total Scope 1 & 2 Emissions",
    "scope 1 and scope 2": "Total Scope 1 & 2 Emissions",
    "scope 1 & scope 2": "Total Scope 1 & 2 Emissions",
    "combined scope 1 and scope 2": "Total Scope 1 & 2 Emissions",
    "combined scope 1 & scope 2": "Total Scope 1 & 2 Emissions",
    "scope 1 + scope 2": "Total Scope 1 & 2 Emissions",
    "scope 1 and 2": "Total Scope 1 & 2 Emissions",
    "greenhouse gas": "Total Scope 1 & 2 Emissions",
    "ghg emissions": "Total Scope 1 & 2 Emissions",
    "scope 1": "Scope 1 Emissions",
    "scope 2": "Scope 2 Emissions",
    "energy": "Energy Consumption",
    "water recycl": "Water Recycling Rate",
    "water intensity": "Water Intensity",
    "water consumption": "Water Consumption",
}

ENTITY_PATTERNS = [
    # CONSOLIDATED must be checked before TML — "TML, TMPVL and TPEML" contains "TML"
    (r"TML\s*,\s*TMPVL\s+and\s+TPEML|TMPVL\s+and\s+TPEML\s+combined|consolidated|combined\s+operations?", EntityBoundary.CONSOLIDATED.value),
    (r"TMPVL\s+and\s+TPEML|TPEML\s+and\s+TMPVL|TMPVL\s*&\s*TPEML", EntityBoundary.TMPVL_TPEML.value),
    (r"Tata\s+Motors\s+Limited\b|(?<!\w)TML\b", EntityBoundary.TML.value),
]

YEAR_ALIASES = {
    "FY2024": "FY24",
    "FY2025": "FY25",
    "FY2023": "FY23",
    "FY2022": "FY22",
    "2024-25": "FY25",
    "2023-24": "FY24",
    "2022-23": "FY23",
    "2024": "FY24",
    "2025": "FY25",
}


# ─────────────────────────────────────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a strict, zero-hallucination data extraction parser for sustainability "
    "and ESG documents. Your ONLY job is to locate and extract quantitative claims "
    "that are explicitly stated in the provided text.\n\n"
    "ABSOLUTE PROHIBITIONS:\n"
    "- DO NOT perform any arithmetic, subtraction, division, or percentage calculations.\n"
    "- DO NOT compute a percentage from table values.\n"
    "- DO NOT invent or estimate any number that is not explicitly written in the text.\n"
    "- DO NOT decide whether a claim is correct or incorrect.\n"
    "- DO NOT assign a reporting entity unless the text explicitly names one.\n"
    "- DO NOT treat evidence table values (FY24=X, FY25=Y) as a claimed percentage.\n\n"
    "Return raw JSON only. No markdown, no explanation."
)

USER_PROMPT_TEMPLATE = """\
Extract all EXPLICIT quantitative sustainability claims from the text below.

A claim must contain:
- A NAMED ESG metric (emissions, energy, water, etc.)
- An EXPLICITLY STATED percentage reduction or change (e.g. "reduced by 20%")
- Ideally: years and reporting entity

If no explicit claim is present, return an empty claims array.

Return JSON with this exact structure:
{{
  "claims": [
    {{
      "claim_text": "<verbatim or close-paraphrase of the claim sentence>",
      "metric": "<metric name, e.g. 'Total Scope 1 & 2 Emissions' or null if unclear>",
      "claimed_percentage": <float if explicitly stated, e.g. 20.8, or null if absent>,
      "baseline_year": "<e.g. FY24 or null if not stated>",
      "target_year": "<e.g. FY25 or null if not stated>",
      "entity": "<TML|TMPVL_TPEML|CONSOLIDATED|UNKNOWN — based only on explicit text>",
      "confidence": <0.0 to 1.0 reflecting extraction confidence only, not claim accuracy>
    }}
  ]
}}

IMPORTANT:
- claimed_percentage must come ONLY from explicitly stated percentages in the narrative.
  If the text contains only raw numbers like "FY24=48736, FY25=43754" without a stated
  percentage, set claimed_percentage to null.
- entity must be one of: TML, TMPVL_TPEML, CONSOLIDATED, UNKNOWN
  Use UNKNOWN if the text does not explicitly identify the boundary.
- Do NOT calculate. Do NOT verify. Do NOT assess accuracy.

Document text (page-labelled):
\"\"\"
{text}
\"\"\"
"""


def _build_prompt(chunk_text: str) -> str:
    return USER_PROMPT_TEMPLATE.format(text=chunk_text[:CHUNK_CHAR_LIMIT])


# ─────────────────────────────────────────────────────────────────────────────
# Chunking strategy
# ─────────────────────────────────────────────────────────────────────────────

def _page_contains_claim_signal(page_text: str) -> bool:
    """Returns True if the page likely contains a quantitative claim worth processing."""
    lower = page_text.lower()
    return any(kw in lower for kw in CLAIM_SIGNAL_KEYWORDS)


def _build_chunks(document: ParsedDocument) -> List[Tuple[str, List[int]]]:
    """
    Builds text chunks from the document for LLM processing.
    Each chunk includes a window of surrounding pages for context.
    Returns list of (chunk_text, page_numbers_included).
    """
    chunks: List[Tuple[str, List[int]]] = []
    pages = document.pages
    total = len(pages)

    i = 0
    while i < total:
        page = pages[i]
        if not _page_contains_claim_signal(page.text):
            i += 1
            continue

        # Include surrounding context pages
        start = max(0, i - CONTEXT_WINDOW_PAGES)
        end = min(total - 1, i + CONTEXT_WINDOW_PAGES)

        chunk_parts = []
        page_nums = []
        for j in range(start, end + 1):
            p = pages[j]
            if p.text and p.text.strip():
                chunk_parts.append(f"[PAGE {p.page_number}]\n{p.text.strip()}")
                page_nums.append(p.page_number)

        if chunk_parts:
            chunk_text = "\n\n".join(chunk_parts)
            chunks.append((chunk_text, page_nums))

        # Skip ahead past the context window to avoid redundant overlap
        i = end + 1

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Year / entity / metric normalization helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_year(raw: Optional[str]) -> Optional[str]:
    """Normalizes year strings like 'FY2024', '2024-25' to 'FY24'."""
    if not raw:
        return None
    s = str(raw).strip()
    # Check alias map
    if s in YEAR_ALIASES:
        return YEAR_ALIASES[s]
    # Match FY + 2 or 4 digits
    m = re.match(r'^FY(\d{2,4})$', s, re.IGNORECASE)
    if m:
        yr = m.group(1)
        return f"FY{yr[-2:]}"
    # Match range like 2024-25
    m = re.match(r'^(?:20)?(\d{2})[-–—/](?:20)?(\d{2})$', s)
    if m:
        return f"FY{m.group(2)}"
    return s  # Return as-is if cannot normalize


def _normalize_metric(raw: Optional[str]) -> Optional[str]:
    """Normalizes metric strings to canonical names."""
    if not raw:
        return None
    lower = raw.strip().lower()
    # Check for specific single-scope indicators first
    if "scope 1" in lower and not any(k in lower for k in ["scope 2", "and 2", "& 2", "+ 2", "+ scope"]):
        return "Scope 1 Emissions"
    if "scope 2" in lower and not any(k in lower for k in ["scope 1", "1 and", "1 &", "1 +", "scope 1 +"]):
        return "Scope 2 Emissions"
    for alias, canonical in METRIC_ALIASES.items():
        if alias in lower:
            return canonical
    return raw.strip()


def _resolve_entity(raw_entity: Optional[str], claim_text: str, context_text: str) -> Tuple[str, Optional[str]]:
    """
    Resolves entity from LLM output or text fallback.
    Returns (entity_boundary_value, raw_matched_text).
    """
    # If LLM returned a valid boundary
    if raw_entity and raw_entity.upper() in [e.value for e in EntityBoundary]:
        return raw_entity.upper(), raw_entity

    # Try pattern matching in claim_text then context_text
    search_texts = [claim_text or "", context_text or ""]
    for text in search_texts:
        for pattern, boundary in ENTITY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return boundary, m.group(0)

    return EntityBoundary.UNKNOWN.value, None


def _infer_primary_page(chunk_page_nums: List[int], claim_text: str, chunk_text: str) -> Optional[int]:
    """Infers the primary source page from the page-labeled chunk text."""
    if not chunk_page_nums:
        return None

    lines = chunk_text.split("\n")
    current_page = chunk_page_nums[0]

    # Walk through the chunk to find the first [PAGE N] line before the claim sentence
    claim_lower = claim_text.lower()[:50] if claim_text else ""
    for line in lines:
        m = re.match(r'\[PAGE (\d+)\]', line)
        if m:
            current_page = int(m.group(1))
        if claim_lower and claim_lower in line.lower():
            return current_page

    # If claim not directly found, return page of first signal keyword
    for line in lines:
        m = re.match(r'\[PAGE (\d+)\]', line)
        if m:
            current_page = int(m.group(1))
        for kw in ["reduced by", "reduction of", "% reduction", "declined"]:
            if kw in line.lower():
                return current_page

    return chunk_page_nums[0]


# ─────────────────────────────────────────────────────────────────────────────
# LLM extraction (Groq)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_response(
    raw_json: str,
    chunk_text: str,
    chunk_page_nums: List[int],
    source_file: str,
) -> List[ClaimCandidate]:
    """Parses the LLM JSON response into ClaimCandidate objects."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON: {e}. raw={raw_json[:200]}")
        return []

    claims_raw = data.get("claims", [])
    if not isinstance(claims_raw, list):
        return []

    candidates: List[ClaimCandidate] = []
    for raw in claims_raw:
        if not isinstance(raw, dict):
            continue

        claim_text = raw.get("claim_text", "").strip()
        if not claim_text:
            continue

        # Normalize percentage — reject any calculated numbers
        raw_pct = raw.get("claimed_percentage")
        claimed_pct: Optional[float] = None
        if raw_pct is not None:
            try:
                claimed_pct = float(raw_pct)
                # Sanity guard: reject implausibly large/negative percentages
                if claimed_pct < 0 or claimed_pct > 200:
                    claimed_pct = None
            except (TypeError, ValueError):
                claimed_pct = None

        metric = _normalize_metric(raw.get("metric"))
        baseline_year = _normalize_year(raw.get("baseline_year"))
        target_year = _normalize_year(raw.get("target_year"))

        entity, entity_raw = _resolve_entity(
            raw.get("entity"),
            claim_text,
            chunk_text,
        )

        confidence = raw.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
                confidence = min(1.0, max(0.0, confidence))
            except (TypeError, ValueError):
                confidence = None

        source_page = _infer_primary_page(chunk_page_nums, claim_text, chunk_text)

        candidates.append(ClaimCandidate(
            claim_text=claim_text,
            metric=metric,
            claimed_percentage=claimed_pct,
            baseline_year=baseline_year,
            target_year=target_year,
            source_page=source_page,
            source_pages=list(chunk_page_nums),
            entity=entity,
            entity_raw=entity_raw,
            confidence=confidence,
            extraction_method=ExtractionMethod.GROQ_LLM.value,
            context_text=chunk_text[:300],
            metadata={"source_file": source_file},
        ))

    return candidates


def _extract_via_groq(
    chunk_text: str,
    chunk_page_nums: List[int],
    source_file: str,
    api_key: str,
) -> List[ClaimCandidate]:
    """Makes one Groq API call for a single text chunk with model fallback."""
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        
        last_error = None
        for model_name in dict.fromkeys(GROQ_MODEL_FALLBACKS):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_prompt(chunk_text)},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                raw_json = response.choices[0].message.content
                return _parse_llm_response(raw_json, chunk_text, chunk_page_nums, source_file)
            except Exception as model_err:
                last_error = model_err
                if "model_not_found" in str(model_err) or "404" in str(model_err):
                    continue
                raise model_err
        
        if last_error:
            raise last_error

    except Exception as e:
        logger.warning(f"Groq API call failed: {e}. Falling back to regex for this chunk.")
        return _extract_via_fallback_chunk(chunk_text, chunk_page_nums, source_file)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic fallback extractor
# ─────────────────────────────────────────────────────────────────────────────

# Patterns for percentage + emissions claim
_CLAIM_PATTERNS = [
    # "reduced ... by 20.8%" / "reduction of 20.8%"
    re.compile(
        r'(?:reduced?|decreased?|declined?|cut|lowered?)\s+[^.]{0,80}?\s+by\s+(?:approximately\s+)?(\d+(?:\.\d+)?)\s*%',
        re.IGNORECASE,
    ),
    re.compile(
        r'(\d+(?:\.\d+)?)\s*%\s+(?:reduction|decrease|decline|cut|lower)',
        re.IGNORECASE,
    ),
    re.compile(
        r'(?:achieved?|attained?)\s+(?:a|an)\s+(?:approximately\s+)?(\d+(?:\.\d+)?)\s*%\s+reduction',
        re.IGNORECASE,
    ),
]

_IRRELEVANT_SIGNALS = [
    "revenue", "profit", "sales", "turnover", "market", "employee", "staff",
    "salary", "dividend", "share price", "customer",
]

_EMISSION_SIGNALS = [
    "scope 1", "scope 2", "emission", "greenhouse", "ghg", "carbon", "co2",
    "energy", "water", "waste",
]


def _determine_metric_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    if any(s in lower for s in ["scope 1 and scope 2", "scope 1 & scope 2",
                                  "scope 1 and 2", "combined scope", "total scope"]):
        return "Total Scope 1 & 2 Emissions"
    if "scope 1" in lower and "scope 2" not in lower:
        return "Scope 1 Emissions"
    if "scope 2" in lower and "scope 1" not in lower:
        return "Scope 2 Emissions"
    if "greenhouse gas" in lower or "ghg" in lower:
        return "Total Scope 1 & 2 Emissions"
    if "energy" in lower:
        return "Energy Consumption"
    if "water recycl" in lower:
        return "Water Recycling Rate"
    if "water" in lower:
        return "Water Consumption"
    if "waste" in lower:
        return "Solid Waste Generated"
    return None


def _extract_years_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts baseline/target year pair from text."""
    # Find all FY years
    fy_hits = re.findall(r'FY\s*(\d{2,4})', text, re.IGNORECASE)
    normalized = sorted(set([f"FY{y[-2:]}" for y in fy_hits]))

    # Also check ranges like "2024-25"
    range_hits = re.findall(r'(?:20)?(\d{2})[-–—/](?:20)?(\d{2})', text)
    for start_yr, end_yr in range_hits:
        normalized.extend([f"FY{start_yr}", f"FY{end_yr}"])
    normalized = sorted(set(normalized))

    if len(normalized) >= 2:
        return normalized[0], normalized[1]
    if len(normalized) == 1:
        return None, normalized[0]
    return None, None


def _extract_entity_from_text(text: str) -> Tuple[str, Optional[str]]:
    for pattern, boundary in ENTITY_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return boundary, m.group(0)
    return EntityBoundary.UNKNOWN.value, None


def extract_claims_from_text_fallback(
    text: str,
    page_number: Optional[int] = None,
    source_file: str = "",
) -> List[ClaimCandidate]:
    """
    Deterministic regex-based claim extraction fallback.
    Supports single text block (no Groq required).
    """
    lower = text.lower()

    # Reject if clearly irrelevant (revenue/profit context without emissions)
    has_emission_signal = any(s in lower for s in _EMISSION_SIGNALS)
    has_irrelevant_only = any(s in lower for s in _IRRELEVANT_SIGNALS)

    if has_irrelevant_only and not has_emission_signal:
        return []

    results: List[ClaimCandidate] = []

    # Split into sentences for targeted extraction
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        s_lower = sentence.lower()

        # Must contain an emission signal to be a valid claim sentence
        if not any(sig in s_lower for sig in _EMISSION_SIGNALS):
            continue

        # Must not be purely an irrelevant domain
        if all(sig in s_lower for sig in _IRRELEVANT_SIGNALS) and not any(
            sig in s_lower for sig in _EMISSION_SIGNALS
        ):
            continue

        # Extract percentage
        claimed_pct = None
        for pattern in _CLAIM_PATTERNS:
            m = pattern.search(sentence)
            if m:
                try:
                    val = float(m.group(1))
                    if 0 < val <= 200:
                        claimed_pct = val
                        break
                except (ValueError, IndexError):
                    pass

        # Only include sentences with explicit percentages
        if claimed_pct is None:
            continue

        metric = _determine_metric_from_text(sentence)
        baseline_year, target_year = _extract_years_from_text(sentence)

        # Broaden year search to full text if not found in sentence
        if not baseline_year and not target_year:
            baseline_year, target_year = _extract_years_from_text(text)

        entity, entity_raw = _extract_entity_from_text(sentence)
        if entity == EntityBoundary.UNKNOWN.value:
            entity, entity_raw = _extract_entity_from_text(text)

        results.append(ClaimCandidate(
            claim_text=sentence.strip(),
            metric=metric,
            claimed_percentage=claimed_pct,
            baseline_year=baseline_year,
            target_year=target_year,
            source_page=page_number,
            source_pages=[page_number] if page_number else [],
            entity=entity,
            entity_raw=entity_raw,
            confidence=0.75,
            extraction_method=ExtractionMethod.FALLBACK_REGEX.value,
            context_text=text[:300],
            metadata={"source_file": source_file},
        ))

    return results


def _extract_via_fallback_chunk(
    chunk_text: str,
    chunk_page_nums: List[int],
    source_file: str,
) -> List[ClaimCandidate]:
    """Runs fallback extractor over a chunk, attributing page numbers."""
    # Process page by page within the chunk
    results: List[ClaimCandidate] = []
    current_page: Optional[int] = chunk_page_nums[0] if chunk_page_nums else None

    page_blocks = re.split(r'\[PAGE (\d+)\]', chunk_text)
    i = 0
    while i < len(page_blocks):
        block = page_blocks[i].strip()
        if block.isdigit():
            current_page = int(block)
            i += 1
            continue
        if block:
            page_results = extract_claims_from_text_fallback(
                block, page_number=current_page, source_file=source_file
            )
            results.extend(page_results)
        i += 1

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main discovery entry points
# ─────────────────────────────────────────────────────────────────────────────

class PDFClaimDiscovery:
    """
    Orchestrates Phase 6B claim discovery over a ParsedDocument.
    Uses Groq/LLM if API key is available, falls back to deterministic regex.
    Does NOT connect to the rules engine or verify_claim().
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")

    def discover(self, document: ParsedDocument) -> Dict[str, Any]:
        """
        Runs claim discovery over the full parsed document.
        Returns a structured report with ClaimCandidate objects and diagnostics.
        """
        start_time = time.perf_counter()
        chunks = _build_chunks(document)

        all_candidates: List[ClaimCandidate] = []
        groq_calls = 0
        fallback_calls = 0

        for chunk_text, page_nums in chunks:
            if self.api_key:
                candidates = _extract_via_groq(
                    chunk_text, page_nums, document.filename, self.api_key
                )
                groq_calls += 1
                # Count how many fell back
                for c in candidates:
                    if c.extraction_method == ExtractionMethod.FALLBACK_REGEX.value:
                        fallback_calls += 1
            else:
                candidates = _extract_via_fallback_chunk(
                    chunk_text, page_nums, document.filename
                )
                fallback_calls += 1

            all_candidates.extend(candidates)

        elapsed = time.perf_counter() - start_time

        return {
            "source_file": document.filename,
            "total_pages": document.total_pages,
            "chunks_processed": len(chunks),
            "groq_calls": groq_calls,
            "fallback_calls": fallback_calls,
            "claims_discovered": len(all_candidates),
            "extraction_time_seconds": round(elapsed, 3),
            "claims": all_candidates,
        }


def discover_claims_in_document(
    document: ParsedDocument,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to discover claims in a ParsedDocument.
    Returns a discovery report with ClaimCandidate list.
    """
    discovery = PDFClaimDiscovery(api_key=api_key)
    return discovery.discover(document)


def discover_claims_from_text(
    text: str,
    source_page: Optional[int] = None,
    source_file: str = "",
    api_key: Optional[str] = None,
) -> List[ClaimCandidate]:
    """
    Convenience function to extract claims from a single text block.
    Used for controlled/synthetic tests and single-page discovery.
    """
    effective_key = api_key or os.getenv("GROQ_API_KEY")

    if effective_key:
        chunk_pages = [source_page] if source_page else []
        try:
            candidates = _extract_via_groq(text, chunk_pages, source_file, effective_key)
            if candidates is not None:
                return candidates
        except Exception as e:
            logger.warning(f"Groq failed on single-text discovery: {e}")

    return extract_claims_from_text_fallback(
        text, page_number=source_page, source_file=source_file
    )
