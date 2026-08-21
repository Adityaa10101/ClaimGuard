import os
import re
import json
from typing import Optional
from dotenv import load_dotenv
from src.schemas import ExtractedClaim

# Load environment variables from .env file
load_dotenv()


def extract_claim_from_narrative(
    narrative_text: str,
    api_key: Optional[str] = None
) -> ExtractedClaim:
    """
    Extracts structured ESG claims from raw PR narrative text.
    Uses Groq API with JSON mode if GROQ_API_KEY is available.
    Falls back to deterministic rule extraction if API key is not present.
    
    The LLM is strictly prohibited from carrying out mathematical calculations.
    """
    effective_api_key = api_key or os.getenv("GROQ_API_KEY")

    if effective_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=effective_api_key)
            
            prompt = (
                "You are a strict data extraction parser. Your sole job is to extract claimed figures "
                "from the provided ESG / BRSR sustainability PR narrative into structured JSON.\n"
                "DO NOT calculate any math or verify numbers. Simply extract the stated claim.\n\n"
                "Return a JSON object with the following exact keys:\n"
                "- metric (string, e.g. 'Total Scope 1 & 2 Emissions')\n"
                "- claimed_percentage (float, e.g. 2.59 or 20.0, positive number representing reduction percentage)\n"
                "- baseline_year (string, earlier comparison baseline year, e.g. 'FY23')\n"
                "- target_year (string, later evaluation target year, e.g. 'FY24')\n"
                "- claim_text (string, verbatim claim sentence)\n\n"
                f"Narrative Text:\n\"\"\"\n{narrative_text}\n\"\"\""
            )
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON-only extraction engine. Return raw JSON adhering strictly to the requested schema without markdown or formatting."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            raw_json = response.choices[0].message.content
            parsed_data = json.loads(raw_json)
            return ExtractedClaim(**parsed_data)
            
        except Exception as e:
            # Fallback if API call fails or model unavailable
            print(f"[Warning] Groq API call failed ({e}). Using deterministic rule fallback.")
    
    # Deterministic fallback parser (for offline testing or zero-config hackathon demo)
    return _fallback_rule_extraction(narrative_text)


def _fallback_rule_extraction(narrative_text: str) -> ExtractedClaim:
    """
    Offline pattern extractor for narrative text.
    Extracts percentage claims, baseline year, target year, and metric.
    """
    # Find percentage claim (e.g. 2.59%, 20.00%, 20%)
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:reduction|decrease|cut)', narrative_text, re.IGNORECASE)
    if not pct_match:
        pct_match = re.search(r'(?:reduced|cut|decreased)\s+.*?\s+(\d+(?:\.\d+)?)\s*%', narrative_text, re.IGNORECASE)
    
    claimed_pct = float(pct_match.group(1)) if pct_match else 0.0

    # Find baseline and target years chronologically (e.g. FY23, FY24)
    found_years = re.findall(r'FY\d{2,4}', narrative_text, re.IGNORECASE)
    unique_years = sorted(list(set([y.upper() for y in found_years])))
    
    if len(unique_years) >= 2:
        baseline_year = unique_years[0]
        target_year = unique_years[1]
    elif len(unique_years) == 1:
        target_year = unique_years[0]
        try:
            yr_num = int(re.sub(r'\D', '', target_year))
            baseline_year = f"FY{yr_num - 1}"
        except ValueError:
            baseline_year = "FY23"
    else:
        baseline_year = "FY23"
        target_year = "FY24"


    # Find verbatim claim sentence
    sentences = narrative_text.split('\n')
    claim_sentence = ""
    for sentence in sentences:
        if "%" in sentence or "reduction" in sentence.lower():
            claim_sentence = sentence.strip("- ").strip()
            break

    # Determine metric name
    metric_name = "Total Scope 1 & 2 Emissions"
    if "water" in narrative_text.lower():
        metric_name = "Facility Water Usage"
    elif "waste" in narrative_text.lower():
        metric_name = "Solid Waste Generated"

    return ExtractedClaim(
        metric=metric_name,
        claimed_percentage=claimed_pct,
        baseline_year=baseline_year,
        target_year=target_year,
        claim_text=claim_sentence or narrative_text[:100]
    )
