import { fetchJson, postJson } from "../api/client.js";
import { metricLabels, metricOrder } from "../types/metrics.js";

const state = {
  selectedDeviceId: null,
  selectedAlertId: null,
  lastSummary: null,
};

function stateClass(value) {
  return ["HEALTHY", "OBSERVE", "WARNING", "CRITICAL"].includes(value) ? value : "";
}

function formatDuration(start, end) {
  if (!start) return "-";
  const from = new Date(start).getTime();
  const to = end ? new Date(end).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((to - from) / 1000));
  if (seconds < 90) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refresh() {
  try {
    const summary = await fetchJson("/api/v1/fleet/summary");
    state.lastSummary = summary;
    if (!state.selectedDeviceId && summary.devices.length) {
      state.selectedDeviceId = summary.devices[0].id;
    }
    renderSummary(summary);
    renderAttention(summary.attention_queue);
    renderDevices(summary.devices);
    await renderDeviceDetail(state.selectedDeviceId);
  } catch (error) {
    console.error(error);
  }
}

function renderSummary(summary) {
  const counts = summary.state_counts;
  document.getElementById("summary-strip").innerHTML = `
    <div class="summary-item"><strong>${summary.device_count}</strong><span>Devices</span></div>
    <div class="summary-item"><strong>${counts.HEALTHY}</strong><span>Healthy</span></div>
    <div class="summary-item"><strong>${counts.OBSERVE}</strong><span>Observe</span></div>
    <div class="summary-item"><strong>${counts.WARNING}</strong><span>Warning</span></div>
    <div class="summary-item"><strong>${counts.CRITICAL}</strong><span>Critical</span></div>
  `;
  const sim = summary.simulation;
  const scenarios = Object.entries(sim.scenarios || {})
    .map(([device, item]) => `${device.replace("cooling-unit-", "CU-")}: ${item.scenario}`)
    .join(", ");
  document.getElementById("sim-status").textContent = `${sim.running ? "Running" : "Stopped"} - ${sim.speed}x${scenarios ? ` - ${scenarios}` : ""}`;
  document.getElementById("updated-at").textContent = `Updated ${formatTime(summary.generated_at)}`;
}

function renderAttention(alerts) {
  const tbody = document.getElementById("attention-body");
  if (!alerts.length) {
    tbody.innerHTML = document.getElementById("empty-row-template").innerHTML;
    return;
  }
  tbody.innerHTML = alerts
    .map((alert) => `
      <tr data-alert-id="${alert.id}" data-device-id="${alert.device_id}">
        <td><span class="severity-chip ${alert.severity}">${alert.severity}</span></td>
        <td>${escapeHtml(alert.device_short_name)}</td>
        <td>${escapeHtml(alert.title)}</td>
        <td>${formatDuration(alert.first_detected_at, alert.resolved_at)}</td>
        <td>${alert.confidence}%</td>
        <td>${escapeHtml(alert.recommended_action)}</td>
      </tr>
    `)
    .join("");
  tbody.querySelectorAll("tr[data-alert-id]").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedAlertId = row.dataset.alertId;
      state.selectedDeviceId = row.dataset.deviceId;
      renderDevices(state.lastSummary.devices);
      renderDeviceDetail(state.selectedDeviceId);
    });
  });
}

function renderDevices(devices) {
  const grid = document.getElementById("device-grid");
  grid.innerHTML = devices
    .map((device) => {
      const health = device.health;
      const selected = device.id === state.selectedDeviceId ? "selected" : "";
      return `
        <article class="device-card ${selected}" data-device-id="${device.id}">
          <div class="device-topline">
            <div>
              <div class="device-name">${escapeHtml(device.short_name)} - ${escapeHtml(device.name.replace("Cooling Unit ", ""))}</div>
              <div class="location">${escapeHtml(device.location)}</div>
            </div>
            <div class="health-number">${Math.round(health.health_score)}</div>
          </div>
          <div class="meter"><div class="meter-fill ${stateClass(health.state)}" style="width:${health.health_score}%"></div></div>
          <div class="primary-issue">${escapeHtml(health.primary_issue)}</div>
          <div class="card-foot">
            <span class="state-chip ${stateClass(health.state)}">${health.state}</span>
            <span>${escapeHtml(health.trend)}</span>
          </div>
        </article>
      `;
    })
    .join("");

  grid.querySelectorAll(".device-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedDeviceId = card.dataset.deviceId;
      state.selectedAlertId = null;
      renderDevices(state.lastSummary.devices);
      renderDeviceDetail(state.selectedDeviceId);
    });
  });
}

async function renderDeviceDetail(deviceId) {
  if (!deviceId) return;
  const [device, telemetry] = await Promise.all([
    fetchJson(`/api/v1/devices/${deviceId}`),
    fetchJson(`/api/v1/devices/${deviceId}/telemetry?limit=600`),
  ]);
  const health = device.health;
  const activeAlerts = device.alerts || [];
  const selectedAlert =
    activeAlerts.find((alert) => alert.id === state.selectedAlertId) || activeAlerts[0] || null;

  document.getElementById("detail-title").textContent = `${device.short_name} Detail`;
  const detailState = document.getElementById("detail-state");
  detailState.textContent = health.state;
  detailState.className = `state-chip ${stateClass(health.state)}`;

  const metricsHtml = metricOrder
    .map((metric) => health.metrics.find((item) => item.metric === metric))
    .filter(Boolean)
    .map((metric) => `
      <div class="metric-tile">
        <div class="metric-label">${metricLabels[metric.metric] || metric.metric}</div>
        <div class="metric-value">${Number(metric.value).toFixed(metric.metric === "coolant_pressure" ? 2 : 1)} ${metric.unit}</div>
        <div class="quality">${metric.quality}${metric.quality_reason ? ` - ${escapeHtml(metric.quality_reason)}` : ""}</div>
      </div>
    `)
    .join("");

  document.getElementById("detail-body").innerHTML = `
    <div class="device-topline">
      <div>
        <div class="location">${escapeHtml(device.location)}</div>
        <h3>${escapeHtml(health.primary_issue)}</h3>
      </div>
      <div class="health-number">${Math.round(health.health_score)}</div>
    </div>
    <div class="meter"><div class="meter-fill ${stateClass(health.state)}" style="width:${health.health_score}%"></div></div>
    <div class="metric-grid">${metricsHtml || '<div class="muted">Waiting for telemetry</div>'}</div>
    ${renderWhyPanel(selectedAlert, health)}
    <div class="charts-grid">${renderCharts(telemetry)}</div>
  `;

  const acknowledge = document.getElementById("acknowledge-alert");
  const resolve = document.getElementById("resolve-alert");
  if (acknowledge && selectedAlert) {
    acknowledge.addEventListener("click", async () => {
      await postJson(`/api/v1/alerts/${selectedAlert.id}/acknowledge`, {
        note: document.getElementById("operator-note").value || null,
      });
      await refresh();
    });
  }
  if (resolve && selectedAlert) {
    resolve.addEventListener("click", async () => {
      await postJson(`/api/v1/alerts/${selectedAlert.id}/resolve`, {
        note: document.getElementById("operator-note").value || null,
      });
      state.selectedAlertId = null;
      await refresh();
    });
  }
}

function renderWhyPanel(alert, health) {
  if (!alert) {
    return `
      <div class="explain-box">
        <h3>Current Assessment</h3>
        <ul class="contributors">
          ${health.contributors.map((item) => `<li>${escapeHtml(item.factor)}</li>`).join("")}
        </ul>
      </div>
    `;
  }
  return `
    <div class="explain-box">
      <h3>Why This Alert Was Generated</h3>
      <p>${escapeHtml(alert.explanation)}</p>
      <ul class="contributors">
        ${health.contributors.map((item) => `<li>${escapeHtml(item.factor)} (${item.impact})</li>`).join("")}
      </ul>
      <p><strong>Recommended action:</strong> ${escapeHtml(alert.recommended_action)}</p>
      <p><strong>Confidence:</strong> ${alert.confidence}%</p>
      <div class="alert-actions">
        <input id="operator-note" maxlength="500" placeholder="Operator note">
        <button id="acknowledge-alert">Acknowledge</button>
        <button id="resolve-alert" class="primary">Resolve</button>
      </div>
    </div>
  `;
}

function renderCharts(telemetry) {
  const grouped = Object.fromEntries(metricOrder.map((metric) => [metric, []]));
  telemetry.forEach((row) => {
    if (grouped[row.metric]) grouped[row.metric].push(row);
  });
  return metricOrder
    .map((metric) => {
      const rows = grouped[metric].slice(-80);
      if (!rows.length) return "";
      const unit = rows[rows.length - 1].unit;
      return `
        <div class="chart-row">
          <header>
            <strong>${metricLabels[metric]}</strong>
            <span>${rows.length} samples - ${unit}</span>
          </header>
          ${sparkline(rows)}
        </div>
      `;
    })
    .join("");
}

function sparkline(rows) {
  const width = 420;
  const height = 72;
  const values = rows.map((row) => Number(row.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(0.001, max - min);
  const points = values
    .map((value, index) => {
      const x = rows.length === 1 ? 0 : (index / (rows.length - 1)) * width;
      const y = height - ((value - min) / spread) * (height - 10) - 5;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const suspectMarkers = rows
    .map((row, index) => {
      if (row.quality !== "SUSPECT") return "";
      const x = rows.length === 1 ? 0 : (index / (rows.length - 1)) * width;
      return `<circle cx="${x.toFixed(1)}" cy="8" r="3" fill="#b24713"></circle>`;
    })
    .join("");
  return `
    <svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img">
      <line x1="0" y1="${height - 5}" x2="${width}" y2="${height - 5}" stroke="#d8dee6"></line>
      <polyline fill="none" stroke="#2457a6" stroke-width="2.4" points="${points}"></polyline>
      ${suspectMarkers}
    </svg>
  `;
}

function bindControls() {
  document.getElementById("sim-start").addEventListener("click", async () => {
    await postJson("/api/v1/simulation/start");
    await refresh();
  });
  document.getElementById("sim-stop").addEventListener("click", async () => {
    await postJson("/api/v1/simulation/stop");
    await refresh();
  });
  document.getElementById("sim-reset").addEventListener("click", async () => {
    await postJson("/api/v1/simulation/reset");
    state.selectedAlertId = null;
    await refresh();
  });
  document.getElementById("sim-speed").addEventListener("change", async (event) => {
    await postJson("/api/v1/simulation/speed", { speed: Number(event.target.value) });
    await refresh();
  });
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.addEventListener("click", async () => {
      await postJson("/api/v1/simulation/inject", {
        scenario: button.dataset.scenario,
      });
      await refresh();
    });
  });
}

bindControls();
refresh();
setInterval(refresh, 2500);
