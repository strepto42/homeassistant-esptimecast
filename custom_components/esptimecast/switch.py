"""Switch platform for ESPTimeCast.

The firmware keeps two separate states: live runtime (changed by ``/set_*``,
reported by ``/status``) and the on-disk ``/config.json`` (only written by
``/save``). Switches therefore read their state from ``/status`` so toggles
"stick". Three toggles (day-of-week, colon blink, weather description) are not
reported by ``/status`` at all, so those are optimistic (assumed) switches.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DeviceData, ESPTimeCastClient, FullConfig
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastSwitchDescription(SwitchEntityDescription):
    """A switch whose live state is reported by /status."""

    value_fn: Callable[[DeviceData], bool]
    set_fn: Callable[[ESPTimeCastClient, bool], Awaitable[Any]]


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastOptimisticSwitchDescription(SwitchEntityDescription):
    """A toggle /status does not report, so its state is assumed.

    Seeded from the on-disk config at startup, then tracked optimistically.
    """

    seed_fn: Callable[[FullConfig], bool]
    set_fn: Callable[[ESPTimeCastClient, bool], Awaitable[Any]]


# Switches whose state is reported live by /status.
SWITCHES: tuple[ESPTimeCastSwitchDescription, ...] = (
    ESPTimeCastSwitchDescription(
        key="display",
        translation_key="display",
        # display_off is a firmware toggle; idempotent turn_on/off keeps it correct.
        value_fn=lambda d: not d.status.display_off,
        set_fn=lambda c, _on: c.set_display_off(True),
    ),
    ESPTimeCastSwitchDescription(
        key="flip",
        translation_key="flip",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.config.flip_display,
        set_fn=lambda c, on: c.set_flip(on),
    ),
    ESPTimeCastSwitchDescription(
        key="twelve_hour",
        translation_key="twelve_hour",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.config.twelve_hour,
        set_fn=lambda c, on: c.set_twelve_hour(on),
    ),
    ESPTimeCastSwitchDescription(
        key="show_date",
        translation_key="show_date",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.config.show_date,
        set_fn=lambda c, on: c.set_show_date(on),
    ),
    ESPTimeCastSwitchDescription(
        key="show_humidity",
        translation_key="show_humidity",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.config.show_humidity,
        set_fn=lambda c, on: c.set_humidity(on),
    ),
    ESPTimeCastSwitchDescription(
        key="countdown",
        translation_key="countdown",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.countdown.enabled,
        set_fn=lambda c, on: c.set_countdown_enabled(on),
    ),
    ESPTimeCastSwitchDescription(
        key="dramatic_countdown",
        translation_key="dramatic_countdown",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.countdown.is_dramatic,
        set_fn=lambda c, on: c.set_dramatic_countdown(on),
    ),
    ESPTimeCastSwitchDescription(
        key="clock_only_dimming",
        translation_key="clock_only_dimming",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.status.dimming.clock_only,
        set_fn=lambda c, on: c.set_clock_only_dimming(on),
    ),
    ESPTimeCastSwitchDescription(
        key="hide_donation",
        translation_key="hide_donation",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda d: bool(d.status.raw.get("hideDonationMsg", False)),
        set_fn=lambda c, on: c.set_hide_donation(on),
    ),
)

# Toggles /status does not report; tracked optimistically.
OPTIMISTIC_SWITCHES: tuple[ESPTimeCastOptimisticSwitchDescription, ...] = (
    ESPTimeCastOptimisticSwitchDescription(
        key="show_day_of_week",
        translation_key="show_day_of_week",
        entity_category=EntityCategory.CONFIG,
        seed_fn=lambda cfg: cfg.show_day_of_week,
        set_fn=lambda c, on: c.set_day_of_week(on),
    ),
    ESPTimeCastOptimisticSwitchDescription(
        key="colon_blink",
        translation_key="colon_blink",
        entity_category=EntityCategory.CONFIG,
        seed_fn=lambda cfg: cfg.colon_blink,
        set_fn=lambda c, on: c.set_colon_blink(on),
    ),
    ESPTimeCastOptimisticSwitchDescription(
        key="show_weather_description",
        translation_key="show_weather_description",
        entity_category=EntityCategory.CONFIG,
        seed_fn=lambda cfg: cfg.show_weather_description,
        set_fn=lambda c, on: c.set_weather_desc(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        ESPTimeCastSwitch(coordinator, description) for description in SWITCHES
    ]
    entities.extend(
        ESPTimeCastOptimisticSwitch(coordinator, description)
        for description in OPTIMISTIC_SWITCHES
    )
    async_add_entities(entities)


class ESPTimeCastSwitch(ESPTimeCastEntity, SwitchEntity):
    """A switch whose state is read live from /status."""

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


class ESPTimeCastOptimisticSwitch(ESPTimeCastEntity, SwitchEntity):
    """A toggle /status does not report; state is assumed after each command."""

    _attr_assumed_state = True
    entity_description: ESPTimeCastOptimisticSwitchDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastOptimisticSwitchDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        # Seed from the last-saved on-disk config.
        self._is_on = description.seed_fn(coordinator.data.config)

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator.client, True)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator.client, False)
        self._is_on = False
        self.async_write_ha_state()
