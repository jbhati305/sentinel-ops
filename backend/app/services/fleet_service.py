from __future__ import annotations

from typing import Any

from backend.app.analysis import AnalysisEngine
from backend.app.repositories.fleet_repository import FleetRepository
from backend.app.simulation.service import SimulatorService
from backend.app.time_utils import isoformat, utcnow


class FleetService:
    """Application service for operator-facing fleet read models."""

    def __init__(
        self,
        repository: FleetRepository,
        analysis: AnalysisEngine,
        simulator: SimulatorService,
    ):
        self.repository = repository
        self.analysis = analysis
        self.simulator = simulator

    def summary(self) -> dict[str, Any]:
        devices = self.repository.list_devices()
        counts = {"HEALTHY": 0, "OBSERVE": 0, "WARNING": 0, "CRITICAL": 0}
        for device in devices:
            counts[device["health"]["state"]] += 1
        alerts = self.repository.list_alerts(active_only=True)
        return {
            "device_count": len(devices),
            "state_counts": counts,
            "active_alert_count": len(alerts),
            "critical_alert_count": sum(1 for alert in alerts if alert["severity"] == "CRITICAL"),
            "devices": devices,
            "attention_queue": alerts,
            "simulation": self.simulator.status(),
            "generated_at": isoformat(utcnow()),
        }

    def devices(self) -> list[dict[str, Any]]:
        return self.repository.list_devices()

    def device_detail(self, device_id: str) -> dict[str, Any] | None:
        self.analysis.analyze_device(device_id)
        device = self.repository.get_device(device_id)
        if device is None:
            return None
        device["alerts"] = self.repository.list_alerts(active_only=True, device_id=device_id)
        return device

    def device_health(self, device_id: str) -> dict[str, Any]:
        return self.analysis.analyze_device(device_id)

    def device_telemetry(
        self,
        device_id: str,
        metric: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self.repository.list_telemetry(device_id, metric=metric, limit=limit)

    def alerts(self, status: str) -> list[dict[str, Any]]:
        if status == "active":
            return self.repository.list_alerts(active_only=True)
        where = None
        if status == "open":
            where = "OPEN"
        elif status == "resolved":
            where = "RESOLVED"
        elif status == "acknowledged":
            where = "ACKNOWLEDGED"
        return self.repository.list_alerts(active_only=False, status=where)
