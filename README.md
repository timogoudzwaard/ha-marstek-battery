# Marstek Battery — Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for **Marstek Venus E 3.0** plug-in home batteries. Communicates over the local network using the Marstek Open API (JSON-RPC over UDP) — no cloud, no internet required.

> **Status:** v1.0.0 — read-only sensors. Controls (operating mode, DOD, LED) planned for a future version.

---

## Features

- **Local-only communication** — all data stays on your LAN (UDP, no cloud dependency)
- **Auto-discovery** — finds Marstek devices on your network via UDP broadcast
- **Manual setup** — enter IP address and port if discovery doesn't work
- **Configurable poll rate** — default 30 seconds, adjustable from 10 to 300 seconds
- **Multi-device ready** — each battery gets its own config entry; add as many as you have

### Sensors

| Sensor                  | Unit | Description                                         |
| ----------------------- | ---- | --------------------------------------------------- |
| **Battery SOC**         | %    | Current battery charge level                        |
| **Battery Power**       | W    | Current charge/discharge power (grid-tied power)    |
| **Total Input Energy**  | Wh   | Cumulative energy charged from the grid (lifetime)  |
| **Total Output Energy** | Wh   | Cumulative energy discharged to the grid (lifetime) |

The energy sensors use Home Assistant's `total_increasing` state class, which means you can create **Utility Meter helpers** to track daily/weekly/monthly energy automatically.

---

## Prerequisites

1. A **Marstek Venus E 3.0** (or compatible Venus C/E device) connected to your home network via WiFi
2. The **Open API** must be enabled in the **Marstek mobile app**:
   - Open the Marstek app → select your device → enable the Open API
   - Note the **UDP port** (default: `30000`)
3. **Home Assistant** 2024.12.0 or newer
4. (Recommended) A **static IP address** for your battery — set a DHCP reservation in your router

---

## Installation

### Option A: HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant
2. In HACS, go to **Integrations** → click the **three dots menu** (top right) → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **"Marstek Battery"** in HACS and install it
5. **Restart Home Assistant**

### Option B: Manual

1. Download or clone this repository
2. Copy the `custom_components/marstek_battery/` folder into your Home Assistant config directory:
   ```
   <ha-config>/custom_components/marstek_battery/
   ```
   Your config directory is typically `/config/` (Home Assistant OS) or `~/.homeassistant/` (Core).
3. **Restart Home Assistant**

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Marstek Battery"**
3. The integration will attempt to auto-discover devices on your network
   - If your device is found, select it from the list
   - If not, choose **"Enter IP address manually"** and enter:
     - **IP Address:** your battery's local IP (e.g. `192.168.1.100`)
     - **UDP Port:** `30000` (or whatever you configured in the Marstek app)
4. The integration validates the connection and creates the device with 4 sensors

### Changing the poll rate

Go to **Settings → Devices & Services → Marstek Battery → Configure** to adjust the polling interval (10–300 seconds).

---

## Tracking Daily Energy (Charged / Discharged Today)

The integration provides **cumulative** (lifetime) energy values. To track **daily** energy:

1. Go to **Settings → Devices & Services → Helpers → Create Helper → Utility Meter**
2. Create two Utility Meters:

   | Name                    | Input sensor                               | Cycle     |
   | ----------------------- | ------------------------------------------ | --------- |
   | Energy Charged Today    | `sensor.<device>_total_grid_input_energy`  | **Daily** |
   | Energy Discharged Today | `sensor.<device>_total_grid_output_energy` | **Daily** |

3. These helpers automatically reset at midnight and show energy charged/discharged per day

You can also create weekly or monthly meters the same way.

## Tested On

- **Device:** Marstek Venus E 3.0 (firmware v144)
- **Home Assistant:** 2024.12+ / 2026.3+
- **Communication verified:** `Marstek.GetDevice`, `ES.GetStatus`, `Bat.GetStatus`, `EM.GetStatus`, `ES.GetMode`, `Wifi.GetStatus`

### Known device quirks (Venus E 3.0)

- `bat_power` is **not returned** by `ES.GetStatus` — the integration uses `ongrid_power` instead
- API method names are **case-sensitive** (`ES.GetStatus` works, `es.GetStatus` does not)
- The `params` object **must** include `"id": 0` — sending `{}` or `null` returns an error
- The first UDP packet after idle may occasionally time out — the retry mechanism handles this

---

## Troubleshooting

| Problem                                  | Solution                                                                                                                 |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Integration not found in Add Integration | Make sure you restarted HA after copying the files                                                                       |
| "Cannot connect to device"               | Verify the Open API is enabled in the Marstek app, check IP and port, ensure HA and battery are on the same network/VLAN |
| Discovery finds no devices               | UDP broadcast may be blocked by your router/firewall. Use manual IP entry instead                                        |
| Sensors show "Unavailable"               | The device may be offline or unreachable. Check the HA logs for error details                                            |
| Energy values seem wrong                 | The API returns cumulative lifetime values. Use Utility Meter helpers for daily tracking                                 |

Check the Home Assistant logs at **Settings → System → Logs** and filter for `marstek_battery` for detailed debug information.

## License

This project is not affiliated with or endorsed by Marstek. The Marstek Open API is provided by Marstek for local use at the device owner's own risk.
