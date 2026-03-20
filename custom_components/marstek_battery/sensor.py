"""Sensor entities for the Marstek Battery integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DATA_ES_STATUS, DOMAIN
from .coordinator import MarstekDataUpdateCoordinator
from .entity import MarstekEntity


@dataclass(frozen=True, kw_only=True)
class MarstekSensorEntityDescription(SensorEntityDescription):
    """Describe a Marstek sensor entity."""

    data_section: str = DATA_ES_STATUS
    value_key: str = ""
    scale: float = 1.0


SENSOR_DESCRIPTIONS: tuple[MarstekSensorEntityDescription, ...] = (
    MarstekSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_key="bat_soc",
    ),
    MarstekSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_key="ongrid_power",
    ),
    MarstekSensorEntityDescription(
        key="total_grid_input_energy",
        translation_key="total_grid_input_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_key="total_grid_input_energy",
    ),
    MarstekSensorEntityDescription(
        key="total_grid_output_energy",
        translation_key="total_grid_output_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_key="total_grid_output_energy",
    ),
)

DAILY_ENERGY_SENSORS: tuple[tuple[str, str, str], ...] = (
    ("energy_charged_today", "energy_charged_today", "charge"),
    ("energy_discharged_today", "energy_discharged_today", "discharge"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek sensor entities from a config entry."""
    coordinator: MarstekDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        MarstekSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        MarstekDailyEnergySensor(coordinator, key, translation_key, direction)
        for key, translation_key, direction in DAILY_ENERGY_SENSORS
    )
    async_add_entities(entities)


class MarstekSensor(MarstekEntity, SensorEntity):
    """Representation of a Marstek sensor."""

    entity_description: MarstekSensorEntityDescription

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        description: MarstekSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        ble_mac = coordinator.device_info_data.get("ble_mac", "")
        self._attr_unique_id = f"{ble_mac}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        section: dict[str, Any] = self.coordinator.data.get(
            self.entity_description.data_section, {}
        )
        value = section.get(self.entity_description.value_key)
        if value is None:
            return None
        try:
            return round(float(value) * self.entity_description.scale, 2)
        except (TypeError, ValueError):
            return None


class MarstekDailyEnergySensor(MarstekEntity, RestoreSensor):
    """Sensor that integrates power over time to compute daily energy (Wh).

    Uses trapezoidal Riemann Sum on ongrid_power with automatic midnight reset.
    Direction "charge" accumulates when ongrid_power < 0 (battery charging).
    Direction "discharge" accumulates when ongrid_power > 0 (battery discharging).
    """

    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        key: str,
        translation_key: str,
        direction: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = translation_key
        ble_mac = coordinator.device_info_data.get("ble_mac", "")
        self._attr_unique_id = f"{ble_mac}_{key}"
        self._direction = direction

        self._accumulated: float = 0.0
        self._last_power: float | None = None
        self._last_update: datetime | None = None
        self._attr_last_reset: datetime | None = None

    @property
    def native_value(self) -> float | None:
        """Return accumulated energy in Wh."""
        return round(self._accumulated, 2)

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to updates."""
        await super().async_added_to_hass()

        # Restore previous state after HA restart
        last_data = await self.async_get_last_sensor_data()
        last_state = await self.async_get_last_state()

        # Recover last_reset from stored state attributes
        restored_last_reset: datetime | None = None
        if last_state and (raw := last_state.attributes.get("last_reset")):
            restored_last_reset = dt_util.parse_datetime(str(raw))

        if last_data and last_data.native_value is not None:
            now = dt_util.now()
            if (
                restored_last_reset is not None
                and restored_last_reset.date() == now.date()
            ):
                # Same day — restore accumulated value
                try:
                    self._accumulated = float(last_data.native_value)
                except (TypeError, ValueError):
                    self._accumulated = 0.0
            # Different day or no last_reset — start fresh (already 0.0)

            if restored_last_reset is not None:
                self._attr_last_reset = restored_last_reset

        # Set initial last_reset if not restored
        if self._attr_last_reset is None:
            self._attr_last_reset = dt_util.start_of_local_day()

        # Schedule midnight reset
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_reset_daily, hour=0, minute=0, second=0
            )
        )

        # Subscribe to coordinator updates
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Integrate power over time on each coordinator update."""
        if self.coordinator.data is None:
            return
        es_data: dict[str, Any] = self.coordinator.data.get(DATA_ES_STATUS, {})
        raw_power = es_data.get("ongrid_power")
        if raw_power is None:
            return
        try:
            power = float(raw_power)
        except (TypeError, ValueError):
            return

        now = dt_util.utcnow()

        # Effective power for this direction
        if self._direction == "charge":
            effective = max(0.0, -power)
        else:
            effective = max(0.0, power)

        if self._last_update is not None and self._last_power is not None:
            dt_hours = (now - self._last_update).total_seconds() / 3600.0
            if dt_hours > 0:
                # Trapezoidal integration
                avg_power = (self._last_power + effective) / 2.0
                self._accumulated += avg_power * dt_hours

        self._last_power = effective
        self._last_update = now
        self.async_write_ha_state()

    @callback
    def _async_reset_daily(self, _now: datetime) -> None:
        """Reset the daily accumulator at midnight."""
        self._accumulated = 0.0
        self._last_power = None
        self._last_update = None
        self._attr_last_reset = dt_util.now()
        self.async_write_ha_state()
