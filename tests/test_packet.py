# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Unit tests for aiomeshtastic.packet.Packet, in particular rx_rssi (problem 5)."""

from __future__ import annotations

from custom_components.meshtastic.aiomeshtastic.packet import Packet
from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2, portnums_pb2

from .aiomeshtastic_helpers import build_from_radio_packet


def test_rx_rssi_returns_negative_value() -> None:
    from_radio = build_from_radio_packet(
        from_id=123, port_num=portnums_pb2.PortNum.TEXT_MESSAGE_APP, payload=b"hi", rx_rssi=-87
    )
    assert Packet(from_radio).rx_rssi == -87


def test_rx_rssi_none_when_unset() -> None:
    from_radio = build_from_radio_packet(from_id=123, port_num=portnums_pb2.PortNum.TEXT_MESSAGE_APP, payload=b"hi")
    assert Packet(from_radio).rx_rssi is None


def test_rx_rssi_zero_is_treated_as_unmeasured() -> None:
    from_radio = build_from_radio_packet(
        from_id=123, port_num=portnums_pb2.PortNum.TEXT_MESSAGE_APP, payload=b"hi", rx_rssi=0
    )
    assert Packet(from_radio).rx_rssi is None


def test_rx_rssi_none_without_mesh_packet() -> None:
    from_radio = mesh_pb2.FromRadio()
    from_radio.config_complete_id = 1
    assert Packet(from_radio).rx_rssi is None
