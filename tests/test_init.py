# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Regression tests for custom_components.meshtastic.__init__."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

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

TEST_NODE_SHORT_NAME_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_node_short_name"


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


async def test_sensors_survive_options_reload(hass: HomeAssistant, mock_meshtastic_api_client) -> None:  # noqa: ARG001
    """Regression test for meshtastic/home-assistant#144.

    async_reload_entry() is invoked by the options-flow update listener on
    *every* options save (adding/removing a tracked node, toggling the web
    client, etc.), not just on a genuine Home Assistant restart. Before the
    fix, that reload path bypassed ConfigEntries' state machine, so the
    coordinator's first refresh was skipped and coordinator.data stayed
    None forever afterwards - which made every node-derived sensor
    disappear. This reproduces that exact path.
    """
    entry = _build_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_NODE_SHORT_NAME_ENTITY_ID)
    assert state is not None
    assert state.state == TEST_NODE["user"]["shortName"]

    # Any options-flow save (re-saving the same options is enough) routes
    # through the update listener -> async_reload_entry().
    hass.config_entries.async_update_entry(entry, options={**entry.options})
    await hass.async_block_till_done()

    state_after_reload = hass.states.get(TEST_NODE_SHORT_NAME_ENTITY_ID)
    assert state_after_reload is not None
    assert state_after_reload.state == TEST_NODE["user"]["shortName"]
