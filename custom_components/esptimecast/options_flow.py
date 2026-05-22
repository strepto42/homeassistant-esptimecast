"""Options (Configure) flow for ESPTimeCast.

Mirrors the device web UI's settings form for the values that can only be
applied via ``/save`` (which reboots the device): Time & Region, Weather,
Dimming and Countdown. Live controls (brightness, the toggles, language, units,
custom message) are entities and are not duplicated here.

Wi-Fi credentials are intentionally excluded — changing them from Home
Assistant would move the device off the network and cut HA off from it.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import voluptuous as vol
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.helpers import selector

from .api import ESPTimeCastError, FullConfig

_LOGGER = logging.getLogger(__name__)

# Form field keys (user-facing) -> mapped to firmware names on submit.
CONF_TIME_ZONE = "time_zone"
CONF_CLOCK_DURATION = "clock_duration"
CONF_WEATHER_DURATION = "weather_duration"
CONF_NTP1 = "ntp_server1"
CONF_NTP2 = "ntp_server2"
CONF_HOSTNAME = "hostname"
CONF_API_KEY = "openweather_api_key"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_DIMMING_ENABLED = "dimming_enabled"
CONF_DIM_START = "dim_start"
CONF_DIM_END = "dim_end"
CONF_DIM_BRIGHTNESS = "dim_brightness"
CONF_AUTO_DIMMING = "auto_dimming"
CONF_COUNTDOWN_ENABLED = "countdown_enabled"
CONF_COUNTDOWN_DATE = "countdown_date"
CONF_COUNTDOWN_TIME = "countdown_time"
CONF_COUNTDOWN_LABEL = "countdown_label"
CONF_DRAMATIC_COUNTDOWN = "dramatic_countdown"


def _time_str(value: Any, fallback: str = "00:00:00") -> str:
    """Format a datetime.time (or None) as HH:MM:SS for a TimeSelector."""
    if value is None:
        return fallback
    return value.strftime("%H:%M:%S")


def _hm(value: str) -> tuple[int, int]:
    """Parse "HH:MM" or "HH:MM:SS" into (hour, minute)."""
    parts = value.split(":")
    return int(parts[0]), int(parts[1])


def _countdown_defaults(config: FullConfig) -> tuple[str, str]:
    """Return (date "YYYY-MM-DD", time "HH:MM:SS") defaults for the countdown."""
    ts = config.countdown.target_timestamp
    if ts:
        try:
            tz = ZoneInfo(config.time_zone) if config.time_zone else None
        except (ZoneInfoNotFoundError, ValueError):
            tz = None
        dt = datetime.fromtimestamp(ts, tz)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    return datetime.now().strftime("%Y-%m-%d"), "00:00:00"


def build_schema(config: FullConfig) -> vol.Schema:
    """Build the options form schema with defaults from the current config."""
    cd_date, cd_time = _countdown_defaults(config)
    return vol.Schema(
        {
            vol.Required(
                CONF_TIME_ZONE, default=config.time_zone or "UTC"
            ): selector.TextSelector(),
            vol.Required(
                CONF_CLOCK_DURATION,
                default=round((config.clock_duration or 10000) / 1000),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=600,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_WEATHER_DURATION,
                default=round((config.weather_duration or 5000) / 1000),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=600,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_NTP1, default=config.ntp_server1 or ""
            ): selector.TextSelector(),
            vol.Optional(
                CONF_NTP2, default=config.ntp_server2 or ""
            ): selector.TextSelector(),
            vol.Optional(
                CONF_HOSTNAME, default=config.hostname or ""
            ): selector.TextSelector(),
            # Blank leaves the stored OpenWeather API key unchanged.
            vol.Optional(CONF_API_KEY, default=""): selector.TextSelector(),
            vol.Optional(
                CONF_LATITUDE, default=config.latitude or ""
            ): selector.TextSelector(),
            vol.Optional(
                CONF_LONGITUDE, default=config.longitude or ""
            ): selector.TextSelector(),
            vol.Required(
                CONF_DIMMING_ENABLED, default=config.dimming_enabled
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_DIM_START, default=_time_str(config.dim_start, "18:00:00")
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DIM_END, default=_time_str(config.dim_end, "08:00:00")
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DIM_BRIGHTNESS,
                default=config.dim_brightness
                if config.dim_brightness is not None
                else 0,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-1, max=15, step=1, mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(
                CONF_AUTO_DIMMING, default=config.auto_dimming
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_COUNTDOWN_ENABLED, default=config.countdown.enabled
            ): selector.BooleanSelector(),
            vol.Required(CONF_COUNTDOWN_DATE, default=cd_date): selector.DateSelector(),
            vol.Required(CONF_COUNTDOWN_TIME, default=cd_time): selector.TimeSelector(),
            vol.Optional(
                CONF_COUNTDOWN_LABEL, default=config.countdown.label or ""
            ): selector.TextSelector(),
            vol.Required(
                CONF_DRAMATIC_COUNTDOWN, default=config.countdown.is_dramatic
            ): selector.BooleanSelector(),
        }
    )


def build_payload(user_input: dict[str, Any]) -> dict[str, Any]:
    """Map the submitted form to firmware /save field names.

    The countdown fields are always included because the firmware rebuilds the
    countdown object from whatever is posted (omitting them would wipe it).
    """
    start_h, start_m = _hm(user_input[CONF_DIM_START])
    end_h, end_m = _hm(user_input[CONF_DIM_END])
    cd_h, cd_m = _hm(user_input[CONF_COUNTDOWN_TIME])
    api_key = (user_input.get(CONF_API_KEY) or "").strip()

    return {
        "timeZone": user_input[CONF_TIME_ZONE],
        "clockDuration": int(user_input[CONF_CLOCK_DURATION]) * 1000,
        "weatherDuration": int(user_input[CONF_WEATHER_DURATION]) * 1000,
        "ntpServer1": user_input.get(CONF_NTP1, ""),
        "ntpServer2": user_input.get(CONF_NTP2, ""),
        "hostname": user_input.get(CONF_HOSTNAME, ""),
        # None -> omitted by save_config, leaving the masked key unchanged.
        "openWeatherApiKey": api_key or None,
        "openWeatherCity": user_input.get(CONF_LATITUDE, ""),
        "openWeatherCountry": user_input.get(CONF_LONGITUDE, ""),
        "dimmingEnabled": user_input[CONF_DIMMING_ENABLED],
        "dimStartHour": start_h,
        "dimStartMinute": start_m,
        "dimEndHour": end_h,
        "dimEndMinute": end_m,
        "dimBrightness": int(user_input[CONF_DIM_BRIGHTNESS]),
        "autoDimmingEnabled": user_input[CONF_AUTO_DIMMING],
        "countdownEnabled": user_input[CONF_COUNTDOWN_ENABLED],
        "countdownDate": user_input[CONF_COUNTDOWN_DATE],
        "countdownTime": f"{cd_h:02d}:{cd_m:02d}",
        "countdownLabel": user_input.get(CONF_COUNTDOWN_LABEL, ""),
        "isDramaticCountdown": user_input[CONF_DRAMATIC_COUNTDOWN],
    }


class ESPTimeCastOptionsFlow(OptionsFlow):
    """Configure the device's persisted (reboot-required) settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = self.config_entry.runtime_data
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await coordinator.client.save_config(build_payload(user_input))
            except ESPTimeCastError:
                errors["base"] = "save_failed"
            else:
                # The device reboots to apply; refresh once it is back.
                await coordinator.async_request_refresh()
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(coordinator.data.config),
            errors=errors,
        )
