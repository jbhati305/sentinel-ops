from __future__ import annotations

from datetime import datetime, timedelta

from backend.app.repositories.interfaces import QueryExecutor
from backend.app.schemas import TelemetryReadingIn
from backend.app.time_utils import to_utc


class TelemetryValidator:
    """Validation and quality classification for incoming sensor readings."""

    def __init__(self, db: QueryExecutor):
        self.db = db

    def rejection_reason(
        self,
        reading: TelemetryReadingIn,
        devices: set[str],
        metrics: dict[str, dict],
        received_at: datetime,
    ) -> str | None:
        if reading.device_id not in devices:
            return "unknown device"
        definition = metrics.get(reading.metric)
        if definition is None:
            return "unknown metric"
        if reading.unit != definition["unit"]:
            return f"wrong unit for {reading.metric}; expected {definition['unit']}"
        event_time = to_utc(reading.timestamp)
        if event_time > received_at + timedelta(minutes=5):
            return "timestamp is too far in the future"
        if reading.value < definition["physical_min"] or reading.value > definition["physical_max"]:
            return "value outside physical limits"
        return None

    def quality(self, reading: TelemetryReadingIn, definition: dict) -> tuple[str, str | None]:
        reasons: list[str] = []
        if (
            reading.value < definition["operational_min"]
            or reading.value > definition["operational_max"]
        ):
            reasons.append("outside normal operating envelope")

        previous = self.db.fetch_one(
            """
            SELECT value
            FROM telemetry_readings
            WHERE device_id = ? AND metric = ?
            ORDER BY event_timestamp DESC
            LIMIT 1
            """,
            (reading.device_id, reading.metric),
        )
        if previous is not None:
            jump_limits = {
                "inlet_temperature": 12.0,
                "outlet_temperature": 15.0,
                "vibration": 8.0,
                "power_draw": 8.0,
                "coolant_pressure": 1.5,
            }
            jump_limit = jump_limits.get(reading.metric)
            if jump_limit and abs(reading.value - previous["value"]) > jump_limit:
                reasons.append("abrupt discontinuity from previous sample")

        if reasons:
            return "SUSPECT", "; ".join(reasons)
        return "GOOD", None
