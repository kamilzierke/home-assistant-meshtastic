# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""
Integration tests for the discovered-fields cache surviving a restart (problem 7).

Simulates "Home Assistant restart" by unloading and re-setting-up the same config
entry within one test - the fixture's mock node data is swapped out in between to
mimic a fresh boot where the gateway hasn't redelivered environment telemetry yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meshtastic.api import (
    ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID,
    ATTR_EVENT_MESHTASTIC_API_DATA,
    ATTR_EVENT_MESHTASTIC_API_NODE,
    ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE,
    EVENT_MESHTASTIC_API_TELEMETRY,
    EventMeshtasticApiTelemetryType,
)
from custom_components.meshtastic.const import (
    CONF_CONNECTION_TCP_HOST,
    CONF_CONNECTION_TCP_PORT,
    CONF_CONNECTION_TYPE,
    CONF_OPTION_FILTER_NODES,
    CURRENT_CONFIG_VERSION_MAJOR,
    CURRENT_CONFIG_VERSION_MINOR,
    DOMAIN,
    ConnectionType,
)

from .conftest import GATEWAY_NODE, GATEWAY_NODE_NUM, TEST_NODE, TEST_NODE_NUM

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

TEMPERATURE_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_temperature"


def _build_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(GATEWAY_NODE_NUM),
        version=CURRENT_CONFIG_VERSION_MAJOR,
        minor_version=CURRENT_CONFIG_VERSION_MINOR,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.TCP.value,
            CONF_CONNECTION_TCP_HOST: "127.0.0.1",
            CONF_CONNECTION_TCP_PORT: 4403,
        },
        options={
            CONF_OPTION_FILTER_NODES: [{"id": TEST_NODE_NUM, "name": TEST_NODE["user"]["longName"]}],
        },
    )


def _make_mock_client(nodes: dict) -> MagicMock:
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.async_get_own_node = AsyncMock(return_value=GATEWAY_NODE)
    client.get_own_node = MagicMock(return_value=GATEWAY_NODE)
    client.async_get_all_nodes = AsyncMock(return_value=nodes)
    client.async_get_channels = AsyncMock(return_value=[])
    client.async_get_node_local_config = AsyncMock(return_value={})
    client.async_get_node_module_config = AsyncMock(return_value={})
    client.metadata = {}
    return client


async def test_environment_sensor_restored_after_restart(hass: HomeAssistant) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)

    # "Boot 1": each boot patches MeshtasticApiClient for exactly its own
    # async_setup() call, so the two client mocks never overlap.
    boot1_nodes = {GATEWAY_NODE_NUM: GATEWAY_NODE, TEST_NODE_NUM: TEST_NODE}
    with patch("custom_components.meshtastic.MeshtasticApiClient", return_value=_make_mock_client(boot1_nodes)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Discover the temperature field via a real telemetry event (not baked into the
    # node's initial data), so this actually exercises the discovery cache recording
    # it (problem 7), rather than the field merely being present from the start.
    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_TELEMETRY,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: TEST_NODE_NUM,
            ATTR_EVENT_MESHTASTIC_API_DATA: {"temperature": 21.5},
            ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE: EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "21.5"

    # Unload flushes the discovery cache (coordinator.async_shutdown, see __init__.py).
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Home Assistant's own entity lifecycle keeps a "removed but restorable" state
    # around after an unload; strip it so the assertion below can only pass because
    # the discovery cache (not that unrelated mechanism) rebuilt the entity - as it
    # would have to on a real process restart, where in-memory state is gone too.
    hass.states.async_remove(TEMPERATURE_ENTITY_ID)

    # "Boot 2" (simulated restart): the node has no environmentMetrics yet - as if the
    # gateway hasn't redelivered telemetry since restart.
    boot2_nodes = {GATEWAY_NODE_NUM: GATEWAY_NODE, TEST_NODE_NUM: TEST_NODE}
    with patch("custom_components.meshtastic.MeshtasticApiClient", return_value=_make_mock_client(boot2_nodes)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert state is not None, "previously discovered sensor must be rebuilt from the discovery cache after restart"
    assert state.state == "unknown"


async def test_unrelated_missing_field_does_not_delete_sensor(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    """A single coordinator update that omits a field must not delete that field's entity."""
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_TELEMETRY,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: TEST_NODE_NUM,
            ATTR_EVENT_MESHTASTIC_API_DATA: {"temperature": 20.0, "relativeHumidity": 50.0},
            ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE: EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "20.0"

    # A second packet only reports humidity (temperature momentarily absent).
    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_TELEMETRY,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: TEST_NODE_NUM,
            ATTR_EVENT_MESHTASTIC_API_DATA: {"relativeHumidity": 55.0},
            ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE: EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert state is not None, "temperature entity must not be deleted by a momentary gap"
