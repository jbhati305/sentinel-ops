from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from backend.app.seed import DEVICE_BASELINES, INSTALLED_AT, METRIC_DEFINITIONS


class SqliteDatabase:
    """Small SQLite adapter used by repositories and services.

    The rest of the application depends on its narrow query-executor interface, so
    replacing SQLite with PostgreSQL/TimescaleDB later is contained here.
    """

    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    short_name TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    location TEXT NOT NULL,
                    status TEXT NOT NULL,
                    installed_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS metric_definitions (
                    metric TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    physical_min REAL NOT NULL,
                    physical_max REAL NOT NULL,
                    operational_min REAL NOT NULL,
                    operational_max REAL NOT NULL,
                    expected_interval_seconds INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    device_id TEXT NOT NULL REFERENCES devices(id),
                    metric TEXT NOT NULL REFERENCES metric_definitions(metric),
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    quality TEXT NOT NULL,
                    quality_reason TEXT,
                    late_arrival INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_telemetry_device_metric_time
                    ON telemetry_readings(device_id, metric, event_timestamp DESC);

                CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
                    ON telemetry_readings(device_id, event_timestamp DESC);

                CREATE TABLE IF NOT EXISTS device_health (
                    device_id TEXT PRIMARY KEY REFERENCES devices(id),
                    health_score REAL NOT NULL,
                    state TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    primary_issue TEXT NOT NULL,
                    trend TEXT NOT NULL,
                    contributors_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES devices(id),
                    alert_key TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    first_detected_at TEXT NOT NULL,
                    last_detected_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    resolved_at TEXT,
                    evidence_json TEXT NOT NULL,
                    operator_note TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_alerts_status_device
                    ON alerts(status, device_id);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_alert_per_key
                    ON alerts(device_id, alert_key)
                    WHERE status IN ('OPEN', 'ACKNOWLEDGED');
                """
            )

    def seed_defaults(self) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO metric_definitions (
                    metric, label, unit, physical_min, physical_max,
                    operational_min, operational_max, expected_interval_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric) DO UPDATE SET
                    label = excluded.label,
                    unit = excluded.unit,
                    physical_min = excluded.physical_min,
                    physical_max = excluded.physical_max,
                    operational_min = excluded.operational_min,
                    operational_max = excluded.operational_max,
                    expected_interval_seconds = excluded.expected_interval_seconds
                """,
                [
                    (
                        metric,
                        definition["label"],
                        definition["unit"],
                        definition["physical_min"],
                        definition["physical_max"],
                        definition["operational_min"],
                        definition["operational_max"],
                        definition["expected_interval_seconds"],
                    )
                    for metric, definition in METRIC_DEFINITIONS.items()
                ],
            )

            conn.executemany(
                """
                INSERT INTO devices (
                    id, name, short_name, device_type, location, status,
                    installed_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    short_name = excluded.short_name,
                    device_type = excluded.device_type,
                    location = excluded.location,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json
                """,
                [
                    (
                        device_id,
                        profile["name"],
                        profile["short_name"],
                        "data_center_cooling_unit",
                        profile["location"],
                        "ACTIVE",
                        INSTALLED_AT,
                        json.dumps(
                            {
                                metric: profile[metric]
                                for metric in METRIC_DEFINITIONS
                            }
                        ),
                    )
                    for device_id, profile in DEVICE_BASELINES.items()
                ],
            )

    def reset_operational_data(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM alerts")
            conn.execute("DELETE FROM device_health")
            conn.execute("DELETE FROM telemetry_readings")

    def fetch_one(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchone()

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(query, tuple(params)).fetchall())

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(query, tuple(params))

    def execute_many(self, query: str, params: Iterable[Iterable[Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(query, params)

    def scalar(self, query: str, params: Iterable[Any] = ()) -> Any:
        row = self.fetch_one(query, params)
        if row is None:
            return None
        return row[0]
