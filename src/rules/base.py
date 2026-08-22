from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import pandas as pd

from src.schemas import ExtractedClaim, RuleResult, RuleStatus


class RuleDomain(str, Enum):
    EMISSIONS = "Emissions"
    ENERGY = "Energy"
    WATER = "Water"
    GENERAL = "General"


class RuleEvaluationContext(BaseModel):
    """
    Context passed to each rule during evaluation.
    Contains the original claim, normalized DataFrame, resolved metric row,
    resolved year columns, and pre-extracted numerical values.
    """
    claim: ExtractedClaim
    metrics_df: Any = Field(..., description="pandas DataFrame containing ground-truth tabular data")
    resolved_metric_row: Optional[Dict[str, Any]] = None
    canonical_baseline_year: Optional[str] = None
    canonical_target_year: Optional[str] = None
    baseline_col: Optional[str] = None
    target_col: Optional[str] = None
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    tolerance: float = 0.05
    all_metric_rows: Optional[List[Dict[str, Any]]] = None
    extra_context: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class BaseRule(ABC):
    """
    Abstract Base Class for all ClaimGuard deterministic audit rules.
    Track 2 and Track 3 developers must subclass BaseRule and implement evaluate().
    """
    rule_id: str
    domain: RuleDomain
    rule_name: str
    description: str = ""

    def is_applicable(self, context: RuleEvaluationContext) -> bool:
        """
        Determines whether this rule is relevant to the given claim and context.
        Defaults to True. Rules may override to skip irrelevant domains.
        """
        return True

    @abstractmethod
    def evaluate(self, context: RuleEvaluationContext) -> RuleResult:
        """
        Executes pure deterministic validation logic.
        Rules MUST NOT make network calls or invoke LLMs.
        Must catch internal exceptions and return RuleStatus.ERROR.
        """
        raise NotImplementedError("Each rule must implement evaluate()")
