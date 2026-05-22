"""DataUpdateCoordinator for ESPTimeCast."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeviceData, ESPTimeCastClient, ESPTimeCastError, FullConfig
from .const import CONF_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type ESPTimeCastConfigEntry = ConfigEntry[ESPTimeCastCoordinator]


class ESPTimeCastCoordinator(DataUpdateCoordinator[DeviceData]):
    """Polls a device's live state (/status) and settings (/config.json)."""

    config_entry: ESPTimeCastConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ESPTimeCastConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = ESPTimeCastClient(
            config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> DeviceData:
        # /status is the live source of truth and is required.
        try:
            status = await self.client.get_status()
        except ESPTimeCastError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

        # /config.json only seeds the settings switches at startup and feeds the
        # Configure dialog. The device returns transient 500s for it (e.g. while
        # busy), so a failure here must never take the integration down: reuse
        # the last good config, or fall back to defaults on the very first poll.
        try:
            config = await self.client.get_config()
        except ESPTimeCastError as err:
            if self.data is not None:
                config = self.data.config
            else:
                _LOGGER.debug("Initial /config.json fetch failed: %s", err)
                config = FullConfig.from_dict({})

        return DeviceData(status=status, config=config)
