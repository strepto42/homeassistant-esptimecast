"""Text platform for ESPTimeCast (the persistent Custom Message)."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ESPTimeCast custom message text entity."""
    async_add_entities([ESPTimeCastMessage(entry.runtime_data)])


class ESPTimeCastMessage(ESPTimeCastEntity, TextEntity):
    """The scrolling Custom Message, mirroring the web UI's message box.

    Setting a value scrolls it on the display indefinitely; clearing it (empty
    string) removes the message.
    """

    _attr_translation_key = "custom_message"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 255

    def __init__(self, coordinator: ESPTimeCastCoordinator) -> None:
        super().__init__(coordinator, "custom_message")

    @property
    def native_value(self) -> str:
        # The firmware reports the message currently on the display.
        return self.coordinator.data.status.message

    async def async_set_value(self, value: str) -> None:
        await self.coordinator.client.display_message(value)
        await self.coordinator.async_request_refresh()
