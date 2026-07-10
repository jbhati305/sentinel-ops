from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

ACTIVE_ALERT_STATUSES = ("OPEN", "ACKNOWLEDGED")
STATE_ORDER = {"CRITICAL": 0, "WARNING": 1, "OBSERVE": 2, "HEALTHY": 3}
SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


@dataclass(frozen=True)
class Detection:
    alert_key: str
    alert_type: str
    severity: str
    title: str
    explanation: str
    recommended_action: str
    confidence: int
    evidence: dict[str, Any]


@dataclass(frozen=True)
class AnalysisContext:
    metrics: dict[str, dict[str, Any]]
    windows: dict[str, list[dict[str, Any]]]
    latest_by_metric: dict[str, dict[str, Any]]
    fleet_reference_time: datetime | None
