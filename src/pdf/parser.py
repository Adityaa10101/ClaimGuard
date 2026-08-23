"""
ClaimGuard — Generic PDF Parser
Extracts page-aware text and structured tables from PDF files without any domain-specific hardcoding.
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Any, List, Optional, Union, Dict

import pdfplumber

from .models import DocumentPage, DocumentTable, ParsedDocument

logger = logging.getLogger("claimguard.pdf.parser")


def _clean_cell(cell: Any) -> str:
    """Cleans up raw cell text from pdfplumber table extraction."""
    if cell is None:
        return ""
    text = str(cell).strip()
    # Normalize multiple whitespaces and newlines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def _is_likely_header_row(row: List[str]) -> bool:
    """
    Determines if a row is truly a header row or a data row.
    Header rows contain descriptive text without quantitative metrics in data cells.
    Data rows typically have metrics and numeric data in subsequent columns.
    """
    if not row:
        return False
    
    # If any cell after col 0 contains numeric values like '43,754' or floats, it is a data row
    for cell in row[1:]:
        cleaned = re.sub(r'[*#†‡\(\)\[\]]', '', cell).replace(',', '').strip()
        if re.search(r'^-?\d+(?:\.\d+)?$', cleaned):
            return False

    joined = " ".join(row).lower()
    header_keywords = [
        'parameter', 'particulars', 'indicator', 'metric', 'unit',
        'fy 2', 'fy 1', 'fy2', 'fy1', 'financial year', 'current financial year',
        'previous financial year', 'reporting year', 'baseline year', 'q1', 'q2', 'q3', 'q4',
        'category', 'scope', 'details'
    ]
    
    return any(kw in joined for kw in header_keywords)


def _normalize_table(raw_table: List[List[Any]], page_number: int) -> Optional[DocumentTable]:
    """
    Cleans and structures a raw extracted table into a DocumentTable.
    Finds meaningful headers and strips completely empty rows/columns.
    """
    if not raw_table or not isinstance(raw_table, list):
        return None

    # Clean all cells
    cleaned_rows: List[List[str]] = []
    for raw_row in raw_table:
        if not raw_row or not isinstance(raw_row, list):
            continue
        cleaned_row = [_clean_cell(cell) for cell in raw_row]
        # Ignore rows where all cells are empty
        if any(bool(c) for c in cleaned_row):
            cleaned_rows.append(cleaned_row)

    if not cleaned_rows:
        return None

    # Check if rows have equal non-empty cell counts (sparse split tables)
    non_empty_counts = [sum(1 for c in r if c) for r in cleaned_rows]
    if len(set(non_empty_counts)) == 1 and non_empty_counts[0] > 0:
        filtered_rows = [[c for c in r if c] for r in cleaned_rows]
    else:
        # Detect if any columns are completely empty across all rows, and trim them
        num_cols = max(len(r) for r in cleaned_rows)
        padded_rows = [r + [""] * (num_cols - len(r)) for r in cleaned_rows]

        col_has_content = [False] * num_cols
        for row in padded_rows:
            for c_idx, val in enumerate(row):
                if val.strip():
                    col_has_content[c_idx] = True

        active_col_indices = [idx for idx, has_content in enumerate(col_has_content) if has_content]
        if not active_col_indices:
            return None

        filtered_rows = [[row[idx] for idx in active_col_indices] for row in padded_rows]

    # Heuristic for table headers:
    headers: List[str] = []
    data_rows: List[List[str]] = []

    if filtered_rows:
        first_row = filtered_rows[0]
        if _is_likely_header_row(first_row):
            headers = [h.replace("\n", " ").strip() for h in first_row]
            data_rows = filtered_rows[1:]
        else:
            headers = []
            data_rows = filtered_rows
    else:
        headers = []
        data_rows = []

    return DocumentTable(
        page_number=page_number,
        headers=headers,
        rows=data_rows,
        raw_data=raw_table,
    )


class PDFParser:
    """
    Generic PDF Parser engine that extracts text and tables on a per-page basis.
    """

    def __init__(self, table_settings: Optional[Dict[str, Any]] = None):
        self.table_settings = table_settings

    def parse(self, file_path: Union[str, Path]) -> ParsedDocument:
        """
        Parses a PDF document into a page-aware ParsedDocument object.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at path: {path}")

        start_time = time.perf_counter()
        pages: List[DocumentPage] = []

        try:
            with pdfplumber.open(path) as pdf:
                for page_idx, page in enumerate(pdf.pages, start=1):
                    try:
                        # Extract page text
                        page_text = page.extract_text() or ""
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_idx} of {path.name}: {e}")
                        page_text = ""

                    # Extract page tables
                    page_tables: List[DocumentTable] = []
                    try:
                        raw_tables = page.extract_tables(table_settings=self.table_settings)
                        if raw_tables:
                            for raw_table in raw_tables:
                                norm_table = _normalize_table(raw_table, page_number=page_idx)
                                if norm_table is not None:
                                    page_tables.append(norm_table)
                    except Exception as e:
                        logger.warning(f"Error extracting tables from page {page_idx} of {path.name}: {e}")

                    doc_page = DocumentPage(
                        page_number=page_idx,
                        text=page_text,
                        tables=page_tables,
                        width=float(page.width) if page.width else None,
                        height=float(page.height) if page.height else None,
                    )
                    pages.append(doc_page)

        except Exception as e:
            logger.error(f"Failed to parse PDF document {path}: {e}")
            raise

        elapsed = time.perf_counter() - start_time

        return ParsedDocument(
            source_path=str(path),
            filename=path.name,
            total_pages=len(pages),
            pages=pages,
            parse_time_seconds=round(elapsed, 4),
            metadata={
                "file_size_bytes": path.stat().st_size if path.exists() else 0,
            },
        )


def parse_pdf(file_path: Union[str, Path], table_settings: Optional[Dict[str, Any]] = None) -> ParsedDocument:
    """
    Convenience function to parse a PDF file into a ParsedDocument.
    """
    parser = PDFParser(table_settings=table_settings)
    return parser.parse(file_path)
