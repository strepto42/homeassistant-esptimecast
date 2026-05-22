"""Notify platform for ESPTimeCast.

Sends a scrolling message to the display. For fine control (speed, scrolls,
auto-clear, big numbers, interrupt) use the ``esptimecast.send_message`` service.
"""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ESPTimeCast notify entity."""
    async_add_entities([ESPTimeCastNotify(entry.runtime_data)])


class ESPTimeCastNotify(ESPTimeCastEntity, NotifyEntity):
    """Push a scrolling message to the display."""

    _attr_translation_key = "message"

    def __init__(self, coordinator: ESPTimeCastCoordinator) -> None:
        super().__init__(coordinator, "notify")

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self.coordinator.client.send_message(message)
