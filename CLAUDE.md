# CLAUDE.md

Guidance for Claude / AI agents working in this repository.

## What this is

A custom **Home Assistant integration** (HACS-installable) for **ESPTimeCast** —
a WiFi LED-matrix clock & weather display running on ESP32 / ESP8266.

Upstream firmware: https://github.com/mfactory-osaka/ESPTimeCast

## Architecture

Two layers, deliberately separated so the lower one is testable anywhere:

1. **API client** — `custom_components/esptimecast/api.py`
   Pure `aiohttp` async client. No Home Assistant imports. Talks to the device's
   HTTP API. Returns typed dataclasses. This is the layer with the heaviest unit
   tests (`tests/test_api.py`), runnable on any OS including Windows.

2. **Integration** — the rest of `custom_components/esptimecast/`
   `DataUpdateCoordinator` polls `/status`; entities/config-flow are thin wrappers
   over the client. Tested with `pytest-homeassistant-custom-component`.

## The device API (firmware 1.6.0, no auth, port 80)

- `GET /status` — the polling source of truth. ~1.5 KB JSON: mode, brightness,
  weather, nightscout, countdown, dimming, RSSI, uptime, firmware, saved config.
  A real captured sample lives at `tests/fixtures/status.json`.
- `GET /get_version` — `{version, board}`; used as the availability probe.
- `POST /action` — generic command bus (next_mode, brightness, timers, restart,
  language, units...). Returns **409** when a protected message is on screen.
- `POST /set_*` — typed single-setting endpoints (brightness, flip, humidity...).
- `POST /set_custom_message` — scrolling message (speed/scrolls/seconds/bignumbers/interrupt).
- `POST /save` — persist config (device reboots).
- mDNS: `_http._tcp.local.`, default hostname `esptimecast.local`.

### Gotchas

- `weather.weatherDescription` is prefixed with a `\f` (form-feed) icon glyph —
  the client strips it.
- `weather.*` numeric fields can be `null` when weather is unavailable.
- `config.openWeatherCity` may be a coordinate string (e.g. `"-27.4808"`).
- `brightness` ranges `-1..15` (`-1` = auto).
- Secrets in `/status.config` are masked (`"***HIDDEN***"`).

## Development

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use source .venv/bin/activate elsewhere
pip install -e ".[test,dev]"    # client tests + lint locally
pip install -e ".[test-ha]"     # HA integration tests (CI / WSL / Linux / macOS)
```

- **Native Windows can run the client tests only.** The HA test harness pulls in
  Unix-only deps (uvloop, etc.); run `tests/` (excluding `test_api.py`) in CI or WSL.
- Lint/format: `ruff check . && ruff format .`
- Types: `mypy custom_components`

## Workflow conventions

- **TDD.** Write/extend the test first, watch it fail, then implement.
- Keep `api.py` free of any `homeassistant` import.
- Add a new device capability to the client first, then expose it as an entity.
- Update `tests/fixtures/status.json` only with a real device response.
