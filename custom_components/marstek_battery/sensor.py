"""Sensor entities for the Marstek Battery integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek sensor entities from a config entry."""
    coordinator: MarstekDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MarstekSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


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
