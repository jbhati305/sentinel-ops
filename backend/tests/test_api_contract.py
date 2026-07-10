from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.api.routes.alerts import acknowledge_alert, list_alerts, resolve_alert
from backend.app.api.routes.devices import device_detail
from backend.app.api.routes.fleet import fleet_summary
from backend.app.api.routes.health import health, ready
from backend.app.api.routes.simulation import (
    simulation_inject,
    simulation_reset,
    simulation_speed,
)
from backend.app.api.routes.telemetry import ingest_telemetry
from backend.app.config import Settings
from backend.app.container import build_container
from backend.app.schemas import AlertActionIn, SimulationInjectIn, SimulationSpeedIn
from backend.app.schemas.telemetry import TelemetryBatchIn
from backend.app.seed import METRIC_DEFINITIONS


@pytest.fixture
def api_container(tmp_path):
    container = build_container(Settings(), str(tmp_path / "sentinel_ops_api.sqlite3"))
    container.analysis.analyze_all()
    return container


def test_health_ready_and_fleet_summary_contract(api_container):
    assert health() == {"status": "ok"}
    assert ready(api_container) == {"status": "ready"}

    payload = fleet_summary(api_container)

    assert payload["device_count"] == 6
    assert payload["state_counts"]["HEALTHY"] == 6
    assert payload["active_alert_count"] == 0
    assert len(payload["devices"]) == 6
    assert payload["simulation"]["running"] is False


def test_telemetry_endpoint_accepts_duplicates_and_rejects_unknown_devices(api_container):
    event_id = str(uuid4())
    reading = _reading(
        event_id=event_id,
        metric="vibration",
        value=3.8,
        timestamp=datetime.now(UTC) - timedelta(minutes=1),
    )

    first = ingest_telemetry(TelemetryBatchIn(readings=[reading]), api_container)
    duplicate = ingest_telemetry(TelemetryBatchIn(readings=[reading]), api_container)
    unknown = ingest_telemetry(
        TelemetryBatchIn(
            readings=[
                _reading(
                    device_id="missing-device",
                    metric="vibration",
                    value=3.8,
                    timestamp=datetime.now(UTC),
                )
            ]
        ),
        api_container,
    )

    assert first["accepted"] == 1
    assert duplicate["duplicates"] == 1
    assert unknown["errors"][0]["reason"] == "unknown device"
    with pytest.raises(HTTPException) as exc_info:
        device_detail("missing-device", api_container)
    assert exc_info.value.status_code == 404


def test_operator_can_acknowledge_and_resolve_alerts(api_container):
    base_time = datetime.now(UTC) - timedelta(minutes=2)
    payload = TelemetryBatchIn(
        readings=[
            _reading(
                metric="vibration",
                value=13.4,
                timestamp=base_time + timedelta(seconds=index * 5),
            )
            for index in range(5)
        ]
    )
    ingest = ingest_telemetry(payload, api_container)
    assert ingest["accepted"] == 5

    alerts = list_alerts(status="active", container=api_container)
    alert = next(item for item in alerts if item["alert_type"] == "SAFETY_THRESHOLD")

    acknowledged = acknowledge_alert(
        alert["id"],
        AlertActionIn(note="Operator is checking vibration source."),
        api_container,
    )
    resolved = resolve_alert(
        alert["id"],
        AlertActionIn(note="Bearing inspected and unit returned to service."),
        api_container,
    )

    assert acknowledged["status"] == "ACKNOWLEDGED"
    assert "checking vibration" in acknowledged["operator_note"]
    assert resolved["status"] == "RESOLVED"
    assert "returned to service" in resolved["operator_note"]
    with pytest.raises(HTTPException) as exc_info:
        resolve_alert("not-an-alert", AlertActionIn(note=None), api_container)
    assert exc_info.value.status_code == 404


def test_simulation_controls_validate_and_expose_state(api_container):
    speed = simulation_speed(SimulationSpeedIn(speed=20), api_container)
    injected = simulation_inject(
        SimulationInjectIn(
            scenario="bearing_degradation",
            device_id="cooling-unit-04",
        ),
        api_container,
    )

    with pytest.raises(HTTPException) as exc_info:
        simulation_inject(
            SimulationInjectIn(
                scenario="bearing_degradation",
                device_id="missing-device",
            ),
            api_container,
        )
    reset = simulation_reset(api_container)

    assert speed["speed"] == 20
    assert injected["scenarios"]["cooling-unit-04"]["scenario"] == "bearing_degradation"
    assert exc_info.value.status_code == 400
    assert "unknown device" in exc_info.value.detail
    assert reset["scenarios"] == {}


def _reading(
    *,
    metric: str,
    value: float,
    timestamp: datetime,
    device_id: str = "cooling-unit-04",
    event_id: str | None = None,
) -> dict[str, object]:
    return {
        "event_id": event_id or str(uuid4()),
        "device_id": device_id,
        "metric": metric,
        "value": value,
        "unit": METRIC_DEFINITIONS[metric]["unit"],
        "timestamp": timestamp,
    }
