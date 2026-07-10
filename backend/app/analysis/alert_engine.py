from __future__ import annotations

import json
from uuid import uuid4

from backend.app.analysis.trend_detector import TrendDetector
from backend.app.models.domain import Detection
from backend.app.repositories.interfaces import QueryExecutor
from backend.app.time_utils import isoformat, parse_datetime, utcnow


class AlertEngine:
    """Owns incident lifecycle persistence and hysteresis-based resolution."""

    def __init__(self, db: QueryExecutor, trend_detector: TrendDetector):
        self.db = db
        self.trend_detector = trend_detector

    def upsert_alert(self, device_id: str, detection: Detection) -> None:
        now = isoformat(utcnow())
        row = self.db.fetch_one(
            """
            SELECT * FROM alerts
            WHERE device_id = ?
              AND alert_key = ?
              AND status IN ('OPEN', 'ACKNOWLEDGED')
            ORDER BY first_detected_at ASC
            LIMIT 1
            """,
            (device_id, detection.alert_key),
        )
        evidence = dict(detection.evidence)
        evidence["alert_key"] = detection.alert_key
        if row is None:
            self.db.execute(
                """
                INSERT INTO alerts (
                    id, device_id, alert_key, alert_type, severity, status,
                    title, explanation, recommended_action, confidence,
                    first_detected_at, last_detected_at, evidence_json
                )
                VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    device_id,
                    detection.alert_key,
                    detection.alert_type,
                    detection.severity,
                    detection.title,
                    detection.explanation,
                    detection.recommended_action,
                    detection.confidence,
                    now,
                    now,
                    json.dumps(evidence),
                ),
            )
            return

        self.db.execute(
            """
            UPDATE alerts
            SET severity = ?,
                title = ?,
                explanation = ?,
                recommended_action = ?,
                confidence = ?,
                last_detected_at = ?,
                evidence_json = ?
            WHERE id = ?
            """,
            (
                detection.severity,
                detection.title,
                detection.explanation,
                detection.recommended_action,
                detection.confidence,
                now,
                json.dumps(evidence),
                row["id"],
            ),
        )

    def resolve_stale_alerts(
        self,
        device_id: str,
        detected_keys: set[str],
        metrics: dict[str, dict],
        windows: dict[str, list[dict]],
        latest_by_metric: dict[str, dict],
    ) -> None:
        rows = self.db.fetch_all(
            """
            SELECT * FROM alerts
            WHERE device_id = ? AND status IN ('OPEN', 'ACKNOWLEDGED')
            """,
            (device_id,),
        )
        for row in rows:
            if row["alert_key"] in detected_keys:
                continue
            if not self._can_resolve(dict(row), metrics, windows, latest_by_metric):
                continue
            self.db.execute(
                """
                UPDATE alerts
                SET status = 'RESOLVED', resolved_at = ?
                WHERE id = ?
                """,
                (isoformat(utcnow()), row["id"]),
            )

    def _can_resolve(
        self,
        alert: dict,
        metrics: dict[str, dict],
        windows: dict[str, list[dict]],
        latest_by_metric: dict[str, dict],
    ) -> bool:
        evidence = json.loads(alert["evidence_json"])
        alert_type = alert["alert_type"]
        if alert_type == "MISSING_TELEMETRY":
            metric = evidence.get("metric")
            latest = latest_by_metric.get(metric)
            if latest is None:
                return False
            reference_time = max(
                parse_datetime(row["event_timestamp"]) for row in latest_by_metric.values()
            )
            age = (reference_time - parse_datetime(latest["event_timestamp"])).total_seconds()
            return age <= metrics[metric]["expected_interval_seconds"] * 3

        if alert_type == "DEVICE_OFFLINE":
            return bool(latest_by_metric)

        if alert_type == "SENSOR_FAULT":
            metric = evidence.get("metric")
            if not metric:
                return False
            rows = windows.get(metric, [])
            if len(rows) < 3:
                return False
            recent = rows[-3:]
            definition = metrics[metric]
            return all(
                definition["operational_min"] <= row["value"] <= definition["operational_max"]
                and row["quality"] == "GOOD"
                for row in recent
            )

        if alert_type == "SAFETY_THRESHOLD":
            metric = evidence.get("metric")
            if not metric:
                return False
            rows = windows.get(metric, [])
            if len(rows) < 5:
                return False
            definition = metrics[metric]
            return all(
                definition["operational_min"] <= row["value"] <= definition["operational_max"]
                for row in rows[-5:]
            )

        if alert_type == "SUDDEN_FAILURE":
            power = windows.get("power_draw", [])[-3:]
            vibration = windows.get("vibration", [])[-3:]
            if len(power) < 3 or len(vibration) < 3:
                return False
            return all(row["value"] > 3.0 for row in power) and all(
                row["value"] > 0.5 for row in vibration
            )

        if alert_type in {"GRADUAL_DEGRADATION", "MULTIVARIATE_ANOMALY"}:
            return self.trend_detector.trend_is_stable(windows)

        return False
