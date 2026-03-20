# Marstek Battery — Custom Home Assistant Integration (HACS)

## Project Overview

Custom HACS integration for the **Marstek Venus E 3.0** plug-in home battery. Communicates over the local network using **JSON-RPC over raw UDP** (not HTTP). The Open API must be enabled in the Marstek mobile app first. Full API documentation is in `documents/marstek-device-open-api.txt`.

## Before You Start

- **Read the existing code** before making changes. Follow the patterns already established in the codebase.
- Answer me in the language I use to ask you questions.

## Tech Information

- Python 3.12+ with `from __future__ import annotations` in every file
- Home Assistant Core (custom integration, distributed via HACS)
- `asyncio` UDP (`asyncio.DatagramProtocol`) — **never use `aiohttp`, `requests`, or any HTTP library**
- `DataUpdateCoordinator` for polling
- `voluptuous` for config flow validation
- `pytest` + `pytest-homeassistant-custom-component` for testing
- Ruff for linting (line length 100)

## Commands

- `pytest tests/ --cov=custom_components/marstek_battery --cov-report=term-missing` — Run all tests with coverage.
- `ruff check custom_components/ tests/` — Lint the codebase.

## Architecture

The integration follows the standard Home Assistant custom component pattern:

- **`api.py`** — Async UDP client (`MarstekUDPClient`). All JSON-RPC protocol logic lives here. Uses a single persistent `DatagramProtocol` transport with request-response correlation via the JSON-RPC `id` field.
- **`coordinator.py`** — `DataUpdateCoordinator` that polls the device and stores results. Entities never talk to the API directly.
- **`entity.py`** — `MarstekEntity` base class (extends `CoordinatorEntity`). Provides shared `DeviceInfo` using the device's BLE MAC as unique identifier.
- **`sensor.py`**, etc. — Entity platforms. Only read data from the coordinator.
- **`config_flow.py`** — UI-based setup with UDP broadcast discovery + manual IP fallback. Options flow for poll interval.
- **`const.py`** — All constants, API method names, coordinator data keys.

Data flow: `Device ←UDP→ api.py ← coordinator.py ← entity platforms`

## Device Quirks (Venus E 3.0, firmware v144)

These are verified on the real device and critical for correct implementation:

1. **`bat_power` is NOT returned** by `ES.GetStatus` — use `ongrid_power` for power flow instead.
2. **Method names are case-sensitive** — `ES.GetStatus` works, `es.GetStatus` returns error `-32601`.
3. **`params` must include `"id": 0`** — sending `{}` returns error `-32602`.
4. **First UDP packet after idle may time out** — the built-in retry (1 retry after 5s timeout) handles this.
5. **`Ble_block` has inverted logic** — `enable: 0` = Bluetooth ON, `enable: 1` = Bluetooth OFF.
6. **EM energy values** (`input_energy`, `output_energy`) are in Wh × 0.1 — must multiply by 0.1.
7. **PV (Photovoltaic) is NOT supported** on Venus E — only on Venus D / Venus A.

## Coordinator Data Structure

```python
coordinator.data = {
    "es_status": { ... },    # ES.GetStatus response (polled every cycle)
    "device_info": { ... },  # Marstek.GetDevice response (fetched once at setup)
}
```

When adding new API calls (e.g., `Bat.GetStatus`, `EM.GetStatus`), add them to `_async_update_data()` and store under new keys (e.g., `"bat_status"`, `"em_status"`).

## Planned Entity Platforms (not yet implemented)

| File               | Entities                                                      |
| ------------------ | ------------------------------------------------------------- |
| `binary_sensor.py` | Charging/discharging flags (`Bat.GetStatus`), CT state (`EM`) |
| `select.py`        | Operating mode: Auto, AI, Manual, Passive, Ups (`ES.SetMode`) |
| `number.py`        | Depth of Discharge (30–88%), passive mode power/countdown     |
| `switch.py`        | LED on/off (`Led_Ctrl`), Bluetooth on/off (`Ble_block`)       |

## Testing Conventions

- Mock the UDP transport — never make real network calls in tests.
- Shared fixtures and mock data live in `tests/conftest.py`.
- Test files are named `test_<module>.py` and mirror the source structure.
- Test config flow paths (success, error, already configured), coordinator error handling, and that entity states reflect coordinator data correctly.

## Error Handling

- UDP timeout → `UpdateFailed` in coordinator, `ConfigEntryNotReady` during setup.
- Entity command errors → `HomeAssistantError` to surface in the UI.
- Device data may contain `null` values — always handle gracefully (return `None`).
- Never let the integration crash Home Assistant.

## Security

- Config flow only accepts private/link-local IP addresses (RFC 1918).
- UDP port must be in range 1024–65535.
- Never log raw API payloads above DEBUG level.
