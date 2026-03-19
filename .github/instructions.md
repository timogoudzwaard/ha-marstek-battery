# Project: Marstek Battery — Custom Home Assistant Integration (HACS)

## Role

You are an expert Python developer and a core contributor to Home Assistant. You write clean, modular, and maintainable Python 3 code. Your goal is to help me build a custom HACS integration that communicates with a **Marstek Venus E 3.0** plug-in battery over its local UDP API.

---

## Target Device

- **Device:** Marstek Venus E 3.0 (plug-in home battery)
- **Communication:** JSON-RPC over **UDP** on the local network (LAN only)
- **Default UDP port:** 30000 (configurable, recommended range 49152–65535)
- **Authentication:** None — the Open API must be enabled in the Marstek mobile app first
- **Discovery:** UDP broadcast with method `Marstek.GetDevice`
- **Supported components (Venus E):** Marstek, WiFi, Bluetooth, Battery, ES (Energy System), EM (Energy Meter), DOD, Ble_block, Led_Ctrl
- **NOT supported on Venus E:** PV (Photovoltaic) — PV is only available on Venus D / Venus A

---

## Technology Stack

| Component         | Library / Tool                                                                 |
| ----------------- | ------------------------------------------------------------------------------ |
| **Language**      | Python 3.13+ (required by Home Assistant 2026.x)                               |
| **Framework**     | Home Assistant Core 2026.3+                                                    |
| **Network**       | `asyncio` UDP — `asyncio.DatagramProtocol` / `loop.create_datagram_endpoint()` |
| **Validation**    | `voluptuous` (config flow schemas)                                             |
| **Data fetching** | `DataUpdateCoordinator` (from `homeassistant.helpers.update_coordinator`)      |
| **Config UI**     | `config_flow.py` (UI-based setup, no YAML)                                     |
| **Serialization** | `json` (stdlib)                                                                |
| **Timeout**       | `asyncio.timeout` (stdlib, Python 3.11+)                                       |
| **Distribution**  | HACS (Home Assistant Community Store)                                          |

> **CRITICAL:** The Marstek API is **NOT HTTP/REST**. Do **NOT** use `aiohttp`, `requests`, or any HTTP library for device communication. All communication is **JSON-RPC over raw UDP datagrams**.

---

## Protocol: Marstek JSON-RPC over UDP

### Request Format

```json
{
  "id": 0,
  "method": "Component.Method",
  "params": { "id": 0 }
}
```

### Response Format (success)

```json
{
  "id": 0,
  "src": "VenusE-24215edb178f",
  "result": { "id": 0, "...": "..." }
}
```

### Response Format (error)

```json
{
  "id": 0,
  "src": "venus-24215ee580e7",
  "error": { "code": -32700, "message": "Parse error", "data": 402 }
}
```

### Error Codes

| Code             | Meaning                              |
| ---------------- | ------------------------------------ |
| -32700           | Parse error — invalid JSON           |
| -32600           | Invalid Request                      |
| -32601           | Method not found                     |
| -32602           | Invalid params                       |
| -32603           | Internal error                       |
| -32000 to -32099 | Server/implementation-defined errors |

### API Endpoints (Venus E)

| Method              | Type    | Description                                                                                                                                                                                                                               |
| ------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Marstek.GetDevice` | Query   | Discover devices on LAN (UDP broadcast). Returns: `device`, `ver`, `ble_mac`, `wifi_mac`, `wifi_name`, `ip`                                                                                                                               |
| `Wifi.GetStatus`    | Query   | Network info: `wifi_mac`, `ssid`, `rssi`, `sta_ip`, `sta_gate`, `sta_mask`, `sta_dns`                                                                                                                                                     |
| `BLE.GetStatus`     | Query   | Bluetooth info: `state`, `ble_mac`                                                                                                                                                                                                        |
| `Bat.GetStatus`     | Query   | Battery info: `soc` (%), `charg_flag`, `dischrg_flag`, `bat_temp` (°C), `bat_capacity` (Wh), `rated_capacity` (Wh)                                                                                                                        |
| `ES.GetStatus`      | Query   | Energy system: `bat_soc` (%), `bat_cap` (Wh), `pv_power` (W), `ongrid_power` (W), `offgrid_power` (W), `bat_power` (W), `total_pv_energy` (Wh), `total_grid_output_energy` (Wh), `total_grid_input_energy` (Wh), `total_load_energy` (Wh) |
| `ES.SetMode`        | Command | Set operating mode: `Auto`, `AI`, `Manual`, `Passive`, `Ups`. Each mode has its own config object.                                                                                                                                        |
| `ES.GetMode`        | Query   | Current mode + live data: `mode`, `ongrid_power`, `offgrid_power`, `bat_soc`, `ct_state`, phase powers, cumulative energy                                                                                                                 |
| `EM.GetStatus`      | Query   | Energy meter / CT: `ct_state`, `a_power` (W), `b_power` (W), `c_power` (W), `total_power` (W), `input_energy` (Wh×0.1), `output_energy` (Wh×0.1)                                                                                          |
| `DOD`               | Command | Set Depth of Discharge: `value` (range 30–88, default 88)                                                                                                                                                                                 |
| `Led_Ctrl`          | Command | LED control: `state` (1=on, 0=off)                                                                                                                                                                                                        |
| `Ble_block`         | Command | Bluetooth control: `enable` (0=enable, 1=disable) — note inverted logic                                                                                                                                                                   |

### ES.SetMode — Mode Configuration Details

**Auto / AI / UPS mode:**

```json
{ "mode": "Auto", "auto_cfg": { "enable": 1 } }
```

**Manual mode** (supports 0–9 time periods on Venus E):

```json
{
  "mode": "Manual",
  "manual_cfg": {
    "time_num": 0,
    "start_time": "08:00",
    "end_time": "16:00",
    "week_set": 127,
    "power": 500,
    "enable": 1
  }
}
```

- `week_set`: bitmask — bit 0=Monday … bit 6=Sunday. 127 = all days.

**Passive mode:**

```json
{ "mode": "Passive", "passive_cfg": { "power": 500, "cd_time": 3600 } }
```

- `cd_time`: countdown in seconds. After expiry, device stops.

---

## Entity Platform Planning

### Sensors (`sensor.py`)

| Entity                     | Key                        | Unit  | Device Class      | State Class        | Source API            |
| -------------------------- | -------------------------- | ----- | ----------------- | ------------------ | --------------------- |
| Battery SOC                | `bat_soc`                  | `%`   | `battery`         | `measurement`      | `ES.GetStatus`        |
| Battery Temperature        | `bat_temp`                 | `°C`  | `temperature`     | `measurement`      | `Bat.GetStatus`       |
| Battery Remaining Capacity | `bat_capacity`             | `Wh`  | `energy_storage`  | `measurement`      | `Bat.GetStatus`       |
| Battery Rated Capacity     | `rated_capacity`           | `Wh`  | `energy_storage`  | —                  | `Bat.GetStatus`       |
| Solar Power                | `pv_power`                 | `W`   | `power`           | `measurement`      | `ES.GetStatus`        |
| Grid Output Power          | `ongrid_power`             | `W`   | `power`           | `measurement`      | `ES.GetStatus`        |
| Off-grid Power             | `offgrid_power`            | `W`   | `power`           | `measurement`      | `ES.GetStatus`        |
| Battery Power              | `bat_power`                | `W`   | `power`           | `measurement`      | `ES.GetStatus`        |
| Total Solar Energy         | `total_pv_energy`          | `Wh`  | `energy`          | `total_increasing` | `ES.GetStatus`        |
| Total Grid Output Energy   | `total_grid_output_energy` | `Wh`  | `energy`          | `total_increasing` | `ES.GetStatus`        |
| Total Grid Input Energy    | `total_grid_input_energy`  | `Wh`  | `energy`          | `total_increasing` | `ES.GetStatus`        |
| Total Load Energy          | `total_load_energy`        | `Wh`  | `energy`          | `total_increasing` | `ES.GetStatus`        |
| CT Phase A Power           | `a_power`                  | `W`   | `power`           | `measurement`      | `EM.GetStatus`        |
| CT Phase B Power           | `b_power`                  | `W`   | `power`           | `measurement`      | `EM.GetStatus`        |
| CT Phase C Power           | `c_power`                  | `W`   | `power`           | `measurement`      | `EM.GetStatus`        |
| CT Total Power             | `total_power`              | `W`   | `power`           | `measurement`      | `EM.GetStatus`        |
| CT Input Energy            | `input_energy`             | `Wh`  | `energy`          | `total_increasing` | `EM.GetStatus` (×0.1) |
| CT Output Energy           | `output_energy`            | `Wh`  | `energy`          | `total_increasing` | `EM.GetStatus` (×0.1) |
| WiFi Signal Strength       | `rssi`                     | `dBm` | `signal_strength` | `measurement`      | `Wifi.GetStatus`      |

### Binary Sensors (`binary_sensor.py`)

| Entity              | Key            | Device Class   | Source API      |
| ------------------- | -------------- | -------------- | --------------- |
| Charging Allowed    | `charg_flag`   | —              | `Bat.GetStatus` |
| Discharging Allowed | `dischrg_flag` | —              | `Bat.GetStatus` |
| CT Connected        | `ct_state`     | `connectivity` | `EM.GetStatus`  |

### Select (`select.py`)

| Entity         | Options                                  | Source API                  |
| -------------- | ---------------------------------------- | --------------------------- |
| Operating Mode | `Auto`, `AI`, `Manual`, `Passive`, `Ups` | `ES.GetMode` / `ES.SetMode` |

### Number (`number.py`)

| Entity                   | Range            | Unit | Source API                 |
| ------------------------ | ---------------- | ---- | -------------------------- |
| Depth of Discharge (DOD) | 30–88            | `%`  | `DOD`                      |
| Passive Mode Power       | device-dependent | `W`  | `ES.SetMode` (passive_cfg) |
| Passive Mode Countdown   | 0+               | `s`  | `ES.SetMode` (passive_cfg) |

### Switch (`switch.py`)

| Entity    | Source API  | Notes                                     |
| --------- | ----------- | ----------------------------------------- |
| LED       | `Led_Ctrl`  | `state`: 1=on, 0=off                      |
| Bluetooth | `Ble_block` | **Inverted logic:** `enable`: 0=on, 1=off |

---

## Project Structure

```
MarstekBattery/                          # GitHub repository root
├── .github/
│   └── instructions.md                  # This file — project instructions for Copilot
├── hacs.json                            # HACS metadata
├── custom_components/
│   └── marstek_battery/
│       ├── __init__.py                  # Integration setup, coordinator init, platform forwarding
│       ├── manifest.json                # HA integration manifest
│       ├── config_flow.py               # UI config: IP + port input, UDP validation, unique ID
│       ├── coordinator.py               # DataUpdateCoordinator — UDP polling cycle
│       ├── api.py                       # Async UDP client — JSON-RPC send/receive, protocol logic
│       ├── const.py                     # DOMAIN, defaults, API method names, entity descriptions
│       ├── entity.py                    # MarstekEntity base class (CoordinatorEntity + device_info)
│       ├── sensor.py                    # ~19 sensor entities
│       ├── binary_sensor.py             # 3 binary sensor entities
│       ├── select.py                    # Operating mode select entity
│       ├── number.py                    # DOD + passive power/countdown number entities
│       ├── switch.py                    # LED + Bluetooth switch entities
│       ├── strings.json                 # UI strings for config flow (English)
│       └── translations/
│           ├── en.json                  # English translations
│           └── nl.json                  # Dutch translations
└── tests/
    ├── conftest.py                      # Shared fixtures, mock UDP transport
    ├── test_config_flow.py              # Config flow tests (full coverage required)
    ├── test_coordinator.py              # Coordinator polling + error handling tests
    ├── test_api.py                      # UDP client unit tests
    ├── test_sensor.py                   # Sensor entity tests
    └── ...
```

---

## Key File Templates

### `manifest.json`

```json
{
  "domain": "marstek_battery",
  "name": "Marstek Battery",
  "codeowners": ["@YOUR_GITHUB_USERNAME"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/YOUR_USERNAME/MarstekBattery",
  "integration_type": "device",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/YOUR_USERNAME/MarstekBattery/issues",
  "requirements": [],
  "version": "1.0.0"
}
```

- `integration_type`: `"device"` — one battery per config entry.
- `iot_class`: `"local_polling"` — we poll the device over LAN via UDP.
- `version`: **required** for custom integrations (HACS). Use SemVer.
- `requirements`: empty — no PyPI dependencies, we use stdlib `asyncio` UDP.

### `hacs.json` (repository root)

```json
{
  "name": "Marstek Battery",
  "homeassistant": "2026.3.0"
}
```

### `strings.json` (minimal)

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Marstek Battery",
        "description": "Enter the IP address and UDP port of your Marstek device. The Open API must be enabled in the Marstek app first.",
        "data": {
          "host": "IP Address",
          "port": "UDP Port"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to device. Verify IP, port, and that the Open API is enabled.",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This device is already configured."
    }
  }
}
```

---

## Core Architectural Rules

1. **100% Asynchronous:** Home Assistant runs on an `asyncio` event loop. NEVER write blocking/synchronous code. Use `asyncio.DatagramProtocol` for all UDP communication — never `socket.socket()` in blocking mode.
2. **Separation of Concerns:** All UDP/JSON-RPC protocol logic lives in `api.py`. The coordinator in `coordinator.py` calls `api.py` methods. Entity files (`sensor.py`, etc.) only read data from the coordinator — they never communicate with the device directly.
3. **DataUpdateCoordinator:** All data fetching goes through the coordinator. Individual entities NEVER poll the API themselves. The coordinator aggregates multiple API calls per cycle.
4. **Config Flow Only:** Use `config_flow.py` for setup via the UI. No `configuration.yaml` support.
5. **CoordinatorEntity:** All entities inherit from `CoordinatorEntity` (via a shared `MarstekEntity` base class in `entity.py`) so they automatically get `available`, `should_poll`, and `async_added_to_hass` behavior.
6. **Device Registry:** Register the battery as a device using `DeviceInfo` in the base entity. Use `ble_mac` from `Marstek.GetDevice` as the unique identifier. Group all entities under one device.

---

## Coordinator Strategy

### Polling Cycle (~30 seconds)

Each coordinator refresh calls these API methods in sequence:

1. `ES.GetStatus` — energy system data (powers, energies, SOC)
2. `Bat.GetStatus` — battery details (temp, capacity, charge/discharge flags)
3. `EM.GetStatus` — energy meter / CT data (phase powers, cumulative energy)
4. `ES.GetMode` — current operating mode + live grid data

### Less Frequent Polling (~5 minutes)

- `Wifi.GetStatus` — WiFi RSSI (use a counter or secondary coordinator)

### Data Structure

Store all API responses in a single `dict` on the coordinator:

```python
coordinator.data = {
    "es_status": { ... },     # ES.GetStatus response
    "bat_status": { ... },    # Bat.GetStatus response
    "em_status": { ... },     # EM.GetStatus response
    "es_mode": { ... },       # ES.GetMode response
    "wifi_status": { ... },   # Wifi.GetStatus response
    "device_info": { ... },   # Marstek.GetDevice response (fetched once at setup)
}
```

### Error Handling in Coordinator

- **Timeout (no UDP response):** Raise `UpdateFailed` — coordinator will retry next cycle.
- **JSON parse error:** Log warning, raise `UpdateFailed`.
- **Device offline during setup:** Raise `ConfigEntryNotReady` — HA will retry setup automatically.
- **Individual API call failure:** Log the error, continue with remaining calls. Only raise `UpdateFailed` if ALL calls fail.

---

## Config Flow Details

### User Step

1. User enters: **IP Address** (string) + **UDP Port** (int, default 30000).
2. Validate by sending `Marstek.GetDevice` to that IP:port via UDP.
3. On success: extract `ble_mac` from response → set as **unique ID** (`format_mac()`).
4. Call `self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})` to handle IP changes.
5. Create config entry with `data = {CONF_HOST: host, CONF_PORT: port}`.

### Optional: UDP Broadcast Discovery

- Send `Marstek.GetDevice` as UDP broadcast to `255.255.255.255:30000`.
- Parse responses to auto-discover devices on the network.
- Nice-to-have for v1.1, not required for v1.0.

### Options Flow (optional, v1.1)

- Allow changing polling interval (default 30s).
- Allow enabling/disabling specific entity groups.

---

## UDP Client Design (`api.py`)

The client must handle the fact that UDP is connectionless and unreliable:

```python
class MarstekUDPClient:
    """Async UDP client for Marstek JSON-RPC protocol."""

    def __init__(self, host: str, port: int) -> None: ...
    async def async_send_command(self, method: str, params: dict) -> dict: ...
    async def async_discover(self) -> dict: ...  # broadcast variant
    def close(self) -> None: ...
```

**Key implementation details:**

- Use `asyncio.DatagramProtocol` with `loop.create_datagram_endpoint()`.
- Implement **request-response correlation** via the `id` field in JSON-RPC.
- Use `asyncio.timeout(5)` for each request (5 second timeout).
- **Retry once** on timeout before raising an error.
- Serialize requests with `json.dumps().encode()`, deserialize with `json.loads()`.
- The transport should be **created once** and reused across calls (not opened/closed per request).

---

## Security Guidelines

1. **IP Address Validation:** Validate user-provided IP addresses in the config flow. Only allow private/link-local ranges (RFC 1918: `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`, `169.254.x.x`). This prevents SSRF-style attacks where a user accidentally or maliciously points at a public IP.
2. **No Sensitive Data Logging:** Never log full API responses at INFO level. Use DEBUG for raw payloads. Never log MAC addresses or IP addresses at WARNING/ERROR level in production.
3. **Input Validation:** Validate all data received from the device (untrusted network data). Check types, ranges, and handle `null` values gracefully. The API explicitly marks many fields as `number or null`.
4. **UDP Timeout Handling:** Always use `asyncio.timeout()` — never block the event loop waiting for a UDP response.
5. **Rate Limiting:** Do not poll more frequently than every 10 seconds. The default 30-second interval is safe. Respect the device's processing capacity.
6. **Port Validation:** Validate UDP port is in range 1024–65535 in the config flow.

---

## Code Style & Standards

- Follow **PEP 8** strictly. Code will be formatted with **Black** and linted with **Ruff**.
- Use **type hints** for all function arguments and return types (PEP 484 / PEP 604).
- Include docstrings for all classes and public methods.
- Naming: `snake_case` for variables/functions, `PascalCase` for classes.
- Use `import logging` and `_LOGGER = logging.getLogger(__name__)`. **Never** use `print()`.
- Constants in `const.py`: `UPPER_SNAKE_CASE`.
- Use `from __future__ import annotations` at the top of every file.

---

## Error Handling

- **Never** let the integration crash Home Assistant.
- Catch specific exceptions and map them to HA exceptions:
  - UDP timeout → `UpdateFailed` (in coordinator) or `ConfigEntryNotReady` (during setup)
  - JSON decode error → `UpdateFailed` + log warning
  - `ConfigEntryAuthFailed` is not needed (no authentication)
- In entity command methods (e.g., `select.async_select_option`), catch errors and raise `HomeAssistantError` to surface them in the UI.
- Use `try/except` at the narrowest possible scope — don't wrap entire functions.

---

## Testing

- Use **`pytest`** with **`pytest-homeassistant-custom-component`**.
- **Config flow:** full test coverage required (success path, connection error, already configured, etc.).
- **Coordinator:** test successful polling, timeout handling, partial failures.
- **API client:** mock the UDP transport using `asyncio` test utilities. Test request serialization, response parsing, timeout, retry logic.
- **Entities:** test that entity state correctly reflects coordinator data.
- Run tests with: `pytest tests/ --cov=custom_components/marstek_battery --cov-report=term-missing`

---

## Task Instructions

When I ask you to write or modify code:

1. Briefly explain your approach in 1–2 sentences.
2. Provide the complete code block for the specific file.
3. If modifying a large existing file, show only the relevant updated sections but ensure context is clear.
4. Always check that the code is consistent with the architecture described in this document (UDP protocol, coordinator pattern, entity base class, etc.).
