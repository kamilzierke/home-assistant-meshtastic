# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

GATEWAY_NODE_NUM = 111111111
TEST_NODE_NUM = 222222222

GATEWAY_NODE = {
    "num": GATEWAY_NODE_NUM,
    "user": {
        "id": "!06a76a8b",
        "longName": "Test Gateway",
        "shortName": "TGW1",
        "hwModel": "TBEAM",
    },
    "deviceMetrics": {"batteryLevel": 95, "voltage": 4.0},
}

TEST_NODE = {
    "num": TEST_NODE_NUM,
    "user": {
        "id": "!0d422b90",
        "longName": "Test Node",
        "shortName": "TN01",
        "hwModel": "HELTEC_V3",
    },
    "deviceMetrics": {"batteryLevel": 80, "voltage": 3.7},
}


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """pytest-homeassistant-custom-component requires this to load custom_components."""


@pytest.fixture
def mock_nodes() -> dict[int, dict]:
    return {GATEWAY_NODE_NUM: GATEWAY_NODE, TEST_NODE_NUM: TEST_NODE}


@pytest.fixture
def mock_meshtastic_api_client(mock_nodes: dict[int, dict]):
    """Patch MeshtasticApiClient as imported into __init__.py's setup path.

    This mocks at the API client boundary rather than the underlying
    aiomeshtastic/protocol layer, since what these tests exercise is the
    integration's own config-entry setup/reload/coordinator lifecycle, not
    the wire protocol.
    """
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.async_get_own_node = AsyncMock(return_value=GATEWAY_NODE)
    client.get_own_node = MagicMock(return_value=GATEWAY_NODE)
    client.async_get_all_nodes = AsyncMock(return_value=mock_nodes)
    client.async_get_channels = AsyncMock(return_value=[])
    client.async_get_node_local_config = AsyncMock(return_value={})
    client.async_get_node_module_config = AsyncMock(return_value={})
    client.metadata = {}

    with patch("custom_components.meshtastic.MeshtasticApiClient", return_value=client):
        yield client
