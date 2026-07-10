from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router as api_router
from backend.app.config import Settings
from backend.app.container import build_container


def create_app(
    database_path: str | None = None,
    start_simulator: bool | None = None,
) -> FastAPI:
    settings = Settings()
    container = build_container(settings, database_path)
    should_start_simulator = (
        settings.simulation_autostart if start_simulator is None else start_simulator
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container.analysis.analyze_all()
        if should_start_simulator:
            container.simulator.generate_tick()
            await container.simulator.start()
        yield
        await container.simulator.stop()
        container.close()

    app = FastAPI(
        title="SentinelOps",
        version="0.1.0",
        description="Explainable early-warning telemetry service for a small equipment fleet.",
        lifespan=lifespan,
    )
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app
