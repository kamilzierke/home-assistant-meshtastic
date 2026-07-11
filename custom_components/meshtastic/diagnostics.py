# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import MeshtasticConfigEntry

# Channel pre-shared keys, PKI key material, node GPS coordinates and
# hardware addresses are personal/security sensitive and must not be
# included verbatim in a diagnostics dump.
TO_REDACT = {
    "psk",
    "public_key",
    "private_key",
    "admin_key",
    "macaddr",
    "bluetooth_address",
    "latitude",
    "longitude",
    "latitude_i",
    "longitude_i",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MeshtasticConfigEntry,
) -> dict[str, Any]:
    runtime_data = entry.runtime_data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "gateway_node": async_redact_data(runtime_data.gateway_node, TO_REDACT) if runtime_data else None,
        "coordinator_data": async_redact_data(dict(runtime_data.coordinator.data or {}), TO_REDACT)
        if runtime_data and runtime_data.coordinator.data
        else None,
        "coordinator_last_update_success": runtime_data.coordinator.last_update_success if runtime_data else None,
    }
