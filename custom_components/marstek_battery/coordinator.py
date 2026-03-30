"""DataUpdateCoordinator for the Marstek Battery integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MarstekConnectionError, MarstekResponseError, MarstekUDPClient
from .const import (
    API_ES_GET_STATUS,
    DATA_DEVICE_INFO,
    DATA_ES_STATUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls ES.GetStatus from the Marstek device."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MarstekUDPClient,
        device_info: dict[str, Any],
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )
        self.client = client
        self._device_info = device_info

    @property
    def device_info_data(self) -> dict[str, Any]:
        """Return the device info fetched during setup."""
        return self._device_info

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device via ES.GetStatus."""
        try:
            es_status = await self.client.async_send_command(
                API_ES_GET_STATUS, {"id": 0}
            )
        except MarstekConnectionError as err:
            raise UpdateFailed(f"Unable to reach device: {err}") from err
        except MarstekResponseError as err:
            raise UpdateFailed(f"Device returned error: {err}") from err

        return {
            DATA_ES_STATUS: es_status,
            DATA_DEVICE_INFO: self._device_info,
        }
