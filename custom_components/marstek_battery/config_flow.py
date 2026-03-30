"""Config flow for the Marstek Battery integration."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .api import MarstekUDPClient, MarstekUDPError
from .const import (
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _is_private_ip(host: str) -> bool:
    """Check if the IP address is in a private/link-local range."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_private or addr.is_link_local


class MarstekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek Battery."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MarstekOptionsFlow:
        """Return the options flow handler."""
        return MarstekOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: try discovery, then show manual form."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input)

        # Attempt auto-discovery
        client = MarstekUDPClient("255.255.255.255", DEFAULT_PORT)
        try:
            devices = await client.async_discover_broadcast(
                port=DEFAULT_PORT, timeout=3
            )
        except Exception:  # noqa: BLE001
            devices = []
        finally:
            client.close()

        if devices:
            self._discovered_devices = devices
            return await self.async_step_pick_device()

        # No devices found — go straight to manual entry
        return self._show_manual_form()

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a discovered device or enter manually."""
        if user_input is not None:
            selected = user_input.get("device")
            if selected == "manual":
                return self._show_manual_form()
            # Find the selected device by BLE MAC
            for device in self._discovered_devices:
                if device.get("ble_mac") == selected:
                    return await self._async_validate_and_create(
                        {
                            CONF_HOST: device.get("_source_ip", device.get("ip")),
                            CONF_PORT: DEFAULT_PORT,
                        }
                    )

        device_options = {
            dev["ble_mac"]: f"{dev.get('device', 'Marstek')} ({dev.get('ip', '?')})"
            for dev in self._discovered_devices
            if "ble_mac" in dev
        }
        device_options["manual"] = "Enter IP address manually"

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_options)}
            ),
        )

    def _show_manual_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the manual IP/port entry form."""
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        int, vol.Range(min=1024, max=65535)
                    ),
                }
            ),
            errors=errors or {},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP/port entry."""
        if user_input is None:
            return self._show_manual_form()
        return await self._async_validate_and_create(user_input)

    async def _async_validate_and_create(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Validate connection and create config entry."""
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        if not _is_private_ip(host):
            return self._show_manual_form(errors={"base": "invalid_ip"})

        client = MarstekUDPClient(host, port)
        try:
            device_info = await client.async_send_command(
                "Marstek.GetDevice", {"ble_mac": "0"}
            )
        except MarstekUDPError:
            return self._show_manual_form(errors={"base": "cannot_connect"})
        finally:
            client.close()

        ble_mac = device_info.get("ble_mac", "")
        if not ble_mac:
            return self._show_manual_form(errors={"base": "cannot_connect"})

        unique_id = format_mac(ble_mac)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: port}
        )

        device_name = device_info.get("device", "Marstek Battery")

        return self.async_create_entry(
            title=device_name,
            data={CONF_HOST: host, CONF_PORT: port},
        )


class MarstekOptionsFlow(OptionsFlow):
    """Handle options for Marstek Battery."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            "scan_interval", DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "scan_interval", default=current_interval
                    ): vol.All(
                        int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    ),
                }
            ),
        )
