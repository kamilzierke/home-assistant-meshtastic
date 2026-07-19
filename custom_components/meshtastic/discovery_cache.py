# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

"""
Persistent cache of which telemetry/position fields have been seen per node.

Dynamically-created sensors (environment metrics, power metrics, GNSS details, ...)
are only built for fields the coordinator has actually seen for a node. Without this
cache, that means a Home Assistant restart drops those sensors entirely until the
next matching packet arrives, instead of restoring them as `unavailable` - see
meshtastic/home-assistant issue on entity restore behavior.

This cache remembers, per node and per metric category, which field names have ever
been reported, and coordinator.py merges that schema (as `None`-valued placeholders)
into freshly loaded node data before building entities, so previously-discovered
sensors always exist even when the current data is empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, MutableMapping

    from homeassistant.core import HomeAssistant

_LOGGER = LOGGER.getChild(__name__.removeprefix(f"{LOGGER.name}."))

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.discovered_fields"

# Debounce delay for persisting newly discovered fields to disk. Repeated
# discoveries (e.g. several new environment fields arriving in the same burst of
# packets) collapse into a single write instead of one per field.
CACHE_SAVE_DELAY = 10

# Node-data categories that are scanned for newly discovered fields, and therefore
# get restored (as unavailable placeholders) after a Home Assistant restart.
DISCOVERY_CATEGORIES: tuple[str, ...] = (
    "deviceMetrics",
    "localStats",
    "environmentMetrics",
    "powerMetrics",
    "airQualityMetrics",
    "healthMetrics",
    "hostMetrics",
    "trafficManagementStats",
    "position",
)


class DiscoveredFieldsCache:
    """Per config-entry cache of discovered telemetry/position field names."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}")
        self._nodes: dict[str, dict[str, list[str]]] = {}
        self._dirty = False

    async def async_load(self) -> None:
        """Load the cache from disk, tolerating a missing or corrupt store."""
        try:
            raw = await self._store.async_load()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Failed to load discovered field cache, starting empty", exc_info=True)
            self._nodes = {}
            return

        if not raw or not isinstance(raw, dict) or raw.get("version") != STORAGE_VERSION:
            if raw:
                _LOGGER.debug("Discovered field cache has unsupported format/version, starting empty")
            self._nodes = {}
            return

        nodes = raw.get("nodes")
        if not isinstance(nodes, dict):
            self._nodes = {}
            return

        parsed: dict[str, dict[str, list[str]]] = {}
        for node_key, categories in nodes.items():
            if not isinstance(categories, dict):
                continue
            parsed[node_key] = {
                category: sorted({str(field) for field in fields})
                for category, fields in categories.items()
                if isinstance(fields, list)
            }
        self._nodes = parsed
        _LOGGER.debug("Loaded discovered field cache for %d node(s)", len(self._nodes))

    def merge_into(self, node_id: int, node_data: MutableMapping[str, Any]) -> None:
        """Seed `node_data` with `None` placeholders for previously-discovered fields."""
        cached = self._nodes.get(str(node_id))
        if not cached:
            return

        for category, fields in cached.items():
            bucket = node_data.setdefault(category, {})
            if not isinstance(bucket, dict):
                continue
            for field in fields:
                bucket.setdefault(field, None)

    def record(self, node_id: int, node_data: Mapping[str, Any]) -> bool:
        """Record any newly-seen fields for `node_id`. Returns True if the cache changed."""
        changed = False
        node_key = str(node_id)
        cached = self._nodes.setdefault(node_key, {})

        for category in DISCOVERY_CATEGORIES:
            value = node_data.get(category)
            if not isinstance(value, dict) or not value:
                continue

            existing = set(cached.get(category, []))
            new_fields = set(value.keys()) - existing
            if new_fields:
                _LOGGER.debug("Discovered new %s field(s) for node %s: %s", category, node_id, sorted(new_fields))
                cached[category] = sorted(existing | new_fields)
                changed = True

        if changed:
            self._dirty = True
        return changed

    def prune_untracked(self, tracked_node_ids: Iterable[int]) -> bool:
        """Drop cached nodes no longer tracked by the config entry. Returns True if changed."""
        tracked_keys = {str(node_id) for node_id in tracked_node_ids}
        stale_keys = [key for key in self._nodes if key not in tracked_keys]
        for key in stale_keys:
            _LOGGER.debug("Removing discovered field cache for untracked node %s", key)
            del self._nodes[key]

        if stale_keys:
            self._dirty = True
        return bool(stale_keys)

    def forget_node(self, node_id: int) -> bool:
        removed = self._nodes.pop(str(node_id), None) is not None
        if removed:
            self._dirty = True
        return removed

    def async_save_debounced(self) -> None:
        if not self._dirty:
            return
        self._store.async_delay_save(self._data_to_save, CACHE_SAVE_DELAY)

    async def async_save_now(self) -> None:
        if not self._dirty:
            return
        await self._store.async_save(self._data_to_save())
        self._dirty = False

    def _data_to_save(self) -> dict[str, Any]:
        self._dirty = False
        return {"version": STORAGE_VERSION, "nodes": self._nodes}
