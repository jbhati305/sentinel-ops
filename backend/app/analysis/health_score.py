from __future__ import annotations

from backend.app.time_utils import isoformat, utcnow


class HealthScorer:
    """Computes the operator-facing health score from active incidents."""

    def calculate(
        self,
        device_id: str,
        latest_by_metric: dict[str, dict],
        active_alerts: list[dict],
        previous_health_score: float | None,
    ) -> dict:
        penalty_by_type = {
            "SUDDEN_FAILURE": 72,
            "SAFETY_THRESHOLD": 32,
            "GRADUAL_DEGRADATION": 35,
            "MULTIVARIATE_ANOMALY": 30,
            "SENSOR_FAULT": 18,
            "DEVICE_OFFLINE": 45,
            "MISSING_TELEMETRY": 10,
        }
        severity_bonus = {"CRITICAL": 20, "WARNING": 6, "INFO": 0}
        contributors: list[dict] = []
        total_penalty = 0
        for alert in active_alerts:
            penalty = penalty_by_type.get(alert["alert_type"], 12) + severity_bonus[alert["severity"]]
            total_penalty += penalty
            contributors.append({"factor": alert["title"], "impact": -penalty})

        suspect_metrics = [
            metric
            for metric, row in latest_by_metric.items()
            if row["quality"] == "SUSPECT"
        ]
        if suspect_metrics:
            penalty = min(15, 5 * len(suspect_metrics))
            total_penalty += penalty
            contributors.append(
                {
                    "factor": f"Recent suspect data: {', '.join(sorted(suspect_metrics))}",
                    "impact": -penalty,
                }
            )

        health_score = max(0, min(100, 100 - total_penalty))
        state = self._state_for_score(health_score)
        trend = self._trend(health_score, previous_health_score)

        primary_issue = "Operating normally"
        if active_alerts:
            primary_issue = active_alerts[0]["title"]
        if not contributors:
            contributors.append({"factor": "All reporting metrics are within normal range", "impact": 0})

        metrics = []
        for metric, row in sorted(latest_by_metric.items()):
            metrics.append(
                {
                    "metric": metric,
                    "value": round(row["value"], 3),
                    "unit": row["unit"],
                    "quality": row["quality"],
                    "quality_reason": row["quality_reason"],
                    "event_timestamp": row["event_timestamp"],
                }
            )

        return {
            "device_id": device_id,
            "health_score": round(health_score, 1),
            "state": state,
            "calculated_at": isoformat(utcnow()),
            "primary_issue": primary_issue,
            "trend": trend,
            "contributors": contributors,
            "metrics": metrics,
        }

    def _state_for_score(self, score: float) -> str:
        if score >= 85:
            return "HEALTHY"
        if score >= 65:
            return "OBSERVE"
        if score >= 40:
            return "WARNING"
        return "CRITICAL"

    def _trend(self, score: float, previous_score: float | None) -> str:
        if previous_score is None:
            return "Stable"
        delta = score - previous_score
        if delta < -3:
            return "Worsening"
        if delta > 3:
            return "Improving"
        return "Stable"
