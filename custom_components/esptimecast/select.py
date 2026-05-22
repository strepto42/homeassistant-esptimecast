"""Select platform for ESPTimeCast."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ESPTimeCastClient, Status
from .const import DISPLAY_MODES, LANGUAGES, UNITS
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastSelectDescription(SelectEntityDescription):
    """Describes an ESPTimeCast select."""

    current_fn: Callable[[Status], str | None]
    select_fn: Callable[[ESPTimeCastClient, str], Awaitable[Any]]


SELECTS: tuple[ESPTimeCastSelectDescription, ...] = (
    ESPTimeCastSelectDescription(
        key="display_mode",
        translation_key="display_mode",
        options=list(DISPLAY_MODES),
        current_fn=lambda s: s.mode if s.mode in DISPLAY_MODES else None,
        select_fn=lambda c, option: c.go_to_mode(option),
    ),
    ESPTimeCastSelectDescription(
        key="language",
        translation_key="language",
        entity_category=EntityCategory.CONFIG,
        options=list(LANGUAGES),
        current_fn=lambda s: s.config.language,
        select_fn=lambda c, option: c.set_language(option),
    ),
    ESPTimeCastSelectDescription(
        key="units",
        translation_key="units",
        entity_category=EntityCategory.CONFIG,
        options=list(UNITS),
        current_fn=lambda s: s.config.weather_units,
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
    """A controllable ESPTimeCast multi-choice setting."""

    entity_description: ESPTimeCastSelectDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastSelectDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        return self.entity_description.current_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.select_fn(self.coordinator.client, option)
        await self.coordinator.async_request_refresh()
