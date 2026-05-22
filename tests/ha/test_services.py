"""Tests for ESPTimeCast services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.esptimecast.const import DOMAIN


async def _setup_and_get_device_id(hass: HomeAssistant, entry) -> str:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, "esptimecast.local")})
    assert device is not None
    return device.id


async def test_send_message_service(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    device_id = await _setup_and_get_device_id(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.send_message",
        new=AsyncMock(),
    ) as mock_send:
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {
                "device_id": device_id,
                "message": "HELLO",
                "speed": 80,
                "seconds": 15,
                "interrupt": True,
            },
            blocking=True,
        )
    mock_send.assert_awaited_once_with(
        "HELLO",
        speed=80,
        scrolls=None,
        seconds=15,
        big_numbers=None,
        interrupt=True,
    )


async def test_start_timer_service(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    device_id = await _setup_and_get_device_id(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.start_timer",
        new=AsyncMock(),
    ) as mock_timer:
        await hass.services.async_call(
            DOMAIN,
            "start_timer",
            {"device_id": device_id, "duration": "5M"},
            blocking=True,
        )
    mock_timer.assert_awaited_once_with("5M")


async def test_go_to_mode_service(
    hass: HomeAssistant, mock_client, mock_config_entry
) -> None:
    device_id = await _setup_and_get_device_id(hass, mock_config_entry)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.go_to_mode",
        new=AsyncMock(),
    ) as mock_mode:
        await hass.services.async_call(
            DOMAIN,
            "go_to_mode",
            {"device_id": device_id, "mode": "clock"},
            blocking=True,
        )
    mock_mode.assert_awaited_once_with("clock")
