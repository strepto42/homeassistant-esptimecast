"""Light platform for ESPTimeCast.

The display is modelled as a single light: brightness 0-15 on the device maps to
the HA brightness slider, and "off" is the firmware's brightness == -1 state.
This mirrors the web UI, where one Brightness control governs the display.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ESPTimeCastConfigEntry, ESPTimeCastCoordinator
from .entity import ESPTimeCastEntity

_MAX_DEVICE_BRIGHTNESS = 15
_DEFAULT_ON_BRIGHTNESS = 8  # used when turning on with no level and none is known


def _device_to_ha(level: int) -> int:
    return max(0, min(255, round(level / _MAX_DEVICE_BRIGHTNESS * 255)))


def _ha_to_device(level: int) -> int:
    # Never map "on" to 0 (that is still on, just dimmest); clamp to 1..15.
    return max(
        1, min(_MAX_DEVICE_BRIGHTNESS, round(level / 255 * _MAX_DEVICE_BRIGHTNESS))
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPTimeCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ESPTimeCast display light."""
    async_add_entities([ESPTimeCastDisplayLight(entry.runtime_data)])


class ESPTimeCastDisplayLight(ESPTimeCastEntity, LightEntity):
    """The matrix display as a dimmable light."""

    _attr_translation_key = "display"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}  # noqa: RUF012

    def __init__(self, coordinator: ESPTimeCastCoordinator) -> None:
        super().__init__(coordinator, "display")
        self._optimistic_is_on: bool | None = None
        self._optimistic_brightness: int | None = None
        self._last_on_level = _DEFAULT_ON_BRIGHTNESS

    @callback
    def _handle_coordinator_update(self) -> None:
        # The device has reported fresh state; drop optimistic overrides.
        self._optimistic_is_on = None
        self._optimistic_brightness = None
        level = self.coordinator.data.status.brightness
        if level is not None and 0 <= level <= _MAX_DEVICE_BRIGHTNESS:
            self._last_on_level = level
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        return not self.coordinator.data.status.display_off

    @property
    def brightness(self) -> int | None:
        if not self.is_on:
            return None
        if self._optimistic_brightness is not None:
            return _device_to_ha(self._optimistic_brightness)
        level = self.coordinator.data.status.brightness
        if level is None or level < 0:
            return None
        return _device_to_ha(level)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            level = _ha_to_device(kwargs[ATTR_BRIGHTNESS])
        else:
            level = self._last_on_level
        await self.coordinator.client.set_brightness(level)
        self._last_on_level = level
        self._optimistic_is_on = True
        self._optimistic_brightness = level
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Brightness -1 is the firmware's "display off".
        await self.coordinator.client.set_brightness(-1)
        self._optimistic_is_on = False
        self._optimistic_brightness = None
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
