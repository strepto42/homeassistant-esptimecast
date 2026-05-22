"""Fixtures for the Home Assistant integration tests.

Loaded only when running under pytest-homeassistant-custom-component (CI/WSL).
Inherits ``status_payload`` from the repo-root tests/conftest.py.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esptimecast.api import DeviceData, FullConfig, Status
from custom_components.esptimecast.const import CONF_HOST, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Allow Home Assistant to load this custom integration in tests."""
    yield


@pytest.fixture
def status_obj(status_payload: dict) -> Status:
    """A parsed Status object from the captured fixture."""
    return Status.from_dict(status_payload)


@pytest.fixture
def config_obj(config_payload: dict) -> FullConfig:
    """A parsed FullConfig object from the captured fixture."""
    return FullConfig.from_dict(config_payload)


@pytest.fixture
def device_data(status_obj: Status, config_obj: FullConfig) -> DeviceData:
    """Combined coordinator data."""
    return DeviceData(status=status_obj, config=config_obj)


@pytest.fixture
def mock_client(status_obj: Status, device_data: DeviceData) -> Generator[AsyncMock]:
    """Patch the API client so no network access occurs.

    Patches the class methods used by both the coordinator (get_device_data)
    and the config flow (get_status).
    """
    with (
        patch(
            "custom_components.esptimecast.api.ESPTimeCastClient.get_device_data",
            new=AsyncMock(return_value=device_data),
        ) as get_device_data,
        patch(
            "custom_components.esptimecast.api.ESPTimeCastClient.get_status",
            new=AsyncMock(return_value=status_obj),
        ),
        patch(
            "custom_components.esptimecast.api.ESPTimeCastClient.get_config",
            new=AsyncMock(return_value=device_data.config),
        ),
        patch(
            "custom_components.esptimecast.api.ESPTimeCastClient.get_version",
            new=AsyncMock(return_value={"version": "1.6.0", "board": "esp32"}),
        ),
        patch(
            "custom_components.esptimecast.api.ESPTimeCastClient._request",
            new=AsyncMock(return_value="OK"),
        ),
    ):
        yield get_device_data


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A configured ESPTimeCast entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="esptimecast.local",
        unique_id="esptimecast.local",
        data={CONF_HOST: "esptimecast.local"},
    )
