"""Sensor platform for ESPTimeCast."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import Status
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


def _temp_unit(status: Status) -> str:
    if status.config.weather_units == "imperial":
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


def _fmt_time(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastSensorDescription(SensorEntityDescription):
    """Describes an ESPTimeCast sensor."""

    value_fn: Callable[[Status], StateType]
    unit_fn: Callable[[Status], str | None] | None = None


SENSORS: tuple[ESPTimeCastSensorDescription, ...] = (
    ESPTimeCastSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=_temp_unit,
        value_fn=lambda s: s.weather.temperature,
    ),
    ESPTimeCastSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.weather.humidity,
    ),
    ESPTimeCastSensorDescription(
        key="weather_description",
        translation_key="weather_description",
        value_fn=lambda s: s.weather.description,
    ),
    ESPTimeCastSensorDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.wifi_signal,
    ),
    ESPTimeCastSensorDescription(
        key="session_runtime",
        translation_key="session_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.session_runtime,
    ),
    ESPTimeCastSensorDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda s: s.mode,
    ),
    ESPTimeCastSensorDescription(
        key="message",
        translation_key="message",
        value_fn=lambda s: s.message or None,
    ),
    ESPTimeCastSensorDescription(
        key="sunrise",
        translation_key="sunrise",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: _fmt_time(s.weather.sunrise),
    ),
    ESPTimeCastSensorDescription(
        key="sunset",
        translation_key="sunset",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: _fmt_time(s.weather.sunset),
    ),
    ESPTimeCastSensorDescription(
        key="countdown_remaining",
        translation_key="countdown_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda s: s.countdown.remaining if s.countdown.enabled else None,
    ),
    ESPTimeCastSensorDescription(
        key="glucose",
        translation_key="glucose",
        native_unit_of_measurement="mg/dL",
        value_fn=lambda s: s.nightscout.glucose if s.nightscout.active else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ESPTimeCastSensor(coordinator, description) for description in SENSORS
    )


class ESPTimeCastSensor(ESPTimeCastEntity, SensorEntity):
    """A read-only ESPTimeCast sensor."""

    entity_description: ESPTimeCastSensorDescription

    def __init__(
        self,
        coordinator: ESPTimeCastCoordinator,
        description: ESPTimeCastSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.coordinator.data)
        return self.entity_description.native_unit_of_measurement
