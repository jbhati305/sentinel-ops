from __future__ import annotations

from datetime import timedelta

from backend.tests.conftest import reading


def test_valid_reading_is_accepted(services, base_time):
    db, _, telemetry = services

    summary = telemetry.ingest_batch(
        [
            reading(
                metric="vibration",
                value=3.8,
                timestamp=base_time,
            )
        ]
    )

    assert summary["accepted"] == 1
    assert summary["rejected"] == 0
    assert db.scalar("SELECT COUNT(*) FROM telemetry_readings") == 1


def test_duplicate_event_id_is_ignored(services, base_time):
    db, _, telemetry = services
    event_id = "duplicate-test-event"
    payload = reading(
        event_id=event_id,
        metric="vibration",
        value=3.8,
        timestamp=base_time,
    )

    first = telemetry.ingest_batch([payload])
    second = telemetry.ingest_batch([payload])

    assert first["accepted"] == 1
    assert second["duplicates"] == 1
    assert db.scalar("SELECT COUNT(*) FROM telemetry_readings WHERE event_id = ?", (event_id,)) == 1


def test_unknown_metric_is_rejected(services, base_time):
    _, _, telemetry = services
    payload = reading(metric="vibration", value=3.8, timestamp=base_time)
    payload.metric = "bearing_temperature"

    summary = telemetry.ingest_batch([payload])

    assert summary["accepted"] == 0
    assert summary["rejected"] == 1
    assert summary["errors"][0]["reason"] == "unknown metric"


def test_future_timestamp_is_rejected(services):
    _, _, telemetry = services
    from backend.app.time_utils import utcnow

    summary = telemetry.ingest_batch(
        [
            reading(
                metric="vibration",
                value=3.8,
                timestamp=utcnow() + timedelta(minutes=10),
            )
        ]
    )

    assert summary["accepted"] == 0
    assert summary["rejected"] == 1
    assert "future" in summary["errors"][0]["reason"]


def test_batch_can_partially_accept_and_reject(services, base_time):
    _, _, telemetry = services
    bad_unit = reading(
        metric="coolant_pressure",
        value=2.8,
        unit="psi",
        timestamp=base_time,
    )
    good = reading(metric="power_draw", value=8.8, timestamp=base_time)

    summary = telemetry.ingest_batch([bad_unit, good])

    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert "wrong unit" in summary["errors"][0]["reason"]


def test_out_of_order_event_is_stored_as_late_arrival(services, base_time):
    db, _, telemetry = services

    first = reading(metric="vibration", value=3.7, timestamp=base_time + timedelta(seconds=20))
    late = reading(metric="vibration", value=3.6, timestamp=base_time)

    summary = telemetry.ingest_batch([first, late])

    assert summary["accepted"] == 2
    assert summary["late_arrivals"] == 1
    assert db.scalar("SELECT COUNT(*) FROM telemetry_readings WHERE late_arrival = 1") == 1
