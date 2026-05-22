"""Number platform for ESPTimeCast."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast numbers."""
    async_add_entities([ESPTimeCastBrightness(entry.runtime_data)])


class ESPTimeCastBrightness(ESPTimeCastEntity, NumberEntity):
    """Display brightness (0-15; -1 means auto)."""

    _attr_translation_key = "brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 15
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: ESPTimeCastCoordinator) -> None:
        super().__init__(coordinator, "brightness")

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.status.brightness
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_brightness(int(value))
        await self.coordinator.async_request_refresh()
