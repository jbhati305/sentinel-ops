from __future__ import annotations

import math
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from backend.app.time_utils import to_utc


class TelemetryReadingIn(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    device_id: str
    metric: str
    value: float
    unit: str
    timestamp: datetime

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        return to_utc(value)


class TelemetryBatchIn(BaseModel):
    readings: list[TelemetryReadingIn] = Field(min_length=1, max_length=500)
