"""Button platform for ESPTimeCast."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ESPTimeCastClient
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastButtonDescription(ButtonEntityDescription):
    """Describes an ESPTimeCast button."""

    press_fn: Callable[[ESPTimeCastClient], Awaitable[Any]]
    # Refresh the coordinator after the press so HA state updates immediately.
    refresh: bool = False


BUTTONS: tuple[ESPTimeCastButtonDescription, ...] = (
    ESPTimeCastButtonDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.restart(),
    ),
    ESPTimeCastButtonDescription(
        key="next_mode",
        translation_key="next_mode",
        press_fn=lambda c: c.next_mode(),
        refresh=True,
    ),
    ESPTimeCastButtonDescription(
        key="previous_mode",
        translation_key="previous_mode",
        press_fn=lambda c: c.previous_mode(),
        refresh=True,
    ),
    ESPTimeCastButtonDescription(
        key="clear_message",
        translation_key="clear_message",
        press_fn=lambda c: c.clear_message(),
        refresh=True,
    ),
    ESPTimeCastButtonDescription(
        key="save_settings",
        translation_key="save_settings",
        entity_category=EntityCategory.CONFIG,
        # Persists the current live runtime (brightness, toggles, ...) to the
        # device's flash so it survives a reboot. No reboot, no /save form.
        press_fn=lambda c: c.send_action("save"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        ESPTimeCastButton(coordinator, description) for description in BUTTONS
    )


class ESPTimeCastButton(ESPTimeCastEntity, ButtonEntity):
    """An ESPTimeCast action button."""

    entity_description: ESPTimeCastButtonDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator.client)
        if self.entity_description.refresh:
            await self.coordinator.async_request_refresh()
