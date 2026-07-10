from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["control"])

_CONTROL_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>SentinelOps Control</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.25rem; }
  section { margin-bottom: 1.5rem; }
  button { padding: 0.5rem 1rem; margin: 0.25rem 0.25rem 0.25rem 0; cursor: pointer; }
  select, input { padding: 0.4rem; margin-right: 0.5rem; }
  #status, #log { font-family: ui-monospace, monospace; font-size: 0.85rem; white-space: pre-wrap; background: #f4f4f4; padding: 0.75rem; border-radius: 4px; }
  a { color: #0a5; }
</style>
</head>
<body>
<h1>SentinelOps Control</h1>

<section>
  <a href="http://localhost:3001/d/sentinelops-fleet-monitoring/sentinelops-fleet-monitoring" target="_blank" rel="noopener">Open Grafana</a>
  &middot;
  <a href="/docs" target="_blank" rel="noopener">API docs</a>
</section>

<section>
  <h2>Simulator</h2>
  <button onclick="call('/api/v1/simulation/start', 'POST')">Start</button>
  <button onclick="call('/api/v1/simulation/stop', 'POST')">Stop</button>
  <button onclick="call('/api/v1/simulation/reset', 'POST')">Reset</button>
  <br />
  <select id="speed">
    <option value="1">1x</option>
    <option value="5">5x</option>
    <option value="20">20x</option>
  </select>
  <button onclick="setSpeed()">Set speed</button>
</section>

<section>
  <h2>Inject scenario</h2>
  <select id="scenario">
    <option value="bearing_degradation">Bearing degradation</option>
    <option value="sensor_fault">Sensor fault</option>
    <option value="cooling_blockage">Cooling blockage</option>
  </select>
  <input id="device_id" placeholder="device id (optional)" />
  <button onclick="inject()">Inject</button>
</section>

<section>
  <h2>Status</h2>
  <button onclick="refreshStatus()">Refresh</button>
  <div id="status">(not loaded)</div>
</section>

<section>
  <h2>Log</h2>
  <div id="log"></div>
</section>

<script>
async function call(path, method, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  log(`${method} ${path} -> ${res.status}\n${text}`);
  refreshStatus();
}

function log(message) {
  document.getElementById('log').textContent = message + '\n\n' + document.getElementById('log').textContent;
}

function setSpeed() {
  const speed = Number(document.getElementById('speed').value);
  call('/api/v1/simulation/speed', 'POST', { speed });
}

function inject() {
  const scenario = document.getElementById('scenario').value;
  const deviceId = document.getElementById('device_id').value || null;
  call('/api/v1/simulation/inject', 'POST', { scenario, device_id: deviceId });
}

async function refreshStatus() {
  const res = await fetch('/api/v1/simulation/status');
  document.getElementById('status').textContent = JSON.stringify(await res.json(), null, 2);
}

refreshStatus();
</script>
</body>
</html>
"""


@router.get("/control", response_class=HTMLResponse)
def control_page() -> str:
    return _CONTROL_PAGE
