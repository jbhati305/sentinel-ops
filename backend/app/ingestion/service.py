from __future__ import annotations

from typing import Any

from backend.app.analysis.engine import AnalysisEngine
from backend.app.ingestion.publisher import (
    NoopTelemetryPublisher,
    PublishedTelemetryReading,
    TelemetryPublisher,
)
from backend.app.ingestion.validator import TelemetryValidator
from backend.app.repositories.interfaces import QueryExecutor
from backend.app.schemas import TelemetryReadingIn
from backend.app.time_utils import isoformat, to_utc, utcnow


class TelemetryService:
    """Application service for idempotent batch ingestion."""

    def __init__(
        self,
        db: QueryExecutor,
        analysis: AnalysisEngine,
        validator: TelemetryValidator | None = None,
        publisher: TelemetryPublisher | None = None,
    ):
        self.db = db
        self.analysis = analysis
        self.validator = validator or TelemetryValidator(db)
        self.publisher = publisher or NoopTelemetryPublisher()

    def ingest_batch(self, readings: list[TelemetryReadingIn]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "accepted": 0,
            "duplicates": 0,
            "rejected": 0,
            "late_arrivals": 0,
            "suspect": 0,
            "errors": [],
        }
        accepted_readings: list[PublishedTelemetryReading] = []
        devices = {row["id"] for row in self.db.fetch_all("SELECT id FROM devices")}
        metrics = {
            row["metric"]: dict(row)
            for row in self.db.fetch_all("SELECT * FROM metric_definitions")
        }
        received_at = utcnow()

        for reading in readings:
            if self._is_duplicate(reading.event_id):
                summary["duplicates"] += 1
                continue

            rejection = self.validator.rejection_reason(
                reading,
                devices,
                metrics,
                received_at,
            )
            if rejection:
                summary["rejected"] += 1
                summary["errors"].append(
                    {
                        "event_id": reading.event_id,
                        "device_id": reading.device_id,
                        "metric": reading.metric,
                        "reason": rejection,
                    }
                )
                continue

            definition = metrics[reading.metric]
            quality, quality_reason = self.validator.quality(reading, definition)
            event_timestamp = isoformat(to_utc(reading.timestamp))
            late_arrival = self._is_late_arrival(
                reading.device_id,
                reading.metric,
                event_timestamp,
            )
            self._store_reading(
                reading,
                event_timestamp,
                received_at=isoformat(received_at),
                quality=quality,
                quality_reason=quality_reason,
                late_arrival=late_arrival,
            )
            accepted_readings.append(
                PublishedTelemetryReading(
                    event_id=reading.event_id,
                    device_id=reading.device_id,
                    metric=reading.metric,
                    value=reading.value,
                    unit=reading.unit,
                    event_timestamp=event_timestamp,
                    quality=quality,
                    quality_reason=quality_reason,
                    late_arrival=late_arrival,
                )
            )

            summary["accepted"] += 1
            if late_arrival:
                summary["late_arrivals"] += 1
            if quality == "SUSPECT":
                summary["suspect"] += 1

        if summary["accepted"]:
            self.analysis.analyze_all()
            self.publisher.publish_batch(accepted_readings)

        return summary

    def close(self) -> None:
        self.publisher.close()

    def _is_duplicate(self, event_id: str) -> bool:
        return self.db.fetch_one(
            "SELECT event_id FROM telemetry_readings WHERE event_id = ?",
            (event_id,),
        ) is not None

    def _is_late_arrival(self, device_id: str, metric: str, event_timestamp: str) -> bool:
        latest_timestamp = self.db.scalar(
            """
            SELECT MAX(event_timestamp)
            FROM telemetry_readings
            WHERE device_id = ? AND metric = ?
            """,
            (device_id, metric),
        )
        return bool(latest_timestamp and event_timestamp < latest_timestamp)

    def _store_reading(
        self,
        reading: TelemetryReadingIn,
        event_timestamp: str,
        *,
        received_at: str,
        quality: str,
        quality_reason: str | None,
        late_arrival: bool,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO telemetry_readings (
                event_id, device_id, metric, value, unit, event_timestamp,
                received_at, quality, quality_reason, late_arrival
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading.event_id,
                reading.device_id,
                reading.metric,
                reading.value,
                reading.unit,
                event_timestamp,
                received_at,
                quality,
                quality_reason,
                1 if late_arrival else 0,
            ),
        )
