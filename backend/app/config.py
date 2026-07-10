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
    simulation_autostart: bool = _bool_from_env("SENTINELOPS_SIM_AUTOSTART", True)
    simulator_tick_seconds: float = float(os.getenv("SENTINELOPS_TICK_SECONDS", "1.0"))
    cors_allow_origins: tuple[str, ...] = ("*",)
