import pandas as pd
from typing import Union
from src.schemas import ExtractedClaim, AuditResult

def verify_claim(
    claim: ExtractedClaim,
    metrics_source: Union[str, pd.DataFrame],
    tolerance: float = 0.05
) -> AuditResult:
    """
    Pure Python & Pandas deterministic rules engine.
    
    Dynamically extracts column names based on baseline_year and target_year
    from ExtractedClaim (e.g. 'fy23_value' and 'fy24_value').
    Calculates actual YoY percentage change in pure Python.
    """
    if isinstance(metrics_source, str):
        df = pd.read_csv(metrics_source)
    else:
        df = metrics_source.copy()
        
    # Clean column names (strip whitespace and convert to lowercase)
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Extract baseline and target year strings
    b_year = claim.baseline_year.strip().upper() if claim.baseline_year else "FY23"
    t_year = claim.target_year.strip().upper() if claim.target_year else "FY24"
    
    b_year_lower = b_year.lower()
    t_year_lower = t_year.lower()
    
    # Construct dynamic column names (e.g., 'fy23_value', 'fy24_value')
    baseline_col = f"{b_year_lower}_value"
    target_col = f"{t_year_lower}_value"
    
    # Locate matching metric row
    matched_row = _find_matching_metric_row(df, claim.metric)
    
    if matched_row is None:
        return AuditResult(
            status="FLAGGED",
            claimed_percentage=claim.claimed_percentage,
            calculated_delta=0.0,
            variance=claim.claimed_percentage,
            discrepancy_reason=f"Unable to locate matching CSV metric record for '{claim.metric}'.",
            matched_metric=None,
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=None,
            target_value=None,
            fy23_value=None,
            fy24_value=None
        )
        
    metric_name = matched_row.get("metric_name", "Emissions Metric")
    
    # Retrieve baseline and target values dynamically
    baseline_val = _extract_year_value(matched_row, baseline_col, b_year_lower)
    target_val = _extract_year_value(matched_row, target_col, t_year_lower)
    
    if baseline_val is None or target_val is None:
        missing_cols = []
        if baseline_val is None:
            missing_cols.append(baseline_col)
        if target_val is None:
            missing_cols.append(target_col)
            
        return AuditResult(
            status="FLAGGED",
            claimed_percentage=claim.claimed_percentage,
            calculated_delta=0.0,
            variance=claim.claimed_percentage,
            discrepancy_reason=f"CSV metrics table is missing required year column(s): {', '.join(missing_cols)}.",
            matched_metric=str(metric_name),
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=baseline_val,
            target_value=target_val,
            fy23_value=baseline_val,
            fy24_value=target_val
        )
        
    if baseline_val == 0.0:
        return AuditResult(
            status="FLAGGED",
            claimed_percentage=claim.claimed_percentage,
            calculated_delta=0.0,
            variance=claim.claimed_percentage,
            discrepancy_reason=f"Baseline year ({b_year}) value is 0. Cannot compute percentage delta.",
            matched_metric=str(metric_name),
            baseline_year=b_year,
            target_year=t_year,
            baseline_value=baseline_val,
            target_value=target_val,
            fy23_value=baseline_val,
            fy24_value=target_val
        )
        
    # PURE PYTHON DETERMINISTIC MATH: Percentage reduction calculation
    # Reduction % = ((Baseline - Target) / Baseline) * 100
    raw_delta = ((baseline_val - target_val) / baseline_val) * 100.0
    calculated_delta = round(raw_delta, 2)
    
    claimed_pct = round(claim.claimed_percentage, 2)
    variance = round(abs(claimed_pct - calculated_delta), 2)
    
    # Verification check
    if variance <= tolerance:
        status = "PASS"
        discrepancy_reason = (
            f"VERIFIED: The claimed {claimed_pct}% reduction matches the ground truth CSV data "
            f"exactly ({b_year}: {baseline_val:,.2f} -> {t_year}: {target_val:,.2f}, actual reduction: {calculated_delta:.2f}%)."
        )
    else:
        status = "FLAGGED"
        discrepancy_reason = (
            f"MATHEMATICAL DISCREPANCY DETECTED: PR narrative claims a {claimed_pct:.2f}% reduction, "
            f"but pure Python audit of metrics.csv calculates only a {calculated_delta:.2f}% reduction "
            f"({b_year}: {baseline_val:,.2f} -> {t_year}: {target_val:,.2f}). Variance: {variance:.2f}%."
        )
        
    return AuditResult(
        status=status,
        claimed_percentage=claimed_pct,
        calculated_delta=calculated_delta,
        variance=variance,
        discrepancy_reason=discrepancy_reason,
        matched_metric=str(metric_name),
        baseline_year=b_year,
        target_year=t_year,
        baseline_value=baseline_val,
        target_value=target_val,
        fy23_value=baseline_val,
        fy24_value=target_val
    )


def _extract_year_value(row: dict, col_name: str, year_str_lower: str) -> Union[float, None]:
    """
    Extracts numerical value for a given dynamic column name or matching year pattern.
    """
    # Direct match on expected column name (e.g. 'fy23_value')
    if col_name in row and pd.notna(row[col_name]):
        try:
            return float(row[col_name])
        except (ValueError, TypeError):
            pass
            
    # Fuzzy match on key containing year string (e.g. 'fy23')
    for key, val in row.items():
        if year_str_lower in str(key).lower() and pd.notna(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
                
    return None


def _find_matching_metric_row(df: pd.DataFrame, claim_metric: str) -> Union[dict, None]:
    """
    Helper function to select the appropriate metric row from metrics.csv.
    """
    # Check for explicit total row (MTR-TOTAL)
    if 'metric_id' in df.columns:
        total_rows = df[df['metric_id'].astype(str).str.upper() == 'MTR-TOTAL']
        if not total_rows.empty:
            return total_rows.iloc[0].to_dict()
            
    # Check for 'Total' in metric_name
    if 'metric_name' in df.columns:
        total_name_rows = df[df['metric_name'].astype(str).str.contains('Total', case=False, na=False)]
        if not total_name_rows.empty:
            return total_name_rows.iloc[0].to_dict()
            
    # Keywords matching
    keywords = [k.lower() for k in claim_metric.split() if len(k) > 3]
    if keywords and 'metric_name' in df.columns:
        for idx, row in df.iterrows():
            m_name = str(row['metric_name']).lower()
            if any(kw in m_name for kw in keywords):
                return row.to_dict()
                
    # Default to first row
    if len(df) > 0:
        return df.iloc[0].to_dict()
        
    return None
