"""Config flow for ESPTimeCast."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import ESPTimeCastClient, ESPTimeCastError, Status
from .const import CONF_HOST, DOMAIN
from .options_flow import ESPTimeCastOptionsFlow

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class ESPTimeCastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESPTimeCast."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._title: str = "ESPTimeCast"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ESPTimeCastOptionsFlow()

    async def _async_probe(self, host: str) -> Status:
        """Confirm a host is an ESPTimeCast and return its status."""
        client = ESPTimeCastClient(host, session=async_get_clientsession(self.hass))
        return await client.get_status()

    @staticmethod
    def _unique_id(status: Status, host: str) -> str:
        """Stable per-device id (configurable mDNS hostname, else host)."""
        return (status.mdns_url or host).lower()

    @staticmethod
    def _make_title(status: Status, host: str) -> str:
        return status.mdns_url or status.id or host

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual host entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                status = await self._async_probe(host)
            except ESPTimeCastError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(self._unique_id(status, host))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=self._make_title(status, host), data={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an _http._tcp device."""
        hostname = (discovery_info.hostname or "").lower().rstrip(".")
        # The firmware advertises a plain _http._tcp service with no identifying
        # TXT records, so filter on the (default/derived) hostname before probing.
        if "esptimecast" not in hostname:
            return self.async_abort(reason="not_esptimecast")

        host = discovery_info.host
        try:
            status = await self._async_probe(host)
        except ESPTimeCastError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self._unique_id(status, host))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._host = host
        self._title = self._make_title(status, host)
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered device."""
        if user_input is not None:
            assert self._host is not None
            return self.async_create_entry(
                title=self._title, data={CONF_HOST: self._host}
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._title},
        )
