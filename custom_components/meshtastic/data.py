# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_component import EntityComponent
    from homeassistant.loader import Integration

    from .api import MeshtasticApiClient
    from .coordinator import MeshtasticDataUpdateCoordinator
    from .entity import MeshtasticEntity


type MeshtasticConfigEntry = ConfigEntry[MeshtasticData]


@dataclass
class MeshtasticData:
    client: MeshtasticApiClient
    coordinator: MeshtasticDataUpdateCoordinator
    integration: Integration
    gateway_node: dict


DATA_COMPONENT: HassKey[EntityComponent[MeshtasticEntity]] = HassKey(DOMAIN)
# Whether the shared meshtastic_web frontend/HTTP views have been registered
# for this hass instance yet (they're shared across config entries, so only
# the first entry that enables the web client needs to set them up, and they
# should only be torn down once no entry has it enabled anymore).
DATA_WEB_CLIENT_LOADED: HassKey[bool] = HassKey(f"{DOMAIN}_web_client_loaded")
