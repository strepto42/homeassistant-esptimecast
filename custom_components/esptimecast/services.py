"""Device-targeted services for ESPTimeCast."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DISPLAY_MODES, DOMAIN

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_START_TIMER = "start_timer"
SERVICE_START_POMODORO = "start_pomodoro"
SERVICE_START_STOPWATCH = "start_stopwatch"
SERVICE_GO_TO_MODE = "go_to_mode"
SERVICE_CLEAR_MESSAGE = "clear_message"

ATTR_MESSAGE = "message"
ATTR_SPEED = "speed"
ATTR_SCROLLS = "scrolls"
ATTR_SECONDS = "seconds"
ATTR_BIG_NUMBERS = "big_numbers"
ATTR_INTERRUPT = "interrupt"
ATTR_DURATION = "duration"
ATTR_SPEC = "spec"
ATTR_MODE = "mode"

_TARGET: dict[Any, Any] = {
    vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])
}

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_SPEED): vol.All(vol.Coerce(int), vol.Range(min=10, max=200)),
        vol.Optional(ATTR_SCROLLS): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(ATTR_SECONDS): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=3600)
        ),
        vol.Optional(ATTR_BIG_NUMBERS): cv.boolean,
        vol.Optional(ATTR_INTERRUPT): cv.boolean,
    }
)
START_TIMER_SCHEMA = vol.Schema({**_TARGET, vol.Required(ATTR_DURATION): cv.string})
START_POMODORO_SCHEMA = vol.Schema({**_TARGET, vol.Required(ATTR_SPEC): cv.string})
START_STOPWATCH_SCHEMA = vol.Schema(_TARGET)
GO_TO_MODE_SCHEMA = vol.Schema(
    {**_TARGET, vol.Required(ATTR_MODE): vol.In(DISPLAY_MODES)}
)
CLEAR_MESSAGE_SCHEMA = vol.Schema(_TARGET)


def _coordinators_for_call(hass: HomeAssistant, call: ServiceCall) -> list:
    """Resolve ESPTimeCast coordinators from the call's target device_ids."""
    dev_reg = dr.async_get(hass)
    coordinators = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        device = dev_reg.async_get(device_id)
        if device is None:
            raise ServiceValidationError(f"Unknown device: {device_id}")
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is not None and entry.domain == DOMAIN:
                coordinators.append(entry.runtime_data)
    if not coordinators:
        raise ServiceValidationError("No ESPTimeCast devices in service target")
    return coordinators


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services (idempotent)."""

    async def _send_message(call: ServiceCall) -> None:
        for coordinator in _coordinators_for_call(hass, call):
            await coordinator.client.send_message(
                call.data[ATTR_MESSAGE],
                speed=call.data.get(ATTR_SPEED),
                scrolls=call.data.get(ATTR_SCROLLS),
                seconds=call.data.get(ATTR_SECONDS),
                big_numbers=call.data.get(ATTR_BIG_NUMBERS),
                interrupt=call.data.get(ATTR_INTERRUPT),
            )

    async def _start_timer(call: ServiceCall) -> None:
        for coordinator in _coordinators_for_call(hass, call):
            await coordinator.client.start_timer(call.data[ATTR_DURATION])

    async def _start_pomodoro(call: ServiceCall) -> None:
        for coordinator in _coordinators_for_call(hass, call):
            await coordinator.client.start_pomodoro(call.data[ATTR_SPEC])

    async def _start_stopwatch(call: ServiceCall) -> None:
        for coordinator in _coordinators_for_call(hass, call):
            await coordinator.client.start_stopwatch()

    async def _go_to_mode(call: ServiceCall) -> None:
        for coordinator in _coordinators_for_call(hass, call):
            await coordinator.client.go_to_mode(call.data[ATTR_MODE])

    async def _clear_message(call: ServiceCall) -> None:
        for coordinator in _coordinators_for_call(hass, call):
            await coordinator.client.clear_message()

    services = (
        (SERVICE_SEND_MESSAGE, _send_message, SEND_MESSAGE_SCHEMA),
        (SERVICE_START_TIMER, _start_timer, START_TIMER_SCHEMA),
        (SERVICE_START_POMODORO, _start_pomodoro, START_POMODORO_SCHEMA),
        (SERVICE_START_STOPWATCH, _start_stopwatch, START_STOPWATCH_SCHEMA),
        (SERVICE_GO_TO_MODE, _go_to_mode, GO_TO_MODE_SCHEMA),
        (SERVICE_CLEAR_MESSAGE, _clear_message, CLEAR_MESSAGE_SCHEMA),
    )
    for name, handler, schema in services:
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(DOMAIN, name, handler, schema=schema)
