# Architecture

SentinelOps is intentionally small but production-shaped.

The simulator emits batches of readings with event IDs, event timestamps, units, and
device IDs. The FastAPI ingestion route delegates to an ingestion service, which
uses a validator and a repository-backed database adapter to validate, classify,
and store accepted samples. The analysis engine then recalculates health and alerts
for impacted devices.

The operator interface is Grafana, not a custom frontend. Grafana is provisioned
(datasource + dashboard) at container startup. It reads durable fleet state from
Postgres for summary cards, health tables, and alert tables, and it subscribes to
Grafana Live channels for the five high-frequency metric charts. The backend
publishes accepted readings to Grafana Live's HTTP push API; the browser side of
Grafana Live is WebSocket-backed. Postgres remains the source of truth for
historical readings and analysis.

Important boundaries:

- `api/routes/` owns HTTP request and response boundaries, including `control.py`
  (`GET /control`, a static HTML page with no build step).
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
- `repositories/` isolates persistence behind a single `QueryExecutor` protocol,
  implemented by both `sqlite.py` (default, used in tests and simple local runs)
  and `postgres.py` (used when `SENTINELOPS_DATABASE_URL` is set, as it is in
  `docker-compose.yml`). Neither the repositories layer above nor any service or
  route knows which one is active.
- `ingestion/publisher.py` defines the telemetry publishing output port. In local
  SQLite mode it is a no-op; in Docker, `services/grafana_live.py` publishes
  accepted readings to Grafana Live's push API without coupling ingestion to
  Grafana-specific code.
- `simulation/` owns reproducible demo scenarios.
- `grafana/` holds datasource/dashboard provisioning read directly by the Grafana
  container. The dashboard keeps Postgres panels for state/history and uses
  built-in Grafana Live targets such as
  `stream/sentinelops/${device}.vibration` for realtime metric panels.

The schema is identical in both databases: devices, metric definitions, telemetry
readings, device health, and alerts. `PostgresDatabase` translates the same `?`
parameterized queries and returns dict-like rows, so `FleetRepository`, the
services, and the analysis engine required zero changes to run against Postgres.
