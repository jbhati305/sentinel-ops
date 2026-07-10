from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_container
from backend.app.container import AppContainer

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


@router.get("/summary")
def fleet_summary(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return container.fleet_service.summary()
