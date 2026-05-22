"""Self-contained async HTTP client for ESPTimeCast devices.

This module deliberately has **no Home Assistant imports and no relative
imports** so it can be unit-tested standalone on any OS (it is loaded by file
path in the test suite). The Home Assistant layer wraps this client.

Device API reference (firmware 1.6.0, port 80, no auth):
  GET  /status              -> full JSON state (polling source of truth)
  GET  /get_version         -> {"version", "board"}
  POST /action              -> generic command bus (409 when busy)
  POST /set_custom_message  -> scrolling message
  POST /set_<setting>       -> typed single-setting endpoints
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import time
from typing import Any

import aiohttp

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 10.0

# The firmware prefixes the weather description with an icon glyph encoded as a
# raw byte (the specific byte varies per icon, e.g. 0x0c for clear sky, 0x10 for
# rain, or non-UTF-8 high bytes like 0xa8). Strip control characters and the
# U+FFFD replacement char (what undecodable bytes become) from display strings.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f\ufffd]")

# Masked secret marker used by the firmware in /status.config.
_MASKED = "***HIDDEN***"


# --- Exceptions -------------------------------------------------------------


class ESPTimeCastError(Exception):
    """Base error for all client failures."""


class ESPTimeCastConnectionError(ESPTimeCastError):
    """Raised when the device cannot be reached."""


class ESPTimeCastTimeoutError(ESPTimeCastError):
    """Raised when a request times out."""


class ESPTimeCastBusyError(ESPTimeCastError):
    """Raised when the device returns HTTP 409 (protected message on screen)."""


# --- Data models ------------------------------------------------------------


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool:
    # /config.json encodes some booleans as the strings "true"/"false".
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "on", "yes")
    return False


def _hm_to_time(hour: Any, minute: Any) -> time | None:
    h = _to_int(hour)
    m = _to_int(minute)
    if h is None or m is None:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m)


@dataclass(slots=True)
class Weather:
    """Weather sub-object from /status."""

    temperature: float | None
    description: str | None
    icon: str | None
    humidity: int | None
    sunrise: time | None
    sunset: time | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Weather:
        desc = data.get("weatherDescription")
        if isinstance(desc, str):
            desc = _CONTROL_CHARS.sub("", desc).strip() or None
        icon = data.get("icon")
        if isinstance(icon, str):
            icon = _CONTROL_CHARS.sub("", icon).strip() or None
        return cls(
            temperature=_to_float(data.get("currentTemperature")),
            description=desc,
            icon=icon,
            humidity=_to_int(data.get("currentHumidity")),
            sunrise=_hm_to_time(data.get("sunriseHour"), data.get("sunriseMinute")),
            sunset=_hm_to_time(data.get("sunsetHour"), data.get("sunsetMinute")),
        )


@dataclass(slots=True)
class Countdown:
    """Countdown sub-object from /status."""

    enabled: bool
    target_timestamp: int | None
    label: str
    is_dramatic: bool
    remaining: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Countdown:
        return cls(
            enabled=bool(data.get("enabled", False)),
            target_timestamp=_to_int(data.get("targetTimestamp")),
            label=data.get("label", "") or "",
            is_dramatic=bool(data.get("isDramatic", False)),
            remaining=_to_int(data.get("remaining")),
        )


@dataclass(slots=True)
class Nightscout:
    """Nightscout glucose sub-object from /status."""

    active: bool
    glucose: float | None
    trend: str | None
    last_reading_epoch: int | None
    minutes_since_reading: int | None
    is_outdated: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Nightscout:
        return cls(
            active=bool(data.get("active", False)),
            glucose=_to_float(data.get("glucose")),
            trend=data.get("trend"),
            last_reading_epoch=_to_int(data.get("lastReadingEpoch")),
            minutes_since_reading=_to_int(data.get("minutesSinceReading")),
            is_outdated=bool(data.get("isOutdated", True)),
        )


@dataclass(slots=True)
class Dimming:
    """Auto-dimming sub-object from /status."""

    enabled: bool
    auto_enabled: bool
    clock_only: bool
    start: time | None
    end: time | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Dimming:
        return cls(
            enabled=bool(data.get("dimmingEnabled", False)),
            auto_enabled=bool(data.get("autoDimmingEnabled", False)),
            clock_only=bool(data.get("clockOnlyDuringDimming", False)),
            start=_hm_to_time(data.get("dimStartHour"), data.get("dimStartMinute")),
            end=_hm_to_time(data.get("dimEndHour"), data.get("dimEndMinute")),
        )


@dataclass(slots=True)
class DeviceConfig:
    """The saved-config sub-object from /status (secrets masked)."""

    ssid: str | None
    has_api_key: bool
    openweather_city: str | None
    weather_units: str | None
    clock_duration: int | None
    weather_duration: int | None
    time_zone: str | None
    language: str | None
    flip_display: bool
    twelve_hour: bool
    show_date: bool
    show_humidity: bool
    ntp_server1: str | None
    ntp_server2: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceConfig:
        api_key = data.get("openWeatherApiKey") or ""
        return cls(
            ssid=data.get("ssid") or None,
            has_api_key=bool(api_key),
            openweather_city=data.get("openWeatherCity") or None,
            weather_units=data.get("weatherUnits") or None,
            clock_duration=_to_int(data.get("clockDuration")),
            weather_duration=_to_int(data.get("weatherDuration")),
            time_zone=data.get("timeZone") or None,
            language=data.get("language") or None,
            flip_display=bool(data.get("flipDisplay", False)),
            twelve_hour=bool(data.get("twelveHourToggle", False)),
            show_date=bool(data.get("showDate", False)),
            show_humidity=bool(data.get("showHumidity", False)),
            ntp_server1=data.get("ntpServer1") or None,
            ntp_server2=data.get("ntpServer2") or None,
        )


@dataclass(slots=True)
class Status:
    """Parsed /status response."""

    id: str | None
    version: str | None
    hardware: str | None
    board: str | None
    display_mode: int | None
    mode: str | None
    message: str
    display_busy: bool
    allow_interrupt: bool
    display_off: bool
    brightness: int | None
    device_runtime: str | None
    session_runtime: int | None
    wifi_signal: int | None
    mdns_url: str | None
    time_synced: bool
    local_time: str | None
    epoch_time: int | None
    weather: Weather
    countdown: Countdown
    nightscout: Nightscout
    dimming: Dimming
    config: DeviceConfig
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Status:
        return cls(
            id=data.get("id"),
            version=data.get("version"),
            hardware=data.get("hardware"),
            board=data.get("board"),
            display_mode=_to_int(data.get("displayMode")),
            mode=data.get("mode"),
            message=data.get("message", "") or "",
            display_busy=bool(data.get("displayBusy", False)),
            allow_interrupt=bool(data.get("allowInterrupt", False)),
            display_off=bool(data.get("displayOff", False)),
            brightness=_to_int(data.get("brightness")),
            device_runtime=data.get("device_runtime"),
            session_runtime=_to_int(data.get("session_runtime")),
            wifi_signal=_to_int(data.get("wifi_signal")),
            mdns_url=data.get("mdns_url"),
            time_synced=bool(data.get("time_synced", False)),
            local_time=data.get("localTime"),
            epoch_time=_to_int(data.get("epochTime")),
            weather=Weather.from_dict(data.get("weather", {}) or {}),
            countdown=Countdown.from_dict(data.get("countdown", {}) or {}),
            nightscout=Nightscout.from_dict(data.get("nightscout", {}) or {}),
            dimming=Dimming.from_dict(data.get("dimming", {}) or {}),
            config=DeviceConfig.from_dict(data.get("config", {}) or {}),
            raw=data,
        )

    @property
    def dimming_active(self) -> bool:
        """Whether the display is currently dimmed, mirroring the firmware.

        Dimming is active when auto-dimming OR scheduled dimming is enabled and
        the current local time falls within the relevant window. Auto-dimming
        (sunset -> sunrise) applies even when scheduled dimming is off.
        """
        d = self.dimming
        if not (d.auto_enabled or d.enabled):
            return False
        if self.local_time is None:
            return False
        try:
            parts = [int(p) for p in self.local_time.split(":")]
        except ValueError:
            return False
        now = parts[0] * 60 + parts[1]

        if d.auto_enabled:
            start, end = self.weather.sunset, self.weather.sunrise
        else:
            start, end = d.start, d.end
        if start is None or end is None:
            return False

        start_total = start.hour * 60 + start.minute
        end_total = end.hour * 60 + end.minute
        if start_total < end_total:
            return start_total <= now < end_total
        return now >= start_total or now < end_total  # overnight window


@dataclass(slots=True)
class CountdownConfig:
    """Countdown settings as stored in /config.json."""

    enabled: bool
    target_timestamp: int | None
    label: str
    is_dramatic: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CountdownConfig:
        return cls(
            enabled=_to_bool(data.get("enabled", False)),
            target_timestamp=_to_int(data.get("targetTimestamp")),
            label=data.get("label", "") or "",
            is_dramatic=_to_bool(data.get("isDramaticCountdown", False)),
        )


@dataclass(slots=True)
class FullConfig:
    """The full persisted configuration from /config.json.

    This is richer than Status.config (the /status block exposes only a
    subset). It is the source of truth for the device's settings, including
    toggles that /status does not report (day-of-week, colon blink, weather
    description) and the persistent custom message.
    """

    brightness: int | None
    clock_duration: int | None
    weather_duration: int | None
    flip_display: bool
    twelve_hour: bool
    show_day_of_week: bool
    show_date: bool
    show_humidity: bool
    colon_blink: bool
    show_weather_description: bool
    weather_units: str | None
    language: str | None
    time_zone: str | None
    hostname: str | None
    ntp_server1: str | None
    ntp_server2: str | None
    dimming_enabled: bool
    dim_start: time | None
    dim_end: time | None
    dim_brightness: int | None
    auto_dimming: bool
    clock_only_dimming: bool
    countdown: CountdownConfig
    custom_message: str
    hide_donation_msg: bool
    latitude: str | None
    longitude: str | None
    has_api_key: bool
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FullConfig:
        # A non-empty value (the asterisk mask or a real key) means configured.
        has_key = bool(data.get("openWeatherApiKey"))
        return cls(
            brightness=_to_int(data.get("brightness")),
            clock_duration=_to_int(data.get("clockDuration")),
            weather_duration=_to_int(data.get("weatherDuration")),
            flip_display=_to_bool(data.get("flipDisplay")),
            twelve_hour=_to_bool(data.get("twelveHourToggle")),
            show_day_of_week=_to_bool(data.get("showDayOfWeek")),
            show_date=_to_bool(data.get("showDate")),
            show_humidity=_to_bool(data.get("showHumidity")),
            colon_blink=_to_bool(data.get("colonBlinkEnabled")),
            show_weather_description=_to_bool(data.get("showWeatherDescription")),
            weather_units=data.get("weatherUnits") or None,
            language=data.get("language") or None,
            time_zone=data.get("timeZone") or None,
            hostname=data.get("hostname") or None,
            ntp_server1=data.get("ntpServer1") or None,
            ntp_server2=data.get("ntpServer2") or None,
            dimming_enabled=_to_bool(data.get("dimmingEnabled")),
            dim_start=_hm_to_time(data.get("dimStartHour"), data.get("dimStartMinute")),
            dim_end=_hm_to_time(data.get("dimEndHour"), data.get("dimEndMinute")),
            dim_brightness=_to_int(data.get("dimBrightness")),
            auto_dimming=_to_bool(data.get("autoDimmingEnabled")),
            clock_only_dimming=_to_bool(data.get("clockOnlyDuringDimming")),
            countdown=CountdownConfig.from_dict(data.get("countdown", {}) or {}),
            custom_message=data.get("customMessage", "") or "",
            hide_donation_msg=_to_bool(data.get("hideDonationMsg")),
            latitude=data.get("openWeatherCity") or None,
            longitude=data.get("openWeatherCountry") or None,
            has_api_key=has_key,
            raw=data,
        )


@dataclass(slots=True)
class DeviceData:
    """Combined live state (/status) and persisted settings (/config.json)."""

    status: Status
    config: FullConfig


# --- Client -----------------------------------------------------------------


def _normalise_host(host: str) -> str:
    """Strip scheme/trailing slash so we control URL construction."""
    host = host.strip()
    for prefix in ("http://", "https://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix) :]
            break
    return host.strip("/")


def _bool_to_int(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    return value


class ESPTimeCastClient:
    """Async client for a single ESPTimeCast device."""

    def __init__(
        self,
        host: str,
        *,
        session: aiohttp.ClientSession,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = _normalise_host(host)
        self._port = port
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def host(self) -> str:
        return self._host

    @property
    def base_url(self) -> str:
        if self._port == DEFAULT_PORT:
            return f"http://{self._host}"
        return f"http://{self._host}:{self._port}"

    # -- low-level request helpers -----------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.request(
                method, url, data=data, timeout=self._timeout
            ) as resp:
                body = await resp.text()
                if resp.status == 409:
                    raise ESPTimeCastBusyError(f"Device busy (409) for {method} {path}")
                if resp.status >= 400:
                    raise ESPTimeCastError(
                        f"HTTP {resp.status} for {method} {path}: {body[:200]}"
                    )
                return body
        except TimeoutError as err:
            raise ESPTimeCastTimeoutError(f"Timeout for {method} {path}") from err
        except aiohttp.ClientError as err:
            raise ESPTimeCastConnectionError(
                f"Connection error for {method} {path}: {err}"
            ) from err

    async def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                if resp.status >= 400:
                    raise ESPTimeCastError(f"HTTP {resp.status} for GET {path}")
                raw = await resp.read()
        except TimeoutError as err:
            raise ESPTimeCastTimeoutError(f"Timeout for GET {path}") from err
        except aiohttp.ClientError as err:
            raise ESPTimeCastConnectionError(
                f"Connection error for GET {path}: {err}"
            ) from err
        # The firmware embeds its own icon/symbol glyphs as raw bytes inside the
        # JSON: both control characters (e.g. form-feed) and non-UTF-8 high bytes
        # (e.g. 0xa8). Decoding the body as text would raise UnicodeDecodeError,
        # and strict JSON parsers (orjson, which HA uses for resp.json()) reject
        # control characters. So decode the raw bytes leniently and parse with
        # strict=False. Bad bytes become U+FFFD, which the display-string
        # cleaning then strips.
        text = raw.decode("utf-8", errors="replace")
        try:
            data: dict[str, Any] = json.loads(text, strict=False)
        except json.JSONDecodeError as err:
            raise ESPTimeCastError(f"Invalid JSON from GET {path}: {err}") from err
        return data

    # -- read API ----------------------------------------------------------

    async def get_status(self) -> Status:
        """Fetch and parse /status."""
        return Status.from_dict(await self._get_json("/status"))

    async def get_config(self) -> FullConfig:
        """Fetch and parse the full /config.json settings."""
        return FullConfig.from_dict(await self._get_json("/config.json"))

    async def get_device_data(self) -> DeviceData:
        """Fetch combined live state (/status) and settings (/config.json)."""
        status = await self.get_status()
        config = await self.get_config()
        return DeviceData(status=status, config=config)

    async def get_version(self) -> dict[str, Any]:
        """Fetch /get_version -> {"version", "board"}."""
        return await self._get_json("/get_version")

    # -- generic command bus ----------------------------------------------

    async def send_action(self, action: str, value: Any = "") -> str:
        """POST a single action=value pair to /action."""
        return await self._request(
            "POST", "/action", data={action: _bool_to_int(value)}
        )

    # -- persisted settings -------------------------------------------------

    async def save_config(self, fields: dict[str, Any]) -> None:
        """Persist settings via POST /save (the device reboots afterwards).

        ``fields`` keys are raw firmware config names (e.g. ``clockDuration``,
        ``dimmingEnabled``, ``countdownDate``). Booleans are sent as the
        firmware's "true"/"false" strings; ``None`` values are dropped (used to
        leave masked secrets unchanged). The firmware merges these into the
        existing config and rebuilds the countdown object from the posted
        ``countdown*`` params, so callers must include all of those together.
        """
        data: dict[str, Any] = {}
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, bool):
                data[key] = "true" if value else "false"
            else:
                data[key] = value
        await self._request("POST", "/save", data=data)

    # -- typed setters ------------------------------------------------------

    async def _set(self, endpoint: str, value: Any) -> str:
        return await self._request(
            "POST", f"/set_{endpoint}", data={"value": _bool_to_int(value)}
        )

    async def set_brightness(self, value: int) -> None:
        await self._set("brightness", int(value))

    async def set_flip(self, value: bool) -> None:
        await self._set("flip", value)

    async def set_twelve_hour(self, value: bool) -> None:
        await self._set("twelvehour", value)

    async def set_day_of_week(self, value: bool) -> None:
        await self._set("dayofweek", value)

    async def set_show_date(self, value: bool) -> None:
        await self._set("showdate", value)

    async def set_humidity(self, value: bool) -> None:
        await self._set("humidity", value)

    async def set_colon_blink(self, value: bool) -> None:
        await self._set("colon_blink", value)

    async def set_weather_desc(self, value: bool) -> None:
        await self._set("weatherdesc", value)

    async def set_hide_donation(self, value: bool) -> None:
        await self._set("hide_donation", value)

    async def set_units(self, value: str) -> None:
        """value: "metric" or "imperial"."""
        await self._set("units", 0 if value == "metric" else 1)

    async def set_language(self, value: str) -> None:
        await self._set("language", value)

    async def set_countdown_enabled(self, value: bool) -> None:
        await self._set("countdown_enabled", value)

    async def set_dramatic_countdown(self, value: bool) -> None:
        await self._set("dramatic_countdown", value)

    async def set_clock_only_dimming(self, value: bool) -> None:
        await self._set("clock_only_dimming", value)

    # -- convenience actions ------------------------------------------------

    async def persist(self) -> None:
        """Persist the current live runtime to flash (deferred, no reboot).

        The firmware applies most /set_* changes to RAM only; this marks the
        config dirty so it is saved, surviving a power cycle.
        """
        await self.send_action("save")

    async def restart(self) -> None:
        await self.send_action("restart")

    async def next_mode(self) -> None:
        await self.send_action("next_mode")

    async def previous_mode(self) -> None:
        await self.send_action("prev_mode")

    async def go_to_mode(self, mode: str | int) -> None:
        await self.send_action("go_to_mode", mode)

    async def set_display_off(self, value: bool) -> None:
        # The firmware exposes display power as a toggle action.
        await self.send_action("display_off", value)

    async def enable_rotation(self, value: bool) -> None:
        await self.send_action("enable_rotation", value)

    async def clear_message(self) -> None:
        await self.send_action("clear_message")

    async def start_timer(self, spec: str) -> None:
        """spec e.g. "5M", "1H30M", "90S"."""
        await self.send_action("timer", spec)

    async def stop_timer(self) -> None:
        await self.send_action("timer_stop")

    async def start_stopwatch(self) -> None:
        await self.send_action("stopwatch_start")

    async def stop_stopwatch(self) -> None:
        await self.send_action("stopwatch_stop")

    async def start_pomodoro(self, spec: str) -> None:
        """spec e.g. "25-5-15"."""
        await self.send_action("pomodoro", spec)

    async def restart_pomodoro(self) -> None:
        await self.send_action("pomodoro_restart")

    # -- messages -----------------------------------------------------------

    async def send_message(
        self,
        message: str,
        *,
        speed: int | None = None,
        scrolls: int | None = None,
        seconds: int | None = None,
        big_numbers: bool | None = None,
        interrupt: bool | None = None,
    ) -> None:
        """Display a scrolling message via /set_custom_message.

        Only the parameters that are explicitly provided are sent.
        """
        data: dict[str, Any] = {"message": message}
        if speed is not None:
            data["speed"] = int(speed)
        if scrolls is not None:
            data["scrolltimes"] = int(scrolls)
        if seconds is not None:
            data["seconds"] = int(seconds)
        if big_numbers is not None:
            data["bignumbers"] = 1 if big_numbers else 0
        if interrupt is not None:
            data["allowInterrupt"] = 1 if interrupt else 0
        await self._request("POST", "/set_custom_message", data=data)

    async def display_message(
        self, message: str, *, scrolls: int = 0, seconds: int = 0
    ) -> None:
        """Set the persistent scrolling message via /action (web-UI parity).

        Defaults (scrolls=0, seconds=0) scroll the message indefinitely with no
        auto-clear, matching the web UI's Custom Message box. Passing an empty
        message clears the display.
        """
        await self._request(
            "POST",
            "/action",
            data={"message": message, "scrolls": scrolls, "seconds": seconds},
        )
