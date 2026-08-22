import re
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd


class MetricResolutionStatus(str, Enum):
    EXACT_NAME_MATCH = "EXACT_NAME_MATCH"
    EXACT_ID_MATCH = "EXACT_ID_MATCH"
    ALIAS_MATCH = "ALIAS_MATCH"
    CATEGORY_KEYWORD_MATCH = "CATEGORY_KEYWORD_MATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    NO_MATCH = "NO_MATCH"


# Controlled domain-specific alias / synonym map
ESG_CANONICAL_ALIASES: Dict[str, str] = {
    # Emissions aliases
    "total scope 1 2 emissions": "total scope 1 & 2 emissions",
    "total scope 1 and 2 emissions": "total scope 1 & 2 emissions",
    "scope 1 and 2 emissions": "total scope 1 & 2 emissions",
    "scope 1 2 emissions": "total scope 1 & 2 emissions",
    "total emissions": "total scope 1 & 2 emissions",
    "total ghg emissions": "total scope 1 & 2 emissions",
    "combined emissions": "total scope 1 & 2 emissions",
    "scope 1 direct emissions": "scope 1 direct emissions",
    "scope 1 direct": "scope 1 direct emissions",
    "scope 1 emissions": "scope 1 direct emissions",
    "scope 1": "scope 1 direct emissions",
    "scope 2 indirect emissions": "scope 2 indirect emissions",
    "scope 2 indirect": "scope 2 indirect emissions",
    "scope 2 emissions": "scope 2 indirect emissions",
    "scope 2": "scope 2 indirect emissions",
    "scope 3 emissions": "scope 3 value chain emissions",
    "scope 3": "scope 3 value chain emissions",

    # Water aliases
    "facility water usage": "facility water usage",
    "water usage": "facility water usage",
    "water consumption": "facility water usage",
    "total water consumption": "facility water usage",
    "total water usage": "facility water usage",
    "facility water consumption": "facility water usage",
    "water withdrawal": "facility water withdrawal",

    # Waste aliases
    "solid waste generated": "solid waste generated",
    "waste generated": "solid waste generated",
    "solid waste": "solid waste generated",
    "total waste": "solid waste generated",

    # Energy aliases
    "renewable energy mix": "renewable energy percentage",
    "renewable energy percentage": "renewable energy percentage",
    "renewable power percentage": "renewable energy percentage",
    "grid electricity consumption": "purchased grid electricity",
    "total energy consumption": "total energy consumption",
}


def normalize_metric_text(text: str) -> str:
    """Normalizes string for comparison: strips punctuation, lowercase, collapse whitespace."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = re.sub(r'[\&\-_/\\,\(\)]+', ' ', text.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def resolve_metric(
    claim_metric: str,
    df: pd.DataFrame
) -> Tuple[MetricResolutionStatus, Optional[Dict[str, Any]], str, List[str]]:
    """
    Conservative, deterministic metric resolution algorithm.
    
    Priority:
    1. Exact normalized metric_name match.
    2. Exact metric_id match.
    3. Explicit controlled alias/synonym map.
    4. Strong category/domain keyword match (with strict ambiguity detection).
    5. Otherwise: NO_MATCH or AMBIGUOUS_MATCH.
    
    Never silently falls back to MTR-TOTAL or df.iloc[0].
    
    Returns:
        (MetricResolutionStatus, matched_row_dict_or_None, reason_message, candidate_matches_list)
    """
    if df is None or df.empty:
        return MetricResolutionStatus.NO_MATCH, None, "Metrics table is empty or None.", []

    claim_norm = normalize_metric_text(claim_metric)
    if not claim_norm:
        return MetricResolutionStatus.NO_MATCH, None, "Extracted claim metric is empty.", []

    # Prepare DataFrame column views
    rows = df.to_dict(orient="records")

    # 1. Exact normalized metric_name match
    for row in rows:
        metric_name = str(row.get("metric_name", ""))
        if normalize_metric_text(metric_name) == claim_norm:
            return (
                MetricResolutionStatus.EXACT_NAME_MATCH,
                row,
                f"Exact match on metric_name: '{metric_name}'",
                [metric_name]
            )

    # 2. Exact metric_id match
    for row in rows:
        metric_id = str(row.get("metric_id", "")).strip().upper()
        if metric_id and metric_id == claim_metric.strip().upper():
            metric_name = str(row.get("metric_name", metric_id))
            return (
                MetricResolutionStatus.EXACT_ID_MATCH,
                row,
                f"Exact match on metric_id: '{metric_id}'",
                [metric_name]
            )

    # 3. Explicit controlled alias / synonym map
    if claim_norm in ESG_CANONICAL_ALIASES:
        canonical_target = ESG_CANONICAL_ALIASES[claim_norm]
        for row in rows:
            metric_name = str(row.get("metric_name", ""))
            if normalize_metric_text(metric_name) == canonical_target:
                return (
                    MetricResolutionStatus.ALIAS_MATCH,
                    row,
                    f"Resolved alias '{claim_metric}' -> '{metric_name}' via controlled synonym dictionary.",
                    [metric_name]
                )

    # 4. Strong domain / category-constrained keyword matching
    # Filter stopwords
    stopwords = {"and", "the", "for", "with", "across", "total", "in", "of", "all", "our", "per", "annual"}
    claim_tokens = set(t for t in claim_norm.split() if len(t) >= 3 and t not in stopwords)

    if not claim_tokens:
        return MetricResolutionStatus.NO_MATCH, None, f"No significant keywords found in claim metric: '{claim_metric}'", []

    candidates: List[Tuple[Dict[str, Any], int, str]] = []

    for row in rows:
        row_name = str(row.get("metric_name", ""))
        row_cat = str(row.get("category", ""))
        row_tokens = set(normalize_metric_text(row_name).split())
        row_cat_tokens = set(normalize_metric_text(row_cat).split())

        # Exact token overlap
        matched_tokens = claim_tokens.intersection(row_tokens)
        cat_matched = claim_tokens.intersection(row_cat_tokens)

        score = len(matched_tokens) * 2 + len(cat_matched)

        # Require that at least 50% of the claim's distinctive tokens are present in the row
        overlap_ratio = len(matched_tokens) / len(claim_tokens) if claim_tokens else 0
        if score > 0 and (overlap_ratio >= 0.5 or len(matched_tokens) >= 2):
            candidates.append((row, score, row_name))

    if not candidates:
        return (
            MetricResolutionStatus.NO_MATCH,
            None,
            f"No matching CSV metric record found for '{claim_metric}'.",
            []
        )

    # Sort candidates by match score descending
    candidates.sort(key=lambda c: c[1], reverse=True)
    top_score = candidates[0][1]
    top_candidates = [c for c in candidates if c[1] == top_score]

    # Check for ambiguity: multiple top-score candidates
    if len(top_candidates) > 1:
        cand_names = [c[2] for c in top_candidates]
        return (
            MetricResolutionStatus.AMBIGUOUS_MATCH,
            None,
            f"Ambiguous metric query: '{claim_metric}' matches multiple candidate rows equally: {cand_names}.",
            cand_names
        )

    # Distinct top candidate selected
    selected_row, _, selected_name = top_candidates[0]
    return (
        MetricResolutionStatus.CATEGORY_KEYWORD_MATCH,
        selected_row,
        f"Matched metric '{selected_name}' via category-constrained keyword resolution.",
        [selected_name]
    )
