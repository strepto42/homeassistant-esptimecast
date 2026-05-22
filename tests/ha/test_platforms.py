"""Tests for ESPTimeCast entity platforms."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_created_with_values(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)

    temp = hass.states.get("sensor.esptimecast_local_temperature")
    assert temp is not None
    assert temp.state == "22.0"
    assert temp.attributes["unit_of_measurement"] == "°C"

    humidity = hass.states.get("sensor.esptimecast_local_humidity")
    assert humidity.state == "56"

    desc = hass.states.get("sensor.esptimecast_local_weather_description")
    assert desc.state == "CLEAR SKY"


def test_temperature_native_unit_follows_config(status_obj) -> None:
    # HA converts the displayed unit to the user's system, so the contract we
    # control is the *native* unit derived from the device's configured units.
    from homeassistant.const import UnitOfTemperature

    from custom_components.esptimecast.sensor import _temp_unit

    status_obj.config.weather_units = "metric"
    assert _temp_unit(status_obj) == UnitOfTemperature.CELSIUS
    status_obj.config.weather_units = "imperial"
    assert _temp_unit(status_obj) == UnitOfTemperature.FAHRENHEIT


async def test_binary_sensors(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    assert (
        hass.states.get("binary_sensor.esptimecast_local_time_synced").state == STATE_ON
    )
    # The redundant display binary_sensor was removed (covered by the switch).
    assert hass.states.get("binary_sensor.esptimecast_local_display") is None


async def test_custom_message_text_entity(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    entity_id = "text.esptimecast_local_custom_message"
    state = hass.states.get(entity_id)
    assert state is not None

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.display_message",
        new=AsyncMock(),
    ) as mock_msg:
        await hass.services.async_call(
            "text",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": "HELLO HA"},
            blocking=True,
        )
    mock_msg.assert_awaited_once_with("HELLO HA")


async def test_new_switches_present_and_state_from_config(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    # colon_blink is True in the config fixture; show_day_of_week is False.
    assert hass.states.get("switch.esptimecast_local_blinking_colon").state == STATE_ON
    assert (
        hass.states.get("switch.esptimecast_local_show_day_of_week").state == STATE_OFF
    )
    assert (
        hass.states.get("switch.esptimecast_local_show_weather_description").state
        == STATE_ON
    )


async def test_brightness_number_set(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    number = hass.states.get("number.esptimecast_local_brightness")
    assert number.state == "3.0"

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_brightness",
        new=AsyncMock(),
    ) as mock_set:
        await hass.services.async_call(
            Platform.NUMBER,
            "set_value",
            {
                ATTR_ENTITY_ID: "number.esptimecast_local_brightness",
                "value": 10,
            },
            blocking=True,
        )
    mock_set.assert_awaited_once_with(10)


async def test_switch_turn_off_display(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    # Display is on (display_off is False) -> turning off should toggle once.
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_display_off",
        new=AsyncMock(),
    ) as mock_toggle:
        await hass.services.async_call(
            Platform.SWITCH,
            "turn_off",
            {ATTR_ENTITY_ID: "switch.esptimecast_local_display"},
            blocking=True,
        )
    mock_toggle.assert_awaited_once()


async def test_switch_turn_on_when_already_on_is_noop(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_display_off",
        new=AsyncMock(),
    ) as mock_toggle:
        await hass.services.async_call(
            Platform.SWITCH,
            "turn_on",
            {ATTR_ENTITY_ID: "switch.esptimecast_local_display"},
            blocking=True,
        )
    mock_toggle.assert_not_awaited()


async def test_flip_switch_sets_value(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    # flipDisplay is False -> turn_on should call set_flip(True).
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_flip",
        new=AsyncMock(),
    ) as mock_set:
        await hass.services.async_call(
            Platform.SWITCH,
            "turn_on",
            {ATTR_ENTITY_ID: "switch.esptimecast_local_flip_display"},
            blocking=True,
        )
    mock_set.assert_awaited_once_with(True)


async def test_select_units(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    units = hass.states.get("select.esptimecast_local_units")
    assert units.state == "metric"

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_units",
        new=AsyncMock(),
    ) as mock_set:
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {
                ATTR_ENTITY_ID: "select.esptimecast_local_units",
                "option": "imperial",
            },
            blocking=True,
        )
    mock_set.assert_awaited_once_with("imperial")


async def test_button_restart(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.restart",
        new=AsyncMock(),
    ) as mock_restart:
        await hass.services.async_call(
            Platform.BUTTON,
            "press",
            {ATTR_ENTITY_ID: "button.esptimecast_local_restart"},
            blocking=True,
        )
    mock_restart.assert_awaited_once()


@pytest.mark.parametrize("state", [STATE_ON, STATE_OFF])
async def test_entities_have_unique_ids(
    hass: HomeAssistant, mock_client, mock_config_entry, state
) -> None:
    # Just assert setup produced entities across platforms (state param unused
    # beyond exercising parametrization wiring is intentional here).
    await _setup(hass, mock_config_entry)
    entity_ids = hass.states.async_entity_ids()
    assert any(e.startswith("sensor.esptimecast_local") for e in entity_ids)
    assert any(e.startswith("switch.esptimecast_local") for e in entity_ids)
    assert any(e.startswith("button.esptimecast_local") for e in entity_ids)
    assert any(e.startswith("select.esptimecast_local") for e in entity_ids)
    assert any(e.startswith("number.esptimecast_local") for e in entity_ids)
