from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.dependencies import get_container
from backend.app.container import AppContainer
from backend.app.schemas import SimulationInjectIn, SimulationSpeedIn

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


@router.get("/status")
def simulation_status(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return container.simulator.status()


@router.post("/start")
async def simulation_start(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return await container.simulator.start()


@router.post("/stop")
async def simulation_stop(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return await container.simulator.stop()


@router.post("/speed")
def simulation_speed(
    payload: SimulationSpeedIn,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    return container.simulator.set_speed(payload.speed)


@router.post("/inject")
def simulation_inject(
    payload: SimulationInjectIn,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    try:
        return container.simulator.inject(payload.scenario, payload.device_id, payload.metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset")
def simulation_reset(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return container.simulator.reset()
