from __future__ import annotations

from datetime import UTC, datetime


METRIC_DEFINITIONS = {
    "inlet_temperature": {
        "label": "Inlet temperature",
        "unit": "C",
        "physical_min": -20.0,
        "physical_max": 100.0,
        "operational_min": 16.0,
        "operational_max": 35.0,
        "expected_interval_seconds": 5,
    },
    "outlet_temperature": {
        "label": "Outlet temperature",
        "unit": "C",
        "physical_min": -20.0,
        "physical_max": 120.0,
        "operational_min": 18.0,
        "operational_max": 45.0,
        "expected_interval_seconds": 5,
    },
    "vibration": {
        "label": "Vibration",
        "unit": "mm/s",
        "physical_min": 0.0,
        "physical_max": 30.0,
        "operational_min": 0.0,
        "operational_max": 8.0,
        "expected_interval_seconds": 5,
    },
    "power_draw": {
        "label": "Power draw",
        "unit": "kW",
        "physical_min": 0.0,
        "physical_max": 40.0,
        "operational_min": 3.0,
        "operational_max": 18.0,
        "expected_interval_seconds": 5,
    },
    "coolant_pressure": {
        "label": "Coolant pressure",
        "unit": "bar",
        "physical_min": 0.0,
        "physical_max": 10.0,
        "operational_min": 1.5,
        "operational_max": 4.5,
        "expected_interval_seconds": 5,
    },
}


DEVICE_BASELINES = {
    "cooling-unit-01": {
        "short_name": "CU-01",
        "name": "Cooling Unit 01",
        "location": "Data Hall A / Row 1",
        "phase": 0.0,
        "inlet_temperature": 22.1,
        "outlet_temperature": 29.2,
        "vibration": 3.2,
        "power_draw": 8.1,
        "coolant_pressure": 2.9,
    },
    "cooling-unit-02": {
        "short_name": "CU-02",
        "name": "Cooling Unit 02",
        "location": "Data Hall A / Row 2",
        "phase": 0.7,
        "inlet_temperature": 21.6,
        "outlet_temperature": 28.7,
        "vibration": 3.6,
        "power_draw": 8.6,
        "coolant_pressure": 3.0,
    },
    "cooling-unit-03": {
        "short_name": "CU-03",
        "name": "Cooling Unit 03",
        "location": "Data Hall B / Row 1",
        "phase": 1.3,
        "inlet_temperature": 22.4,
        "outlet_temperature": 30.1,
        "vibration": 3.1,
        "power_draw": 8.3,
        "coolant_pressure": 2.8,
    },
    "cooling-unit-04": {
        "short_name": "CU-04",
        "name": "Cooling Unit 04",
        "location": "Data Hall B / Row 2",
        "phase": 2.2,
        "inlet_temperature": 22.8,
        "outlet_temperature": 30.4,
        "vibration": 3.8,
        "power_draw": 8.9,
        "coolant_pressure": 2.7,
    },
    "cooling-unit-05": {
        "short_name": "CU-05",
        "name": "Cooling Unit 05",
        "location": "Data Hall C / Row 1",
        "phase": 2.9,
        "inlet_temperature": 21.9,
        "outlet_temperature": 29.5,
        "vibration": 3.4,
        "power_draw": 8.0,
        "coolant_pressure": 3.1,
    },
    "cooling-unit-06": {
        "short_name": "CU-06",
        "name": "Cooling Unit 06",
        "location": "Data Hall C / Row 2",
        "phase": 3.6,
        "inlet_temperature": 22.3,
        "outlet_temperature": 30.0,
        "vibration": 3.5,
        "power_draw": 8.7,
        "coolant_pressure": 2.9,
    },
}


INSTALLED_AT = datetime(2025, 11, 15, tzinfo=UTC).isoformat().replace("+00:00", "Z")
