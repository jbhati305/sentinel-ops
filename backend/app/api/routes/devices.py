from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.dependencies import get_container
from backend.app.container import AppContainer

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.get("")
def list_devices(container: AppContainer = Depends(get_container)) -> list[dict[str, Any]]:
    return container.fleet_service.devices()


@router.get("/{device_id}/telemetry")
def device_telemetry(
    device_id: str,
    metric: str | None = None,
    limit: int = Query(default=120, ge=1, le=1000),
    container: AppContainer = Depends(get_container),
) -> list[dict[str, Any]]:
    _require_device(container, device_id)
    return container.fleet_service.device_telemetry(device_id, metric, limit)


@router.get("/{device_id}/health")
def device_health(
    device_id: str,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    _require_device(container, device_id)
    return container.fleet_service.device_health(device_id)


@router.get("/{device_id}")
def device_detail(
    device_id: str,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    _require_device(container, device_id)
    device = container.fleet_service.device_detail(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    return device


def _require_device(container: AppContainer, device_id: str) -> None:
    if not container.fleet_repository.device_exists(device_id):
        raise HTTPException(status_code=404, detail="device not found")
