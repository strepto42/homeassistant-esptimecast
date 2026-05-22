"""Tests for setup/unload of the ESPTimeCast integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esptimecast.api import ESPTimeCastConnectionError


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.get_device_data",
        new=AsyncMock(side_effect=ESPTimeCastConnectionError("down")),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_registered(
    hass: HomeAssistant, mock_client, mock_config_entry: MockConfigEntry
) -> None:
    from homeassistant.helpers import device_registry as dr

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    device = registry.async_get_device(
        identifiers={("esptimecast", "esptimecast.local")}
    )
    assert device is not None
    assert device.sw_version == "1.6.0"
    assert device.manufacturer == "mfactory-osaka"
