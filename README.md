# ESPTimeCast for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

A Home Assistant integration for [**ESPTimeCast**](https://github.com/mfactory-osaka/ESPTimeCast),
the WiFi LED-matrix clock & weather display for ESP32 / ESP8266.

It polls the device's local HTTP API (no cloud, no auth) and exposes its state and
controls as native Home Assistant entities, plus services for messages and timers.

> **Status:** early development. See [CLAUDE.md](CLAUDE.md) for architecture.

## Features

- **Local polling** of `GET /status` (live state) and `GET /config.json`
  (full settings), default every 30 s.
- **Zeroconf discovery** — devices on your network are offered automatically.
- Entities:
  - **Text:** custom message — type to scroll a message on the display, clear
    to remove it (mirrors the web UI's Custom Message box).
  - **Sensors:** temperature, humidity, weather description, signal strength
    (diagnostic), uptime (diagnostic); countdown remaining (when a countdown is
    set) and glucose (when Nightscout is active).
  - **Binary sensors:** time synced, display busy, dimming active (and glucose
    outdated when Nightscout is active) — all diagnostic.
  - **Switches:** display, flip, 12-hour, show day-of-week, show date,
    show humidity, blinking colon, show weather description, countdown,
    dramatic countdown, clock-only-during-dimming, hide donation message.
  - **Number:** brightness.
  - **Selects:** display mode, language, units (metric/imperial).
  - **Buttons:** restart, next/previous mode, save config, stop timer/stopwatch,
    restart pomodoro, clear message.
  - **Notify:** push a scrolling message (with advanced options) to the display.
- **Services:** `send_message`, `start_timer`, `start_pomodoro`, `start_stopwatch`,
  `go_to_mode`, `clear_message`.

Settings that require a device reboot to apply (clock/weather durations, dimming
schedule, countdown date/time, hostname, NTP servers, timezone) are handled
separately and not yet exposed; use the device's web UI for those for now.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/strepto42/homeassistant-esptimecast`, category **Integration**.
3. Install **ESPTimeCast**, then restart Home Assistant.

### Manual

Copy `custom_components/esptimecast/` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

**Settings → Devices & Services → Add Integration → ESPTimeCast.**

A discovered device can be added in one click; otherwise enter its host
(e.g. `esptimecast.local` or its IP address). No API key or password is required —
the device API is unauthenticated on the local network.

## Compatibility

- Home Assistant **2026.5** or newer.
- ESPTimeCast firmware **1.6.0+** (ESP32 and ESP8266).

## Development

```bash
python -m venv .venv
source .venv/bin/activate            # .venv\Scripts\activate on Windows
pip install -e ".[test,dev]"         # client tests + lint
pytest tests/test_api.py             # API client suite (runs on any OS)
pip install -e ".[test-ha]"          # HA integration tests (Linux/macOS/WSL/CI)
pytest tests
```

## License

MIT. ESPTimeCast firmware © mfactory-osaka.
