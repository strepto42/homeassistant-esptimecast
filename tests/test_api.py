"""Unit tests for the self-contained ESPTimeCast API client.

These run without Home Assistant installed (any OS). The client module is loaded
by file path via the ``api_module`` fixture in conftest.py.
"""

from __future__ import annotations

from datetime import time

import aiohttp
import pytest
from aioresponses import aioresponses


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


@pytest.fixture
def client(api_module, session):
    return api_module.ESPTimeCastClient("esptimecast.local", session=session)


# --- URL construction -------------------------------------------------------


def test_base_url_default_port(api_module, session):
    client = api_module.ESPTimeCastClient("1.2.3.4", session=session)
    assert client.base_url == "http://1.2.3.4"


def test_base_url_custom_port(api_module, session):
    client = api_module.ESPTimeCastClient("1.2.3.4", session=session, port=8080)
    assert client.base_url == "http://1.2.3.4:8080"


def test_host_with_scheme_is_normalised(api_module, session):
    client = api_module.ESPTimeCastClient("http://host.local/", session=session)
    assert client.base_url == "http://host.local"


# --- get_status parsing -----------------------------------------------------


async def test_get_status_top_level_fields(client, status_payload):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        status = await client.get_status()

    assert status.id == "esptimecast"
    assert status.version == "1.6.0"
    assert status.board == "ESP32"
    assert status.mode == "weather"
    assert status.display_mode == 1
    assert status.brightness == 3
    assert status.wifi_signal == -38
    assert status.display_off is False
    assert status.display_busy is False
    assert status.time_synced is True
    assert status.local_time == "11:03:36"
    assert status.session_runtime == 50166


async def test_get_status_weather_parsing(client, status_payload):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        status = await client.get_status()

    w = status.weather
    assert w.temperature == 22
    assert w.humidity == 56
    # The form-feed icon glyph must be stripped from the description.
    assert w.description == "CLEAR SKY"
    assert "\f" not in (w.description or "")
    assert w.sunrise == time(6, 24)
    assert w.sunset == time(17, 4)


async def test_get_status_weather_nulls_become_none(client, status_payload):
    status_payload["weather"]["currentTemperature"] = None
    status_payload["weather"]["currentHumidity"] = None
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        status = await client.get_status()

    assert status.weather.temperature is None
    assert status.weather.humidity is None


async def test_get_status_nightscout_inactive(client, status_payload):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        status = await client.get_status()

    ns = status.nightscout
    assert ns.active is False
    assert ns.glucose is None
    assert ns.is_outdated is True


async def test_get_status_config_parsing(client, status_payload):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        status = await client.get_status()

    cfg = status.config
    assert cfg.weather_units == "metric"
    assert cfg.time_zone == "Australia/Brisbane"
    assert cfg.twelve_hour is True
    assert cfg.show_humidity is True
    assert cfg.flip_display is False
    # The masked key should be reported as "configured" without leaking it.
    assert cfg.has_api_key is True


async def test_get_status_keeps_raw(client, status_payload):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        status = await client.get_status()
    assert status.raw["nextDonationTime"] == "N/A"


async def test_get_status_tolerates_raw_control_chars(client):
    # The firmware embeds a raw form-feed byte (0x0c) as an icon glyph inside
    # JSON strings. That is invalid per the JSON spec and rejected by strict
    # parsers (e.g. orjson, or stdlib json with the default strict=True). The
    # client must parse leniently so polling does not crash.
    # Use 0x10 here (not 0x0c) because the icon byte varies per weather icon;
    # the client must strip any control character, not just form-feed.
    raw_body = (
        '{"id":"esptimecast","mode":"weather_desc","brightness":3,'
        '"weather":{"weatherDescription":"\x10 LIGHT RAIN","icon":"\x10",'
        '"currentTemperature":23}}'
    )
    with aioresponses() as m:
        m.get(
            "http://esptimecast.local/status",
            body=raw_body,
            content_type="application/json",
        )
        status = await client.get_status()
    assert status.mode == "weather_desc"
    assert status.weather.temperature == 23
    assert status.weather.description == "LIGHT RAIN"
    assert status.weather.icon is None  # control-only glyph reduces to nothing


async def test_get_status_tolerates_invalid_utf8(client):
    # The firmware can emit raw non-UTF-8 bytes (e.g. 0xa8) as icon/symbol
    # glyphs inside the JSON. resp.text() would raise UnicodeDecodeError, so the
    # client must decode the raw bytes leniently and still parse.
    raw_bytes = (
        b'{"id":"esptimecast","mode":"weather","brightness":3,'
        b'"weather":{"weatherDescription":"\xa8 CLEAR SKY","icon":"\xa8",'
        b'"currentTemperature":22}}'
    )
    with aioresponses() as m:
        m.get(
            "http://esptimecast.local/status",
            body=raw_bytes,
            content_type="application/json",
        )
        status = await client.get_status()
    assert status.mode == "weather"
    assert status.weather.temperature == 22
    assert status.weather.description == "CLEAR SKY"
    assert status.weather.icon is None


# --- get_config (full /config.json) -----------------------------------------


async def test_get_config_parsing(client, config_payload):
    with aioresponses() as m:
        m.get("http://esptimecast.local/config.json", payload=config_payload)
        cfg = await client.get_config()

    # Settings the /status block did not expose.
    assert cfg.show_day_of_week is False
    assert cfg.colon_blink is True
    assert cfg.show_weather_description is True
    assert cfg.custom_message == ""
    assert cfg.hostname == "esptimecast"
    assert cfg.clock_duration == 10000
    assert cfg.weather_duration == 5000
    # String booleans must be coerced.
    assert cfg.auto_dimming is True
    assert cfg.countdown.enabled is False
    assert cfg.countdown.is_dramatic is True
    # dimming schedule
    assert cfg.dim_start == time(18, 0)
    assert cfg.dim_end == time(8, 0)
    assert cfg.hide_donation_msg is True
    # secrets reported as configured, never leaked
    assert cfg.has_api_key is True


async def test_get_device_data_combines_status_and_config(
    client, status_payload, config_payload
):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", payload=status_payload)
        m.get("http://esptimecast.local/config.json", payload=config_payload)
        data = await client.get_device_data()

    assert data.status.mode == "weather"
    assert data.config.hostname == "esptimecast"


# --- get_version ------------------------------------------------------------


async def test_get_version(client):
    with aioresponses() as m:
        m.get(
            "http://esptimecast.local/get_version",
            payload={"version": "1.6.0", "board": "esp32"},
        )
        info = await client.get_version()
    assert info == {"version": "1.6.0", "board": "esp32"}


# --- commands ---------------------------------------------------------------


async def test_send_action_posts_form(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/action", status=200, body="OK")
        await client.send_action("next_mode")
        m.assert_called_once()
        req = m.requests[("POST", _url("http://esptimecast.local/action"))][0]
        assert req.kwargs["data"] == {"next_mode": ""}


async def test_send_action_with_value(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/action", status=200, body="OK")
        await client.send_action("go_to_mode", "clock")
        req = m.requests[("POST", _url("http://esptimecast.local/action"))][0]
        assert req.kwargs["data"] == {"go_to_mode": "clock"}


async def test_restart_sends_restart_action(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/action", status=200, body="OK")
        await client.restart()
        req = m.requests[("POST", _url("http://esptimecast.local/action"))][0]
        assert req.kwargs["data"] == {"restart": ""}


async def test_save_config_posts_form(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/save", status=200, body="OK")
        await client.save_config(
            {
                "clockDuration": 12000,
                "dimmingEnabled": True,
                "countdownEnabled": False,
                "hostname": "lobby",
                "openWeatherApiKey": None,  # unchanged -> omitted
            }
        )
        req = m.requests[("POST", _url("http://esptimecast.local/save"))][0]
        data = req.kwargs["data"]
        assert data["clockDuration"] == 12000
        # Booleans must be sent as the firmware's "true"/"false" strings.
        assert data["dimmingEnabled"] == "true"
        assert data["countdownEnabled"] == "false"
        assert data["hostname"] == "lobby"
        # None values are dropped (e.g. a masked secret left unchanged).
        assert "openWeatherApiKey" not in data


async def test_send_message_posts_all_params(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/set_custom_message", status=200, body="OK")
        await client.send_message(
            "HELLO",
            speed=80,
            scrolls=3,
            seconds=15,
            big_numbers=True,
            interrupt=False,
        )
        req = m.requests[("POST", _url("http://esptimecast.local/set_custom_message"))][
            0
        ]
        data = req.kwargs["data"]
        assert data["message"] == "HELLO"
        assert data["speed"] == 80
        assert data["scrolltimes"] == 3
        assert data["seconds"] == 15
        assert data["bignumbers"] == 1
        assert data["allowInterrupt"] == 0


async def test_send_message_omits_unset_params(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/set_custom_message", status=200, body="OK")
        await client.send_message("HI")
        req = m.requests[("POST", _url("http://esptimecast.local/set_custom_message"))][
            0
        ]
        assert req.kwargs["data"] == {"message": "HI"}


async def test_set_brightness_posts_value(client):
    with aioresponses() as m:
        m.post(
            "http://esptimecast.local/set_brightness", status=200, body='{"ok":true}'
        )
        await client.set_brightness(7)
        req = m.requests[("POST", _url("http://esptimecast.local/set_brightness"))][0]
        assert req.kwargs["data"] == {"value": 7}


async def test_set_flip_bool_becomes_int(client):
    with aioresponses() as m:
        m.post("http://esptimecast.local/set_flip", status=200, body='{"ok":true}')
        await client.set_flip(True)
        req = m.requests[("POST", _url("http://esptimecast.local/set_flip"))][0]
        assert req.kwargs["data"] == {"value": 1}


# --- error handling ---------------------------------------------------------


async def test_busy_409_raises_busy_error(client, api_module):
    with aioresponses() as m:
        m.post("http://esptimecast.local/set_custom_message", status=409, body="busy")
        with pytest.raises(api_module.ESPTimeCastBusyError):
            await client.send_message("HELLO")


async def test_server_error_raises_generic_error(client, api_module):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", status=500, body="boom")
        with pytest.raises(api_module.ESPTimeCastError):
            await client.get_status()


async def test_connection_error_raises_connection_error(client, api_module):
    with aioresponses() as m:
        m.get(
            "http://esptimecast.local/status",
            exception=aiohttp.ClientConnectionError("nope"),
        )
        with pytest.raises(api_module.ESPTimeCastConnectionError):
            await client.get_status()


async def test_timeout_raises_timeout_error(client, api_module):
    with aioresponses() as m:
        m.get("http://esptimecast.local/status", exception=TimeoutError())
        with pytest.raises(api_module.ESPTimeCastTimeoutError):
            await client.get_status()


def _url(raw: str):
    """aioresponses keys its request registry by yarl.URL."""
    from yarl import URL

    return URL(raw)
