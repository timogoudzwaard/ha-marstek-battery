"""Tests for the Marstek Battery coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.marstek_battery.api import (
    MarstekConnectionError,
    MarstekResponseError,
)
from custom_components.marstek_battery.const import DATA_DEVICE_INFO, DATA_ES_STATUS
from custom_components.marstek_battery.coordinator import MarstekDataUpdateCoordinator

from .conftest import MOCK_DEVICE_INFO, MOCK_ES_STATUS


async def _make_coordinator(
    hass: HomeAssistant, client: MagicMock
) -> MarstekDataUpdateCoordinator:
    """Create a coordinator with a mocked client."""
    coordinator = MarstekDataUpdateCoordinator(
        hass, client, MOCK_DEVICE_INFO, scan_interval=30
    )
    return coordinator


async def test_update_success(hass: HomeAssistant) -> None:
    """Test that a successful poll returns expected data."""
    client = MagicMock()
    client.async_send_command = AsyncMock(return_value=MOCK_ES_STATUS)

    coordinator = await _make_coordinator(hass, client)
    data = await coordinator._async_update_data()

    assert data[DATA_ES_STATUS] == MOCK_ES_STATUS
    assert data[DATA_DEVICE_INFO] == MOCK_DEVICE_INFO
    client.async_send_command.assert_called_once_with("ES.GetStatus", {"id": 0})


async def test_update_connection_error(hass: HomeAssistant) -> None:
    """Test that a connection error raises UpdateFailed."""
    client = MagicMock()
    client.async_send_command = AsyncMock(
        side_effect=MarstekConnectionError("Timeout")
    )

    coordinator = await _make_coordinator(hass, client)
    with pytest.raises(UpdateFailed, match="Unable to reach device"):
        await coordinator._async_update_data()


async def test_update_response_error(hass: HomeAssistant) -> None:
    """Test that a JSON-RPC error raises UpdateFailed."""
    client = MagicMock()
    client.async_send_command = AsyncMock(
        side_effect=MarstekResponseError("Invalid params")
    )

    coordinator = await _make_coordinator(hass, client)
    with pytest.raises(UpdateFailed, match="Device returned error"):
        await coordinator._async_update_data()


async def test_device_info_accessible(hass: HomeAssistant) -> None:
    """Test that device_info_data is accessible on the coordinator."""
    client = MagicMock()
    coordinator = await _make_coordinator(hass, client)
    assert coordinator.device_info_data == MOCK_DEVICE_INFO
