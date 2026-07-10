from __future__ import annotations

from backend.app.repositories.fleet_repository import FleetRepository
from backend.app.repositories.interfaces import QueryExecutor
from backend.app.time_utils import isoformat, utcnow


class AlertService:
    """Application service for operator alert actions."""

    def __init__(self, db: QueryExecutor, repository: FleetRepository):
        self.db = db
        self.repository = repository

    def acknowledge(self, alert_id: str, note: str | None = None) -> dict | None:
        alert = self.repository.get_alert(alert_id)
        if alert is None:
            return None
        if alert["status"] == "RESOLVED":
            raise ValueError("resolved alerts cannot be acknowledged")
        self.db.execute(
            """
            UPDATE alerts
            SET status = 'ACKNOWLEDGED',
                acknowledged_at = COALESCE(acknowledged_at, ?),
                operator_note = COALESCE(?, operator_note)
            WHERE id = ?
            """,
            (isoformat(utcnow()), note, alert_id),
        )
        return self.repository.get_alert(alert_id)

    def resolve(self, alert_id: str, note: str | None = None) -> dict | None:
        if self.repository.get_alert(alert_id) is None:
            return None
        self.db.execute(
            """
            UPDATE alerts
            SET status = 'RESOLVED',
                resolved_at = COALESCE(resolved_at, ?),
                operator_note = COALESCE(?, operator_note)
            WHERE id = ?
            """,
            (isoformat(utcnow()), note, alert_id),
        )
        return self.repository.get_alert(alert_id)
