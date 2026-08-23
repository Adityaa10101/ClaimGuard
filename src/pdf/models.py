"""
ClaimGuard — PDF Ingestion Models
Defines page-aware data models for document pages, tables, and extracted evidence.
All structures strictly retain source page provenance.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict
import re


@dataclass
class DocumentTable:
    """
    Represents an extracted table from a specific PDF page.
    Retains page provenance, structured headers, and clean rows.
    """
    page_number: int
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    raw_data: Optional[List[List[Any]]] = None
    title: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def col_count(self) -> int:
        if self.headers:
            return len(self.headers)
        if self.rows and self.rows[0]:
            return len(self.rows[0])
        return 0

    def find_rows(self, keyword: str, case_sensitive: bool = False) -> List[Tuple[int, List[str]]]:
        """
        Finds all rows containing a specific keyword.
        Returns list of (row_index, row_values).
        """
        results = []
        target = keyword if case_sensitive else keyword.lower()
        for idx, row in enumerate(self.rows):
            row_str = " ".join(str(c) for c in row)
            match_str = row_str if case_sensitive else row_str.lower()
            if target in match_str:
                results.append((idx, row))
        return results

    def get_column_index(self, col_name: str, case_sensitive: bool = False) -> Optional[int]:
        """Find the index of a column by header name or partial match."""
        target = col_name if case_sensitive else col_name.lower()
        for idx, h in enumerate(self.headers):
            h_str = h if case_sensitive else h.lower()
            if target in h_str:
                return idx
        return None

    def get_cell(self, row_idx: int, col_identifier: Any) -> Optional[str]:
        """Retrieves cell value by row index and column name/index."""
        if row_idx < 0 or row_idx >= len(self.rows):
            return None
        row = self.rows[row_idx]
        
        if isinstance(col_identifier, int):
            if 0 <= col_identifier < len(row):
                return row[col_identifier]
            return None
            
        col_idx = self.get_column_index(str(col_identifier))
        if col_idx is not None and col_idx < len(row):
            return row[col_idx]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "headers": self.headers,
            "rows": self.rows,
            "title": self.title,
            "row_count": self.row_count,
            "col_count": self.col_count,
        }


@dataclass
class DocumentPage:
    """
    Represents a single page in the PDF document.
    Maintains full page text and structured tables with explicit page number.
    """
    page_number: int  # 1-indexed
    text: str = ""
    tables: List[DocumentTable] = field(default_factory=list)
    width: Optional[float] = None
    height: Optional[float] = None

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def has_text(self) -> bool:
        return bool(self.text and self.text.strip())

    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0

    def search_text(self, query: str, case_sensitive: bool = False) -> List[str]:
        """Searches for lines containing query on this page."""
        target = query if case_sensitive else query.lower()
        matched_lines = []
        for line in self.text.split("\n"):
            line_check = line if case_sensitive else line.lower()
            if target in line_check:
                matched_lines.append(line.strip())
        return matched_lines


@dataclass
class ParsedDocument:
    """
    Container for the fully parsed PDF document.
    Provides querying and inspection helpers with provenance preservation.
    """
    source_path: str
    filename: str
    total_pages: int
    pages: List[DocumentPage] = field(default_factory=list)
    parse_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_page(self, page_number: int) -> Optional[DocumentPage]:
        """1-indexed page lookup."""
        if 1 <= page_number <= len(self.pages):
            return self.pages[page_number - 1]
        return None

    def search_text(self, query: str, case_sensitive: bool = False) -> List[Tuple[int, str]]:
        """Searches text across all pages. Returns [(page_number, matching_line)]."""
        results = []
        for page in self.pages:
            for line in page.search_text(query, case_sensitive=case_sensitive):
                results.append((page.page_number, line))
        return results

    def find_tables_with_keyword(self, keyword: str, case_sensitive: bool = False) -> List[Tuple[int, DocumentTable]]:
        """Searches for tables containing keyword across all pages. Returns [(page_number, DocumentTable)]."""
        matches = []
        for page in self.pages:
            for table in page.tables:
                if table.find_rows(keyword, case_sensitive=case_sensitive):
                    matches.append((page.page_number, table))
        return matches

    @property
    def total_tables_count(self) -> int:
        return sum(len(p.tables) for p in self.pages)

    @property
    def pages_with_text_count(self) -> int:
        return sum(1 for p in self.pages if p.has_text)


@dataclass
class ExtractedEvidence:
    """
    Normalized representation of a single quantitative or qualitative disclosure.
    Strictly preserves source file and page number for audit provenance.
    """
    source_file: str
    page_number: int
    metric: str
    reporting_year: str
    value: float
    raw_value: str
    unit: Optional[str] = None
    entity: Optional[str] = None
    context_text: Optional[str] = None
    table_page: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "page_number": self.page_number,
            "metric": self.metric,
            "reporting_year": self.reporting_year,
            "value": self.value,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "entity": self.entity,
            "context_text": self.context_text,
            "table_page": self.table_page,
            "metadata": self.metadata,
        }
