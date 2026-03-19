"""Shared test fixtures for Marstek Battery tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.marstek_battery.const import (
    CONF_HOST,
    CONF_PORT,
    DATA_DEVICE_INFO,
    DATA_ES_STATUS,
    DOMAIN,
)

MOCK_HOST = "192.168.86.44"
MOCK_PORT = 30000
MOCK_BLE_MAC = "a8dd9fd8e707"

MOCK_DEVICE_INFO: dict[str, Any] = {
    "device": "VenusE 3.0",
    "ver": 144,
    "ble_mac": MOCK_BLE_MAC,
    "wifi_mac": "bcdf58b8ff4c",
    "wifi_name": "TestNetwork",
    "ip": MOCK_HOST,
}

MOCK_ES_STATUS: dict[str, Any] = {
    "id": 0,
    "bat_soc": 81,
    "bat_cap": 5120,
    "pv_power": 0,
    "ongrid_power": 698,
    "offgrid_power": 0,
    "total_pv_energy": 0,
    "total_grid_output_energy": 5091,
    "total_grid_input_energy": 7576,
    "total_load_energy": 0,
}

MOCK_COORDINATOR_DATA: dict[str, Any] = {
    DATA_ES_STATUS: MOCK_ES_STATUS,
    DATA_DEVICE_INFO: MOCK_DEVICE_INFO,
}

MOCK_CONFIG_ENTRY_DATA: dict[str, Any] = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
}


@pytest.fixture
def mock_client():
    """Return a mocked MarstekUDPClient."""
    with patch(
        "custom_components.marstek_battery.api.MarstekUDPClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.async_connect = AsyncMock()
        client.async_send_command = AsyncMock(return_value=MOCK_DEVICE_INFO)
        client.async_discover_broadcast = AsyncMock(return_value=[MOCK_DEVICE_INFO])
        client.close = MagicMock()
        client.host = MOCK_HOST
        client.port = MOCK_PORT
        yield client


@pytest.fixture
def mock_config_entry(hass):
    """Return a mock config entry."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="VenusE 3.0",
        data=MOCK_CONFIG_ENTRY_DATA,
        source="user",
        unique_id="a8:dd:9f:d8:e7:07",
    )
    entry.add_to_hass(hass)
    return entry
