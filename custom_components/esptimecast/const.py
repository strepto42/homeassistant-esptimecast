"""Constants for the ESPTimeCast integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "esptimecast"

# Config entry data keys
CONF_HOST: Final = "host"

# Default polling interval. The /status payload is ~1.5 KB and cheap to fetch.
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)

# Default networking
DEFAULT_PORT: Final = 80
DEFAULT_TIMEOUT: Final = 10.0

# Manufacturer / model strings for the device registry.
MANUFACTURER: Final = "mfactory-osaka"
MODEL: Final = "ESPTimeCast"

# Zeroconf service type advertised by the firmware (MDNS.addService("http", "tcp", 80)).
ZEROCONF_SERVICE_TYPE: Final = "_http._tcp.local."

# Display modes exposed by the firmware (go_to_mode accepts these names or 0-7).
DISPLAY_MODES: Final = [
    "clock",
    "weather",
    "weather_desc",
    "countdown",
    "nightscout",
    "date",
    "message",
    "timer",
]

# Languages supported by the firmware web UI.
LANGUAGES: Final = ["en", "ja", "sv"]

# Weather unit options.
UNITS: Final = ["metric", "imperial"]
