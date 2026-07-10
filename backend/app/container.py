from __future__ import annotations

from dataclasses import dataclass

from backend.app.analysis import AnalysisEngine
from backend.app.config import Settings
from backend.app.ingestion import TelemetryService, TelemetryValidator
from backend.app.repositories import FleetRepository, SqliteDatabase
from backend.app.services.alert_service import AlertService
from backend.app.services.fleet_service import FleetService
from backend.app.simulation import SimulatorService


@dataclass(frozen=True)
class AppContainer:
    db: SqliteDatabase
    analysis: AnalysisEngine
    telemetry: TelemetryService
    simulator: SimulatorService
    fleet_repository: FleetRepository
    fleet_service: FleetService
    alert_service: AlertService


def build_container(settings: Settings, database_path: str | None = None) -> AppContainer:
    db = SqliteDatabase(database_path or settings.database_path)
    db.init_schema()
    db.seed_defaults()

    analysis = AnalysisEngine(db)
    validator = TelemetryValidator(db)
    telemetry = TelemetryService(db, analysis, validator)
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
