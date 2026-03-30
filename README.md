# Marstek Battery

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-blue.svg)](https://www.home-assistant.io/)

Custom [Home Assistant](https://www.home-assistant.io/) integration for **Marstek Venus E 3.0** plug-in home batteries. Communicates entirely over your local network — no cloud, no internet required.

## Features

- **100% local** — all communication stays on your LAN, no cloud dependency
- **Auto-discovery** — automatically finds your Marstek battery on the network
- **Manual setup** — enter IP and port manually if auto-discovery doesn't work
- **Adjustable polling** — default every 30 seconds, configurable from 10 to 300 seconds
- **Multiple devices** — add as many batteries as you have
- **Energy Dashboard ready** — all energy sensors are compatible with the HA Energy Dashboard

## Sensors

| Sensor                  | Unit | Description                                  |
| ----------------------- | ---- | -------------------------------------------- |
| Battery SOC             | %    | Current battery charge level                 |
| Battery Power           | W    | Current charge / discharge power             |
| Total Input Energy      | Wh   | Cumulative energy charged (lifetime)         |
| Total Output Energy     | Wh   | Cumulative energy discharged (lifetime)      |
| Energy Charged Today    | Wh   | Energy charged today — resets at midnight    |
| Energy Discharged Today | Wh   | Energy discharged today — resets at midnight |

> The daily energy sensors reset automatically at midnight and survive Home Assistant restarts.

## Requirements

- **Marstek Venus E 3.0** (or compatible Venus C/E) connected to your WiFi
- **Open API enabled** in the Marstek mobile app (see [Enabling the Open API](#enabling-the-open-api))
- **Home Assistant** 2025.1.0 or newer
- (Recommended) A **static IP** for your battery — set a DHCP reservation in your router

## Installation

### HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed
2. In HACS → **Integrations** → three-dot menu (⋮) → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **Marstek Battery** and click **Install**
5. **Restart Home Assistant**

### Manual

1. Download or clone this repository
2. Copy `custom_components/marstek_battery/` to your Home Assistant config directory:
   ```
   config/custom_components/marstek_battery/
   ```
3. **Restart Home Assistant**

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Marstek Battery**
3. The integration tries to discover your device automatically
   - If found, select it from the list
   - If not, choose **Enter IP address manually** and fill in your battery's IP and UDP port (default `30000`)
4. Done! The device and sensors will appear automatically

### Change the poll interval

**Settings → Devices & Services → Marstek Battery → Configure**

Adjust the polling interval between 10 and 300 seconds.

## Energy Dashboard

All energy sensors are ready for the Home Assistant **Energy Dashboard** out of the box.

For **weekly or monthly** tracking, create a **Utility Meter** helper:

1. **Settings → Devices & Services → Helpers → Create Helper → Utility Meter**
2. Select one of the lifetime energy sensors as input
3. Set the cycle to **Weekly** or **Monthly**

## Enabling the Open API

The integration communicates with your battery using the Marstek Open API. This must be enabled first:

1. Open the **Marstek mobile app**
2. Select your battery device
3. Enable the **Open API**
4. Note the **UDP port** shown (default: `30000`)

> **Tip:** Make sure your Home Assistant instance and the battery are on the same network (VLAN).

## Troubleshooting

| Problem                             | Solution                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------- |
| Integration not found after install | Restart Home Assistant and clear your browser cache                          |
| "Cannot connect to device"          | Check that the Open API is enabled, verify the IP address and port           |
| No devices discovered               | Your router/firewall may block UDP broadcast — use manual IP entry instead   |
| Sensors show "Unavailable"          | The battery may be in standby or unreachable — check your network connection |

For detailed logs, go to **Settings → System → Logs** and filter for `marstek_battery`.

To enable debug logging, add this to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.marstek_battery: debug
```

## Disclaimer

This project is not affiliated with or endorsed by Marstek. Use at your own risk.
