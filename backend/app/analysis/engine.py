from __future__ import annotations

import json
from datetime import datetime

from backend.app.analysis.alert_engine import AlertEngine
from backend.app.analysis.anomaly_detector import AnomalyDetector
from backend.app.analysis.health_score import HealthScorer
from backend.app.analysis.trend_detector import TrendDetector
from backend.app.models.domain import AnalysisContext, Detection, SEVERITY_ORDER
from backend.app.repositories.interfaces import QueryExecutor
from backend.app.time_utils import parse_datetime


class AnalysisEngine:
    """Coordinates detectors, alert lifecycle, and health scoring."""

    def __init__(
        self,
        db: QueryExecutor,
        anomaly_detector: AnomalyDetector | None = None,
        trend_detector: TrendDetector | None = None,
        alert_engine: AlertEngine | None = None,
        health_scorer: HealthScorer | None = None,
    ):
        self.db = db
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.trend_detector = trend_detector or TrendDetector()
        self.alert_engine = alert_engine or AlertEngine(db, self.trend_detector)
        self.health_scorer = health_scorer or HealthScorer()

    def analyze_all(self) -> None:
        for row in self.db.fetch_all("SELECT id FROM devices ORDER BY id"):
            self.analyze_device(row["id"])

    def analyze_device(self, device_id: str) -> dict:
        context = self._context_for_device(device_id)
        detections = self._dedupe_detections(
            [
                *self.anomaly_detector.detect(context),
                *self.trend_detector.detect(context.windows),
            ]
        )
        detected_keys = {detection.alert_key for detection in detections}

        for detection in detections:
            self.alert_engine.upsert_alert(device_id, detection)

        self.alert_engine.resolve_stale_alerts(
            device_id,
            detected_keys,
            context.metrics,
            context.windows,
            context.latest_by_metric,
        )

        health = self.health_scorer.calculate(
            device_id,
            context.latest_by_metric,
            self._active_alerts(device_id),
            self._previous_health_score(device_id),
        )
        self._save_health(device_id, health)
        return health

    def _context_for_device(self, device_id: str) -> AnalysisContext:
        metrics = self._metric_definitions()
        windows = {
            metric: self._readings_for_metric(device_id, metric, limit=80)
            for metric in metrics
        }
        latest_by_metric = {
            metric: rows[-1]
            for metric, rows in windows.items()
            if rows
        }
        return AnalysisContext(
            metrics=metrics,
            windows=windows,
            latest_by_metric=latest_by_metric,
            fleet_reference_time=self._fleet_reference_time(),
        )

    def _metric_definitions(self) -> dict[str, dict]:
        rows = self.db.fetch_all("SELECT * FROM metric_definitions ORDER BY metric")
        return {row["metric"]: dict(row) for row in rows}

    def _readings_for_metric(self, device_id: str, metric: str, limit: int) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT * FROM (
                SELECT * FROM telemetry_readings
                WHERE device_id = ? AND metric = ?
                ORDER BY event_timestamp DESC
                LIMIT ?
            )
            ORDER BY event_timestamp ASC, id ASC
            """,
            (device_id, metric, limit),
        )
        return [dict(row) for row in rows]

    def _fleet_reference_time(self) -> datetime | None:
        latest = self.db.scalar("SELECT MAX(event_timestamp) FROM telemetry_readings")
        if latest is None:
            return None
        return parse_datetime(latest)

    def _dedupe_detections(self, detections: list[Detection]) -> list[Detection]:
        by_key: dict[str, Detection] = {}
        for detection in detections:
            existing = by_key.get(detection.alert_key)
            if existing is None:
                by_key[detection.alert_key] = detection
                continue
            if SEVERITY_ORDER[detection.severity] < SEVERITY_ORDER[existing.severity]:
                by_key[detection.alert_key] = detection
            elif detection.confidence > existing.confidence:
                by_key[detection.alert_key] = detection
        return list(by_key.values())

    def _active_alerts(self, device_id: str) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT * FROM alerts
            WHERE device_id = ? AND status IN ('OPEN', 'ACKNOWLEDGED')
            ORDER BY
                CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END,
                first_detected_at ASC
            """,
            (device_id,),
        )
        return [dict(row) for row in rows]

    def _previous_health_score(self, device_id: str) -> float | None:
        previous = self.db.fetch_one(
            "SELECT health_score FROM device_health WHERE device_id = ?",
            (device_id,),
        )
        if previous is None:
            return None
        return float(previous["health_score"])

    def _save_health(self, device_id: str, health: dict) -> None:
        self.db.execute(
            """
            INSERT INTO device_health (
                device_id, health_score, state, calculated_at, primary_issue,
                trend, contributors_json, metrics_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                health_score = excluded.health_score,
                state = excluded.state,
                calculated_at = excluded.calculated_at,
                primary_issue = excluded.primary_issue,
                trend = excluded.trend,
                contributors_json = excluded.contributors_json,
                metrics_json = excluded.metrics_json
            """,
            (
                device_id,
                health["health_score"],
                health["state"],
                health["calculated_at"],
                health["primary_issue"],
                health["trend"],
                json.dumps(health["contributors"]),
                json.dumps(health["metrics"]),
            ),
        )
