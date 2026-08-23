"""
ClaimGuard — BRSR & Environmental Evidence Extractor
Discovers and extracts normalized quantitative disclosures (Scope 1, Scope 2, etc.)
from parsed PDF documents with strict page-level provenance.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import DocumentPage, DocumentTable, ExtractedEvidence, ParsedDocument

logger = logging.getLogger("claimguard.pdf.evidence_extractor")


def _clean_numeric_value(raw_val: str) -> Optional[float]:
    """
    Parses numeric strings commonly found in Indian BRSR disclosures,
    including comma separators (e.g., '48,736', '1,72,409'), footnote marks
    (e.g., '48,736*', '22,542#'), and negative numbers.
    """
    if not raw_val or not isinstance(raw_val, str):
        return None
        
    s = raw_val.strip()
    # Remove footnote markers and special characters
    s = re.sub(r'[*#†‡\(\)\[\]]', '', s).strip()
    
    # Remove standard and Indian commas
    s = s.replace(',', '')
    
    # Check if this matches a valid float or integer
    match = re.search(r'^-?\d+(?:\.\d+)?$', s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def _normalize_year_header(header: str) -> Optional[str]:
    """
    Normalizes year column strings such as 'FY 25', 'FY24', 'FY 2024-25', '2024-25', 'FY 24-25'
    into standard canonical format like 'FY25', 'FY24'.
    """
    if not header:
        return None
    
    h = header.strip()
    
    # 1. Check for range formats first, e.g. 'FY 2024-25', '2024-25', 'FY 24-25', '2023-24'
    m_range = re.search(r'(?:FY\s*)?(?:20)?(\d{2})[-–—/](?:20)?(\d{2})', h, re.IGNORECASE)
    if m_range:
        end_yr = m_range.group(2)
        return f"FY{end_yr}"

    # 2. Check for single year formats, e.g. 'FY 25', 'FY 2025', 'FY25', 'FY 24'
    m_fy = re.search(r'FY\s*(\d{2,4})', h, re.IGNORECASE)
    if m_fy:
        yr = m_fy.group(1)
        if len(yr) == 4:
            return f"FY{yr[2:]}"
        return f"FY{yr}"

    return None


def _extract_metric_from_table(
    table: DocumentTable,
    source_file: str,
    page_context: str = "",
    last_known_years: Optional[Dict[int, str]] = None,
) -> Tuple[List[ExtractedEvidence], Optional[Dict[int, str]]]:
    """
    Extracts structured disclosures from a DocumentTable.
    Searches for Scope 1, Scope 2, and other environmental indicators.
    Returns (extracted_evidence, current_year_col_map).
    """
    extracted: List[ExtractedEvidence] = []
    headers = table.headers
    
    # 1. Identify year columns from headers
    year_col_map: Dict[int, str] = {}
    for col_idx, h in enumerate(headers):
        norm_yr = _normalize_year_header(h)
        if norm_yr:
            year_col_map[col_idx] = norm_yr

    # 2. If headers didn't have years, check first row
    if not year_col_map and table.rows:
        for col_idx, cell in enumerate(table.rows[0]):
            norm_yr = _normalize_year_header(cell)
            if norm_yr:
                year_col_map[col_idx] = norm_yr

    # 3. If no years found yet, check last known table headers or page context
    if not year_col_map:
        if last_known_years:
            year_col_map = dict(last_known_years)
        else:
            # Check if page context has standard "Parameter Unit FY 25 FY 24"
            m_years = re.findall(r'FY\s*(\d{2,4})', page_context, re.IGNORECASE)
            if len(m_years) >= 2:
                # Typically, col 2 is current year, col 3 is baseline/previous year
                year_col_map[2] = f"FY{m_years[0][-2:]}"
                year_col_map[3] = f"FY{m_years[1][-2:]}"

    # Determine entity from page context / table surroundings
    entity = None
    # Check if this specific table has an explicit entity label in headers or rows
    table_text = " ".join([" ".join(table.headers)] + [" ".join(r) for r in table.rows])
    if "TML, TMPVL and TPEML" in table_text or "Consolidated" in table_text:
        entity = "Consolidated (TML, TMPVL and TPEML)"
    elif "TMPVL and TPEML" in table_text:
        entity = "TMPVL and TPEML"
    elif "TML" in table_text:
        entity = "TML"
    else:
        # Fall back to page context position
        if "TML, TMPVL and TPEML" in page_context:
            entity = "Consolidated (TML, TMPVL and TPEML)"
        elif "TMPVL and TPEML" in page_context:
            # If multiple tables on page, earlier table may be TML
            entity = "TML" if (not table.headers and "Total Scope 1" in table_text) else "TMPVL and TPEML"
        elif "TML" in page_context:
            entity = "TML"

    # Known metric patterns to search (generic environmental indicators)
    metric_patterns = [
        (r'total\s*scope\s*1\s*emissions?', 'Scope 1'),
        (r'total\s*scope\s*2\s*emissions?', 'Scope 2'),
        (r'scope\s*1\s*emissions?', 'Scope 1'),
        (r'scope\s*2\s*emissions?', 'Scope 2'),
        (r'total\s*scope\s*1\s*and\s*scope\s*2\s*emissions?', 'Total Scope 1 and 2'),
    ]

    for row_idx, row in enumerate(table.rows):
        if not row:
            continue
        first_cell = str(row[0]).strip()
        unit_cell = str(row[1]).strip() if len(row) > 1 else None

        matched_metric = None
        for pattern, m_name in metric_patterns:
            if re.search(pattern, first_cell, re.IGNORECASE):
                # Avoid matching intensity rows as absolute emissions
                if "intensity" in first_cell.lower() or "per rupee" in first_cell.lower() or "turnover" in first_cell.lower():
                    continue
                matched_metric = m_name
                break

        if not matched_metric:
            continue

        # Extract values for mapped year columns
        for col_idx, reporting_yr in year_col_map.items():
            if col_idx < len(row):
                raw_val = row[col_idx]
                parsed_num = _clean_numeric_value(raw_val)
                if parsed_num is not None:
                    evidence = ExtractedEvidence(
                        source_file=source_file,
                        page_number=table.page_number,
                        metric=matched_metric,
                        reporting_year=reporting_yr,
                        value=parsed_num,
                        raw_value=str(raw_val).strip(),
                        unit=unit_cell if unit_cell else "tCO2e",
                        entity=entity,
                        context_text=first_cell,
                        table_page=table.page_number,
                        metadata={
                            "row_index": row_idx,
                            "column_index": col_idx,
                            "raw_row": row,
                        },
                    )
                    extracted.append(evidence)

    current_years = year_col_map if year_col_map else last_known_years
    return extracted, current_years


def _extract_metric_from_text_fallback(
    page: DocumentPage,
    source_file: str,
) -> List[ExtractedEvidence]:
    """
    Fallback parser for text-based tables where table borders are absent.
    Looks for line patterns like:
    'Total Scope 1 emissions# tCO2e 48,736* 43,754' or
    'Total Scope 1 emissions Metric tonnes 43,754 48,736*'
    """
    extracted: List[ExtractedEvidence] = []
    lines = page.text.split("\n")
    
    # Check for header line with years
    current_years: List[str] = []
    for line in lines:
        if "FY" in line and ("24" in line or "25" in line):
            found_years = re.findall(r'FY\s*(\d{2,4})', line, re.IGNORECASE)
            if found_years:
                current_years = [f"FY{y[-2:]}" for y in found_years]
                break

    if not current_years:
        current_years = ["FY25", "FY24"]

    scope1_pattern = re.compile(r'Total\s+Scope\s+1\s+emissions.*?(?:tCO2e|Metric tonnes|MT)?\s+([\d,]+\*?)\s+([\d,]+\*?)', re.IGNORECASE)
    scope2_pattern = re.compile(r'Total\s+Scope\s+2\s+emissions.*?(?:tCO2|Metric tonnes|MT)?\s+([\d,]+\*?)\s+([\d,]+\*?)', re.IGNORECASE)

    for line in lines:
        m1 = scope1_pattern.search(line)
        if m1 and "intensity" not in line.lower():
            val1_raw, val2_raw = m1.group(1), m1.group(2)
            v1, v2 = _clean_numeric_value(val1_raw), _clean_numeric_value(val2_raw)
            if v1 is not None and len(current_years) > 0:
                extracted.append(ExtractedEvidence(
                    source_file=source_file,
                    page_number=page.page_number,
                    metric="Scope 1",
                    reporting_year=current_years[0],
                    value=v1,
                    raw_value=val1_raw,
                    unit="tCO2e",
                    context_text=line.strip(),
                    table_page=page.page_number,
                ))
            if v2 is not None and len(current_years) > 1:
                extracted.append(ExtractedEvidence(
                    source_file=source_file,
                    page_number=page.page_number,
                    metric="Scope 1",
                    reporting_year=current_years[1],
                    value=v2,
                    raw_value=val2_raw,
                    unit="tCO2e",
                    context_text=line.strip(),
                    table_page=page.page_number,
                ))

        m2 = scope2_pattern.search(line)
        if m2 and "intensity" not in line.lower():
            val1_raw, val2_raw = m2.group(1), m2.group(2)
            v1, v2 = _clean_numeric_value(val1_raw), _clean_numeric_value(val2_raw)
            if v1 is not None and len(current_years) > 0:
                extracted.append(ExtractedEvidence(
                    source_file=source_file,
                    page_number=page.page_number,
                    metric="Scope 2",
                    reporting_year=current_years[0],
                    value=v1,
                    raw_value=val1_raw,
                    unit="tCO2",
                    context_text=line.strip(),
                    table_page=page.page_number,
                ))
            if v2 is not None and len(current_years) > 1:
                extracted.append(ExtractedEvidence(
                    source_file=source_file,
                    page_number=page.page_number,
                    metric="Scope 2",
                    reporting_year=current_years[1],
                    value=v2,
                    raw_value=val2_raw,
                    unit="tCO2",
                    context_text=line.strip(),
                    table_page=page.page_number,
                ))

    return extracted


class EvidenceExtractor:
    """
    Extracts structured disclosures from a ParsedDocument.
    """

    def __init__(self, document: ParsedDocument):
        self.document = document

    def extract_emissions_evidence(self) -> List[ExtractedEvidence]:
        """
        Extracts Scope 1 and Scope 2 disclosures across all document pages.
        Discovers pages dynamically based on text and table contents.
        """
        results: List[ExtractedEvidence] = []
        last_known_years: Optional[Dict[int, str]] = None
        
        for page in self.document.pages:
            # Check if page has emission mentions
            text_lower = page.text.lower()
            if "scope 1" in text_lower or "scope 2" in text_lower or "greenhouse gas" in text_lower:
                # 1. Try table extraction first
                for table in page.tables:
                    table_evidence, updated_years = _extract_metric_from_table(
                        table=table,
                        source_file=self.document.filename,
                        page_context=page.text,
                        last_known_years=last_known_years,
                    )
                    if updated_years:
                        last_known_years = updated_years
                    results.extend(table_evidence)
                
                # 2. If no table evidence was found on this page, try text fallback
                if not any(e.page_number == page.page_number for e in results):
                    text_evidence = _extract_metric_from_text_fallback(
                        page=page,
                        source_file=self.document.filename,
                    )
                    results.extend(text_evidence)
            else:
                # Still check tables for headers to keep tracking years
                for table in page.tables:
                    if table.headers:
                        y_map = {}
                        for idx, h in enumerate(table.headers):
                            norm_yr = _normalize_year_header(h)
                            if norm_yr:
                                y_map[idx] = norm_yr
                        if y_map:
                            last_known_years = y_map

        return results

    def find_evidence_by_metric(self, metric_name: str, year: Optional[str] = None) -> List[ExtractedEvidence]:
        """
        Query helper to find evidence by metric and optional reporting year.
        """
        all_emissions = self.extract_emissions_evidence()
        target_m = metric_name.lower()
        
        filtered = []
        for ev in all_emissions:
            if target_m in ev.metric.lower():
                if year is None or ev.reporting_year.upper() == year.upper():
                    filtered.append(ev)
        return filtered
