from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv(
        "SENTINELOPS_DB_PATH",
        str(Path.cwd() / "sentinel_ops.sqlite3"),
    )
    database_url: str | None = os.getenv("SENTINELOPS_DATABASE_URL")
    simulation_autostart: bool = _bool_from_env("SENTINELOPS_SIM_AUTOSTART", True)
    simulator_tick_seconds: float = float(os.getenv("SENTINELOPS_TICK_SECONDS", "1.0"))
    grafana_live_url: str | None = os.getenv("SENTINELOPS_GRAFANA_LIVE_URL")
    grafana_live_username: str | None = os.getenv("SENTINELOPS_GRAFANA_LIVE_USERNAME")
    grafana_live_password: str | None = os.getenv("SENTINELOPS_GRAFANA_LIVE_PASSWORD")
    grafana_live_token: str | None = os.getenv("SENTINELOPS_GRAFANA_LIVE_TOKEN")
    grafana_live_queue_size: int = int(
        os.getenv("SENTINELOPS_GRAFANA_LIVE_QUEUE_SIZE", "5000")
    )
    cors_allow_origins: tuple[str, ...] = ("*",)
