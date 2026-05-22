"""Shared test fixtures.

The API-client tests must run on any OS (including native Windows) without
Home Assistant installed. Importing ``custom_components.esptimecast.api`` the
normal way would execute the package ``__init__.py``, which imports Home
Assistant. To avoid that, we load ``api.py`` directly from its file path — it is
deliberately self-contained (no HA imports, no relative imports).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_PATH = _REPO_ROOT / "custom_components" / "esptimecast" / "api.py"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_api_module() -> ModuleType:
    """Load api.py as a standalone module, bypassing the HA package."""
    spec = importlib.util.spec_from_file_location("esptimecast_api", _API_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def api_module() -> ModuleType:
    """The standalone-loaded ESPTimeCast API client module."""
    return _load_api_module()


@pytest.fixture
def status_payload() -> dict:
    """A real /status response captured from firmware 1.6.0."""
    return json.loads((_FIXTURES / "status.json").read_text(encoding="utf-8"))


@pytest.fixture
def config_payload() -> dict:
    """A real /config.json response captured from firmware 1.6.0."""
    return json.loads((_FIXTURES / "config.json").read_text(encoding="utf-8"))
