import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.rules.emissions
import src.rules.energy
import src.rules.water
import src.rules.general
from src.rules.registry import RuleRegistry

rules = RuleRegistry.get_all_rules()
print(f"Total rules: {len(rules)}")
for r in rules:
    print(f"{r.rule_id} ({r.domain.value})")

if len(rules) == 15:
    print("[PASS] Exactly 15 registered rules.")
else:
    print(f"[FAIL] Expected 15, got {len(rules)}")
