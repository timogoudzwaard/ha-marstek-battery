"""Base entity for the Marstek Battery integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MarstekDataUpdateCoordinator


class MarstekEntity(CoordinatorEntity[MarstekDataUpdateCoordinator]):
    """Base entity for all Marstek Battery entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MarstekDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        device_info = coordinator.device_info_data
        ble_mac = device_info.get("ble_mac", "")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_mac(ble_mac))},
            name=device_info.get("device", "Marstek Battery"),
            manufacturer=MANUFACTURER,
            model=device_info.get("device", "Unknown"),
            sw_version=str(device_info.get("ver", "")),
        )
