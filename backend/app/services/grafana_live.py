from __future__ import annotations

import base64
import logging
import queue
import threading
from collections.abc import Iterable
from urllib import error, request

from backend.app.ingestion.publisher import PublishedTelemetryReading
from backend.app.time_utils import parse_datetime

LOGGER = logging.getLogger(__name__)


def telemetry_to_line_protocol(reading: PublishedTelemetryReading) -> str:
    measurement = _escape_measurement(f"{reading.device_id}.{reading.metric}")
    tags = {
        "device_id": reading.device_id,
        "metric": reading.metric,
        "unit": reading.unit,
        "quality": reading.quality,
        "late_arrival": "true" if reading.late_arrival else "false",
    }
    tag_set = ",".join(
        f"{_escape_tag(key)}={_escape_tag(value)}"
        for key, value in sorted(tags.items())
    )
    timestamp_ns = int(
        parse_datetime(reading.event_timestamp).timestamp() * 1_000_000_000
    )
    return f"{measurement},{tag_set} value={reading.value} {timestamp_ns}"


class GrafanaLivePublisher:
    """Publishes accepted telemetry into Grafana Live using its push API.

    Grafana converts Influx line protocol messages into Live data frames, then
    delivers them to browser panels over Grafana Live WebSockets. The dashboard
    subscribes to channels named:
    stream/sentinelops/<device_id>.<metric>
    """

    def __init__(
        self,
        url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        bearer_token: str | None = None,
        queue_size: int = 5000,
        batch_size: int = 100,
        timeout_seconds: float = 2.0,
    ):
        self.url = url
        self.username = username
        self.password = password
        self.bearer_token = bearer_token
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self._queue: queue.Queue[str] = queue.Queue(maxsize=queue_size)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_worker,
            name="grafana-live-publisher",
            daemon=True,
        )
        self._thread.start()

    def publish_batch(self, readings: Iterable[PublishedTelemetryReading]) -> None:
        for reading in readings:
            try:
                self._queue.put_nowait(telemetry_to_line_protocol(reading))
            except queue.Full:
                LOGGER.warning(
                    "dropping telemetry live event because Grafana Live queue is full"
                )
                return

    def close(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            batch = self._next_batch()
            if not batch:
                continue
            try:
                self._post("\n".join(batch).encode())
            except (OSError, error.URLError, RuntimeError) as exc:
                LOGGER.debug("Grafana Live push unavailable: %s", exc)
            finally:
                for _ in batch:
                    self._queue.task_done()

    def _next_batch(self) -> list[str]:
        try:
            first_line = self._queue.get(timeout=0.5)
        except queue.Empty:
            return []

        batch = [first_line]
        while len(batch) < self.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _post(self, body: bytes) -> None:
        live_request = request.Request(
            self.url,
            data=body,
            method="POST",
            headers=self._headers(),
        )
        with request.urlopen(live_request, timeout=self.timeout_seconds) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(
                    f"Grafana Live push failed with HTTP {response.status}"
                )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        headers["Content-Type"] = "text/plain"
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif self.username is not None and self.password is not None:
            token = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"
        return headers


def _escape_measurement(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def _escape_tag(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("=", "\\=")
        .replace(" ", "\\ ")
    )
