from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.dependencies import get_container
from backend.app.container import AppContainer
from backend.app.schemas import AlertActionIn

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    status: str = Query(default="active", pattern="^(active|all|open|resolved|acknowledged)$"),
    container: AppContainer = Depends(get_container),
) -> list[dict[str, Any]]:
    return container.fleet_service.alerts(status)


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    payload: AlertActionIn | None = None,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    note = payload.note if payload else None
    try:
        alert = container.alert_service.acknowledge(alert_id, note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    payload: AlertActionIn | None = None,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    alert = container.alert_service.resolve(alert_id, payload.note if payload else None)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert
