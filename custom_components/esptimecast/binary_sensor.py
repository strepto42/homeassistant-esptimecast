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

from .api import DeviceData
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an ESPTimeCast binary sensor."""

    value_fn: Callable[[DeviceData], bool]


BINARY_SENSORS: tuple[ESPTimeCastBinarySensorDescription, ...] = (
    ESPTimeCastBinarySensorDescription(
        key="time_synced",
        translation_key="time_synced",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status.time_synced,
    ),
    ESPTimeCastBinarySensorDescription(
        key="dimming_active",
        translation_key="dimming_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status.dimming.enabled,
    ),
)

# Created only when Nightscout is active.
GLUCOSE_OUTDATED = ESPTimeCastBinarySensorDescription(
    key="glucose_outdated",
    translation_key="glucose_outdated",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda d: d.status.nightscout.is_outdated,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast binary sensors."""
    coordinator = entry.runtime_data
    descriptions = list(BINARY_SENSORS)
    if coordinator.data.status.nightscout.active:
        descriptions.append(GLUCOSE_OUTDATED)
    async_add_entities(
        ESPTimeCastBinarySensor(coordinator, description)
        for description in descriptions
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
