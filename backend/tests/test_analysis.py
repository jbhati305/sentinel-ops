from __future__ import annotations

from datetime import timedelta

from backend.tests.conftest import active_alerts, all_alerts, metric_batch, reading


def test_single_spike_does_not_create_operator_alert(services, base_time):
    db, _, telemetry = services
    rows = []
    for index in range(6):
        rows.append(
            reading(
                metric="vibration",
                value=12.5 if index == 3 else 3.6,
                timestamp=base_time + timedelta(seconds=index * 5),
            )
        )

    telemetry.ingest_batch(rows)

    assert not [
        alert for alert in active_alerts(db) if alert["alert_type"] == "SAFETY_THRESHOLD"
    ]


def test_persistent_abnormality_creates_one_alert(services, base_time):
    db, _, telemetry = services
    rows = [
        reading(
            metric="vibration",
            value=9.2,
            timestamp=base_time + timedelta(seconds=index * 5),
        )
        for index in range(7)
    ]

    telemetry.ingest_batch(rows)
    telemetry.ingest_batch(
        [
            reading(
                metric="vibration",
                value=9.4,
                timestamp=base_time + timedelta(seconds=40),
            )
        ]
    )

    alerts = [
        alert for alert in active_alerts(db) if alert["alert_type"] == "SAFETY_THRESHOLD"
    ]
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "WARNING"


def test_healthy_readings_resolve_threshold_alert(services, base_time):
    db, _, telemetry = services
    telemetry.ingest_batch(
        [
            reading(
                metric="vibration",
                value=9.3,
                timestamp=base_time + timedelta(seconds=index * 5),
            )
            for index in range(5)
        ]
    )
    telemetry.ingest_batch(
        [
            reading(
                metric="vibration",
                value=3.8,
                timestamp=base_time + timedelta(seconds=(index + 5) * 5),
            )
            for index in range(5)
        ]
    )

    alerts = all_alerts(db)
    assert any(alert["status"] == "RESOLVED" for alert in alerts)
    assert not [
        alert for alert in active_alerts(db) if alert["alert_type"] == "SAFETY_THRESHOLD"
    ]


def test_gradual_bearing_degradation_creates_early_warning(services, base_time):
    db, _, telemetry = services
    for index in range(16):
        telemetry.ingest_batch(
            metric_batch(
                timestamp=base_time + timedelta(seconds=index * 5),
                vibration=3.6 + (index * 0.18),
                power_draw=8.5 + (index * 0.08),
                outlet_temperature=29.6 + max(0, index - 8) * 0.04,
            )
        )

    alerts = [
        alert for alert in active_alerts(db) if alert["alert_type"] == "GRADUAL_DEGRADATION"
    ]
    assert len(alerts) == 1
    assert "bearing" in alerts[0]["title"].lower()
    assert alerts[0]["confidence"] >= 75


def test_zero_temperature_with_normal_correlated_metrics_is_sensor_fault(services, base_time):
    db, _, telemetry = services
    telemetry.ingest_batch(
        metric_batch(
            device_id="cooling-unit-02",
            timestamp=base_time,
            outlet_temperature=30.0,
            power_draw=8.6,
            coolant_pressure=2.9,
        )
    )
    telemetry.ingest_batch(
        metric_batch(
            device_id="cooling-unit-02",
            timestamp=base_time + timedelta(seconds=5),
            outlet_temperature=0.0,
            power_draw=8.7,
            coolant_pressure=2.9,
        )
    )

    alerts = active_alerts(db, device_id="cooling-unit-02")
    assert any(alert["alert_type"] == "SENSOR_FAULT" for alert in alerts)
    assert not any(alert["alert_type"] == "SUDDEN_FAILURE" for alert in alerts)


def test_missing_metric_creates_data_quality_alert(services, base_time):
    db, _, telemetry = services
    device_id = "cooling-unit-05"
    telemetry.ingest_batch(
        [
            reading(
                device_id=device_id,
                metric="coolant_pressure",
                value=2.8,
                timestamp=base_time,
            )
        ]
    )
    fresh_time = base_time + timedelta(seconds=95)
    telemetry.ingest_batch(
        [
            reading(
                device_id=device_id,
                metric="vibration",
                value=3.7,
                timestamp=fresh_time,
            ),
            reading(
                device_id=device_id,
                metric="power_draw",
                value=8.9,
                timestamp=fresh_time,
            ),
        ]
    )

    alerts = active_alerts(db, device_id=device_id)
    assert any(alert["alert_type"] == "MISSING_TELEMETRY" for alert in alerts)


def test_fully_silent_device_creates_offline_alert(services, base_time):
    db, _, telemetry = services
    silent_device = "cooling-unit-04"
    reporting_device = "cooling-unit-05"

    telemetry.ingest_batch(
        metric_batch(
            device_id=silent_device,
            timestamp=base_time,
        )
    )
    telemetry.ingest_batch(
        [
            reading(
                device_id=reporting_device,
                metric="vibration",
                value=3.7,
                timestamp=base_time + timedelta(seconds=130),
            )
        ]
    )

    alerts = active_alerts(db, device_id=silent_device)
    assert any(alert["alert_type"] == "DEVICE_OFFLINE" for alert in alerts)


def test_health_score_tracks_healthy_and_critical_states(services, base_time):
    db, _, telemetry = services
    for index in range(5):
        telemetry.ingest_batch(
            metric_batch(
                device_id="cooling-unit-06",
                timestamp=base_time + timedelta(seconds=index * 5),
            )
        )
    healthy = db.fetch_one(
        "SELECT * FROM device_health WHERE device_id = ?",
        ("cooling-unit-06",),
    )
    assert healthy["health_score"] >= 85

    telemetry.ingest_batch(
        metric_batch(
            device_id="cooling-unit-06",
            timestamp=base_time + timedelta(seconds=30),
            vibration=0.0,
            power_draw=0.2,
        )
    )
    critical = db.fetch_one(
        "SELECT * FROM device_health WHERE device_id = ?",
        ("cooling-unit-06",),
    )
    assert critical["state"] == "CRITICAL"
    assert critical["health_score"] <= 40
