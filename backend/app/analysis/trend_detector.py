from __future__ import annotations

from statistics import mean
from typing import Literal

from backend.app.models.domain import Detection
from backend.app.time_utils import parse_datetime


class TrendDetector:
    """Trend and multivariate deterioration rules."""

    def detect(self, windows: dict[str, list[dict]]) -> list[Detection]:
        detections: list[Detection] = []
        detections.extend(self.detect_gradual_degradation(windows))
        detections.extend(self.detect_cooling_blockage(windows))
        return detections

    def detect_gradual_degradation(self, windows: dict[str, list[dict]]) -> list[Detection]:
        vibration = self.trend_summary(windows.get("vibration", []), min_points=8)
        power = self.trend_summary(windows.get("power_draw", []), min_points=8)
        outlet = self.trend_summary(windows.get("outlet_temperature", []), min_points=8)
        if vibration is None or power is None:
            return []

        vibration_pct = vibration["percent_change"]
        power_pct = power["percent_change"]
        outlet_increase = outlet["absolute_change"] if outlet else 0.0
        if vibration_pct < 25 or vibration["absolute_change"] < 1.0 or power_pct < 6:
            return []

        projected_minutes = self.project_minutes_to_limit(
            windows.get("vibration", []),
            limit=8.0,
            direction="above",
        )
        projection_text = ""
        if projected_minutes is not None and projected_minutes > 0:
            projection_text = (
                " At the current slope it is projected to cross 8.0 mm/s "
                f"in about {int(projected_minutes)} minutes."
            )

        confidence = min(94, 68 + int(vibration_pct / 3) + int(power_pct / 3))
        if outlet_increase > 1.0:
            confidence = min(96, confidence + 4)

        return [
            Detection(
                alert_key="trend:bearing-degradation",
                alert_type="GRADUAL_DEGRADATION",
                severity="WARNING",
                title="Bearing degradation suspected",
                explanation=(
                    f"Vibration increased from {vibration['first']:.1f} to "
                    f"{vibration['latest']:.1f} mm/s while power draw rose from "
                    f"{power['first']:.1f} to {power['latest']:.1f} kW."
                    f"{projection_text} The correlated rise is consistent with "
                    "bearing or fan friction rather than a single noisy spike."
                ),
                recommended_action="Inspect the fan bearing during the next maintenance window.",
                confidence=confidence,
                evidence={
                    "vibration_change_percent": round(vibration_pct, 1),
                    "power_change_percent": round(power_pct, 1),
                    "outlet_temperature_change": round(outlet_increase, 2),
                    "projected_minutes_to_8mm_s": projected_minutes,
                },
            )
        ]

    def detect_cooling_blockage(self, windows: dict[str, list[dict]]) -> list[Detection]:
        pressure = self.trend_summary(windows.get("coolant_pressure", []), min_points=8)
        outlet = self.trend_summary(windows.get("outlet_temperature", []), min_points=8)
        power = self.trend_summary(windows.get("power_draw", []), min_points=8)
        if pressure is None or outlet is None or power is None:
            return []
        if pressure["absolute_change"] > -0.35:
            return []
        if outlet["absolute_change"] < 2.0 or power["percent_change"] < 5:
            return []

        return [
            Detection(
                alert_key="trend:cooling-blockage",
                alert_type="MULTIVARIATE_ANOMALY",
                severity="WARNING",
                title="Cooling blockage suspected",
                explanation=(
                    f"Coolant pressure fell from {pressure['first']:.2f} to "
                    f"{pressure['latest']:.2f} bar while outlet temperature rose "
                    f"by {outlet['absolute_change']:.1f} C and power draw increased."
                ),
                recommended_action="Inspect coolant filters, valves, and pump flow.",
                confidence=88,
                evidence={
                    "pressure_change": round(pressure["absolute_change"], 2),
                    "outlet_temperature_change": round(outlet["absolute_change"], 2),
                    "power_change_percent": round(power["percent_change"], 1),
                },
            )
        ]

    def trend_summary(self, rows: list[dict], min_points: int) -> dict | None:
        good_rows = [row for row in rows if row["quality"] != "INVALID"]
        if len(good_rows) < min_points:
            return None
        window = good_rows[-min(24, len(good_rows)) :]
        segment = max(2, len(window) // 4)
        first = mean(row["value"] for row in window[:segment])
        latest = mean(row["value"] for row in window[-segment:])
        absolute_change = latest - first
        percent_change = 0.0 if abs(first) < 0.001 else (absolute_change / first) * 100
        return {
            "first": first,
            "latest": latest,
            "absolute_change": absolute_change,
            "percent_change": percent_change,
            "points": len(window),
        }

    def project_minutes_to_limit(
        self,
        rows: list[dict],
        limit: float,
        direction: Literal["above", "below"],
    ) -> int | None:
        if len(rows) < 5:
            return None
        window = rows[-min(20, len(rows)) :]
        start = parse_datetime(window[0]["event_timestamp"])
        xs = [
            (parse_datetime(row["event_timestamp"]) - start).total_seconds() / 60
            for row in window
        ]
        ys = [row["value"] for row in window]
        x_bar = mean(xs)
        y_bar = mean(ys)
        denom = sum((x - x_bar) ** 2 for x in xs)
        if denom <= 0:
            return None
        slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys, strict=True)) / denom
        latest = ys[-1]
        if direction == "above" and slope <= 0:
            return None
        if direction == "below" and slope >= 0:
            return None
        minutes = (limit - latest) / slope
        if minutes < 0 or minutes > 240:
            return None
        return max(1, int(minutes))

    def trend_is_stable(self, windows: dict[str, list[dict]]) -> bool:
        vibration = self.trend_summary(windows.get("vibration", []), min_points=8)
        power = self.trend_summary(windows.get("power_draw", []), min_points=8)
        pressure = self.trend_summary(windows.get("coolant_pressure", []), min_points=8)
        outlet = self.trend_summary(windows.get("outlet_temperature", []), min_points=8)
        bearing_clear = not (
            vibration
            and power
            and vibration["percent_change"] > 15
            and power["percent_change"] > 4
        )
        blockage_clear = not (
            pressure
            and outlet
            and pressure["absolute_change"] < -0.2
            and outlet["absolute_change"] > 1.0
        )
        return bearing_clear and blockage_clear
