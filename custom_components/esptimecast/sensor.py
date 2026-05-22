"""Sensor platform for ESPTimeCast."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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

from .api import DeviceData
from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity


def _temp_unit(data: DeviceData) -> str:
    if data.config.weather_units == "imperial":
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


def _runtime_seconds(data: DeviceData) -> int | None:
    # device_runtime is total uptime formatted "HH:MM:SS" (hours may exceed 24).
    raw = data.status.device_runtime
    if not raw:
        return None
    try:
        parts = [int(p) for p in raw.split(":")]
    except ValueError:
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


@dataclass(frozen=True, kw_only=True)
class ESPTimeCastSensorDescription(SensorEntityDescription):
    """Describes an ESPTimeCast sensor."""

    value_fn: Callable[[DeviceData], StateType]
    unit_fn: Callable[[DeviceData], str | None] | None = None


# Always-present sensors.
SENSORS: tuple[ESPTimeCastSensorDescription, ...] = (
    ESPTimeCastSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=_temp_unit,
        value_fn=lambda d: d.status.weather.temperature,
    ),
    ESPTimeCastSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.status.weather.humidity,
    ),
    ESPTimeCastSensorDescription(
        key="weather_description",
        translation_key="weather_description",
        value_fn=lambda d: d.status.weather.description,
    ),
    ESPTimeCastSensorDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.status.wifi_signal,
    ),
    ESPTimeCastSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_runtime_seconds,
    ),
)

# Created only when a countdown is configured.
COUNTDOWN_SENSOR = ESPTimeCastSensorDescription(
    key="countdown_remaining",
    translation_key="countdown_remaining",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.SECONDS,
    value_fn=lambda d: d.status.countdown.remaining,
)

# Created only when Nightscout is active.
GLUCOSE_SENSOR = ESPTimeCastSensorDescription(
    key="glucose",
    translation_key="glucose",
    native_unit_of_measurement="mg/dL",
    value_fn=lambda d: d.status.nightscout.glucose,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPTimeCast sensors."""
    coordinator = entry.runtime_data
    descriptions = list(SENSORS)
    data = coordinator.data
    if data.config.countdown.enabled or data.status.countdown.enabled:
        descriptions.append(COUNTDOWN_SENSOR)
    if data.status.nightscout.active:
        descriptions.append(GLUCOSE_SENSOR)
    async_add_entities(
        ESPTimeCastSensor(coordinator, description) for description in descriptions
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
