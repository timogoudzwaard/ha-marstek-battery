"""Constants for the Marstek Battery integration."""

from __future__ import annotations

DOMAIN = "marstek_battery"

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_PORT = 30000
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

# API method names (case-sensitive — verified on real Venus E 3.0 device)
API_GET_DEVICE = "Marstek.GetDevice"
API_ES_GET_STATUS = "ES.GetStatus"
API_ES_GET_MODE = "ES.GetMode"
API_ES_SET_MODE = "ES.SetMode"
API_BAT_GET_STATUS = "Bat.GetStatus"
API_EM_GET_STATUS = "EM.GetStatus"
API_WIFI_GET_STATUS = "Wifi.GetStatus"

# Data keys in coordinator.data
DATA_ES_STATUS = "es_status"
DATA_DEVICE_INFO = "device_info"

# Manufacturer
MANUFACTURER = "Marstek"
