"""Switch platform for ESPTimeCast.

Only settings that are *both* readable from /status and writable via a typed
/set_* endpoint are exposed here, so switch state always reflects the device.
Toggles whose state /status does not report (day-of-week, colon blink, weather
description) are intentionally omitted from v1.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ESPTimeCastClient, Status
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastSwitchDescription(SwitchEntityDescription):
    """Describes an ESPTimeCast switch."""

    value_fn: Callable[[Status], bool]
    set_fn: Callable[[ESPTimeCastClient, bool], Awaitable[Any]]


SWITCHES: tuple[ESPTimeCastSwitchDescription, ...] = (
    ESPTimeCastSwitchDescription(
        key="display",
        translation_key="display",
        # display_off is a firmware toggle; idempotent turn_on/off keeps it correct.
        value_fn=lambda s: not s.display_off,
        set_fn=lambda c, _on: c.set_display_off(True),
    ),
    ESPTimeCastSwitchDescription(
        key="flip",
        translation_key="flip",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.config.flip_display,
        set_fn=lambda c, on: c.set_flip(on),
    ),
    ESPTimeCastSwitchDescription(
        key="twelve_hour",
        translation_key="twelve_hour",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.config.twelve_hour,
        set_fn=lambda c, on: c.set_twelve_hour(on),
    ),
    ESPTimeCastSwitchDescription(
        key="show_date",
        translation_key="show_date",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.config.show_date,
        set_fn=lambda c, on: c.set_show_date(on),
    ),
    ESPTimeCastSwitchDescription(
        key="show_humidity",
        translation_key="show_humidity",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.config.show_humidity,
        set_fn=lambda c, on: c.set_humidity(on),
    ),
    ESPTimeCastSwitchDescription(
        key="countdown",
        translation_key="countdown",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.raw.get("countdownEnabled", False),
        set_fn=lambda c, on: c.set_countdown_enabled(on),
    ),
    ESPTimeCastSwitchDescription(
        key="dramatic_countdown",
        translation_key="dramatic_countdown",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.countdown.is_dramatic,
        set_fn=lambda c, on: c.set_dramatic_countdown(on),
    ),
    ESPTimeCastSwitchDescription(
        key="clock_only_dimming",
        translation_key="clock_only_dimming",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.dimming.clock_only,
        set_fn=lambda c, on: c.set_clock_only_dimming(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        ESPTimeCastSwitch(coordinator, description) for description in SWITCHES
    )


class ESPTimeCastSwitch(ESPTimeCastEntity, SwitchEntity):
    """A controllable ESPTimeCast setting."""

    entity_description: ESPTimeCastSwitchDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastSwitchDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not self.is_on:
            await self.entity_description.set_fn(self.coordinator.client, True)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on:
            await self.entity_description.set_fn(self.coordinator.client, False)
            await self.coordinator.async_request_refresh()
