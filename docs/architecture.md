# Architecture

SentinelOps is intentionally small but production-shaped.

The simulator emits batches of readings with event IDs, event timestamps, units, and
device IDs. The FastAPI ingestion route delegates to an ingestion service, which
uses a validator and a repository-backed database adapter to validate, classify,
and store accepted samples. The analysis engine then recalculates health and alerts
for impacted devices.

The dashboard polls REST endpoints every few seconds. It is static HTML, CSS, and
JavaScript served by the backend so there is no separate build pipeline for the
assignment.

Important boundaries:

- `api/routes/` owns HTTP request and response boundaries.
- `ingestion/` owns telemetry validation, quality classification, deduplication,
  late-arrival handling, and persistence orchestration.
- `analysis/anomaly_detector.py` owns data-quality, threshold, sensor-fault, and
  sudden-failure rules.
- `analysis/trend_detector.py` owns gradual degradation and multivariate trend
  rules.
- `analysis/alert_engine.py` owns incident lifecycle and hysteresis resolution.
- `analysis/health_score.py` owns scoring heuristics.
- `analysis/engine.py` composes detectors and scoring without embedding rule
  details.
- `repositories/` isolates SQLite and read-model queries.
- `simulation/` owns reproducible demo scenarios.
- `frontend/src/` contains the dashboard assets served by the backend.

The schema can move from SQLite to PostgreSQL or TimescaleDB without changing the
domain model: devices, metric definitions, telemetry readings, device health, and
alerts remain the core tables. Services depend on narrow repository/query
interfaces rather than on FastAPI route internals.
