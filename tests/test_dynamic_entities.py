# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Integration tests for dynamic entity creation (helpers.setup_platform_entry)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er
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

from .conftest import GATEWAY_NODE_NUM, TEST_NODE, TEST_NODE_NUM

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


def _fire_environment_telemetry(hass: HomeAssistant, entry: MockConfigEntry, data: dict) -> None:
    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_TELEMETRY,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: TEST_NODE_NUM,
            ATTR_EVENT_MESHTASTIC_API_DATA: data,
            ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE: EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS,
        },
    )


async def test_repeated_identical_events_do_not_duplicate_entities(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    for _ in range(3):
        _fire_environment_telemetry(hass, entry, {"temperature": 20.0})
        await hass.async_block_till_done()

    matches = [e for e in entity_registry.entities.values() if e.entity_id == TEMPERATURE_ENTITY_ID]
    assert len(matches) == 1


async def test_new_field_creates_exactly_one_new_entity(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    before = {e.entity_id for e in entity_registry.entities.values() if str(TEST_NODE_NUM) in e.entity_id}

    _fire_environment_telemetry(hass, entry, {"temperature": 20.0, "relativeHumidity": 45.0})
    await hass.async_block_till_done()

    after = {e.entity_id for e in entity_registry.entities.values() if str(TEST_NODE_NUM) in e.entity_id}
    new_entities = after - before
    assert new_entities == {
        f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_temperature",
        f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_relative_humidity",
    }


async def test_deselecting_node_removes_its_entities(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_device_battery_level") is not None

    hass.config_entries.async_update_entry(entry, options={CONF_OPTION_FILTER_NODES: []})
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_device_battery_level") is None


async def test_unique_id_stable_across_reload(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    battery_entity_id = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_device_battery_level"
    unique_id_before = entity_registry.entities[battery_entity_id].unique_id

    hass.config_entries.async_update_entry(entry, options={**entry.options})
    await hass.async_block_till_done()

    unique_id_after = entity_registry.entities[battery_entity_id].unique_id
    assert unique_id_before == unique_id_after
