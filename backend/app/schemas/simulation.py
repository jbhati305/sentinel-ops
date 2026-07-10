from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SimulationInjectIn(BaseModel):
    scenario: Literal[
        "normal",
        "bearing_degradation",
        "cooling_blockage",
        "sensor_fault",
        "transient_spike",
        "missing_telemetry",
        "sudden_failure",
    ]
    device_id: str | None = None
    metric: str | None = None


class SimulationSpeedIn(BaseModel):
    speed: float = Field(default=1.0, ge=0.25, le=20.0)
