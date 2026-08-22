import importlib
import logging
from typing import Dict, List, Type, Optional
from src.rules.base import BaseRule

logger = logging.getLogger(__name__)


class RuleRegistry:
    """
    Central registry for deterministic validation rules.
    Allows Track 2 and Track 3 developers to register rules via decorator
    without modifying the central engine dispatcher.
    """
    _registry: Dict[str, Type[BaseRule]] = {}

    @classmethod
    def register(cls, rule_cls: Type[BaseRule]):
        """
        Decorator to register a rule class.
        Usage:
            @RuleRegistry.register
            class MyRule(BaseRule):
                rule_id = "EM-01"
                ...
        """
        # Validate rule_id presence
        rule_id = getattr(rule_cls, "rule_id", None)
        if not rule_id:
            raise ValueError(f"Rule class {rule_cls.__name__} must define a non-empty 'rule_id' attribute.")
        
        cls._registry[rule_id] = rule_cls
        return rule_cls

    @classmethod
    def get_rule_class(cls, rule_id: str) -> Optional[Type[BaseRule]]:
        return cls._registry.get(rule_id)

    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[BaseRule]:
        rule_cls = cls._registry.get(rule_id)
        if rule_cls:
            return rule_cls()
        return None

    @classmethod
    def get_all_rules(cls) -> List[BaseRule]:
        """Instantiates and returns all registered rules sorted by rule_id."""
        rules = [rule_cls() for rule_cls in cls._registry.values()]
        return sorted(rules, key=lambda r: r.rule_id)

    @classmethod
    def get_rules_by_domain(cls, domain: str) -> List[BaseRule]:
        """Returns all registered rules for a given domain string."""
        domain_normalized = domain.strip().lower()
        rules = [
            rule_cls() for rule_cls in cls._registry.values()
            if getattr(rule_cls(), "domain", "").lower() == domain_normalized
        ]
        return sorted(rules, key=lambda r: r.rule_id)

    @classmethod
    def clear(cls):
        """Clears registry (useful for isolated unit testing)."""
        cls._registry.clear()

    @classmethod
    def auto_discover(cls):
        """
        Discovers and imports domain rule modules so decorators execute.
        Safe against missing or stubbed domain files.
        """
        domain_modules = [
            "src.rules.emissions",
            "src.rules.energy",
            "src.rules.water",
            "src.rules.general",
        ]
        for mod_name in domain_modules:
            try:
                importlib.import_module(mod_name)
            except ModuleNotFoundError:
                logger.debug(f"Module {mod_name} not yet implemented or imported.")
            except Exception as e:
                logger.warning(f"Error importing domain rule module {mod_name}: {e}")
