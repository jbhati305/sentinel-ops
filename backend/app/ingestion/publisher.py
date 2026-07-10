from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class PublishedTelemetryReading:
    event_id: str
    device_id: str
    metric: str
    value: float
    unit: str
    event_timestamp: str
    quality: str
    quality_reason: str | None
    late_arrival: bool


class TelemetryPublisher(Protocol):
    """Output port for accepted telemetry side effects such as live dashboards."""

    def publish_batch(self, readings: Iterable[PublishedTelemetryReading]) -> None:
        ...

    def close(self) -> None:
        ...


class NoopTelemetryPublisher:
    def publish_batch(self, readings: Iterable[PublishedTelemetryReading]) -> None:
        return None

    def close(self) -> None:
        return None
