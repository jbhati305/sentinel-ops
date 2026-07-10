from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_container
from backend.app.container import AppContainer
from backend.app.schemas import TelemetryBatchIn

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


@router.post("/telemetry")
def ingest_telemetry(
    payload: TelemetryBatchIn,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    return container.telemetry.ingest_batch(payload.readings)
