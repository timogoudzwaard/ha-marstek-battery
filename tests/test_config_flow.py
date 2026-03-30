"""Tests for the Marstek Battery config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.marstek_battery.const import (
    DOMAIN,
)

from .conftest import MOCK_BLE_MAC, MOCK_DEVICE_INFO, MOCK_HOST, MOCK_PORT


async def test_manual_flow_success(hass: HomeAssistant) -> None:
    """Test a successful manual config flow."""
    with patch(
        "custom_components.marstek_battery.config_flow.MarstekUDPClient"
    ) as mock_client_cls:
        # Discovery returns nothing → goes to manual
        discover_client = MagicMock()
        discover_client.async_discover_broadcast = AsyncMock(return_value=[])
        discover_client.close = MagicMock()

        # Validation client returns device info
        validate_client = MagicMock()
        validate_client.async_send_command = AsyncMock(return_value=MOCK_DEVICE_INFO)
        validate_client.close = MagicMock()

        mock_client_cls.side_effect = [discover_client, validate_client]

        # Step 1: Start the flow (no devices discovered → manual form)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Step 2: Submit manual form
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "VenusE 3.0"
        assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}
        assert result["unique_id"] == "a8:dd:9f:d8:e7:07"


async def test_manual_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test manual flow when device is unreachable."""
    from custom_components.marstek_battery.api import MarstekConnectionError

    with patch(
        "custom_components.marstek_battery.config_flow.MarstekUDPClient"
    ) as mock_client_cls:
        discover_client = MagicMock()
        discover_client.async_discover_broadcast = AsyncMock(return_value=[])
        discover_client.close = MagicMock()

        validate_client = MagicMock()
        validate_client.async_send_command = AsyncMock(
            side_effect=MarstekConnectionError("Timeout")
        )
        validate_client.close = MagicMock()

        mock_client_cls.side_effect = [discover_client, validate_client]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "manual"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_flow_invalid_ip(hass: HomeAssistant) -> None:
    """Test manual flow with a public IP address."""
    with patch(
        "custom_components.marstek_battery.config_flow.MarstekUDPClient"
    ) as mock_client_cls:
        discover_client = MagicMock()
        discover_client.async_discover_broadcast = AsyncMock(return_value=[])
        discover_client.close = MagicMock()

        mock_client_cls.return_value = discover_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "manual"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "8.8.8.8", CONF_PORT: MOCK_PORT},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_ip"}


async def test_discovery_flow_success(hass: HomeAssistant) -> None:
    """Test flow with successful auto-discovery."""
    discovered = {**MOCK_DEVICE_INFO, "_source_ip": MOCK_HOST}

    with patch(
        "custom_components.marstek_battery.config_flow.MarstekUDPClient"
    ) as mock_client_cls:
        discover_client = MagicMock()
        discover_client.async_discover_broadcast = AsyncMock(
            return_value=[discovered]
        )
        discover_client.close = MagicMock()

        validate_client = MagicMock()
        validate_client.async_send_command = AsyncMock(return_value=MOCK_DEVICE_INFO)
        validate_client.close = MagicMock()

        mock_client_cls.side_effect = [discover_client, validate_client]

        # Step 1: Start flow (devices discovered → pick_device)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_device"

        # Step 2: Select the discovered device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": MOCK_BLE_MAC},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "VenusE 3.0"


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a duplicate device is rejected."""
    from homeassistant.config_entries import ConfigEntry

    # Add an existing entry
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="VenusE 3.0",
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        source="user",
        unique_id="a8:dd:9f:d8:e7:07",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.marstek_battery.config_flow.MarstekUDPClient"
    ) as mock_client_cls:
        discover_client = MagicMock()
        discover_client.async_discover_broadcast = AsyncMock(return_value=[])
        discover_client.close = MagicMock()

        validate_client = MagicMock()
        validate_client.async_send_command = AsyncMock(return_value=MOCK_DEVICE_INFO)
        validate_client.close = MagicMock()

        mock_client_cls.side_effect = [discover_client, validate_client]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
