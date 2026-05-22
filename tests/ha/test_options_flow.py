"""Tests for the ESPTimeCast options (Configure) flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_options_flow_shows_form(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_saves_mapped_payload(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.save_config",
        new=AsyncMock(),
    ) as mock_save:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "time_zone": "Australia/Brisbane",
                "clock_duration": 12,
                "weather_duration": 6,
                "ntp_server1": "pool.ntp.org",
                "ntp_server2": "time.nist.gov",
                "hostname": "lobby",
                "openweather_api_key": "",
                "latitude": "-27.4808",
                "longitude": "153.0398",
                "dimming_enabled": True,
                "dim_start": "18:30:00",
                "dim_end": "07:15:00",
                "dim_brightness": 2,
                "auto_dimming": True,
                "countdown_enabled": True,
                "countdown_date": "2026-12-25",
                "countdown_time": "09:00:00",
                "countdown_label": "XMAS",
                "dramatic_countdown": False,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_save.assert_awaited_once()
    payload = mock_save.call_args[0][0]
    # seconds -> milliseconds
    assert payload["clockDuration"] == 12000
    assert payload["weatherDuration"] == 6000
    # times -> hour/minute pairs
    assert payload["dimStartHour"] == 18
    assert payload["dimStartMinute"] == 30
    assert payload["dimEndHour"] == 7
    assert payload["dimEndMinute"] == 15
    # countdown fields are always present (firmware rebuilds the object)
    assert payload["countdownEnabled"] is True
    assert payload["countdownDate"] == "2026-12-25"
    assert payload["countdownTime"] == "09:00"
    assert payload["countdownLabel"] == "XMAS"
    assert payload["hostname"] == "lobby"
    # blank API key is omitted so the stored key is left unchanged
    assert payload["openWeatherApiKey"] is None


async def test_options_flow_save_failure_shows_error(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    from custom_components.esptimecast.api import ESPTimeCastConnectionError

    await _setup(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.save_config",
        new=AsyncMock(side_effect=ESPTimeCastConnectionError("down")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "time_zone": "UTC",
                "clock_duration": 10,
                "weather_duration": 5,
                "dim_start": "18:00:00",
                "dim_end": "08:00:00",
                "dim_brightness": 0,
                "dimming_enabled": False,
                "auto_dimming": True,
                "countdown_enabled": False,
                "countdown_date": "2026-01-01",
                "countdown_time": "00:00:00",
                "dramatic_countdown": True,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "save_failed"}
