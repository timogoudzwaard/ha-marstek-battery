"""Tests for the Marstek Battery sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.marstek_battery.const import DATA_DEVICE_INFO, DATA_ES_STATUS
from custom_components.marstek_battery.sensor import (
    SENSOR_DESCRIPTIONS,
    MarstekSensor,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_DEVICE_INFO, MOCK_ES_STATUS


def _make_mock_coordinator(data=None):
    """Create a mock coordinator with data."""
    coordinator = MagicMock()
    coordinator.data = data if data is not None else MOCK_COORDINATOR_DATA
    coordinator.device_info_data = MOCK_DEVICE_INFO
    return coordinator


class TestSensorDescriptions:
    """Test sensor entity descriptions are correct."""

    def test_all_descriptions_have_value_key(self):
        """Verify that all sensor descriptions have a value_key."""
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.value_key, f"Sensor {desc.key} missing value_key"

    def test_description_count(self):
        """Verify the expected number of sensors."""
        assert len(SENSOR_DESCRIPTIONS) == 4


class TestMarstekSensor:
    """Test individual sensor entities."""

    def test_battery_soc_value(self):
        """Test battery SOC sensor returns correct value."""
        coordinator = _make_mock_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_soc")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value == 81

    def test_battery_power_value(self):
        """Test battery power sensor returns ongrid_power."""
        coordinator = _make_mock_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_power")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value == 698

    def test_total_grid_input_energy(self):
        """Test total grid input energy sensor."""
        coordinator = _make_mock_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_grid_input_energy")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value == 7576

    def test_total_grid_output_energy(self):
        """Test total grid output energy sensor."""
        coordinator = _make_mock_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_grid_output_energy")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value == 5091

    def test_none_when_no_data(self):
        """Test that sensor returns None when coordinator has no data."""
        coordinator = _make_mock_coordinator(data=None)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_soc")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value is None

    def test_none_when_key_missing(self):
        """Test that sensor returns None when key is missing from response."""
        data = {DATA_ES_STATUS: {"id": 0}, DATA_DEVICE_INFO: MOCK_DEVICE_INFO}
        coordinator = _make_mock_coordinator(data=data)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_soc")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value is None

    def test_none_when_value_is_null(self):
        """Test that sensor returns None when API returns null for a field."""
        data = {
            DATA_ES_STATUS: {**MOCK_ES_STATUS, "bat_soc": None},
            DATA_DEVICE_INFO: MOCK_DEVICE_INFO,
        }
        coordinator = _make_mock_coordinator(data=data)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_soc")
        sensor = MarstekSensor(coordinator, desc)
        assert sensor.native_value is None

    def test_unique_ids_are_unique(self):
        """Test that all sensors produce unique IDs."""
        coordinator = _make_mock_coordinator()
        sensors = [MarstekSensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS]
        unique_ids = [s.unique_id for s in sensors]
        assert len(unique_ids) == len(set(unique_ids))
