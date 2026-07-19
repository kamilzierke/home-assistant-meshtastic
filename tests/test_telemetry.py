# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""
Integration tests for telemetry entity creation/update (problems 1, 2, 3, 4).

Mocks at the API client boundary (like test_init.py) and drives the coordinator
through the real EVENT_MESHTASTIC_API_* events it listens for, so these exercise the
real coordinator/entity-factory wiring without needing a live radio connection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meshtastic.aiomeshtastic.interface import TelemetryType
from custom_components.meshtastic.aiomeshtastic.protobuf import telemetry_pb2
from custom_components.meshtastic.api import (
    ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID,
    ATTR_EVENT_MESHTASTIC_API_DATA,
    ATTR_EVENT_MESHTASTIC_API_NODE,
    ATTR_EVENT_MESHTASTIC_API_NODE_INFO,
    ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE,
    EVENT_MESHTASTIC_API_TELEMETRY,
    EventMeshtasticApiTelemetryType,
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

BATTERY_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_device_battery_level"
TEMPERATURE_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_temperature"
HUMIDITY_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_relative_humidity"
PRESSURE_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_barometric_pressure"
WHITE_LUX_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_white_lux"
WIND_SPEED_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_environment_wind_speed"
AIR_QUALITY_PM25_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_airquality_pm25_standard"


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


def _fire_telemetry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    node_id: int,
    telemetry_type: EventMeshtasticApiTelemetryType,
    data: dict,
) -> None:
    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_TELEMETRY,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: node_id,
            ATTR_EVENT_MESHTASTIC_API_DATA: data,
            ATTR_EVENT_MESHTASTIC_API_TELEMETRY_TYPE: telemetry_type,
            ATTR_EVENT_MESHTASTIC_API_NODE_INFO: {"name": TEST_NODE["user"]["longName"]},
        },
    )


async def test_battery_entity_exists_without_initial_device_metrics(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    """Baseline entities (problem 7 / "always exist") must exist even with no deviceMetrics yet."""
    mock_nodes[TEST_NODE_NUM] = {k: v for k, v in TEST_NODE.items() if k != "deviceMetrics"}
    entry = _build_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


async def test_battery_zero_is_not_ignored(hass: HomeAssistant, mock_meshtastic_api_client, mock_nodes) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_telemetry(
        hass, entry, TEST_NODE_NUM, EventMeshtasticApiTelemetryType.DEVICE_METRICS, {"batteryLevel": 0, "voltage": 3.2}
    )
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == "0"


async def test_environment_metrics_create_sensors_on_first_packet(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID) is None

    _fire_telemetry(
        hass,
        entry,
        TEST_NODE_NUM,
        EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS,
        {"temperature": 21.5, "relativeHumidity": 45.0, "barometricPressure": 1013.0},
    )
    await hass.async_block_till_done()

    temp_state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert temp_state is not None
    assert temp_state.state == "21.5"
    assert hass.states.get(HUMIDITY_ENTITY_ID).state == "45.0"
    assert hass.states.get(PRESSURE_ENTITY_ID).state == "1013.0"


async def test_environment_lowercamelcase_fields_are_detected(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    """whiteLux/windSpeed etc must be picked up under their real MessageToDict() names (problem 4)."""
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_telemetry(
        hass,
        entry,
        TEST_NODE_NUM,
        EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS,
        {"whiteLux": 500.0, "windSpeed": 3.5, "windDirection": 270},
    )
    await hass.async_block_till_done()

    assert hass.states.get(WHITE_LUX_ENTITY_ID) is not None
    assert hass.states.get(WHITE_LUX_ENTITY_ID).state == "500.0"
    assert hass.states.get(WIND_SPEED_ENTITY_ID) is not None
    assert hass.states.get(WIND_SPEED_ENTITY_ID).state == "3.5"


async def test_air_quality_metrics_create_sensors(hass: HomeAssistant, mock_meshtastic_api_client, mock_nodes) -> None:
    """AirQualityMetrics must reach the coordinator (problem 3)."""
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_telemetry(
        hass,
        entry,
        TEST_NODE_NUM,
        EventMeshtasticApiTelemetryType.AIR_QUALITY_METRICS,
        {"pm25Standard": 12},
    )
    await hass.async_block_till_done()

    state = hass.states.get(AIR_QUALITY_PM25_ENTITY_ID)
    assert state is not None
    assert state.state == "12"


async def test_request_telemetry_updates_coordinator(hass: HomeAssistant, mock_nodes) -> None:
    """
    A manual meshtastic.request_telemetry call must update entities, not just return data (problem 2).

    Unlike the other tests in this module, this one does NOT use mock_meshtastic_api_client:
    that fixture replaces MeshtasticApiClient itself, which is exactly the class under test
    here. Instead it constructs a real MeshtasticApiClient with its aiomeshtastic interface
    mocked out below the request/response boundary, then asserts request_telemetry() drives
    the same update path a spontaneously received packet would (_on_telemetry -> coordinator
    event), not just the direct-response fast path.
    """
    with patch("custom_components.meshtastic.api.AioTcpConnection"):
        client = MeshtasticApiClient(
            data={CONF_CONNECTION_TYPE: ConnectionType.TCP.value, "tcp_host": "127.0.0.1", "tcp_port": 4403},
            hass=hass,
            config_entry_id="entry1",
        )

    telemetry = telemetry_pb2.Telemetry()
    telemetry.environment_metrics.temperature = 19.0
    telemetry.environment_metrics.relative_humidity = 40.0
    client._interface.request_telemetry = AsyncMock(return_value=telemetry)  # noqa: SLF001

    captured_events = []
    hass.bus.async_listen(
        EVENT_MESHTASTIC_API_TELEMETRY,
        lambda event: captured_events.append(event.data[ATTR_EVENT_MESHTASTIC_API_DATA]),
    )

    result = await client.request_telemetry(TEST_NODE_NUM, TelemetryType.ENVIRONMENT_METRICS)
    await hass.async_block_till_done()

    # The service response still contains the decoded data...
    assert result["environmentMetrics"]["temperature"] == 19.0
    # ...and the same data was routed through _on_telemetry -> the coordinator event,
    # exactly like a spontaneously received ENVIRONMENT_METRICS packet would be.
    assert any(data.get("temperature") == 19.0 for data in captured_events)
