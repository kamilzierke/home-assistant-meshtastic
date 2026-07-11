# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class CannotConnectError(HomeAssistantError):
    """Raised when the config flow could not connect to a Meshtastic device."""
