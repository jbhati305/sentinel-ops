from __future__ import annotations

import json
from typing import Any

from backend.app.models.domain import STATE_ORDER
from backend.app.repositories.interfaces import QueryExecutor


class FleetRepository:
    """Read-model repository for dashboard and API queries."""

    def __init__(self, db: QueryExecutor):
        self.db = db

    def device_exists(self, device_id: str) -> bool:
        return self.db.fetch_one("SELECT id FROM devices WHERE id = ?", (device_id,)) is not None

    def alert_exists(self, alert_id: str) -> bool:
        return self.db.fetch_one("SELECT id FROM alerts WHERE id = ?", (alert_id,)) is not None

    def list_devices(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM devices ORDER BY id")
        devices = [
            device
            for row in rows
            if (device := self.get_device(row["id"])) is not None
        ]
        devices.sort(
            key=lambda device: (
                STATE_ORDER.get(device["health"]["state"], 99),
                device["health"]["health_score"],
                device["name"],
            )
        )
        return devices

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        device = self.db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        if device is None:
            return None
        health = self.db.fetch_one(
            "SELECT * FROM device_health WHERE device_id = ?",
            (device_id,),
        )
        health_payload = self._health_payload(device_id, health)
        active_alerts = self.list_alerts(active_only=True, device_id=device_id)
        return {
            "id": device["id"],
            "name": device["name"],
            "short_name": device["short_name"],
            "device_type": device["device_type"],
            "location": device["location"],
            "status": device["status"],
            "installed_at": device["installed_at"],
            "metadata": json.loads(device["metadata_json"]),
            "health": health_payload,
            "active_alert_count": len(active_alerts),
            "highest_severity": active_alerts[0]["severity"] if active_alerts else None,
        }

    def list_telemetry(
        self,
        device_id: str,
        metric: str | None = None,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        if metric:
            rows = self.db.fetch_all(
                """
                SELECT * FROM (
                    SELECT *
                    FROM telemetry_readings
                    WHERE device_id = ? AND metric = ?
                    ORDER BY event_timestamp DESC
                    LIMIT ?
                )
                ORDER BY event_timestamp ASC
                """,
                (device_id, metric, limit),
            )
        else:
            rows = self.db.fetch_all(
                """
                SELECT * FROM (
                    SELECT *
                    FROM telemetry_readings
                    WHERE device_id = ?
                    ORDER BY event_timestamp DESC
                    LIMIT ?
                )
                ORDER BY event_timestamp ASC
                """,
                (device_id, limit),
            )
        return [self._row_to_dict(row) for row in rows]

    def list_alerts(
        self,
        active_only: bool,
        device_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if active_only:
            clauses.append("a.status IN ('OPEN', 'ACKNOWLEDGED')")
        if status:
            clauses.append("a.status = ?")
            params.append(status.upper())
        if device_id:
            clauses.append("a.device_id = ?")
            params.append(device_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.fetch_all(
            f"""
            SELECT a.*, d.name AS device_name, d.short_name AS device_short_name
            FROM alerts a
            JOIN devices d ON d.id = a.device_id
            {where}
            ORDER BY
                CASE a.severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END,
                a.first_detected_at ASC
            """,
            tuple(params),
        )
        return [self._alert_row_to_dict(row) for row in rows]

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        row = self.db.fetch_one(
            """
            SELECT a.*, d.name AS device_name, d.short_name AS device_short_name
            FROM alerts a
            JOIN devices d ON d.id = a.device_id
            WHERE a.id = ?
            """,
            (alert_id,),
        )
        if row is None:
            return None
        return self._alert_row_to_dict(row)

    def _health_payload(self, device_id: str, health) -> dict[str, Any]:
        if health is None:
            return {
                "device_id": device_id,
                "health_score": 100,
                "state": "HEALTHY",
                "calculated_at": None,
                "primary_issue": "No readings yet",
                "trend": "Stable",
                "contributors": [],
                "metrics": [],
            }
        return {
            "device_id": device_id,
            "health_score": health["health_score"],
            "state": health["state"],
            "calculated_at": health["calculated_at"],
            "primary_issue": health["primary_issue"],
            "trend": health["trend"],
            "contributors": json.loads(health["contributors_json"]),
            "metrics": json.loads(health["metrics_json"]),
        }

    def _alert_row_to_dict(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "device_name": row["device_name"],
            "device_short_name": row["device_short_name"],
            "alert_key": row["alert_key"],
            "alert_type": row["alert_type"],
            "severity": row["severity"],
            "status": row["status"],
            "title": row["title"],
            "explanation": row["explanation"],
            "recommended_action": row["recommended_action"],
            "confidence": row["confidence"],
            "first_detected_at": row["first_detected_at"],
            "last_detected_at": row["last_detected_at"],
            "acknowledged_at": row["acknowledged_at"],
            "resolved_at": row["resolved_at"],
            "operator_note": row["operator_note"],
            "evidence": json.loads(row["evidence_json"]),
        }

    def _row_to_dict(self, row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}
