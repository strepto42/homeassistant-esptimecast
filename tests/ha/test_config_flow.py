"""Tests for the ESPTimeCast config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esptimecast.api import ESPTimeCastConnectionError
from custom_components.esptimecast.const import CONF_HOST, DOMAIN


def _zeroconf_info(hostname: str = "esptimecast.local.") -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=[],
        hostname=hostname,
        name="esptimecast._http._tcp.local.",
        port=80,
        type="_http._tcp.local.",
        properties={},
    )


async def test_user_flow_success(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "esptimecast.local"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "esptimecast.local"
    assert result["data"] == {CONF_HOST: "esptimecast.local"}
    assert result["result"].unique_id == "esptimecast.local"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.esptimecast.api.ESPTimeCastClient.get_status",
        new=AsyncMock(side_effect=ESPTimeCastConnectionError("nope")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "bad.local"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(
    hass: HomeAssistant, mock_client, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "esptimecast.local"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow_success(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.50"}
    assert result["result"].unique_id == "esptimecast.local"


async def test_zeroconf_ignores_non_esptimecast(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(hostname="some-printer.local."),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_esptimecast"
