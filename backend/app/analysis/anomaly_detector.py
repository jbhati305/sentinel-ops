from __future__ import annotations

from backend.app.models.domain import AnalysisContext, Detection
from backend.app.time_utils import parse_datetime


class AnomalyDetector:
    """Point, persistence, and data-quality anomaly rules."""

    def detect(self, context: AnalysisContext) -> list[Detection]:
        detections: list[Detection] = []
        detections.extend(
            self.detect_device_offline(
                context.metrics,
                context.latest_by_metric,
                context.fleet_reference_time,
            )
        )
        detections.extend(self.detect_missing_telemetry(context.metrics, context.latest_by_metric))
        detections.extend(self.detect_sensor_faults(context.latest_by_metric, context.windows))
        detections.extend(self.detect_sudden_failure(context.latest_by_metric, context.windows))
        detections.extend(self.detect_safety_thresholds(context.metrics, context.windows))
        detections.extend(self.detect_flatlined_sensors(context.windows))
        return detections

    def detect_device_offline(
        self,
        metrics: dict[str, dict],
        latest_by_metric: dict[str, dict],
        fleet_reference_time,
    ) -> list[Detection]:
        if not latest_by_metric or fleet_reference_time is None:
            return []

        latest_device_time = max(
            parse_datetime(row["event_timestamp"]) for row in latest_by_metric.values()
        )
        age_seconds = (fleet_reference_time - latest_device_time).total_seconds()
        expected_interval = max(
            definition["expected_interval_seconds"] for definition in metrics.values()
        )
        threshold = expected_interval * 24
        if age_seconds <= threshold:
            return []

        severity = "CRITICAL" if age_seconds > threshold * 3 else "WARNING"
        return [
            Detection(
                alert_key="device:offline",
                alert_type="DEVICE_OFFLINE",
                severity=severity,
                title="Device telemetry offline",
                explanation=(
                    f"No metric from this device has reported for {int(age_seconds)} "
                    "seconds while the rest of the fleet is still sending data."
                ),
                recommended_action=(
                    "Check device power, gateway connectivity, and site network path "
                    "before assuming the equipment is healthy."
                ),
                confidence=90,
                evidence={
                    "missing_seconds": round(age_seconds, 1),
                    "expected_interval_seconds": expected_interval,
                    "latest_device_timestamp": latest_device_time.isoformat(),
                    "fleet_reference_timestamp": fleet_reference_time.isoformat(),
                },
            )
        ]

    def detect_missing_telemetry(
        self,
        metrics: dict[str, dict],
        latest_by_metric: dict[str, dict],
    ) -> list[Detection]:
        if not latest_by_metric:
            return []

        reference_time = max(
            parse_datetime(row["event_timestamp"]) for row in latest_by_metric.values()
        )
        detections: list[Detection] = []
        for metric, definition in metrics.items():
            latest = latest_by_metric.get(metric)
            if latest is None:
                continue
            age_seconds = (
                reference_time - parse_datetime(latest["event_timestamp"])
            ).total_seconds()
            threshold = definition["expected_interval_seconds"] * 18
            if age_seconds <= threshold:
                continue
            severity = "WARNING" if age_seconds > threshold * 3 else "INFO"
            detections.append(
                Detection(
                    alert_key=f"missing:{metric}",
                    alert_type="MISSING_TELEMETRY",
                    severity=severity,
                    title=f"{definition['label']} telemetry gap",
                    explanation=(
                        f"No {definition['label'].lower()} reading has arrived for "
                        f"{int(age_seconds)} seconds. Other metrics are still reporting."
                    ),
                    recommended_action=(
                        "Check the sensor connection or gateway path before treating "
                        "this as equipment behavior."
                    ),
                    confidence=92,
                    evidence={
                        "metric": metric,
                        "missing_seconds": round(age_seconds, 1),
                        "expected_interval_seconds": definition["expected_interval_seconds"],
                    },
                )
            )
        return detections

    def detect_sensor_faults(
        self,
        latest_by_metric: dict[str, dict],
        windows: dict[str, list[dict]],
    ) -> list[Detection]:
        detections: list[Detection] = []
        for metric in ("inlet_temperature", "outlet_temperature"):
            rows = windows.get(metric, [])
            if len(rows) < 2:
                continue
            latest = rows[-1]
            previous = rows[-2]
            if latest["value"] > 0.5 or previous["value"] < 10:
                continue

            pressure = latest_by_metric.get("coolant_pressure")
            power = latest_by_metric.get("power_draw")
            pressure_normal = pressure is not None and 1.5 <= pressure["value"] <= 4.5
            power_normal = power is not None and 3.0 <= power["value"] <= 18.0
            if not (pressure_normal and power_normal):
                continue

            label = "Inlet" if metric == "inlet_temperature" else "Outlet"
            detections.append(
                Detection(
                    alert_key=f"sensor-zero:{metric}",
                    alert_type="SENSOR_FAULT",
                    severity="WARNING",
                    title=f"{label} temperature sensor fault suspected",
                    explanation=(
                        f"{label} temperature dropped from {previous['value']:.1f} C "
                        f"to {latest['value']:.1f} C in one sample while pressure and "
                        "power remained normal. This is more consistent with a sensor "
                        "fault than a physical cooling event."
                    ),
                    recommended_action=(
                        "Inspect or recalibrate the temperature sensor before dispatching "
                        "mechanical maintenance."
                    ),
                    confidence=89,
                    evidence={
                        "metric": metric,
                        "previous_value": round(previous["value"], 2),
                        "current_value": round(latest["value"], 2),
                        "correlated_metrics_normal": ["coolant_pressure", "power_draw"],
                    },
                )
            )
        return detections

    def detect_sudden_failure(
        self,
        latest_by_metric: dict[str, dict],
        windows: dict[str, list[dict]],
    ) -> list[Detection]:
        power = latest_by_metric.get("power_draw")
        vibration = latest_by_metric.get("vibration")
        if power is None or vibration is None:
            return []
        power_rows = windows.get("power_draw", [])
        previous_power = power_rows[-2]["value"] if len(power_rows) > 1 else None
        if power["value"] >= 1.0 or vibration["value"] > 0.2:
            return []
        if previous_power is not None and previous_power < 3.0:
            return []
        return [
            Detection(
                alert_key="sudden-failure:motor-stop",
                alert_type="SUDDEN_FAILURE",
                severity="CRITICAL",
                title="Motor stop suspected",
                explanation=(
                    f"Power draw collapsed to {power['value']:.1f} kW and vibration "
                    f"is {vibration['value']:.1f} mm/s. The pattern indicates the unit "
                    "may have stopped rather than gradually deteriorated."
                ),
                recommended_action="Inspect the unit immediately and verify power delivery.",
                confidence=98,
                evidence={
                    "power_draw": round(power["value"], 2),
                    "vibration": round(vibration["value"], 2),
                },
            )
        ]

    def detect_safety_thresholds(
        self,
        metrics: dict[str, dict],
        windows: dict[str, list[dict]],
    ) -> list[Detection]:
        detections: list[Detection] = []
        critical_limits = {
            "outlet_temperature": ("above", 90.0),
            "inlet_temperature": ("above", 90.0),
            "vibration": ("above", 12.0),
            "coolant_pressure": ("below", 1.2),
        }
        for metric, rows in windows.items():
            if not rows:
                continue
            definition = metrics[metric]
            latest = rows[-1]
            critical = critical_limits.get(metric)
            if critical and self._crossed(latest["value"], critical[0], critical[1]):
                detections.append(
                    Detection(
                        alert_key=f"threshold-critical:{metric}",
                        alert_type="SAFETY_THRESHOLD",
                        severity="CRITICAL",
                        title=f"{definition['label']} critical threshold",
                        explanation=(
                            f"{definition['label']} is {latest['value']:.1f} "
                            f"{definition['unit']}, crossing the critical safety limit."
                        ),
                        recommended_action="Inspect the unit immediately and reduce load if safe.",
                        confidence=96,
                        evidence={
                            "metric": metric,
                            "current_value": round(latest["value"], 2),
                            "limit": critical[1],
                            "direction": critical[0],
                        },
                    )
                )
                continue

            if len(rows) < 5:
                continue
            last_five = rows[-5:]
            abnormal = [
                row
                for row in last_five
                if row["value"] < definition["operational_min"]
                or row["value"] > definition["operational_max"]
            ]
            if len(abnormal) < 4:
                continue

            direction = (
                "above"
                if latest["value"] > definition["operational_max"]
                else "below"
            )
            boundary = (
                definition["operational_max"]
                if direction == "above"
                else definition["operational_min"]
            )
            detections.append(
                Detection(
                    alert_key=f"threshold-persistent:{metric}:{direction}",
                    alert_type="SAFETY_THRESHOLD",
                    severity="WARNING",
                    title=f"Persistent {definition['label'].lower()} deviation",
                    explanation=(
                        f"{definition['label']} has been {direction} its operating "
                        f"range in {len(abnormal)} of the last 5 samples. Latest value "
                        f"is {latest['value']:.1f} {definition['unit']}."
                    ),
                    recommended_action="Review recent operating context and schedule inspection.",
                    confidence=82,
                    evidence={
                        "metric": metric,
                        "current_value": round(latest["value"], 2),
                        "boundary": boundary,
                        "direction": direction,
                        "abnormal_samples": len(abnormal),
                        "window_samples": 5,
                    },
                )
            )
        return detections

    def detect_flatlined_sensors(self, windows: dict[str, list[dict]]) -> list[Detection]:
        detections: list[Detection] = []
        for metric, rows in windows.items():
            if len(rows) < 15:
                continue
            last = rows[-15:]
            values = [row["value"] for row in last]
            tolerance = 0.01 if metric != "coolant_pressure" else 0.001
            if max(values) - min(values) > tolerance:
                continue

            changing_context = False
            for other_metric, other_rows in windows.items():
                if other_metric == metric or len(other_rows) < 15:
                    continue
                other_values = [row["value"] for row in other_rows[-15:]]
                if max(other_values) - min(other_values) > 0.5:
                    changing_context = True
                    break
            if not changing_context:
                continue

            detections.append(
                Detection(
                    alert_key=f"sensor-flatline:{metric}",
                    alert_type="SENSOR_FAULT",
                    severity="INFO",
                    title=f"{metric.replace('_', ' ').title()} sensor may be stuck",
                    explanation=(
                        f"{metric.replace('_', ' ')} has not changed across 15 samples "
                        "while related metrics continued moving."
                    ),
                    recommended_action="Check sensor wiring and calibration.",
                    confidence=78,
                    evidence={"metric": metric, "flatline_samples": 15},
                )
            )
        return detections

    def _crossed(self, value: float, direction: str, limit: float) -> bool:
        if direction == "above":
            return value > limit
        return value < limit
