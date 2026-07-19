# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""Unit tests for DiscoveredFieldsCache (problem 7)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.meshtastic.discovery_cache import STORAGE_VERSION, DiscoveredFieldsCache

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

NODE_ID = 222222222


async def test_record_discovers_and_dedupes_fields(hass: HomeAssistant) -> None:
    cache = DiscoveredFieldsCache(hass, "entry1")

    assert cache.record(NODE_ID, {"environmentMetrics": {"temperature": 21.5}}) is True
    assert cache.record(NODE_ID, {"environmentMetrics": {"temperature": 22.0}}) is False


async def test_merge_into_seeds_placeholders_without_clobbering_real_values(hass: HomeAssistant) -> None:
    cache = DiscoveredFieldsCache(hass, "entry1")
    cache.record(NODE_ID, {"environmentMetrics": {"temperature": 21.5, "relativeHumidity": 50.0}})

    node_data = {"num": NODE_ID, "environmentMetrics": {"temperature": 23.0}}
    cache.merge_into(NODE_ID, node_data)

    assert node_data["environmentMetrics"]["temperature"] == 23.0
    assert node_data["environmentMetrics"]["relativeHumidity"] is None


async def test_round_trip_through_real_store(hass: HomeAssistant) -> None:
    cache = DiscoveredFieldsCache(hass, "entry1")
    cache.record(NODE_ID, {"position": {"satsInView": 5}})
    await cache.async_save_now()

    reloaded = DiscoveredFieldsCache(hass, "entry1")
    await reloaded.async_load()

    node_data: dict = {}
    reloaded.merge_into(NODE_ID, node_data)
    assert node_data == {"position": {"satsInView": None}}


async def test_corrupt_cache_does_not_raise(hass: HomeAssistant) -> None:
    cache = DiscoveredFieldsCache(hass, "entry1")
    cache._store.async_load = AsyncMock(return_value={"not": "the expected shape"})  # noqa: SLF001

    await cache.async_load()  # must not raise

    node_data: dict = {}
    cache.merge_into(NODE_ID, node_data)
    assert node_data == {}


async def test_unsupported_version_starts_empty(hass: HomeAssistant) -> None:
    cache = DiscoveredFieldsCache(hass, "entry1")
    cache._store.async_load = AsyncMock(return_value={"version": STORAGE_VERSION + 1, "nodes": {}})  # noqa: SLF001

    await cache.async_load()

    node_data: dict = {}
    cache.merge_into(NODE_ID, node_data)
    assert node_data == {}


async def test_prune_untracked_removes_deselected_node(hass: HomeAssistant) -> None:
    cache = DiscoveredFieldsCache(hass, "entry1")
    cache.record(NODE_ID, {"environmentMetrics": {"temperature": 21.5}})

    assert cache.prune_untracked([]) is True

    node_data: dict = {}
    cache.merge_into(NODE_ID, node_data)
    assert node_data == {}
