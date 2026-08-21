"""
ClaimGuard Rules Engine — Registry-based deterministic validation.

Architecture:
- BaseRule: Abstract base class for all validation rules
- RuleEngine: Registry that manages and executes rules
- DataFrame helpers: Utilities for finding data in source CSVs

Each rule:
1. Receives a Claim and source DataFrame
2. Performs DETERMINISTIC math (no LLM)
3. Returns a RuleResult with full evidence chain
"""

import time
import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, List, Union

from src.schemas import (
    Claim, RuleResult, AuditReport, AuditSummary,
    ProcessingTime, ValidationStatus, Severity, Authority,
)


# ─── DataFrame Helpers ───────────────────────────────────────────────────────

def find_metric_row(
    df: pd.DataFrame,
    metric_name: str
) -> Optional[dict]:
    """
    Find a row in the source DataFrame matching the given metric name.

    Search priority:
    1. Exact metric_id match (e.g. 'MTR-TOTAL')
    2. Exact metric_name match (case-insensitive)
    3. Keyword overlap match
    4. First row fallback
    """
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    metric_lower = metric_name.strip().lower()

    # 1. Check for explicit total row
    if "metric_id" in df.columns:
        id_match = df[df["metric_id"].astype(str).str.strip().str.upper() == metric_name.strip().upper()]
        if not id_match.empty:
            return id_match.iloc[0].to_dict()

    # 2. Exact metric_name match
    if "metric_name" in df.columns:
        exact = df[df["metric_name"].astype(str).str.strip().str.lower() == metric_lower]
        if not exact.empty:
            return exact.iloc[0].to_dict()

    # 3. Check for 'Total' rows if metric mentions total
    if "total" in metric_lower and "metric_name" in df.columns:
        total_rows = df[df["metric_name"].astype(str).str.contains("Total", case=False, na=False)]
        if not total_rows.empty:
            return total_rows.iloc[0].to_dict()

    # 4. Keyword overlap
    keywords = [k.lower() for k in metric_name.split() if len(k) > 3]
    if keywords and "metric_name" in df.columns:
        best_match = None
        best_score = 0
        for _, row in df.iterrows():
            m_name = str(row.get("metric_name", "")).lower()
            score = sum(1 for kw in keywords if kw in m_name)
            if score > best_score:
                best_score = score
                best_match = row.to_dict()
        if best_match and best_score > 0:
            return best_match

    # 5. Fallback to first row
    if len(df) > 0:
        return df.iloc[0].to_dict()

    return None


def find_row_by_keyword(
    df: pd.DataFrame,
    keywords: List[str],
    exclude_keywords: Optional[List[str]] = None
) -> Optional[dict]:
    """
    Find a row whose metric_name contains any of the given keywords
    but none of the exclude_keywords.
    """
    df_clean = df.copy()
    df_clean.columns = [c.strip().lower() for c in df_clean.columns]

    if "metric_name" not in df_clean.columns:
        return None

    exclude = exclude_keywords or []

    for _, row in df_clean.iterrows():
        m_name = str(row.get("metric_name", "")).lower()
        if any(kw.lower() in m_name for kw in keywords):
            if not any(ex.lower() in m_name for ex in exclude):
                return row.to_dict()

    return None


def get_period_value(row: dict, period: str) -> Optional[float]:
    """
    Extract the numerical value for a given period (e.g. 'FY24') from a row dict.

    Looks for columns like 'fy24_value', or any column containing 'fy24'.
    """
    period_lower = period.strip().lower()
    target_col = f"{period_lower}_value"

    # Direct match: 'fy24_value'
    if target_col in row and pd.notna(row[target_col]):
        try:
            return float(row[target_col])
        except (ValueError, TypeError):
            pass

    # Fuzzy match: any column containing the period string
    for key, val in row.items():
        if period_lower in str(key).lower() and "value" in str(key).lower():
            if pd.notna(val):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue

    # Even fuzzier: any column with the period string
    for key, val in row.items():
        if period_lower in str(key).lower() and pd.notna(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                continue

    return None


def get_unit_for_row(row: dict) -> Optional[str]:
    """Extract the unit field from a row dict."""
    for key in ["unit", "units", "uom"]:
        if key in row and pd.notna(row[key]):
            return str(row[key]).strip()
    return None


# ─── Base Rule ────────────────────────────────────────────────────────────────

class BaseRule(ABC):
    """
    Abstract base class for all deterministic validation rules.

    Subclasses must set class-level attributes:
        rule_id, rule_name, category, severity
    and implement evaluate().
    """

    rule_id: str = ""
    rule_name: str = ""
    category: str = "general"
    severity: Severity = Severity.MEDIUM
    authority: Authority = Authority.DETERMINISTIC

    def applies_to(self, claim: Claim) -> bool:
        """Check if this rule applies to the given claim's category."""
        if self.category == "general":
            return True
        return claim.category.value == self.category

    @abstractmethod
    def evaluate(self, claim: Claim, source_data: pd.DataFrame) -> RuleResult:
        """Execute deterministic validation. No LLM involvement."""
        ...

    def _pass(
        self,
        reported: float,
        calculated: float,
        formula: str,
        explanation: str,
        evidence: str = "",
        claim_id: str = ""
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            claim_id=claim_id,
            status=ValidationStatus.PASS,
            severity=self.severity,
            reported_value=round(reported, 4),
            calculated_value=round(calculated, 4),
            variance=round(abs(reported - calculated), 4),
            formula=formula,
            explanation=explanation,
            source_evidence=evidence,
            authority=self.authority,
        )

    def _fail(
        self,
        reported: float,
        calculated: float,
        formula: str,
        explanation: str,
        evidence: str = "",
        claim_id: str = ""
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            claim_id=claim_id,
            status=ValidationStatus.FAIL,
            severity=self.severity,
            reported_value=round(reported, 4),
            calculated_value=round(calculated, 4),
            variance=round(abs(reported - calculated), 4),
            formula=formula,
            explanation=explanation,
            source_evidence=evidence,
            authority=self.authority,
        )

    def _unsupported(
        self,
        explanation: str,
        evidence: str = "",
        claim_id: str = ""
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            claim_id=claim_id,
            status=ValidationStatus.UNSUPPORTED,
            severity=Severity.INFO,
            explanation=explanation,
            source_evidence=evidence,
            authority=self.authority,
        )


# ─── Rule Engine ──────────────────────────────────────────────────────────────

class RuleEngine:
    """
    Registry of deterministic rules.

    Evaluates claims against source data and produces audit reports.
    """

    def __init__(self) -> None:
        self._rules: List[BaseRule] = []

    def register(self, rule: BaseRule) -> None:
        """Register a single rule."""
        self._rules.append(rule)

    def register_all(self, rules: List[BaseRule]) -> None:
        """Register multiple rules at once."""
        self._rules.extend(rules)

    @property
    def rules(self) -> List[BaseRule]:
        return list(self._rules)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def evaluate_claim(
        self,
        claim: Claim,
        source_data: pd.DataFrame
    ) -> List[RuleResult]:
        """Run all applicable rules against a single claim."""
        results: List[RuleResult] = []
        for rule in self._rules:
            if rule.applies_to(claim):
                try:
                    result = rule.evaluate(claim, source_data)
                    result.claim_id = claim.claim_id
                    results.append(result)
                except Exception as e:
                    results.append(RuleResult(
                        rule_id=rule.rule_id,
                        rule_name=rule.rule_name,
                        claim_id=claim.claim_id,
                        status=ValidationStatus.UNSUPPORTED,
                        severity=Severity.INFO,
                        explanation=f"Rule execution error: {str(e)}",
                        authority=rule.authority,
                    ))
        return results

    def evaluate_all(
        self,
        claims: List[Claim],
        source_data: pd.DataFrame,
        company: str = "",
        filing_period: str = "",
        processing_time: Optional[ProcessingTime] = None,
    ) -> AuditReport:
        """Run all rules against all claims and produce a complete audit report."""
        start = time.time()
        all_results: List[RuleResult] = []

        for claim in claims:
            results = self.evaluate_claim(claim, source_data)
            all_results.extend(results)

        validation_time = time.time() - start

        passed = sum(1 for r in all_results if r.status == ValidationStatus.PASS)
        failed = sum(1 for r in all_results if r.status == ValidationStatus.FAIL)
        unsupported = sum(1 for r in all_results if r.status == ValidationStatus.UNSUPPORTED)
        high_failures = sum(
            1 for r in all_results
            if r.status == ValidationStatus.FAIL and r.severity == Severity.HIGH
        )

        pt = processing_time or ProcessingTime()
        pt.validation_s = round(validation_time, 3)
        pt.total_s = round(
            pt.pdf_extraction_s + pt.ai_extraction_s + pt.validation_s, 3
        )

        return AuditReport(
            company=company,
            filing_period=filing_period,
            claims=claims,
            results=all_results,
            summary=AuditSummary(
                total_claims=len(claims),
                total_rules_executed=len(all_results),
                passed=passed,
                failed=failed,
                unsupported=unsupported,
                high_severity_failures=high_failures,
            ),
            processing_time=pt,
        )


# ─── Factory ─────────────────────────────────────────────────────────────────

def create_default_engine() -> RuleEngine:
    """
    Create a RuleEngine with all 15 production rules registered.

    Import here to avoid circular imports.
    """
    from src.rules.emissions import (
        EmissionsAbsoluteRule,
        EmissionsReductionPctRule,
        EmissionsYoYDirectionRule,
        EmissionsScopeConsistencyRule,
    )
    from src.rules.energy import (
        EnergyRenewablePctRule,
        EnergyTotalChangeRule,
        EnergyRenewableCrosscheckRule,
    )
    from src.rules.water import (
        WaterConsumptionChangeRule,
        WaterRecyclingPctRule,
    )
    from src.rules.general import (
        UnitConsistencyRule,
        YearConsistencyRule,
        PctBoundsRule,
        TotalSubtotalRule,
        CrossTableConsistencyRule,
        MissingEvidenceRule,
    )

    engine = RuleEngine()
    engine.register_all([
        # Emissions (4 rules)
        EmissionsAbsoluteRule(),
        EmissionsReductionPctRule(),
        EmissionsYoYDirectionRule(),
        EmissionsScopeConsistencyRule(),
        # Energy (3 rules)
        EnergyRenewablePctRule(),
        EnergyTotalChangeRule(),
        EnergyRenewableCrosscheckRule(),
        # Water (2 rules)
        WaterConsumptionChangeRule(),
        WaterRecyclingPctRule(),
        # General (6 rules)
        UnitConsistencyRule(),
        YearConsistencyRule(),
        PctBoundsRule(),
        TotalSubtotalRule(),
        CrossTableConsistencyRule(),
        MissingEvidenceRule(),
    ])
    return engine
