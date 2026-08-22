"""
Track 3: General Validation Rules Domain Module
Rules:
- GEN-01: Baseline Year Period Alignment
- GEN-02: Metric Unit Scale Consistency
- GEN-03: >100% Impossibility & Zero-Div Guard
"""
import logging
from src.rules.base import BaseRule, RuleDomain, RuleEvaluationContext
from src.rules.registry import RuleRegistry
from src.schemas import RuleResult, RuleStatus, RuleEvidence

logger = logging.getLogger(__name__)

# Track 3 developers will implement domain rules here subclassing BaseRule and registering via @RuleRegistry.register
