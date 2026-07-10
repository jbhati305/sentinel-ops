# SentinelOps Testing And Demo Commands

This file is a quick command sheet for running, testing, and demoing SentinelOps.

## Login Details

Grafana URL:

```bash
http://localhost:3001
```

Default Grafana login:

```text
username: admin
password: admin
```

The project uses port `3001` because many machines already have a local Grafana
service on port `3000`.

If Grafana says the password is wrong, your Docker volume probably contains an
older saved Grafana password. Reset this local project container password:

```bash
docker exec sentinel-ops-grafana-1 grafana cli admin reset-admin-password admin
docker compose restart backend
```

## Start Everything

Build and start Postgres, backend, and Grafana:

```bash
docker compose up --build
```

Run in the background:

```bash
docker compose up -d --build
```

Stop everything:

```bash
docker compose down
```

Restart only one service:

```bash
docker compose restart backend
docker compose restart grafana
docker compose restart postgres
```

## Open The App

Grafana dashboard:

```bash
http://localhost:3001
```

Backend control page:

```bash
http://localhost:8000/control
```

API docs:

```bash
http://localhost:8000/docs
```

Backend health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Check Containers

```bash
docker ps
docker compose ps
```

View logs:

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 grafana
docker compose logs --tail=100 postgres
```

Follow backend logs live:

```bash
docker compose logs -f backend
```

## Simulator Commands

Check simulator status:

```bash
curl http://localhost:8000/api/v1/simulation/status
```

Start simulator:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/start
```

Stop simulator:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/stop
```

Reset simulator, telemetry, health, and alerts:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/reset
```

Set simulator speed:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/speed \
  -H "Content-Type: application/json" \
  -d '{"speed": 10}'
```

Maximum useful demo speed:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/speed \
  -H "Content-Type: application/json" \
  -d '{"speed": 20}'
```

## Inject Demo Scenarios

Use the control page for the easiest demo:

```bash
http://localhost:8000/control
```

Or use these API commands.

Transient vibration spike, default device `cooling-unit-01`:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "transient_spike"}'
```

Sensor fault, default device `cooling-unit-02`:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "sensor_fault"}'
```

Cooling blockage, default device `cooling-unit-03`:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "cooling_blockage"}'
```

Bearing degradation, default device `cooling-unit-04`:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "bearing_degradation"}'
```

Missing telemetry, default device `cooling-unit-05`:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "missing_telemetry"}'
```

Sudden failure, default device `cooling-unit-06`:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "sudden_failure"}'
```

Inject a scenario into a specific device:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "bearing_degradation", "device_id": "cooling-unit-04"}'
```

Inject a sensor fault into a specific metric:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "sensor_fault", "device_id": "cooling-unit-02", "metric": "outlet_temperature"}'
```

Return one device to normal:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "normal", "device_id": "cooling-unit-04"}'
```

Reset all injected issues:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/reset
```

## Scenario To Grafana Device Mapping

When demoing, select the matching device in the Grafana `Device` dropdown:

```text
transient_spike      -> Cooling Unit 01
sensor_fault         -> Cooling Unit 02
cooling_blockage     -> Cooling Unit 03
bearing_degradation  -> Cooling Unit 04
missing_telemetry    -> Cooling Unit 05
sudden_failure       -> Cooling Unit 06
```

Recommended demo:

```bash
curl -X POST http://localhost:8000/api/v1/simulation/reset
curl -X POST http://localhost:8000/api/v1/simulation/speed \
  -H "Content-Type: application/json" \
  -d '{"speed": 20}'
curl -X POST http://localhost:8000/api/v1/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "bearing_degradation"}'
```

Then open Grafana and select `Cooling Unit 04`.

## Backend API Checks

Fleet summary:

```bash
curl http://localhost:8000/api/v1/fleet/summary
```

Devices:

```bash
curl http://localhost:8000/api/v1/devices
```

One device:

```bash
curl http://localhost:8000/api/v1/devices/cooling-unit-04
```

Recent telemetry for one device:

```bash
curl "http://localhost:8000/api/v1/devices/cooling-unit-04/telemetry?limit=50"
```

Device health:

```bash
curl http://localhost:8000/api/v1/devices/cooling-unit-04/health
```

Active alerts:

```bash
curl "http://localhost:8000/api/v1/alerts?status=active"
```

All alerts:

```bash
curl http://localhost:8000/api/v1/alerts
```

## Manual Telemetry Ingestion

Send one custom reading:

```bash
curl -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "readings": [
      {
        "event_id": "manual-test-001",
        "device_id": "cooling-unit-04",
        "metric": "vibration",
        "value": 8.4,
        "unit": "mm/s",
        "timestamp": "2026-07-10T10:00:00Z"
      }
    ]
  }'
```

Send the same event again to test deduplication:

```bash
curl -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "readings": [
      {
        "event_id": "manual-test-001",
        "device_id": "cooling-unit-04",
        "metric": "vibration",
        "value": 8.4,
        "unit": "mm/s",
        "timestamp": "2026-07-10T10:00:00Z"
      }
    ]
  }'
```

Expected result: the second response should increment `duplicates`.

## Postgres Checks

Open a SQL shell inside the project Postgres container:

```bash
docker exec -it sentinel-ops-postgres-1 psql -U sentinelops -d sentinelops
```

Count readings:

```bash
docker exec sentinel-ops-postgres-1 psql -U sentinelops -d sentinelops \
  -c "SELECT COUNT(*) AS readings, MAX(event_timestamp) AS latest FROM telemetry_readings;"
```

Show latest readings:

```bash
docker exec sentinel-ops-postgres-1 psql -U sentinelops -d sentinelops \
  -c "SELECT device_id, metric, value, quality, event_timestamp FROM telemetry_readings ORDER BY event_timestamp DESC LIMIT 20;"
```

Show active alerts:

```bash
docker exec sentinel-ops-postgres-1 psql -U sentinelops -d sentinelops \
  -c "SELECT device_id, severity, status, title, confidence, last_detected_at FROM alerts WHERE status IN ('OPEN', 'ACKNOWLEDGED') ORDER BY last_detected_at DESC;"
```

Show device health:

```bash
docker exec sentinel-ops-postgres-1 psql -U sentinelops -d sentinelops \
  -c "SELECT device_id, health_score, state, primary_issue, trend, calculated_at FROM device_health ORDER BY health_score ASC;"
```

## Automated Tests

Run all backend tests:

```bash
uv run pytest
```

Alternative without `uv`:

```bash
python3 -m pytest backend/tests -q
```

## SQLite Local Backend Mode

Use this only when you do not need Grafana:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
python3 -m uvicorn backend.app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

Clean local SQLite files:

```bash
make clean
```

## Grafana Live Troubleshooting

If metric charts are blank:

1. Confirm the simulator is running.

```bash
curl http://localhost:8000/api/v1/simulation/status
```

2. Confirm telemetry is being written.

```bash
docker exec sentinel-ops-postgres-1 psql -U sentinelops -d sentinelops \
  -c "SELECT COUNT(*) AS readings, MAX(event_timestamp) AS latest FROM telemetry_readings;"
```

3. Confirm Grafana password matches `docker-compose.yml`.

```bash
docker exec sentinel-ops-grafana-1 grafana cli admin reset-admin-password admin
docker compose restart backend
```

4. Restart Grafana to reload the provisioned dashboard JSON.

```bash
docker compose restart grafana
```

5. Open Grafana and select the same device as the injected scenario.

```bash
http://localhost:3001
```

## Full Clean Reset

Stop services but keep data:

```bash
docker compose down
```

Stop services and remove project volumes:

```bash
docker compose down -v
```

Start fresh:

```bash
docker compose up -d --build
```

Use `docker compose down -v` carefully. It deletes project Postgres and Grafana
state, including stored telemetry and Grafana internal settings.
