"""
ClaimGuard Claim Extractor — Multi-claim extraction from narrative text.

Supports:
1. Groq API (Llama 3.3) with structured JSON output → list of Claims
2. Robust regex fallback for offline / zero-config usage

The LLM is STRICTLY PROHIBITED from performing mathematical validation.
It only extracts stated claims as structured data.
"""

import os
import re
import json
from typing import Optional, List
from dotenv import load_dotenv

from src.schemas import (
    Claim, ExtractedClaim, ClaimCategory, detect_category,
)

load_dotenv()


# ─── Multi-Claim Extraction (Production) ─────────────────────────────────────

def extract_claims_from_narrative(
    narrative_text: str,
    company: str = "",
    api_key: Optional[str] = None,
) -> List[Claim]:
    """
    Extract ALL ESG claims from narrative text as a list of Claim objects.

    Uses Groq API if available, otherwise falls back to regex extraction.
    The LLM is forbidden from doing any math — it only extracts stated values.
    """
    effective_api_key = api_key or os.getenv("GROQ_API_KEY")

    if effective_api_key:
        try:
            return _extract_via_llm(narrative_text, company, effective_api_key)
        except Exception as e:
            print(f"[Warning] Groq API call failed ({e}). Using regex fallback.")

    return _extract_via_regex(narrative_text, company)


def _extract_via_llm(
    narrative_text: str,
    company: str,
    api_key: str,
) -> List[Claim]:
    """Extract claims using Groq LLM with structured JSON output."""
    from groq import Groq

    client = Groq(api_key=api_key)

    prompt = (
        "You are a strict data extraction parser for ESG/BRSR sustainability reports.\n"
        "Your SOLE job is to extract ALL claimed figures from the text into structured JSON.\n"
        "DO NOT calculate, verify, or validate any numbers. Simply extract what is stated.\n\n"
        "Return a JSON object with a single key 'claims' containing an array.\n"
        "Each claim object MUST have these keys:\n"
        "- metric (string): The ESG metric (e.g. 'Total Scope 1 & 2 Emissions')\n"
        "- category (string): One of 'emissions', 'energy', 'water', 'waste', 'general'\n"
        "- reported_value (float): The numerical value claimed (e.g. 2.59 for 2.59%)\n"
        "- reported_unit (string): 'percent' for percentages, or the unit (MT CO2e, kWh, etc.)\n"
        "- previous_value (float or null): Baseline period value if mentioned\n"
        "- current_value (float or null): Current period value if mentioned\n"
        "- previous_period (string): Baseline year (e.g. 'FY23')\n"
        "- current_period (string): Current year (e.g. 'FY24')\n"
        "- source_text (string): The verbatim sentence containing the claim\n"
        "- confidence (float): Your extraction confidence (0.0 to 1.0)\n\n"
        "IMPORTANT: Extract EVERY quantitative claim in the text, not just the first one.\n"
        "Look for: percentage changes, absolute values, year-over-year comparisons.\n\n"
        f"Narrative Text:\n\"\"\"\n{narrative_text}\n\"\"\""
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a JSON-only extraction engine. Return raw JSON "
                    "adhering strictly to the requested schema. No markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw_json = response.choices[0].message.content
    parsed = json.loads(raw_json)

    claims_data = parsed.get("claims", [parsed] if "metric" in parsed else [])

    claims = []
    for i, item in enumerate(claims_data):
        try:
            claim = Claim(
                company=company,
                metric=item.get("metric", "Unknown Metric"),
                category=item.get("category", detect_category(item.get("metric", ""))),
                reported_value=float(item.get("reported_value", 0)),
                reported_unit=item.get("reported_unit", "percent"),
                previous_value=_safe_float(item.get("previous_value")),
                current_value=_safe_float(item.get("current_value")),
                previous_period=item.get("previous_period", "FY23"),
                current_period=item.get("current_period", "FY24"),
                source_text=item.get("source_text", ""),
                confidence=float(item.get("confidence", 0.8)),
            )
            claims.append(claim)
        except Exception as e:
            print(f"[Warning] Failed to parse claim {i}: {e}")
            continue

    return claims if claims else _extract_via_regex(narrative_text, company)


def _extract_via_regex(
    narrative_text: str,
    company: str = "",
) -> List[Claim]:
    """
    Robust offline pattern extractor for narrative text.

    Extracts multiple claims by scanning for percentage and numerical patterns
    across emissions, energy, water, and waste categories.
    """
    claims: List[Claim] = []
    text = narrative_text

    # --- Find baseline and target years ---
    found_years = re.findall(r"FY\d{2,4}", text, re.IGNORECASE)
    unique_years = sorted(list(set(y.upper() for y in found_years)))

    if len(unique_years) >= 2:
        baseline_year = unique_years[0]
        target_year = unique_years[1]
    elif len(unique_years) == 1:
        target_year = unique_years[0]
        try:
            yr_num = int(re.sub(r"\D", "", target_year))
            baseline_year = f"FY{yr_num - 1}"
        except ValueError:
            baseline_year = "FY23"
    else:
        baseline_year = "FY23"
        target_year = "FY24"

    # --- Split into sentences for per-claim extraction ---
    # Split on newlines and sentence-ending periods, but NOT decimal points
    sentences = re.split(r"\n|(?<=\D)\.(?=\s|$)", text)

    # Percentage claim patterns
    pct_patterns = [
        # "2.59% reduction" / "35% decrease" / "35% cut"
        r"(\d+(?:\.\d+)?)\s*%\s*(?:reduction|decrease|cut|decline|drop|improvement)",
        # "reduced by 35%" / "decreased by 35%"
        r"(?:reduced?|decreased?|cut|dropped?|declined?|improved?)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
        # "a 35% reduction" / "a 2.59% decrease"
        r"a\s+(\d+(?:\.\d+)?)\s*%\s+(?:reduction|decrease|drop|decline)",
        # Just a standalone percentage near keywords
        r"(\d+(?:\.\d+)?)\s*%\s*(?:year-over-year|yoy|y-o-y|compared)",
        # Broad fallback: any number followed by %
        r"(\d+(?:\.\d+)?)\s*%",
    ]

    # Absolute value patterns
    abs_patterns = [
        # "10,228.05 metric tons" / "10228.05 MT CO2e"
        r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:metric\s+tons?|MT|tonnes?)\s*(?:CO2e?|CO₂e?)?",
        # "15,200 kGal" / "14900.00 kGal"
        r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:kGal|kiloliters?|KL)",
        # "850 tons"
        r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:tons?|tonnes?)\s+(?:of\s+)?(?:waste|solid)",
    ]

    # Category detection keywords
    category_keywords = {
        "emissions": ["emission", "scope", "co2", "ghg", "carbon", "greenhouse"],
        "energy": ["energy", "electricity", "renewable", "solar", "wind", "kwh", "mwh"],
        "water": ["water", "kgal", "consumption"],
        "waste": ["waste", "landfill", "solid waste", "recycl"],
    }

    # Extract percentage claims from each sentence
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue

        for pattern in pct_patterns:
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            for match_val in matches:
                try:
                    pct_val = float(match_val)
                except ValueError:
                    continue

                # Detect category and metric
                cat, metric = _detect_metric_from_context(
                    sentence, category_keywords
                )

                # Avoid duplicates
                is_dup = any(
                    abs(c.reported_value - pct_val) < 0.01
                    and c.metric == metric
                    for c in claims
                )
                if is_dup:
                    continue

                # Try to extract absolute values from the sentence
                prev_val = _extract_absolute_value(sentence, baseline_year)
                curr_val = _extract_absolute_value(sentence, target_year)

                claims.append(Claim(
                    company=company,
                    metric=metric,
                    category=cat,
                    reported_value=pct_val,
                    reported_unit="percent",
                    previous_value=prev_val,
                    current_value=curr_val,
                    previous_period=baseline_year,
                    current_period=target_year,
                    source_text=sentence.strip("- ").strip(),
                    confidence=0.7,
                ))

    # If nothing found, try a broader scan of the entire text
    if not claims:
        for pattern in pct_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match_val in matches:
                try:
                    pct_val = float(match_val)
                except ValueError:
                    continue

                cat, metric = _detect_metric_from_context(text, category_keywords)

                claims.append(Claim(
                    company=company,
                    metric=metric,
                    category=cat,
                    reported_value=pct_val,
                    reported_unit="percent",
                    previous_period=baseline_year,
                    current_period=target_year,
                    source_text=text[:200],
                    confidence=0.5,
                ))
                break  # At least get one

    # If still nothing, return a default unsupported claim
    if not claims:
        claims.append(Claim(
            company=company,
            metric="Unknown Metric",
            category=ClaimCategory.GENERAL,
            reported_value=0.0,
            reported_unit="percent",
            previous_period=baseline_year,
            current_period=target_year,
            source_text=text[:200] if text else "",
            confidence=0.1,
        ))

    return claims


def _detect_metric_from_context(
    text: str,
    category_keywords: dict,
) -> tuple:
    """Detect the ESG category and metric name from context text."""
    text_lower = text.lower()

    for cat, keywords in category_keywords.items():
        if any(kw in text_lower for kw in keywords):
            if cat == "emissions":
                if "scope 1" in text_lower and "scope 2" in text_lower:
                    return ClaimCategory.EMISSIONS, "Total Scope 1 & 2 Emissions"
                elif "scope 1" in text_lower:
                    return ClaimCategory.EMISSIONS, "Scope 1 Direct Emissions"
                elif "scope 2" in text_lower:
                    return ClaimCategory.EMISSIONS, "Scope 2 Indirect Emissions"
                return ClaimCategory.EMISSIONS, "Total Scope 1 & 2 Emissions"
            elif cat == "energy":
                if "renewable" in text_lower:
                    return ClaimCategory.ENERGY, "Renewable Energy"
                return ClaimCategory.ENERGY, "Total Energy Consumption"
            elif cat == "water":
                if "recycl" in text_lower:
                    return ClaimCategory.WATER, "Water Recycled"
                return ClaimCategory.WATER, "Facility Water Usage"
            elif cat == "waste":
                return ClaimCategory.WASTE, "Solid Waste Generated"

    return ClaimCategory.GENERAL, "Unknown Metric"


def _extract_absolute_value(text: str, period: str) -> Optional[float]:
    """Try to extract an absolute numerical value near a period reference."""
    period_lower = period.lower()
    text_lower = text.lower()

    if period_lower not in text_lower:
        return None

    # Look for numbers near the period reference
    pattern = (
        rf"(?:{re.escape(period_lower)}[^0-9]{{0,30}})"
        rf"(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)"
    )
    match = re.search(pattern, text_lower)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass

    return None


def _safe_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ─── Legacy API (Backward Compatibility) ────────────────────────────────────

def extract_claim_from_narrative(
    narrative_text: str,
    api_key: Optional[str] = None,
) -> ExtractedClaim:
    """
    Legacy API: extract a single claim as ExtractedClaim.

    For new code, use extract_claims_from_narrative() instead.
    """
    effective_api_key = api_key or os.getenv("GROQ_API_KEY")

    if effective_api_key:
        try:
            from groq import Groq

            client = Groq(api_key=effective_api_key)

            prompt = (
                "You are a strict data extraction parser. Your sole job is to extract "
                "claimed figures from the provided ESG / BRSR sustainability PR "
                "narrative into structured JSON.\n"
                "DO NOT calculate any math or verify numbers. Simply extract the stated claim.\n\n"
                "Return a JSON object with the following exact keys:\n"
                "- metric (string, e.g. 'Total Scope 1 & 2 Emissions')\n"
                "- claimed_percentage (float, e.g. 2.59 or 20.0, positive number)\n"
                "- baseline_year (string, earlier year, e.g. 'FY23')\n"
                "- target_year (string, later year, e.g. 'FY24')\n"
                "- claim_text (string, verbatim claim sentence)\n\n"
                f"Narrative Text:\n\"\"\"\n{narrative_text}\n\"\"\""
            )

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON-only extraction engine. Return raw JSON "
                            "adhering strictly to the requested schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            raw_json = response.choices[0].message.content
            parsed_data = json.loads(raw_json)
            return ExtractedClaim(**parsed_data)

        except Exception as e:
            print(f"[Warning] Groq API call failed ({e}). Using regex fallback.")

    return _fallback_rule_extraction(narrative_text)


def _fallback_rule_extraction(narrative_text: str) -> ExtractedClaim:
    """Offline pattern extractor returning legacy ExtractedClaim format."""
    # Use the new multi-claim extractor and convert back
    claims = _extract_via_regex(narrative_text)

    if claims:
        c = claims[0]
        return ExtractedClaim(
            metric=c.metric,
            claimed_percentage=c.reported_value,
            baseline_year=c.previous_period,
            target_year=c.current_period,
            claim_text=c.source_text,
        )

    # Ultimate fallback
    return ExtractedClaim(
        metric="Total Scope 1 & 2 Emissions",
        claimed_percentage=0.0,
        baseline_year="FY23",
        target_year="FY24",
        claim_text=narrative_text[:100],
    )
