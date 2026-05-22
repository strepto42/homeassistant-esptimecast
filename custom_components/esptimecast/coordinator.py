"""DataUpdateCoordinator for ESPTimeCast."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ESPTimeCastClient, ESPTimeCastError, Status
from .const import CONF_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type ESPTimeCastConfigEntry = ConfigEntry[ESPTimeCastCoordinator]


class ESPTimeCastCoordinator(DataUpdateCoordinator[Status]):
    """Polls a single ESPTimeCast device's /status endpoint."""

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

    async def _async_update_data(self) -> Status:
        try:
            return await self.client.get_status()
        except ESPTimeCastError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
