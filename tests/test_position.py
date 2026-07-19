# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Integration tests for GNSS/position sensors and device_tracker (problem 6)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2
from custom_components.meshtastic.api import (
    ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID,
    ATTR_EVENT_MESHTASTIC_API_DATA,
    ATTR_EVENT_MESHTASTIC_API_NODE,
    ATTR_EVENT_MESHTASTIC_API_NODE_INFO,
    EVENT_MESHTASTIC_API_POSITION,
    MeshtasticApiClient,
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

DEVICE_TRACKER_ENTITY_ID = f"device_tracker.{DOMAIN}_tgw1_{TEST_NODE_NUM}_node_position"
SATS_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_satellites_in_view"
GROUND_TRACK_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_ground_track"
HDOP_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_hdop"
GPS_ACCURACY_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_gps_accuracy"


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


def _fire_position(hass: HomeAssistant, entry: MockConfigEntry, node_id: int, data: dict) -> None:
    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_POSITION,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: node_id,
            ATTR_EVENT_MESHTASTIC_API_DATA: data,
            ATTR_EVENT_MESHTASTIC_API_NODE_INFO: {"name": TEST_NODE["user"]["longName"]},
        },
    )


async def test_position_packet_creates_gnss_sensors(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(SATS_ENTITY_ID) is None

    _fire_position(
        hass,
        entry,
        TEST_NODE_NUM,
        {
            "latitudeI": 473000000,
            "longitudeI": 85000000,
            "satsInView": 9,
            "groundTrack": 12345,
            "HDOP": 145,
            "gpsAccuracy": 2500,
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(SATS_ENTITY_ID).state == "9"
    assert hass.states.get(GROUND_TRACK_ENTITY_ID).state == "123.45"
    assert hass.states.get(HDOP_ENTITY_ID).state == "1.45"
    # gpsAccuracy must stay in raw millimeters, not be reinterpreted as horizontal accuracy.
    assert hass.states.get(GPS_ACCURACY_ENTITY_ID).state == "2500"


async def test_satellites_in_view_zero_is_not_ignored(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "satsInView": 0})
    await hass.async_block_till_done()

    state = hass.states.get(SATS_ENTITY_ID)
    assert state is not None
    assert state.state == "0"


async def test_device_tracker_still_works_alongside_new_sensors(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass,
        entry,
        TEST_NODE_NUM,
        {"latitudeI": 473000000, "longitudeI": 85000000, "precisionBits": 16, "satsInView": 7},
    )
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_TRACKER_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["latitude"]) == 47.3
    assert float(state.attributes["longitude"]) == 8.5
    # precisionBits must still drive tracker accuracy, unaffected by the new sensors.
    assert state.attributes["gps_accuracy"] == 364


async def test_request_position_updates_coordinator(hass: HomeAssistant, mock_nodes) -> None:
    """A manual meshtastic.request_position call must update entities (problem 2)."""
    with patch("custom_components.meshtastic.api.AioTcpConnection"):
        client = MeshtasticApiClient(
            data={CONF_CONNECTION_TYPE: ConnectionType.TCP.value, "tcp_host": "127.0.0.1", "tcp_port": 4403},
            hass=hass,
            config_entry_id="entry1",
        )

    position = mesh_pb2.Position()
    position.latitude_i = 473000000
    position.longitude_i = 85000000
    position.sats_in_view = 11
    client._interface.request_position = AsyncMock(return_value=position)  # noqa: SLF001

    captured_events = []
    hass.bus.async_listen(
        EVENT_MESHTASTIC_API_POSITION,
        lambda event: captured_events.append(event.data[ATTR_EVENT_MESHTASTIC_API_DATA]),
    )

    result = await client.request_position(TEST_NODE_NUM)
    await hass.async_block_till_done()

    assert result["satsInView"] == 11
    assert result["latitude"] == 47.3
    assert any(data.get("satsInView") == 11 for data in captured_events)
