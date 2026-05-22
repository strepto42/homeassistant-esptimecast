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
  - **Light:** the display — on/off plus a brightness slider (0–15 on the
    device), mirroring the web UI's single Brightness control.
  - **Text:** custom message — type to scroll a message on the display, clear
    to remove it (mirrors the web UI's Custom Message box).
  - **Sensors:** temperature, humidity, weather description, sunrise, sunset,
    countdown remaining; signal strength and uptime (diagnostic); glucose (when
    Nightscout is active).
  - **Binary sensors:** time synced, dimming active — reflects whether the
    display is *currently* dimmed (auto sunset→sunrise or the scheduled window),
    not just whether dimming is enabled — and glucose outdated (when Nightscout
    is active). All diagnostic.
  - **Switches:** flip, 12-hour, show day-of-week, show date, show humidity,
    animated seconds, show weather description, clock-only-during-dimming, hide
    donation message.
  - **Buttons:** restart, next/previous mode, clear message.
- **Services:** `send_message` (with advanced options), `clear_message`.

Switch changes apply instantly and are **persisted to the device automatically**
(no reboot), so they survive a power cycle. A few toggles (day-of-week, animated
seconds, weather description) can't be read back from the running device, so
they reflect the last saved value.

### Configure dialog

Persistent settings are in the integration's **Configure** dialog (Settings →
Devices & Services → ESPTimeCast → Configure); saving them reboots the device
(~10–20s): **language, units**, time zone, clock/weather durations, NTP servers,
hostname, OpenWeather API key & location, the dimming schedule, and the
**countdown** (enabled, date, time, label, dramatic). Wi-Fi credentials are
intentionally not configurable here — changing them would move the device off
your network; use the device's own web UI for Wi-Fi.

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
