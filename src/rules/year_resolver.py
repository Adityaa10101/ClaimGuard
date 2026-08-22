import re
from typing import Optional, Dict, Any, List, Tuple


DISALLOWED_COLUMN_SUBSTRINGS = [
    "note", "notes", "status", "verification", "verified",
    "comment", "comments", "desc", "description", "source",
    "audit", "unit", "units", "category", "metric_id", "metric_name",
    "yoy", "change", "pct", "percent", "percentage",
    "variance", "delta", "diff", "ratio", "growth"
]


def normalize_fiscal_year(raw_year: Optional[str]) -> Optional[str]:
    """
    Normalizes arbitrary year strings into canonical 'FYxx' format.
    Examples:
        'FY23' -> 'FY23'
        'fy24' -> 'FY24'
        '2024' -> 'FY24'
        'FY2024' -> 'FY24'
        'Fiscal Year 2025' -> 'FY25'
        'F.Y. 23' -> 'FY23'
    """
    if not raw_year or not isinstance(raw_year, str):
        return None

    cleaned = raw_year.strip().upper()
    
    # Match patterns like FY23, FY2023, 2023, FY 24, FISCAL YEAR 2024
    match = re.search(r'(?:FY|F\.Y\.|FISCAL\s*YEAR)?\s*(20)?(\d{2})\b', cleaned, re.IGNORECASE)
    if match:
        two_digit_yr = match.group(2)
        return f"FY{two_digit_yr}"
        
    return None


def is_safe_value_column(col_name: str) -> bool:
    """Verifies that a column name is not a metadata, notes, or pre-calculated delta column."""
    col_lower = col_name.strip().lower()
    for disallowed in DISALLOWED_COLUMN_SUBSTRINGS:
        # Check if the disallowed token exists as a word or suffix
        if disallowed in col_lower:
            return False
    return True


def resolve_year_column(df_columns: List[str], canonical_year: str) -> Optional[str]:
    """
    Resolves the ground-truth value column corresponding to a canonical fiscal year.
    Never matches notes, status, verification, or pre-computed variance columns.
    
    Priority:
    1. Exact 'fyXX_value' (e.g. 'fy24_value')
    2. Exact 'fyXX' (e.g. 'fy24')
    3. Exact 'fy20XX_value' (e.g. 'fy2024_value')
    4. Exact 'fy20XX' (e.g. 'fy2024')
    5. Exact '20XX_value' or 'XX_value'
    6. Exact '20XX' or 'XX' (if column contains safe data)
    """
    if not canonical_year or not df_columns:
        return None

    yr_num = canonical_year.replace("FY", "").strip()
    four_digit_yr = f"20{yr_num}"
    
    col_map = {col.strip().lower(): col for col in df_columns}
    
    # Priority candidate list in order of strictness
    candidate_patterns = [
        f"fy{yr_num.lower()}_value",
        f"fy{four_digit_yr}_value",
        f"fy{yr_num.lower()}",
        f"fy{four_digit_yr}",
        f"{four_digit_yr}_value",
        f"{yr_num.lower()}_value",
        f"fy{yr_num.lower()}_actual",
        f"{four_digit_yr}",
    ]

    for pat in candidate_patterns:
        if pat in col_map:
            original_col = col_map[pat]
            if is_safe_value_column(original_col):
                return original_col

    # Fallback: scan columns that contain the year token and the word 'value' or 'actual'
    for col_lower, original_col in col_map.items():
        if (f"fy{yr_num.lower()}" in col_lower or four_digit_yr in col_lower):
            if ("value" in col_lower or "actual" in col_lower) and is_safe_value_column(original_col):
                return original_col

    return None


def extract_numeric_value(row: Dict[str, Any], col_name: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts a numeric float value from a row dict for the resolved column.
    Returns (float_value, error_message).
    """
    if col_name not in row:
        return None, f"Column '{col_name}' not found in record."

    raw_val = row[col_name]
    if raw_val is None or (isinstance(raw_val, float) and str(raw_val) == "nan"):
        return None, f"Value in column '{col_name}' is empty (NaN)."

    try:
        # Handle formatted strings like "10,500.00"
        if isinstance(raw_val, str):
            cleaned_str = raw_val.replace(",", "").strip()
            return float(cleaned_str), None
        return float(raw_val), None
    except (ValueError, TypeError):
        return None, f"Value '{raw_val}' in column '{col_name}' cannot be converted to numeric float."
