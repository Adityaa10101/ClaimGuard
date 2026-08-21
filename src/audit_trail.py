"""
ClaimGuard Audit Trail — First-class evidence chain storage.

For every decision, stores:
    Claim → Source → Extracted Values → Rule Applied → Formula →
    Calculated Result → Reported Result → Variance → Decision

Enables judges to click "Why flagged?" and trace the full chain.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional

from src.schemas import AuditReport


# ─── Storage ─────────────────────────────────────────────────────────────────

def save_audit_report(
    report: AuditReport,
    base_dir: str = "data/results",
) -> str:
    """
    Save an audit report as JSON for future reference.

    Returns the path to the saved file.
    """
    os.makedirs(base_dir, exist_ok=True)

    filename = f"{report.report_id}.json"
    filepath = os.path.join(base_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)

    return filepath


def load_audit_report(
    report_id: str,
    base_dir: str = "data/results",
) -> Optional[AuditReport]:
    """Load a previously saved audit report."""
    filepath = os.path.join(base_dir, f"{report_id}.json")

    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return AuditReport(**data)


def list_audit_reports(
    base_dir: str = "data/results",
) -> list:
    """List all saved audit reports."""
    if not os.path.exists(base_dir):
        return []

    reports = []
    for filename in os.listdir(base_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(base_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reports.append({
                    "report_id": data.get("report_id", ""),
                    "company": data.get("company", ""),
                    "filing_period": data.get("filing_period", ""),
                    "timestamp": data.get("timestamp", ""),
                    "summary": data.get("summary", {}),
                })
            except (json.JSONDecodeError, KeyError):
                continue

    return sorted(reports, key=lambda r: r.get("timestamp", ""), reverse=True)


def export_report_json(report: AuditReport) -> str:
    """Export an audit report as a formatted JSON string for download."""
    return json.dumps(report.model_dump(), indent=2, default=str)
