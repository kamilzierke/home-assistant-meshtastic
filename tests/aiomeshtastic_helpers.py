# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Shared helpers for building aiomeshtastic protobuf test fixtures."""

from __future__ import annotations

from google.protobuf.message import Message

from custom_components.meshtastic.aiomeshtastic.protobuf import mesh_pb2, portnums_pb2


def build_from_radio_packet(  # noqa: PLR0913
    *,
    from_id: int,
    port_num: portnums_pb2.PortNum.ValueType,
    payload: Message | bytes,
    to_id: int = 0xFFFFFFFF,
    rx_rssi: int | None = None,
    rx_snr: float | None = None,
    rx_time: int | None = None,
) -> mesh_pb2.FromRadio:
    """Build a FromRadio wrapping a decoded MeshPacket, as seen when received off the wire."""
    from_radio = mesh_pb2.FromRadio()
    packet = from_radio.packet
    packet.__setattr__("from", from_id)
    packet.to = to_id
    packet.decoded.portnum = port_num
    packet.decoded.payload = payload.SerializeToString() if isinstance(payload, Message) else payload
    if rx_rssi is not None:
        packet.rx_rssi = rx_rssi
    if rx_snr is not None:
        packet.rx_snr = rx_snr
    if rx_time is not None:
        packet.rx_time = rx_time
    return from_radio
