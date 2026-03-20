"""Tests for the Marstek Battery sensor entities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.marstek_battery.const import DATA_DEVICE_INFO, DATA_ES_STATUS
from custom_components.marstek_battery.sensor import (
    SENSOR_DESCRIPTIONS,
    MarstekDailyEnergySensor,
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


def _make_daily_sensor(direction="discharge", data=None):
    """Create a MarstekDailyEnergySensor for testing."""
    coordinator = _make_mock_coordinator(data)
    key = (
        "energy_discharged_today" if direction == "discharge"
        else "energy_charged_today"
    )
    sensor = MarstekDailyEnergySensor(coordinator, key, key, direction)
    return sensor


class TestMarstekDailyEnergySensor:
    """Test daily energy (Riemann Sum) sensors."""

    def test_initial_value_is_zero(self):
        """Test that the sensor starts at 0 Wh."""
        sensor = _make_daily_sensor("discharge")
        assert sensor.native_value == 0.0

    def test_discharge_accumulates_positive_power(self):
        """Test discharge sensor accumulates when ongrid_power > 0."""
        sensor = _make_daily_sensor("discharge")
        now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        later = now + timedelta(seconds=30)

        # First update — just records power + time, no accumulation
        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._handle_coordinator_update()

        assert sensor.native_value == 0.0

        # Second update 30s later — should accumulate
        # ongrid_power=698 W for 30s = 698 * (30/3600) = 5.817 Wh
        # Trapezoidal: (698+698)/2 * 30/3600 = 5.82 Wh
        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = later
            sensor._handle_coordinator_update()

        assert sensor.native_value == pytest.approx(5.82, abs=0.01)

    def test_charge_accumulates_negative_power(self):
        """Test charge sensor accumulates when ongrid_power < 0."""
        data = {
            DATA_ES_STATUS: {**MOCK_ES_STATUS, "ongrid_power": -500},
            DATA_DEVICE_INFO: MOCK_DEVICE_INFO,
        }
        sensor = _make_daily_sensor("charge", data)
        now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        later = now + timedelta(seconds=60)

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._handle_coordinator_update()

        # 500 W * 60s/3600 = 8.33 Wh
        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = later
            sensor._handle_coordinator_update()

        assert sensor.native_value == pytest.approx(8.33, abs=0.01)

    def test_discharge_ignores_negative_power(self):
        """Test discharge sensor does NOT accumulate when power is negative."""
        data = {
            DATA_ES_STATUS: {**MOCK_ES_STATUS, "ongrid_power": -500},
            DATA_DEVICE_INFO: MOCK_DEVICE_INFO,
        }
        sensor = _make_daily_sensor("discharge", data)
        now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        later = now + timedelta(seconds=60)

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._handle_coordinator_update()

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = later
            sensor._handle_coordinator_update()

        assert sensor.native_value == 0.0

    def test_charge_ignores_positive_power(self):
        """Test charge sensor does NOT accumulate when power is positive."""
        sensor = _make_daily_sensor("charge")  # ongrid_power=698 in mock
        now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        later = now + timedelta(seconds=60)

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._handle_coordinator_update()

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = later
            sensor._handle_coordinator_update()

        assert sensor.native_value == 0.0

    def test_midnight_reset(self):
        """Test that _async_reset_daily resets the accumulator."""
        sensor = _make_daily_sensor("discharge")
        sensor._accumulated = 1234.56
        now = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = now
            sensor._async_reset_daily(now)

        assert sensor.native_value == 0.0
        assert sensor._last_power is None
        assert sensor._last_update is None
        assert sensor._attr_last_reset == now

    def test_none_power_skipped(self):
        """Test that None ongrid_power does not cause errors."""
        data = {
            DATA_ES_STATUS: {**MOCK_ES_STATUS, "ongrid_power": None},
            DATA_DEVICE_INFO: MOCK_DEVICE_INFO,
        }
        sensor = _make_daily_sensor("discharge", data)
        sensor._handle_coordinator_update()
        assert sensor.native_value == 0.0

    def test_none_data_skipped(self):
        """Test that None coordinator data does not cause errors."""
        sensor = _make_daily_sensor("discharge")
        sensor.coordinator.data = None
        sensor._handle_coordinator_update()
        assert sensor.native_value == 0.0

    def test_first_update_no_accumulation(self):
        """Test that the first update only records power, no energy added."""
        sensor = _make_daily_sensor("discharge")
        now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)

        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._handle_coordinator_update()

        assert sensor.native_value == 0.0
        assert sensor._last_power == 698.0
        assert sensor._last_update == now

    def test_trapezoidal_varying_power(self):
        """Test trapezoidal integration with changing power levels."""
        sensor = _make_daily_sensor("discharge")
        now = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)

        # First update: 698 W
        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._handle_coordinator_update()

        # Second update 30s later: power changes to 500 W
        sensor.coordinator.data = {
            DATA_ES_STATUS: {**MOCK_ES_STATUS, "ongrid_power": 500},
            DATA_DEVICE_INFO: MOCK_DEVICE_INFO,
        }
        later = now + timedelta(seconds=30)
        with patch("custom_components.marstek_battery.sensor.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = later
            sensor._handle_coordinator_update()

        # Trapezoidal: (698 + 500) / 2 * (30/3600) = 4.99 Wh
        assert sensor.native_value == pytest.approx(4.99, abs=0.01)

    def test_unique_ids_differ(self):
        """Test that charge and discharge sensors have different unique IDs."""
        coordinator = _make_mock_coordinator()
        charge = MarstekDailyEnergySensor(
            coordinator, "energy_charged_today", "energy_charged_today", "charge"
        )
        discharge = MarstekDailyEnergySensor(
            coordinator, "energy_discharged_today", "energy_discharged_today", "discharge"
        )
        assert charge.unique_id != discharge.unique_id
