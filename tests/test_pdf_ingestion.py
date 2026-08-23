"""
ClaimGuard — PDF Ingestion & Evidence Extraction Tests
Verifies that:
1. PDFs load and parse reliably without crashing.
2. Page-level metadata and page numbers are preserved.
3. Structured tables are extracted accurately.
4. Scope 1 and Scope 2 disclosures are dynamically discovered and recovered from the Tata Motors BRSR PDF.
5. Extracted evidence retains strict source page provenance.
"""

import os
from pathlib import Path
import pytest

from src.pdf.models import DocumentPage, DocumentTable, ExtractedEvidence, ParsedDocument
from src.pdf.parser import PDFParser, parse_pdf
from src.pdf.evidence_extractor import EvidenceExtractor, _clean_numeric_value, _normalize_year_header


def get_test_pdf_path() -> Path:
    """
    Dynamically locates the Tata Motors FY2024-25 BRSR PDF.
    Checks environment variable, workspace data directories, and parent directory.
    """
    env_path = os.getenv("TATA_BRSR_PDF_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    candidates = [
        Path(__file__).parent.parent / "data" / "Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf",
        Path(__file__).parent.parent / "data" / "fixtures" / "Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf",
        Path(__file__).parent.parent.parent / "Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf",
        Path(__file__).parent.parent.parent / "Tata-Motors-BRSR_r3-Only-Web-Link-1.pdf",
        Path(r"C:\Users\Lenovo\Desktop\CLAIMGUARD\Voluntary-Report-based-on-BRSR-Framework-for-FY-2024-25.pdf"),
        Path(r"C:\Users\Lenovo\Desktop\CLAIMGUARD\Tata-Motors-BRSR_r3-Only-Web-Link-1.pdf"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    pytest.skip("Tata Motors BRSR PDF fixture not found in workspace or parent directory.")


@pytest.fixture(scope="module")
def parsed_brsr_doc() -> ParsedDocument:
    """Fixture that parses the Tata Motors BRSR once for all ingestion tests."""
    pdf_path = get_test_pdf_path()
    return parse_pdf(pdf_path)


class TestPDFParserGeneric:
    """Tests generic PDF parsing capabilities."""

    def test_missing_file_raises_error(self):
        with pytest.raises(FileNotFoundError):
            parse_pdf("non_existent_file_path_12345.pdf")

    def test_numeric_cleaning(self):
        assert _clean_numeric_value("48,736*") == 48736.0
        assert _clean_numeric_value("1,72,409*") == 172409.0
        assert _clean_numeric_value("43,754") == 43754.0
        assert _clean_numeric_value("131,407") == 131407.0
        assert _clean_numeric_value("0.000000258") == 2.58e-07
        assert _clean_numeric_value("-15.5") == -15.5
        assert _clean_numeric_value("N/A") is None
        assert _clean_numeric_value("") is None

    def test_year_header_normalization(self):
        assert _normalize_year_header("FY 25") == "FY25"
        assert _normalize_year_header("FY24") == "FY24"
        assert _normalize_year_header("FY 2024-25") == "FY25"
        assert _normalize_year_header("2023-24") == "FY24"
        assert _normalize_year_header("Parameter") is None


class TestBRSRDocumentIngestion:
    """Tests parsing fidelity on the real Tata Motors BRSR PDF."""

    def test_pdf_loads_and_has_pages(self, parsed_brsr_doc: ParsedDocument):
        assert parsed_brsr_doc is not None
        assert parsed_brsr_doc.total_pages > 40
        assert parsed_brsr_doc.pages_with_text_count > 40
        assert parsed_brsr_doc.total_tables_count > 10
        assert parsed_brsr_doc.parse_time_seconds > 0

    def test_page_metadata_provenance(self, parsed_brsr_doc: ParsedDocument):
        for idx, page in enumerate(parsed_brsr_doc.pages, start=1):
            assert page.page_number == idx
            if page.has_tables:
                for table in page.tables:
                    assert table.page_number == idx
                    assert isinstance(table.headers, list)
                    assert isinstance(table.rows, list)

    def test_page_text_search(self, parsed_brsr_doc: ParsedDocument):
        matches = parsed_brsr_doc.search_text("Scope 1")
        assert len(matches) > 0
        # Verify match tuple structure: (page_number, line_text)
        page_num, line_text = matches[0]
        assert isinstance(page_num, int)
        assert "scope 1" in line_text.lower()


class TestScope1Scope2EvidenceExtraction:
    """Validates dynamic discovery and accurate recovery of Scope 1 & 2 values."""

    def test_extract_all_emissions_evidence(self, parsed_brsr_doc: ParsedDocument):
        extractor = EvidenceExtractor(parsed_brsr_doc)
        evidence = extractor.extract_emissions_evidence()
        assert len(evidence) >= 4

        # Verify all evidence objects contain page numbers and source provenance
        for ev in evidence:
            assert ev.page_number > 0
            assert ev.source_file == parsed_brsr_doc.filename
            assert ev.metric in ["Scope 1", "Scope 2", "Total Scope 1 and 2"]
            assert ev.reporting_year in ["FY24", "FY25"]
            assert isinstance(ev.value, float)
            assert ev.raw_value != ""

    def test_recover_target_tata_motors_disclosures(self, parsed_brsr_doc: ParsedDocument):
        extractor = EvidenceExtractor(parsed_brsr_doc)
        evidence = extractor.extract_emissions_evidence()

        # Scope 1 TML: FY24 = 48,736, FY25 = 43,754
        s1_fy24 = [e for e in evidence if e.metric == "Scope 1" and e.reporting_year == "FY24" and e.value == 48736.0]
        s1_fy25 = [e for e in evidence if e.metric == "Scope 1" and e.reporting_year == "FY25" and e.value == 43754.0]

        # Scope 2 TML: FY24 = 172,409, FY25 = 131,407
        s2_fy24 = [e for e in evidence if e.metric == "Scope 2" and e.reporting_year == "FY24" and e.value == 172409.0]
        s2_fy25 = [e for e in evidence if e.metric == "Scope 2" and e.reporting_year == "FY25" and e.value == 131407.0]

        assert len(s1_fy24) >= 1, "Expected to recover Scope 1 FY24 (48,736) from PDF"
        assert len(s1_fy25) >= 1, "Expected to recover Scope 1 FY25 (43,754) from PDF"
        assert len(s2_fy24) >= 1, "Expected to recover Scope 2 FY24 (172,409) from PDF"
        assert len(s2_fy25) >= 1, "Expected to recover Scope 2 FY25 (131,407) from PDF"

        # Verify page provenance for recovered values
        recovered_page = s1_fy25[0].page_number
        assert recovered_page > 0
        assert s1_fy24[0].page_number == recovered_page
        assert s2_fy25[0].page_number == recovered_page
        assert s2_fy24[0].page_number == recovered_page

    def test_find_evidence_by_metric_helper(self, parsed_brsr_doc: ParsedDocument):
        extractor = EvidenceExtractor(parsed_brsr_doc)
        s1_evidence = extractor.find_evidence_by_metric("Scope 1", year="FY25")
        assert len(s1_evidence) >= 1
        assert any(e.value == 43754.0 for e in s1_evidence)
