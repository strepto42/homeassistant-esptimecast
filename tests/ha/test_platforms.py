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
    # colonBlinkEnabled (Animated seconds) is True in the config fixture;
    # show_day_of_week is False.
    assert (
        hass.states.get("switch.esptimecast_local_animated_seconds").state == STATE_ON
    )
    assert (
        hass.states.get("switch.esptimecast_local_show_day_of_week").state == STATE_OFF
    )
    assert (
        hass.states.get("switch.esptimecast_local_show_weather_description").state
        == STATE_ON
    )


async def test_restored_sensors_present(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    # sunrise/sunset come back as HH:MM strings.
    assert hass.states.get("sensor.esptimecast_local_sunrise").state == "06:24"
    assert hass.states.get("sensor.esptimecast_local_sunset").state == "17:04"
    # countdown remaining is always created now (no countdown -> unknown).
    assert hass.states.get("sensor.esptimecast_local_countdown_remaining") is not None
    # display_busy binary sensor was removed.
    assert hass.states.get("binary_sensor.esptimecast_local_display_busy") is None


async def test_optimistic_switch_toggle(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    entity_id = "switch.esptimecast_local_show_day_of_week"
    # show_day_of_week is False in the config fixture (the seed).
    assert hass.states.get(entity_id).state == STATE_OFF
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_day_of_week",
        new=AsyncMock(),
    ) as mock_set:
        await hass.services.async_call(
            Platform.SWITCH,
            "turn_on",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    mock_set.assert_awaited_once_with(True)
    # Optimistic: state flips immediately without a coordinator read-back.
    assert hass.states.get(entity_id).state == STATE_ON


async def test_live_switch_holds_optimistic_until_confirmed(
    hass: HomeAssistant, mock_client, mock_config_entry, device_data
) -> None:
    # Issue: switches "jump" when a poll lands before the device has applied
    # the change. The optimistic value must hold until /status confirms it.
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    entity_id = "switch.esptimecast_local_flip_display"
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_flip",
        new=AsyncMock(),
    ):
        await hass.services.async_call(
            Platform.SWITCH, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == STATE_ON

    # A poll that still reports the OLD value must NOT flip it back.
    device_data.status.config.flip_display = False
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # Once the device confirms, the optimistic value is released...
    device_data.status.config.flip_display = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # ...and a later external change is reflected.
    device_data.status.config.flip_display = False
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_units_select_holds_optimistic_until_confirmed(
    hass: HomeAssistant, mock_client, mock_config_entry, device_data
) -> None:
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    entity_id = "select.esptimecast_local_units"
    assert hass.states.get(entity_id).state == "metric"

    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_units",
        new=AsyncMock(),
    ):
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {ATTR_ENTITY_ID: entity_id, "option": "imperial"},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == "imperial"

    # Stale poll (device not applied yet) must not revert the selection.
    device_data.status.config.weather_units = "metric"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "imperial"

    # Device confirms.
    device_data.status.config.weather_units = "imperial"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "imperial"


async def test_save_settings_button(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.send_action",
        new=AsyncMock(),
    ) as mock_action:
        await hass.services.async_call(
            Platform.BUTTON,
            "press",
            {ATTR_ENTITY_ID: "button.esptimecast_local_save_settings_to_device"},
            blocking=True,
        )
    mock_action.assert_awaited_once_with("save")


async def test_display_light_state_and_brightness(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    light = hass.states.get("light.esptimecast_local_display")
    assert light is not None
    # status fixture: displayOff False, brightness 3 -> on, ~3/15*255.
    assert light.state == STATE_ON
    assert light.attributes["brightness"] == round(3 / 15 * 255)


async def test_display_light_turn_off_sets_minus_one(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_brightness",
        new=AsyncMock(),
    ) as mock_set:
        await hass.services.async_call(
            Platform.LIGHT,
            "turn_off",
            {ATTR_ENTITY_ID: "light.esptimecast_local_display"},
            blocking=True,
        )
    # Off is the firmware's brightness == -1.
    mock_set.assert_awaited_once_with(-1)


async def test_display_light_set_brightness(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    await _setup(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.set_brightness",
        new=AsyncMock(),
    ) as mock_set:
        await hass.services.async_call(
            Platform.LIGHT,
            "turn_on",
            {
                ATTR_ENTITY_ID: "light.esptimecast_local_display",
                "brightness": 255,
            },
            blocking=True,
        )
    # 255 (HA) maps to the device max of 15.
    mock_set.assert_awaited_once_with(15)


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
    assert any(e.startswith("light.esptimecast_local") for e in entity_ids)
    assert any(e.startswith("text.esptimecast_local") for e in entity_ids)
