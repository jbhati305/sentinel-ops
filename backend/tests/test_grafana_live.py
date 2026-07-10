from __future__ import annotations

from backend.app.ingestion.publisher import PublishedTelemetryReading
from backend.app.services.grafana_live import telemetry_to_line_protocol


def test_telemetry_to_line_protocol_uses_device_metric_channel_name():
    line = telemetry_to_line_protocol(
        PublishedTelemetryReading(
            event_id="evt-1",
            device_id="cooling-unit-01",
            metric="vibration",
            value=3.14,
            unit="mm/s",
            event_timestamp="2026-07-10T12:00:00Z",
            quality="GOOD",
            quality_reason=None,
            late_arrival=False,
        )
    )

    assert line == (
        "cooling-unit-01.vibration,"
        "device_id=cooling-unit-01,"
        "late_arrival=false,"
        "metric=vibration,"
        "quality=GOOD,"
        "unit=mm/s "
        "value=3.14 "
        "1783684800000000000"
    )


def test_telemetry_to_line_protocol_escapes_influx_tags_and_measurements():
    line = telemetry_to_line_protocol(
        PublishedTelemetryReading(
            event_id="evt-2",
            device_id="cooling unit,01",
            metric="outlet temperature",
            value=42.0,
            unit="deg C",
            event_timestamp="2026-07-10T12:00:00Z",
            quality="SUSPECT",
            quality_reason="outside envelope",
            late_arrival=True,
        )
    )

    assert line.startswith("cooling\\ unit\\,01.outlet\\ temperature,")
    assert "device_id=cooling\\ unit\\,01" in line
    assert "unit=deg\\ C" in line
    assert "late_arrival=true" in line
