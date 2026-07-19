# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import typing
from collections import defaultdict

from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_OPTION_FILTER_NODES, LOGGER

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Any

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import MeshtasticConfigEntry, MeshtasticData


def get_nodes(entry: MeshtasticConfigEntry) -> typing.Mapping[int, typing.Mapping[str, Any]]:
    filter_nodes = entry.options.get(CONF_OPTION_FILTER_NODES, [])
    filter_node_nums = [el["id"] for el in filter_nodes]
    if not entry.runtime_data.coordinator.data:
        return {}

    return {
        node_num: node_info
        for node_num, node_info in entry.runtime_data.coordinator.data.items()
        if node_num in filter_node_nums
    }


_remove_listeners = defaultdict(lambda: defaultdict(list))


async def setup_platform_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_factory: Callable[[typing.Mapping[int, typing.Mapping[str, Any]], MeshtasticData], Iterable[Entity]],
) -> None:
    async_add_entities(entity_factory(get_nodes(entry), entry.runtime_data))
    platform = entity_platform.async_get_current_platform()

    def on_coordinator_data_update() -> None:
        current_nodes = get_nodes(entry)
        entities = entity_factory(current_nodes, entry.runtime_data)
        new_entities = [s for s in entities if s.entity_id not in platform.entities]
        if new_entities:
            LOGGER.debug(
                "Dynamically adding %d new %s entities: %s",
                len(new_entities),
                platform.domain,
                [e.entity_id for e in new_entities],
            )
            async_add_entities(new_entities)

        # Gold quality-scale "dynamic-devices" pattern: remove entities for
        # nodes that are no longer selected/tracked. This deliberately only
        # checks node_id membership in current_nodes, not whether
        # entity_factory's *current* output still contains this exact
        # entity_id: a metric that's simply absent from a single coordinator
        # update (e.g. a momentary telemetry gap) must not delete its
        # entity - only an explicit deselection of the node should.
        stale_entity_ids = [
            entity_id
            for entity_id, entity in platform.entities.items()
            if getattr(entity, "node_id", None) is not None and entity.node_id not in current_nodes
        ]
        if stale_entity_ids:
            LOGGER.debug("Removing %d entities for untracked nodes: %s", len(stale_entity_ids), stale_entity_ids)
            entity_registry = er.async_get(hass)
            for entity_id in stale_entity_ids:
                entity_registry.async_remove(entity_id)

    remove_listener = entry.runtime_data.coordinator.async_add_listener(on_coordinator_data_update)
    _remove_listeners[platform.domain][entry.entry_id].append(remove_listener)


async def async_unload_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MeshtasticConfigEntry,
) -> bool:
    platform = entity_platform.async_get_current_platform()
    for remove_listener in _remove_listeners[platform.domain].pop(entry.entry_id, []):
        remove_listener()

    return True


async def fetch_meshtastic_hardware_names(hass: HomeAssistant) -> typing.Mapping[str, str]:
    try:
        session = async_get_clientsession(hass)
        async with session.get("https://api.meshtastic.org/resource/deviceHardware", raise_for_status=True) as response:
            response_json = await response.json()
            device_hardware_names = {h["hwModelSlug"]: h["displayName"] for h in response_json}
    except Exception:  # noqa: BLE001
        LOGGER.info("Failed to fetch meshtastic hardware infos", exc_info=True)
        device_hardware_names = {}
    return device_hardware_names
