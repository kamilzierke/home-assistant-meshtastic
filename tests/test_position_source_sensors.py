# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""
Integration tests for position.locationSource / position.altitudeSource sensors.

These fields are proto3 enums rendered by MessageToDict() as strings (e.g.
"LOC_MANUAL"), not numbers. Declaring them with the SensorEntityDescription default
state_class (MEASUREMENT) makes Home Assistant try to parse that string as a number
and raise ValueError out of the sensor's `state` property on every coordinator update
- these tests exercise the real Home Assistant state-write path (not value_fn in
isolation) so a regression here is caught the same way it showed up in production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meshtastic.api import (
    ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID,
    ATTR_EVENT_MESHTASTIC_API_DATA,
    ATTR_EVENT_MESHTASTIC_API_NODE,
    ATTR_EVENT_MESHTASTIC_API_NODE_INFO,
    EVENT_MESHTASTIC_API_POSITION,
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
    import pytest
    from homeassistant.core import HomeAssistant

LOCATION_SOURCE_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_location_source"
ALTITUDE_SOURCE_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_altitude_source"

# Numeric GNSS sensors that must be unaffected by the locationSource/altitudeSource fix.
SATS_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_satellites_in_view"
ALTITUDE_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_altitude"
GROUND_SPEED_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_ground_speed"
GROUND_TRACK_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_ground_track"
PDOP_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_pdop"
HDOP_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_hdop"
VDOP_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_vdop"
GPS_ACCURACY_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_gps_accuracy"
PRECISION_BITS_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_precision_bits"
SEQ_NUMBER_ENTITY_ID = f"sensor.{DOMAIN}_tgw1_{TEST_NODE_NUM}_position_seq_number"

# Text seen in the production traceback this regression test protects against.
_CRASH_LOG_NEEDLE = "has state class"


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
    enriched = dict(data)
    if "latitudeI" in enriched:
        enriched["latitude"] = float(enriched["latitudeI"] * 10**-7)
    if "longitudeI" in enriched:
        enriched["longitude"] = float(enriched["longitudeI"] * 10**-7)

    hass.bus.async_fire(
        EVENT_MESHTASTIC_API_POSITION,
        {
            ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_EVENT_MESHTASTIC_API_NODE: node_id,
            ATTR_EVENT_MESHTASTIC_API_DATA: enriched,
            ATTR_EVENT_MESHTASTIC_API_NODE_INFO: {"name": TEST_NODE["user"]["longName"]},
        },
    )


async def test_location_source_manual_is_textual_state(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "locationSource": "LOC_MANUAL"}
    )
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_SOURCE_ENTITY_ID)
    assert state is not None
    assert state.state == "LOC_MANUAL"
    assert state.attributes.get("state_class") is None
    assert _CRASH_LOG_NEEDLE not in caplog.text


async def test_location_source_internal_is_not_coerced_to_number(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "locationSource": "LOC_INTERNAL"}
    )
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_SOURCE_ENTITY_ID)
    assert state is not None
    assert state.state == "LOC_INTERNAL"
    with_exc_raised = [r for r in caplog.records if r.levelname in ("ERROR", "WARNING") and "ValueError" in r.message]
    assert not with_exc_raised


async def test_location_source_unset_does_not_raise_and_has_no_numeric_state(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LOC_UNSET must never surface as a literal 'LOC_UNSET' numeric-looking state, and must never crash the write."""
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "locationSource": "LOC_UNSET"}
    )
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_SOURCE_ENTITY_ID)
    assert state is not None
    # native_value is None for LOC_UNSET. MeshtasticNodeEntity.available reflects
    # coordinator/node reachability only, not the individual field's value, so a
    # tracked, reachable node reports "unknown" here (value not determined) rather
    # than "unavailable" (device unreachable) - same convention already established
    # for every other MeshtasticSensor with a missing field (see commit 6ea6c1d).
    assert state.state == "unknown"
    assert state.state != "LOC_UNSET"
    assert _CRASH_LOG_NEEDLE not in caplog.text


async def test_altitude_source_gps_is_textual_state(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "altitudeSource": "ALT_GPS"}
    )
    await hass.async_block_till_done()

    state = hass.states.get(ALTITUDE_SOURCE_ENTITY_ID)
    assert state is not None
    assert state.state == "ALT_GPS"
    assert state.attributes.get("state_class") is None
    assert _CRASH_LOG_NEEDLE not in caplog.text


async def test_altitude_source_unset_does_not_raise(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "altitudeSource": "ALT_UNSET"}
    )
    await hass.async_block_till_done()

    state = hass.states.get(ALTITUDE_SOURCE_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    assert state.state != "ALT_UNSET"
    assert _CRASH_LOG_NEEDLE not in caplog.text


async def test_multi_node_coordinator_update_does_not_raise_a_series_of_exceptions(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reproduce the production traceback.

    Several nodes' locationSource/altitudeSource update in the same coordinator
    refresh, each going through _handle_coordinator_update and a real
    async_write_ha_state() call.
    """
    node_a = TEST_NODE_NUM
    node_b = TEST_NODE_NUM + 1
    node_c = TEST_NODE_NUM + 2
    extra_nodes = {
        node_a: {**TEST_NODE, "num": node_a},
        node_b: {**TEST_NODE, "num": node_b, "user": {**TEST_NODE["user"], "id": "!0d422b91"}},
        node_c: {**TEST_NODE, "num": node_c, "user": {**TEST_NODE["user"], "id": "!0d422b92"}},
    }
    mock_meshtastic_api_client.async_get_all_nodes.return_value = {
        GATEWAY_NODE_NUM: mock_nodes[GATEWAY_NODE_NUM],
        **extra_nodes,
    }

    entry = MockConfigEntry(
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
            CONF_OPTION_FILTER_NODES: [{"id": n, "name": "n"} for n in (node_a, node_b, node_c)],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for node_id, location_source, altitude_source in (
        (node_a, "LOC_MANUAL", "ALT_MANUAL"),
        (node_b, "LOC_UNSET", "ALT_UNSET"),
        (node_c, "LOC_INTERNAL", "ALT_GPS"),
    ):
        _fire_position(
            hass,
            entry,
            node_id,
            {
                "latitudeI": 473000000,
                "longitudeI": 85000000,
                "locationSource": location_source,
                "altitudeSource": altitude_source,
            },
        )
    await hass.async_block_till_done()

    assert _CRASH_LOG_NEEDLE not in caplog.text

    for node_id, expected_location, expected_altitude in (
        (node_a, "LOC_MANUAL", "ALT_MANUAL"),
        (node_c, "LOC_INTERNAL", "ALT_GPS"),
    ):
        location_state = hass.states.get(f"sensor.{DOMAIN}_tgw1_{node_id}_position_location_source")
        altitude_state = hass.states.get(f"sensor.{DOMAIN}_tgw1_{node_id}_position_altitude_source")
        assert location_state is not None
        assert location_state.state == expected_location
        assert altitude_state is not None
        assert altitude_state.state == expected_altitude

    unset_location_state = hass.states.get(f"sensor.{DOMAIN}_tgw1_{node_b}_position_location_source")
    assert unset_location_state is not None
    assert unset_location_state.state == "unknown"


async def test_numeric_gnss_sensors_are_unaffected(
    hass: HomeAssistant,
    mock_meshtastic_api_client,
    mock_nodes,
) -> None:
    """Confirms the locationSource/altitudeSource fix does not regress numeric GNSS sensors."""
    entry = _build_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _fire_position(
        hass,
        entry,
        TEST_NODE_NUM,
        {
            "latitudeI": 473000000,
            "longitudeI": 85000000,
            "satsInView": 9,
            "altitude": 450,
            "groundSpeed": 3,
            "groundTrack": 12345,
            "PDOP": 120,
            "HDOP": 145,
            "VDOP": 160,
            "gpsAccuracy": 2500,
            "precisionBits": 16,
            "seqNumber": 42,
        },
    )
    await hass.async_block_till_done()

    numeric_measurement_entities = {
        SATS_ENTITY_ID: "9",
        ALTITUDE_ENTITY_ID: "450",
        GROUND_TRACK_ENTITY_ID: "123.45",
        PDOP_ENTITY_ID: "1.2",
        HDOP_ENTITY_ID: "1.45",
        VDOP_ENTITY_ID: "1.6",
        GPS_ACCURACY_ENTITY_ID: "2500",
        PRECISION_BITS_ENTITY_ID: "16",
    }
    for entity_id, expected_state in numeric_measurement_entities.items():
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == expected_state
        assert state.attributes.get("state_class") == "measurement"

    # groundSpeed has device_class=SPEED, which - like windSpeed (see test_telemetry.py) -
    # triggers Home Assistant's unit-system display conversion (m/s -> km/h here); only
    # check it exists with a numeric reading, not the exact displayed number.
    ground_speed_state = hass.states.get(GROUND_SPEED_ENTITY_ID)
    assert ground_speed_state is not None
    assert float(ground_speed_state.state) > 0
    assert ground_speed_state.attributes.get("state_class") == "measurement"

    seq_state = hass.states.get(SEQ_NUMBER_ENTITY_ID)
    assert seq_state is not None
    assert seq_state.state == "42"
    assert seq_state.attributes.get("state_class") == "total_increasing"


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


async def test_cached_unset_source_survives_restart_without_raising(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Confirm a previously-cached LOC_UNSET/ALT_UNSET field restores cleanly.

    A node whose locationSource/altitudeSource were previously discovered as
    LOC_UNSET/ALT_UNSET must still restore cleanly after a restart (problem 8): the
    discovery cache only remembers field *names*, not their last value, so on reload
    the placeholder is `None` regardless of what was last observed - this must not
    raise and must not resurrect the raw enum string as a state.
    """
    entry = _build_entry()
    entry.add_to_hass(hass)

    boot1_nodes = {GATEWAY_NODE_NUM: GATEWAY_NODE, TEST_NODE_NUM: TEST_NODE}
    with patch("custom_components.meshtastic.MeshtasticApiClient", return_value=_make_mock_client(boot1_nodes)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    _fire_position(
        hass, entry, TEST_NODE_NUM, {"latitudeI": 473000000, "longitudeI": 85000000, "locationSource": "LOC_UNSET"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(LOCATION_SOURCE_ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_remove(LOCATION_SOURCE_ENTITY_ID)

    boot2_nodes = {GATEWAY_NODE_NUM: GATEWAY_NODE, TEST_NODE_NUM: TEST_NODE}
    with patch("custom_components.meshtastic.MeshtasticApiClient", return_value=_make_mock_client(boot2_nodes)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(LOCATION_SOURCE_ENTITY_ID)
    assert state is not None, "previously discovered locationSource sensor must be rebuilt from the discovery cache"
    assert state.state == "unknown"
    assert state.state != "LOC_UNSET"
    assert _CRASH_LOG_NEEDLE not in caplog.text
