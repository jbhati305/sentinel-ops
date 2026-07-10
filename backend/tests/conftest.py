from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.analysis.engine import AnalysisEngine
from backend.app.ingestion.service import TelemetryService
from backend.app.repositories.sqlite import SqliteDatabase
from backend.app.schemas import TelemetryReadingIn
from backend.app.seed import METRIC_DEFINITIONS


@pytest.fixture
def services(tmp_path):
    db = SqliteDatabase(str(tmp_path / "sentinel_ops_test.sqlite3"))
    db.init_schema()
    db.seed_defaults()
    analysis = AnalysisEngine(db)
    telemetry = TelemetryService(db, analysis)
    analysis.analyze_all()
    return db, analysis, telemetry


@pytest.fixture
def base_time():
    return datetime.now(UTC) - timedelta(minutes=3)


def reading(
    *,
    device_id: str = "cooling-unit-04",
    metric: str,
    value: float,
    timestamp: datetime,
    event_id: str | None = None,
    unit: str | None = None,
) -> TelemetryReadingIn:
    return TelemetryReadingIn(
        event_id=event_id or str(uuid4()),
        device_id=device_id,
        metric=metric,
        value=value,
        unit=unit or METRIC_DEFINITIONS[metric]["unit"],
        timestamp=timestamp,
    )


def metric_batch(
    *,
    device_id: str = "cooling-unit-04",
    timestamp: datetime,
    inlet_temperature: float = 22.2,
    outlet_temperature: float = 29.8,
    vibration: float = 3.6,
    power_draw: float = 8.7,
    coolant_pressure: float = 2.8,
) -> list[TelemetryReadingIn]:
    values = {
        "inlet_temperature": inlet_temperature,
        "outlet_temperature": outlet_temperature,
        "vibration": vibration,
        "power_draw": power_draw,
        "coolant_pressure": coolant_pressure,
    }
    return [
        reading(
            device_id=device_id,
            metric=metric,
            value=value,
            timestamp=timestamp,
        )
        for metric, value in values.items()
    ]


def active_alerts(db: SqliteDatabase, device_id: str = "cooling-unit-04"):
    return [
        dict(row)
        for row in db.fetch_all(
            """
            SELECT *
            FROM alerts
            WHERE device_id = ? AND status IN ('OPEN', 'ACKNOWLEDGED')
            ORDER BY first_detected_at
            """,
            (device_id,),
        )
    ]


def all_alerts(db: SqliteDatabase, device_id: str = "cooling-unit-04"):
    return [
        dict(row)
        for row in db.fetch_all(
            "SELECT * FROM alerts WHERE device_id = ? ORDER BY first_detected_at",
            (device_id,),
        )
    ]
