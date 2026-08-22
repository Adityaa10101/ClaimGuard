from typing import List, Optional, Dict, Any
from src.schemas import (
    AuditResult,
    AuditDecision,
    ExecutionStatus,
    RuleResult,
    RuleStatus,
    RuleSummaryCounts,
    ExtractedClaim
)


class ResultAggregator:
    """
    Aggregates individual RuleResult outputs into a unified, consolidated AuditResult.
    Preserves audit evidence, calculates summary counts, and separates mathematical
    flagging decisions from engine/data pipeline failures.
    """

    @classmethod
    def aggregate(
        cls,
        claim: ExtractedClaim,
        rule_results: List[RuleResult],
        matched_metric_name: Optional[str],
        baseline_year: str,
        target_year: str,
        baseline_val: Optional[float],
        target_val: Optional[float],
        primary_claimed_pct: float,
        primary_calculated_delta: float,
        primary_variance: float,
        primary_discrepancy_reason: str,
        default_execution_status: ExecutionStatus = ExecutionStatus.SUCCESS,
        default_audit_decision: Optional[AuditDecision] = None
    ) -> AuditResult:
        counts = RuleSummaryCounts(
            total_rules=len(rule_results),
            passed=sum(1 for r in rule_results if r.status == RuleStatus.PASS),
            flagged=sum(1 for r in rule_results if r.status == RuleStatus.FLAGGED),
            not_applicable=sum(1 for r in rule_results if r.status == RuleStatus.NOT_APPLICABLE),
            missing_data=sum(1 for r in rule_results if r.status == RuleStatus.MISSING_DATA),
            invalid_data=sum(1 for r in rule_results if r.status == RuleStatus.INVALID_DATA),
            error=sum(1 for r in rule_results if r.status == RuleStatus.ERROR),
        )

        # Determine overall AuditDecision and ExecutionStatus
        if default_audit_decision is not None:
            audit_decision = default_audit_decision
            execution_status = default_execution_status
        elif counts.flagged > 0:
            audit_decision = AuditDecision.FLAGGED
            execution_status = ExecutionStatus.SUCCESS
        elif counts.error > 0:
            audit_decision = AuditDecision.UNVERIFIED
            execution_status = ExecutionStatus.ERROR
        elif counts.invalid_data > 0:
            audit_decision = AuditDecision.UNVERIFIED
            execution_status = ExecutionStatus.INVALID_DATA
        elif counts.missing_data > 0:
            audit_decision = AuditDecision.UNVERIFIED
            execution_status = ExecutionStatus.MISSING_DATA
        elif counts.passed > 0:
            audit_decision = AuditDecision.PASS
            execution_status = ExecutionStatus.SUCCESS
        else:
            audit_decision = AuditDecision.UNVERIFIED
            execution_status = ExecutionStatus.PARTIAL

        # Map to legacy status for app.py UI binding
        # app.py expects "PASS" for verified green checkmark, otherwise renders error/flagged
        legacy_status = "PASS" if audit_decision == AuditDecision.PASS else "FLAGGED"

        # Build comprehensive discrepancy reason if secondary rules flagged
        discrepancy_reason = primary_discrepancy_reason
        if counts.flagged > 0 and audit_decision == AuditDecision.FLAGGED:
            flagged_rules = [r for r in rule_results if r.status == RuleStatus.FLAGGED]
            if len(flagged_rules) > 1 or (flagged_rules and flagged_rules[0].rule_id != "EM-02"):
                flag_summaries = [f"[{r.rule_id} {r.rule_name}]: {r.message}" for r in flagged_rules]
                discrepancy_reason = f"{primary_discrepancy_reason} Secondary Rule Findings: " + " | ".join(flag_summaries)

        return AuditResult(
            status=legacy_status,
            claimed_percentage=primary_claimed_pct,
            calculated_delta=primary_calculated_delta,
            variance=primary_variance,
            discrepancy_reason=discrepancy_reason,
            matched_metric=matched_metric_name,
            baseline_year=baseline_year,
            target_year=target_year,
            baseline_value=baseline_val,
            target_value=target_val,
            fy23_value=baseline_val,
            fy24_value=target_val,
            audit_decision=audit_decision,
            execution_status=execution_status,
            summary=counts,
            rule_results=rule_results
        )
