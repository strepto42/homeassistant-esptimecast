"""Select platform for ESPTimeCast."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DeviceData, ESPTimeCastClient
from .const import LANGUAGES, UNITS
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastSelectDescription(SelectEntityDescription):
    """Describes an ESPTimeCast select."""

    current_fn: Callable[[DeviceData], str | None]
    select_fn: Callable[[ESPTimeCastClient, str], Awaitable[Any]]


SELECTS: tuple[ESPTimeCastSelectDescription, ...] = (
    ESPTimeCastSelectDescription(
        key="language",
        translation_key="language",
        entity_category=EntityCategory.CONFIG,
        options=list(LANGUAGES),
        current_fn=lambda d: d.config.language,
        select_fn=lambda c, option: c.set_language(option),
    ),
    ESPTimeCastSelectDescription(
        key="units",
        translation_key="units",
        entity_category=EntityCategory.CONFIG,
        options=list(UNITS),
        current_fn=lambda d: d.config.weather_units,
        select_fn=lambda c, option: c.set_units(option),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast selects."""
    coordinator = entry.runtime_data
    async_add_entities(
        ESPTimeCastSelect(coordinator, description) for description in SELECTS
    )


class ESPTimeCastSelect(ESPTimeCastEntity, SelectEntity):
    """A controllable ESPTimeCast multi-choice setting (optimistic on change)."""

    entity_description: ESPTimeCastSelectDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastSelectDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._optimistic: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        # Release the optimistic value only once the device confirms it, so a
        # poll landing before the change applies doesn't revert the selection.
        if (
            self._optimistic is not None
            and self.entity_description.current_fn(self.coordinator.data)
            == self._optimistic
        ):
            self._optimistic = None
        super()._handle_coordinator_update()

    @property
    def current_option(self) -> str | None:
        if self._optimistic is not None:
            return self._optimistic
        return self.entity_description.current_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.select_fn(self.coordinator.client, option)
        self._optimistic = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
