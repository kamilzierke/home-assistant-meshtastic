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
# Whether the meshtastic_web HTTP views/static paths have been registered
# with hass.http for this process. These cannot be unregistered once added
# (Home Assistant/aiohttp has no API for it), so - unlike DATA_WEB_CLIENT_LOADED
# below - this flag is only ever set, never cleared, and must guard against
# calling meshtastic_web.async_setup() more than once per process; doing so a
# second time raises (duplicate route registration) and used to happen on
# every reload after the web client had been enabled and then any config
# entry got unloaded/reloaded once (e.g. after any options-flow save).
DATA_WEB_VIEWS_REGISTERED: HassKey[bool] = HassKey(f"{DOMAIN}_web_views_registered")
# Whether the shared meshtastic_web sidebar panel is currently registered.
# Unlike the HTTP views above, panels *can* be added/removed cleanly, so this
# tracks the "is at least one config entry currently requesting the web
# client" state and toggles across reloads/unloads as expected.
DATA_WEB_CLIENT_LOADED: HassKey[bool] = HassKey(f"{DOMAIN}_web_client_loaded")
