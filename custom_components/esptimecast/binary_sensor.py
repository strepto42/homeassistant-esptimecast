"""Binary sensor platform for ESPTimeCast."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Status
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an ESPTimeCast binary sensor."""

    value_fn: Callable[[Status], bool]


BINARY_SENSORS: tuple[ESPTimeCastBinarySensorDescription, ...] = (
    ESPTimeCastBinarySensorDescription(
        key="display_on",
        translation_key="display_on",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda s: not s.display_off,
    ),
    ESPTimeCastBinarySensorDescription(
        key="time_synced",
        translation_key="time_synced",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.time_synced,
    ),
    ESPTimeCastBinarySensorDescription(
        key="display_busy",
        translation_key="display_busy",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.display_busy,
    ),
    ESPTimeCastBinarySensorDescription(
        key="dimming_active",
        translation_key="dimming_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.dimming.enabled,
    ),
    ESPTimeCastBinarySensorDescription(
        key="glucose_outdated",
        translation_key="glucose_outdated",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.nightscout.active and s.nightscout.is_outdated,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ESPTimeCastBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class ESPTimeCastBinarySensor(ESPTimeCastEntity, BinarySensorEntity):
    """A read-only ESPTimeCast binary sensor."""

    entity_description: ESPTimeCastBinarySensorDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
