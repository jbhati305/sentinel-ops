from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes import alerts, control, devices, fleet, health, simulation, telemetry

router = APIRouter()
router.include_router(health.router)
router.include_router(telemetry.router)
router.include_router(fleet.router)
router.include_router(devices.router)
router.include_router(alerts.router)
router.include_router(simulation.router)
router.include_router(control.router)
