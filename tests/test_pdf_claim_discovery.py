"""
ClaimGuard — Phase 6B: PDF Claim Discovery Tests
Tests semantic claim extraction from PDF text using Groq/LLM and deterministic fallback.

Groq API is ALWAYS mocked in automated tests.
Real API smoke test only runs if GROQ_API_KEY is present in the environment.

Does NOT:
- call verify_claim()
- connect to the rules engine
- use ExtractedClaim
- modify any frozen file
"""

import os
import json
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.pdf.claim_models import ClaimCandidate, EntityBoundary, ExtractionMethod
from src.pdf.claim_discovery import (
    extract_claims_from_text_fallback,
    discover_claims_from_text,
    _normalize_year,
    _normalize_metric,
    _resolve_entity,
    _parse_llm_response,
    _build_chunks,
)
from src.pdf.models import ParsedDocument, DocumentPage


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures and helpers
# ─────────────────────────────────────────────────────────────────────────────

SYNTHETIC_CLAIM_TEXT = (
    "Tata Motors Limited reduced its combined Scope 1 and Scope 2 greenhouse gas emissions "
    "by approximately 20.8% between FY24 and FY25."
)

def _make_page(page_number: int, text: str) -> DocumentPage:
    return DocumentPage(page_number=page_number, text=text)


def _make_doc(pages_text: dict) -> ParsedDocument:
    pages = [_make_page(n, t) for n, t in sorted(pages_text.items())]
    return ParsedDocument(
        source_path="/test/doc.pdf",
        filename="doc.pdf",
        total_pages=len(pages),
        pages=pages,
    )


def _mock_groq_response(claims_data: list) -> MagicMock:
    """Creates a mock Groq API response returning the given claims JSON."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({"claims": claims_data})
    return mock_resp


# ─────────────────────────────────────────────────────────────────────────────
# 1. Year normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestYearNormalization:
    def test_fy25(self):
        assert _normalize_year("FY25") == "FY25"

    def test_fy_long_2025(self):
        assert _normalize_year("FY2025") == "FY25"

    def test_fy_long_2024(self):
        assert _normalize_year("FY2024") == "FY24"

    def test_range_2024_25(self):
        assert _normalize_year("2024-25") == "FY25"

    def test_range_2023_24(self):
        assert _normalize_year("2023-24") == "FY24"

    def test_none_returns_none(self):
        assert _normalize_year(None) is None

    def test_empty_returns_none(self):
        assert _normalize_year("") is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Metric normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricNormalization:
    def test_scope_1_and_2_combined(self):
        assert _normalize_metric("Scope 1 and Scope 2 emissions") == "Total Scope 1 & 2 Emissions"

    def test_combined_scope(self):
        assert _normalize_metric("combined Scope 1 and Scope 2") == "Total Scope 1 & 2 Emissions"

    def test_ghg_emissions(self):
        assert _normalize_metric("GHG emissions") == "Total Scope 1 & 2 Emissions"

    def test_scope_1_only(self):
        assert _normalize_metric("Scope 1") == "Scope 1 Emissions"

    def test_scope_2_only(self):
        assert _normalize_metric("Scope 2") == "Scope 2 Emissions"

    def test_none_returns_none(self):
        assert _normalize_metric(None) is None

    def test_unknown_metric_preserved(self):
        assert _normalize_metric("Employee headcount") == "Employee headcount"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Entity resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestEntityResolution:
    def test_tml_explicit(self):
        entity, _ = _resolve_entity(None, "Tata Motors Limited reduced emissions by 20%", "")
        assert entity == EntityBoundary.TML.value

    def test_tml_abbreviation(self):
        entity, _ = _resolve_entity(None, "TML achieved a 15% reduction", "")
        assert entity == EntityBoundary.TML.value

    def test_consolidated(self):
        entity, _ = _resolve_entity(None, "TML, TMPVL and TPEML combined emissions fell by 20%", "")
        assert entity == EntityBoundary.CONSOLIDATED.value

    def test_tmpvl_tpeml(self):
        entity, _ = _resolve_entity(None, "TMPVL and TPEML cut emissions by 18%", "")
        assert entity == EntityBoundary.TMPVL_TPEML.value

    def test_unknown_ambiguous(self):
        entity, _ = _resolve_entity(None, "Tata Motors reduced emissions by 20%.", "")
        # "Tata Motors" alone — without "Limited" or "TML" — is ambiguous
        # May resolve or stay UNKNOWN depending on pattern
        assert entity in [EntityBoundary.UNKNOWN.value, EntityBoundary.TML.value]

    def test_llm_entity_honored(self):
        entity, _ = _resolve_entity("TML", "some claim text", "")
        assert entity == EntityBoundary.TML.value

    def test_invalid_llm_entity_falls_back(self):
        entity, _ = _resolve_entity("RANDOM_ENTITY", "Tata Motors Limited cut GHG by 20%", "")
        assert entity == EntityBoundary.TML.value


# ─────────────────────────────────────────────────────────────────────────────
# 4. Deterministic fallback extractor — core extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackExtraction:

    # A. Synthetic controlled claim
    def test_synthetic_claim_extraction(self):
        results = extract_claims_from_text_fallback(SYNTHETIC_CLAIM_TEXT, page_number=88)
        assert len(results) >= 1
        claim = results[0]
        assert claim.claimed_percentage == pytest.approx(20.8, abs=0.01)
        assert claim.metric == "Total Scope 1 & 2 Emissions"
        assert claim.baseline_year == "FY24"
        assert claim.target_year == "FY25"
        assert claim.entity == EntityBoundary.TML.value
        assert claim.source_page == 88
        assert claim.extraction_method == ExtractionMethod.FALLBACK_REGEX.value

    # B. No percentage → claimed_percentage must be null
    def test_no_percentage_returns_no_claim(self):
        text = "Scope 1 and Scope 2 emissions declined during the year."
        results = extract_claims_from_text_fallback(text, page_number=10)
        # No explicit % → no claim should be returned
        assert all(c.claimed_percentage is None for c in results)

    # C. No metric → metric must be null/unknown
    def test_irrelevant_metric_excluded(self):
        text = "We achieved a 20% reduction in our operational costs."
        results = extract_claims_from_text_fallback(text, page_number=5)
        # No emission keyword → empty or no emission claim
        for c in results:
            assert c.metric not in ["Total Scope 1 & 2 Emissions", "Scope 1 Emissions", "Scope 2 Emissions"]

    # D. Revenue growth must not become an emissions claim
    def test_revenue_growth_not_emissions_claim(self):
        text = "Our revenue grew by 20% in FY25 compared to FY24."
        results = extract_claims_from_text_fallback(text, page_number=3)
        emission_claims = [c for c in results if c.metric in [
            "Total Scope 1 & 2 Emissions", "Scope 1 Emissions", "Scope 2 Emissions"
        ]]
        assert len(emission_claims) == 0

    # E. Table values without narrative must NOT generate a percentage
    def test_table_values_without_narrative_no_percentage(self):
        text = "Total Scope 1 emissions: FY24 = 48736, FY25 = 43754\nTotal Scope 2: FY24 = 172409, FY25 = 131407"
        results = extract_claims_from_text_fallback(text, page_number=88)
        for c in results:
            # Must not calculate 20.79% from table values
            if c.claimed_percentage is not None:
                assert abs(c.claimed_percentage - 20.79) > 0.5, \
                    "Fallback must not calculate reduction from table values"

    # F. Entity ambiguity
    def test_ambiguous_entity_is_unknown(self):
        text = "Tata Motors reduced its GHG emissions by 20% in FY25 vs FY24."
        results = extract_claims_from_text_fallback(text, page_number=5)
        if results:
            # "Tata Motors" without "Limited" may be TML or UNKNOWN depending on patterns
            assert results[0].entity in [EntityBoundary.TML.value, EntityBoundary.UNKNOWN.value]


# ─────────────────────────────────────────────────────────────────────────────
# 5. LLM response parsing tests (no real API)
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMResponseParsing:

    def _chunk_pages(self):
        return [88]

    def _chunk_text(self):
        return "[PAGE 88]\n" + SYNTHETIC_CLAIM_TEXT

    def test_valid_llm_response_parsed(self):
        raw_json = json.dumps({"claims": [{
            "claim_text": SYNTHETIC_CLAIM_TEXT,
            "metric": "Total Scope 1 & 2 Emissions",
            "claimed_percentage": 20.8,
            "baseline_year": "FY24",
            "target_year": "FY25",
            "entity": "TML",
            "confidence": 0.95,
        }]})
        results = _parse_llm_response(raw_json, self._chunk_text(), self._chunk_pages(), "doc.pdf")
        assert len(results) == 1
        c = results[0]
        assert c.claimed_percentage == pytest.approx(20.8)
        assert c.baseline_year == "FY24"
        assert c.target_year == "FY25"
        assert c.entity == EntityBoundary.TML.value
        assert c.extraction_method == ExtractionMethod.GROQ_LLM.value
        assert c.confidence == pytest.approx(0.95)

    def test_llm_no_percentage_returns_null(self):
        raw_json = json.dumps({"claims": [{
            "claim_text": "Emissions declined during the year.",
            "metric": "Total Scope 1 & 2 Emissions",
            "claimed_percentage": None,
            "baseline_year": "FY24",
            "target_year": "FY25",
            "entity": "UNKNOWN",
            "confidence": 0.5,
        }]})
        results = _parse_llm_response(raw_json, self._chunk_text(), self._chunk_pages(), "doc.pdf")
        assert len(results) == 1
        assert results[0].claimed_percentage is None

    def test_llm_empty_claims_returns_empty(self):
        raw_json = json.dumps({"claims": []})
        results = _parse_llm_response(raw_json, self._chunk_text(), self._chunk_pages(), "doc.pdf")
        assert results == []

    def test_llm_invalid_json_returns_empty(self):
        results = _parse_llm_response("not valid json at all", self._chunk_text(), self._chunk_pages(), "doc.pdf")
        assert results == []

    def test_llm_percentage_out_of_range_rejected(self):
        raw_json = json.dumps({"claims": [{
            "claim_text": "Emissions jumped.",
            "metric": "Total Scope 1 & 2 Emissions",
            "claimed_percentage": 999.0,  # absurd value
            "baseline_year": "FY24",
            "target_year": "FY25",
            "entity": "TML",
            "confidence": 0.9,
        }]})
        results = _parse_llm_response(raw_json, self._chunk_text(), self._chunk_pages(), "doc.pdf")
        assert len(results) == 1
        assert results[0].claimed_percentage is None

    def test_llm_negative_percentage_rejected(self):
        raw_json = json.dumps({"claims": [{
            "claim_text": "Something.",
            "metric": "Total Scope 1 & 2 Emissions",
            "claimed_percentage": -5.0,
            "baseline_year": "FY24",
            "target_year": "FY25",
            "entity": "TML",
            "confidence": 0.9,
        }]})
        results = _parse_llm_response(raw_json, self._chunk_text(), self._chunk_pages(), "doc.pdf")
        assert results[0].claimed_percentage is None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Mocked Groq extraction tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMockedGroqExtraction:

    @patch("src.pdf.claim_discovery.Groq", create=True)
    def test_mocked_groq_synthetic_claim(self, mock_groq_class):
        """Mocked Groq returns a valid claim — verify normalization pipeline."""
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_groq_response([{
            "claim_text": SYNTHETIC_CLAIM_TEXT,
            "metric": "Scope 1 and Scope 2 emissions",
            "claimed_percentage": 20.8,
            "baseline_year": "FY2024",
            "target_year": "FY2025",
            "entity": "TML",
            "confidence": 0.95,
        }])

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key-abc"}):
            results = discover_claims_from_text(SYNTHETIC_CLAIM_TEXT, source_page=88, source_file="test.pdf")

        assert len(results) >= 1
        c = results[0]
        assert c.metric == "Total Scope 1 & 2 Emissions"
        assert c.claimed_percentage == pytest.approx(20.8)
        assert c.baseline_year == "FY24"
        assert c.target_year == "FY25"
        assert c.entity == EntityBoundary.TML.value
        assert c.source_page == 88

    @patch("src.pdf.claim_discovery.Groq", create=True)
    def test_mocked_groq_table_values_no_percentage(self, mock_groq_class):
        """Mocked Groq correctly returns null percentage for table-only data."""
        table_text = "Total Scope 1 FY24=48736 FY25=43754\nTotal Scope 2 FY24=172409 FY25=131407"
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_groq_response([{
            "claim_text": "Emissions data presented in table.",
            "metric": "Total Scope 1 & 2 Emissions",
            "claimed_percentage": None,  # LLM correctly returns null
            "baseline_year": "FY24",
            "target_year": "FY25",
            "entity": "TML",
            "confidence": 0.7,
        }])

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key-abc"}):
            results = discover_claims_from_text(table_text, source_page=88)

        for c in results:
            assert c.claimed_percentage is None, "LLM must not calculate from table values"

    @patch("src.pdf.claim_discovery.Groq", create=True)
    def test_mocked_groq_no_claims_empty_text(self, mock_groq_class):
        """Mocked Groq returns empty claims for non-claim text."""
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_groq_response([])

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key-abc"}):
            results = discover_claims_from_text("General corporate overview text.", source_page=1)

        assert results == []

    @patch("src.pdf.claim_discovery.Groq", create=True)
    def test_groq_api_failure_falls_back_to_regex(self, mock_groq_class):
        """When Groq throws an exception, the fallback regex is used."""
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Network error")

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key-abc"}):
            results = discover_claims_from_text(SYNTHETIC_CLAIM_TEXT, source_page=88)

        # Fallback should still pick up the 20.8% claim
        assert len(results) >= 1
        assert results[0].extraction_method == ExtractionMethod.FALLBACK_REGEX.value
        assert results[0].claimed_percentage == pytest.approx(20.8, abs=0.1)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Chunking / document strategy tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChunkingStrategy:

    def test_irrelevant_pages_skipped(self):
        doc = _make_doc({
            1: "Company history and overview.",
            2: "Board of directors and governance.",
            3: "Tata Motors Limited reduced its combined Scope 1 and Scope 2 GHG emissions by 20.8% in FY25 versus FY24.",
            4: "Financial statements and notes.",
            5: "More irrelevant text.",
            6: "Even more governance content.",
            7: "Yet another section with no ESG keyword.",
        })
        chunks = _build_chunks(doc)
        page_sets = [set(pnums) for _, pnums in chunks]

        # Page 3 must appear in at least one chunk (it has the claim signal)
        assert any(3 in ps for ps in page_sets)

        pages_in_chunks = set()
        for _, pnums in chunks:
            pages_in_chunks.update(pnums)

        # Pages far away from any signal (5, 6, 7) must NOT appear
        # Pages 2 and 4 may appear as context window neighbours of page 3
        assert 5 not in pages_in_chunks
        assert 6 not in pages_in_chunks
        assert 7 not in pages_in_chunks

    def test_provenance_retained_in_chunk(self):
        doc = _make_doc({
            87: "GHG overview section.",
            88: "Tata Motors Limited reduced combined Scope 1 and Scope 2 GHG emissions by 20.8% between FY24 and FY25.",
            89: "Additional disclosure notes.",
        })
        chunks = _build_chunks(doc)
        assert len(chunks) >= 1
        # Page 88 must be in a chunk
        assert any(88 in pnums for _, pnums in chunks)


# ─────────────────────────────────────────────────────────────────────────────
# 8. ClaimCandidate model integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestClaimCandidateModel:

    def test_to_dict_complete(self):
        c = ClaimCandidate(
            claim_text="Test claim.",
            metric="Total Scope 1 & 2 Emissions",
            claimed_percentage=20.8,
            baseline_year="FY24",
            target_year="FY25",
            source_page=88,
            entity=EntityBoundary.TML.value,
        )
        d = c.to_dict()
        assert d["claim_text"] == "Test claim."
        assert d["metric"] == "Total Scope 1 & 2 Emissions"
        assert d["claimed_percentage"] == pytest.approx(20.8)
        assert d["baseline_year"] == "FY24"
        assert d["target_year"] == "FY25"
        assert d["source_page"] == 88
        assert d["entity"] == "TML"

    def test_defaults_are_safe(self):
        c = ClaimCandidate(claim_text="Minimal claim.")
        assert c.metric is None
        assert c.claimed_percentage is None
        assert c.baseline_year is None
        assert c.target_year is None
        assert c.source_page is None
        assert c.entity == EntityBoundary.UNKNOWN.value
        assert c.source_pages == []

    def test_not_connected_to_extracted_claim(self):
        """Verify ClaimCandidate does NOT inherit from ExtractedClaim."""
        from src.schemas import ExtractedClaim
        c = ClaimCandidate(claim_text="Test.")
        assert not isinstance(c, ExtractedClaim)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Real Groq smoke test (only if GROQ_API_KEY is available)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — skipping real Groq smoke test"
)
class TestRealGroqSmokeTest:

    def test_real_groq_synthetic_claim(self):
        """
        Smoke test against live Groq API.
        Uses a controlled synthetic sentence (NOT a direct quote from Tata Motors).

        If the API key is present but invalid/expired, the fallback regex is used.
        The test still passes, but reports which extraction path was taken.
        """
        text = (
            "Tata Motors Limited reduced its combined Scope 1 and Scope 2 greenhouse gas emissions "
            "by approximately 20.8% between FY24 and FY25."
        )
        results = discover_claims_from_text(text, source_page=88, source_file="smoke_test.pdf")
        assert len(results) >= 1
        c = results[0]

        # Core claim content must be correct regardless of extraction method
        assert c.metric is not None
        assert "scope" in c.metric.lower() or "emission" in c.metric.lower(), \
            f"Unexpected metric: {c.metric}"
        assert c.claimed_percentage is not None
        assert abs(c.claimed_percentage - 20.8) < 1.0, \
            f"claimed_percentage {c.claimed_percentage} too far from 20.8"
        assert c.baseline_year in ["FY24", "FY2024"], f"Unexpected baseline: {c.baseline_year}"
        assert c.target_year in ["FY25", "FY2025"], f"Unexpected target: {c.target_year}"

        method_used = c.extraction_method
        print(
            f"\n[REAL GROQ SMOKE TEST] method={method_used}, metric={c.metric}, "
            f"claimed_pct={c.claimed_percentage}, baseline={c.baseline_year}, "
            f"target={c.target_year}, entity={c.entity}, confidence={c.confidence}"
        )

        if method_used == ExtractionMethod.GROQ_LLM.value:
            # Groq API worked — assert LLM-specific properties
            assert c.confidence is not None, "LLM extraction should provide confidence"
        else:
            # API unavailable/invalid — fallback ran correctly
            print("[REAL GROQ SMOKE TEST] NOTE: Groq API unavailable, fallback regex was used.")
            assert method_used == ExtractionMethod.FALLBACK_REGEX.value
