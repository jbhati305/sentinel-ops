from __future__ import annotations

from dataclasses import dataclass

from backend.app.analysis import AnalysisEngine
from backend.app.config import Settings
from backend.app.ingestion import (
    NoopTelemetryPublisher,
    TelemetryService,
    TelemetryValidator,
)
from backend.app.ingestion.publisher import TelemetryPublisher
from backend.app.repositories import FleetRepository, PostgresDatabase, SqliteDatabase
from backend.app.repositories.interfaces import QueryExecutor
from backend.app.services.alert_service import AlertService
from backend.app.services.fleet_service import FleetService
from backend.app.services.grafana_live import GrafanaLivePublisher
from backend.app.simulation import SimulatorService


@dataclass(frozen=True)
class AppContainer:
    db: QueryExecutor
    analysis: AnalysisEngine
    telemetry: TelemetryService
    simulator: SimulatorService
    fleet_repository: FleetRepository
    fleet_service: FleetService
    alert_service: AlertService

    def close(self) -> None:
        self.telemetry.close()


def _build_database(settings: Settings, database_path: str | None) -> QueryExecutor:
    if settings.database_url:
        return PostgresDatabase(settings.database_url)
    return SqliteDatabase(database_path or settings.database_path)


def _build_publisher(settings: Settings) -> TelemetryPublisher:
    if not settings.grafana_live_url:
        return NoopTelemetryPublisher()
    return GrafanaLivePublisher(
        settings.grafana_live_url,
        username=settings.grafana_live_username,
        password=settings.grafana_live_password,
        bearer_token=settings.grafana_live_token,
        queue_size=settings.grafana_live_queue_size,
    )


def build_container(settings: Settings, database_path: str | None = None) -> AppContainer:
    db = _build_database(settings, database_path)
    db.init_schema()
    db.seed_defaults()

    analysis = AnalysisEngine(db)
    validator = TelemetryValidator(db)
    publisher = _build_publisher(settings)
    telemetry = TelemetryService(db, analysis, validator, publisher)
    simulator = SimulatorService(
        db=db,
        telemetry=telemetry,
        analysis=analysis,
        tick_seconds=settings.simulator_tick_seconds,
    )
    fleet_repository = FleetRepository(db)
    fleet_service = FleetService(fleet_repository, analysis, simulator)
    alert_service = AlertService(db, fleet_repository)

    return AppContainer(
        db=db,
        analysis=analysis,
        telemetry=telemetry,
        simulator=simulator,
        fleet_repository=fleet_repository,
        fleet_service=fleet_service,
        alert_service=alert_service,
    )
