"""Switch platform for ESPTimeCast.

The firmware keeps two states: live runtime (changed by ``/set_*``, reported by
``/status``) and the on-disk ``/config.json`` (only written by ``/save``).

- Switches whose state ``/status`` reports read it live, with an optimistic
  override so the UI doesn't flip-flop while the confirming poll lands.
- Three toggles ``/status`` never reports (show day-of-week, animated seconds,
  show weather description) keep their state internally, seeded from the
  on-disk config at startup.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
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
class ESPTimeCastStoredSwitchDescription(SwitchEntityDescription):
    """A toggle /status does not report; state is held locally."""

    seed_fn: Callable[[FullConfig], bool]
    set_fn: Callable[[ESPTimeCastClient, bool], Awaitable[Any]]


# Switches whose state is reported live by /status.
SWITCHES: tuple[ESPTimeCastSwitchDescription, ...] = (
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
        value_fn=lambda d: bool(d.status.raw.get("hideDonationMsg", False)),
        set_fn=lambda c, on: c.set_hide_donation(on),
    ),
)

# Toggles /status does not report; state held locally.
STORED_SWITCHES: tuple[ESPTimeCastStoredSwitchDescription, ...] = (
    ESPTimeCastStoredSwitchDescription(
        key="show_day_of_week",
        translation_key="show_day_of_week",
        entity_category=EntityCategory.CONFIG,
        seed_fn=lambda cfg: cfg.show_day_of_week,
        set_fn=lambda c, on: c.set_day_of_week(on),
    ),
    ESPTimeCastStoredSwitchDescription(
        key="animated_seconds",
        translation_key="animated_seconds",
        entity_category=EntityCategory.CONFIG,
        seed_fn=lambda cfg: cfg.colon_blink,
        set_fn=lambda c, on: c.set_colon_blink(on),
    ),
    ESPTimeCastStoredSwitchDescription(
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
        ESPTimeCastStoredSwitch(coordinator, description)
        for description in STORED_SWITCHES
    )
    async_add_entities(entities)


class _OptimisticSwitch(ESPTimeCastEntity, SwitchEntity):
    """Base switch that holds an optimistic value until the device confirms it.

    This avoids the "jump" where a poll that lands before the device has applied
    a change briefly reverts the switch. The optimistic value is only released
    once the polled state matches it; later external changes are then reflected.
    """

    def __init__(self, coordinator: ESPTimeCastCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._optimistic: bool | None = None

    def _device_state(self) -> bool:
        raise NotImplementedError

    async def _device_set(self, on: bool) -> None:
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._optimistic is not None and self._device_state() == self._optimistic:
            self._optimistic = None
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        if self._optimistic is not None:
            return self._optimistic
        return self._device_state()

    async def _async_set(self, on: bool) -> None:
        await self._device_set(on)
        # /set_* applies to RAM only; persist so the toggle survives a power
        # cycle (and the saved config catches up, which is the only readback
        # source for the toggles /status does not report).
        await self.coordinator.client.persist()
        self._optimistic = on
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class ESPTimeCastSwitch(_OptimisticSwitch):
    """A switch whose state is read live from /status."""

    entity_description: ESPTimeCastSwitchDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastSwitchDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _device_state(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)

    async def _device_set(self, on: bool) -> None:
        await self.entity_description.set_fn(self.coordinator.client, on)


class ESPTimeCastStoredSwitch(_OptimisticSwitch):
    """A toggle /status does not report; state comes from the saved config.

    /status never reports these, so the state reflects the last-saved
    /config.json value (what the web UI's settings form shows), with an
    optimistic override after a toggle that holds until the saved config agrees.
    """

    entity_description: ESPTimeCastStoredSwitchDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastStoredSwitchDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _device_state(self) -> bool:
        return self.entity_description.seed_fn(self.coordinator.data.config)

    async def _device_set(self, on: bool) -> None:
        await self.entity_description.set_fn(self.coordinator.client, on)
