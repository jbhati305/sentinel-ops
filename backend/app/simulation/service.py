from __future__ import annotations

import asyncio
import math
import random
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import uuid4

from backend.app.analysis import AnalysisEngine
from backend.app.ingestion import TelemetryService
from backend.app.repositories.sqlite import SqliteDatabase
from backend.app.schemas import TelemetryReadingIn
from backend.app.seed import DEVICE_BASELINES, METRIC_DEFINITIONS
from backend.app.time_utils import utcnow


@dataclass
class ScenarioState:
    scenario: str = "normal"
    metric: str | None = None
    ticks: int = 0
    remaining_ticks: int | None = None


class SimulatorService:
    """Continuously emits realistic-ish telemetry for demonstration scenarios."""

    def __init__(
        self,
        db: SqliteDatabase,
        telemetry: TelemetryService,
        analysis: AnalysisEngine,
        tick_seconds: float = 1.0,
    ):
        self.db = db
        self.telemetry = telemetry
        self.analysis = analysis
        self.tick_seconds = tick_seconds
        self.speed = 1.0
        self.running = False
        self._task: asyncio.Task | None = None
        self._rng = random.Random(42)
        self._tick = 0
        self._scenarios = {
            device_id: ScenarioState()
            for device_id in DEVICE_BASELINES
        }
        self._previous_payloads: list[TelemetryReadingIn] = []

    async def start(self) -> dict[str, Any]:
        if self.running:
            return self.status()
        self.running = True
        self._task = asyncio.create_task(self._loop())
        return self.status()

    async def stop(self) -> dict[str, Any]:
        self.running = False
        task = self._task
        self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return self.status()

    def set_speed(self, speed: float) -> dict[str, Any]:
        self.speed = max(0.25, min(20.0, speed))
        return self.status()

    def inject(
        self,
        scenario: str,
        device_id: str | None = None,
        metric: str | None = None,
    ) -> dict[str, Any]:
        selected_device = device_id or {
            "bearing_degradation": "cooling-unit-04",
            "cooling_blockage": "cooling-unit-03",
            "sensor_fault": "cooling-unit-02",
            "missing_telemetry": "cooling-unit-05",
            "transient_spike": "cooling-unit-01",
            "sudden_failure": "cooling-unit-06",
            "normal": "cooling-unit-04",
        }.get(scenario, "cooling-unit-04")

        if selected_device not in self._scenarios:
            raise ValueError(f"unknown device {selected_device}")

        selected_metric = metric
        if selected_metric is None:
            selected_metric = {
                "sensor_fault": "outlet_temperature",
                "missing_telemetry": "coolant_pressure",
                "transient_spike": "vibration",
            }.get(scenario)
        if selected_metric is not None and selected_metric not in METRIC_DEFINITIONS:
            raise ValueError(f"unknown metric {selected_metric}")

        remaining_ticks = 2 if scenario == "transient_spike" else None
        self._scenarios[selected_device] = ScenarioState(
            scenario=scenario,
            metric=selected_metric,
            remaining_ticks=remaining_ticks,
        )
        return self.status()

    def reset(self) -> dict[str, Any]:
        self.db.reset_operational_data()
        self.db.seed_defaults()
        self._tick = 0
        self._previous_payloads.clear()
        self._scenarios = {
            device_id: ScenarioState()
            for device_id in DEVICE_BASELINES
        }
        self.generate_tick()
        self.analysis.analyze_all()
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "speed": self.speed,
            "tick": self._tick,
            "scenarios": {
                device_id: {
                    "scenario": state.scenario,
                    "metric": state.metric,
                    "ticks": state.ticks,
                    "remaining_ticks": state.remaining_ticks,
                }
                for device_id, state in self._scenarios.items()
                if state.scenario != "normal"
            },
        }

    async def _loop(self) -> None:
        while self.running:
            self.generate_tick()
            await asyncio.sleep(max(0.1, self.tick_seconds / self.speed))

    def generate_tick(self) -> dict[str, Any]:
        self._tick += 1
        timestamp = utcnow()
        payloads: list[TelemetryReadingIn] = []
        for device_id, baseline in DEVICE_BASELINES.items():
            state = self._scenarios[device_id]
            state.ticks += 1
            for metric, definition in METRIC_DEFINITIONS.items():
                if state.scenario == "missing_telemetry" and state.metric == metric:
                    continue

                event_time = timestamp
                if self._rng.random() < 0.03:
                    event_time = timestamp - timedelta(seconds=self._rng.choice([10, 20, 35]))
                value = self._metric_value(metric, baseline, state)
                payloads.append(
                    TelemetryReadingIn(
                        event_id=str(uuid4()),
                        device_id=device_id,
                        metric=metric,
                        value=value,
                        unit=definition["unit"],
                        timestamp=event_time,
                    )
                )

            if state.scenario == "transient_spike" and state.remaining_ticks is not None:
                state.remaining_ticks -= 1
                if state.remaining_ticks <= 0:
                    self._scenarios[device_id] = ScenarioState()

        if self._previous_payloads and self._rng.random() < 0.02:
            payloads.append(deepcopy(self._rng.choice(self._previous_payloads)))

        self._previous_payloads = (self._previous_payloads + payloads)[-100:]
        return self.telemetry.ingest_batch(payloads)

    def _metric_value(
        self,
        metric: str,
        baseline: dict,
        state: ScenarioState,
    ) -> float:
        phase = baseline["phase"]
        load = 0.5 + 0.5 * math.sin((self._tick / 10) + phase)
        noise_scale = {
            "inlet_temperature": 0.18,
            "outlet_temperature": 0.22,
            "vibration": 0.10,
            "power_draw": 0.18,
            "coolant_pressure": 0.035,
        }[metric]
        value = baseline[metric] + self._rng.gauss(0, noise_scale)

        if metric == "inlet_temperature":
            value += 0.5 * load
        elif metric == "outlet_temperature":
            value += 1.3 * load
        elif metric == "vibration":
            value += 0.35 * load
        elif metric == "power_draw":
            value += 1.1 * load
        elif metric == "coolant_pressure":
            value -= 0.12 * load

        tick = state.ticks
        if state.scenario == "bearing_degradation":
            if metric == "vibration":
                value += 0.14 * tick
            elif metric == "power_draw":
                value += 0.065 * tick
            elif metric == "outlet_temperature":
                value += 0.04 * max(0, tick - 8)

        elif state.scenario == "cooling_blockage":
            if metric == "coolant_pressure":
                value -= 0.04 * tick
            elif metric == "outlet_temperature":
                value += 0.12 * tick
            elif metric == "power_draw":
                value += 0.06 * tick

        elif state.scenario == "sensor_fault" and state.metric == metric:
            value = 0.0

        elif state.scenario == "transient_spike" and state.metric == metric:
            value += 10.0

        elif state.scenario == "sudden_failure":
            if metric == "power_draw":
                value = 0.2
            elif metric == "vibration":
                value = 0.0
            elif metric == "outlet_temperature":
                value += 4.0

        definition = METRIC_DEFINITIONS[metric]
        value = max(definition["physical_min"], min(definition["physical_max"], value))
        return round(value, 3)
