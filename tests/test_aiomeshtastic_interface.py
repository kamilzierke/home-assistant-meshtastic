# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""
Unit tests for MeshInterface packet processing (problems 1 and 5).

These exercise MeshInterface's internal packet-handling methods directly against a
mocked connection, without a real radio/TCP/BLE transport - the methods under test
(_process_packet_for_app_listener, _process_node_info) don't touch self._connection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.meshtastic.aiomeshtastic.interface import MeshInterface
from custom_components.meshtastic.aiomeshtastic.protobuf import portnums_pb2, telemetry_pb2

from .aiomeshtastic_helpers import build_from_radio_packet

NODE_ID = 0x12345678


@pytest.fixture
def interface() -> MeshInterface:
    return MeshInterface(connection=MagicMock())


async def test_telemetry_before_nodeinfo_creates_node(interface: MeshInterface) -> None:
    """A TELEMETRY_APP packet from an unknown node must not be dropped (problem 1)."""
    telemetry = telemetry_pb2.Telemetry()
    telemetry.device_metrics.battery_level = 42
    from_radio = build_from_radio_packet(
        from_id=NODE_ID, port_num=portnums_pb2.PortNum.TELEMETRY_APP, payload=telemetry
    )

    await interface._process_packet_for_app_listener(from_radio)  # noqa: SLF001

    assert NODE_ID in interface._node_database  # noqa: SLF001
    assert interface._node_database[NODE_ID]["deviceMetrics"]["batteryLevel"] == 42  # noqa: SLF001


async def test_position_before_nodeinfo_creates_node(interface: MeshInterface) -> None:
    from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2

    position = mesh_pb2.Position()
    position.latitude_i = 123456789
    from_radio = build_from_radio_packet(from_id=NODE_ID, port_num=portnums_pb2.PortNum.POSITION_APP, payload=position)

    await interface._process_packet_for_app_listener(from_radio)  # noqa: SLF001

    assert NODE_ID in interface._node_database  # noqa: SLF001
    assert "position" in interface._node_database[NODE_ID]  # noqa: SLF001


async def test_telemetry_does_not_create_broadcast_node(interface: MeshInterface) -> None:
    telemetry = telemetry_pb2.Telemetry()
    telemetry.device_metrics.battery_level = 10
    from_radio = build_from_radio_packet(
        from_id=MeshInterface.BROADCAST_NUM, port_num=portnums_pb2.PortNum.TELEMETRY_APP, payload=telemetry
    )

    await interface._process_packet_for_app_listener(from_radio)  # noqa: SLF001

    assert MeshInterface.BROADCAST_NUM not in interface._node_database  # noqa: SLF001


async def test_nodeinfo_after_telemetry_enriches_existing_entry(interface: MeshInterface) -> None:
    from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2

    telemetry = telemetry_pb2.Telemetry()
    telemetry.device_metrics.battery_level = 42
    telemetry_packet = build_from_radio_packet(
        from_id=NODE_ID, port_num=portnums_pb2.PortNum.TELEMETRY_APP, payload=telemetry
    )
    await interface._process_packet_for_app_listener(telemetry_packet)  # noqa: SLF001

    node_info_from_radio = mesh_pb2.FromRadio()
    node_info_from_radio.node_info.num = NODE_ID
    node_info_from_radio.node_info.user.id = "!12345678"
    node_info_from_radio.node_info.user.long_name = "Test Node"
    node_info_from_radio.node_info.user.short_name = "TN"
    await interface._process_node_info(node_info_from_radio)  # noqa: SLF001

    node = interface._node_database[NODE_ID]  # noqa: SLF001
    assert node["user"]["longName"] == "Test Node"
    # Telemetry received earlier must survive the later NodeInfo enrichment.
    assert node["deviceMetrics"]["batteryLevel"] == 42


async def test_rssi_is_stored_on_node(interface: MeshInterface) -> None:
    from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2

    node_info_from_radio = mesh_pb2.FromRadio()
    node_info_from_radio.packet.__setattr__("from", NODE_ID)
    node_info_from_radio.packet.rx_rssi = -73
    node_info_from_radio.packet.rx_snr = 4.5

    await interface._process_node_info(node_info_from_radio)  # noqa: SLF001

    node = interface._node_database[NODE_ID]  # noqa: SLF001
    assert node["rssi"] == -73
    assert node["snr"] == 4.5


async def test_rssi_not_overwritten_by_none(interface: MeshInterface) -> None:
    from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2

    good_rssi = mesh_pb2.FromRadio()
    good_rssi.packet.__setattr__("from", NODE_ID)
    good_rssi.packet.rx_rssi = -50
    await interface._process_node_info(good_rssi)  # noqa: SLF001
    assert interface._node_database[NODE_ID]["rssi"] == -50  # noqa: SLF001

    # A subsequent packet without a measured RSSI (e.g. relayed via MQTT) must not
    # clobber the last known-good value.
    no_rssi = mesh_pb2.FromRadio()
    no_rssi.packet.__setattr__("from", NODE_ID)
    await interface._process_node_info(no_rssi)  # noqa: SLF001
    assert interface._node_database[NODE_ID]["rssi"] == -50  # noqa: SLF001
