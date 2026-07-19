# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Integration tests for the node_rssi sensor (problem 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meshtastic.api import (
    ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID,
    ATTR_EVENT_MESHTASTIC_API_DATA,
    ATTR_EVENT_MESHTASTIC_API_NODE,
    EVENT_MESHTASTIC_API_NODE_UPDATED,
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

from .conftest import GATEWAY_NODE_NUM, TEST_NODE, TEST_NODE_NUM

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

RSSI_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_node_rssi"


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


async def test_rssi_sensor_exists_as_baseline_entity(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(RSSI_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["unit_of_measurement"] == "dBm"


async def test_rssi_sensor_updates_from_node_updated_event(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_NODE_UPDATED,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: TEST_NODE_NUM,
            ATTR_EVENT_MESHTASTIC_API_DATA: {**TEST_NODE, "rssi": -62, "snr": 5.25},
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(RSSI_ENTITY_ID)
    assert state is not None
    assert state.state == "-62"
