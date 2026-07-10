from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_container
from backend.app.container import AppContainer

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(container: AppContainer = Depends(get_container)) -> dict[str, str]:
    container.db.fetch_one("SELECT 1")
    return {"status": "ready"}
