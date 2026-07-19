# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID,
    ATTR_EVENT_MESHTASTIC_API_DATA,
    ATTR_EVENT_MESHTASTIC_API_NODE,
    EVENT_MESHTASTIC_API_NODE_UPDATED,
    EVENT_MESHTASTIC_API_POSITION,
    EVENT_MESHTASTIC_API_TELEMETRY,
    EventMeshtasticApiTelemetryType,
    MeshtasticApiClientError,
)
from .const import CONF_OPTION_FILTER_NODES, DOMAIN, LOGGER
from .discovery_cache import DiscoveredFieldsCache

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import Event, HomeAssistant, _DataT

    from .data import MeshtasticConfigEntry

# Maps a telemetry event type to the key it is stored under in a node's coordinator
# data dict. Kept in sync with api.TELEMETRY_VARIANTS, which maps the other
# direction (MessageToDict() field name -> event type). Adding a telemetry variant
# is a one-line addition to each of these two maps rather than a new if/elif branch.
TELEMETRY_TYPE_TO_DATA_KEY: Mapping[EventMeshtasticApiTelemetryType, str] = {
    EventMeshtasticApiTelemetryType.DEVICE_METRICS: "deviceMetrics",
    EventMeshtasticApiTelemetryType.LOCAL_STATS: "localStats",
    EventMeshtasticApiTelemetryType.ENVIRONMENT_METRICS: "environmentMetrics",
    EventMeshtasticApiTelemetryType.POWER_METRICS: "powerMetrics",
    EventMeshtasticApiTelemetryType.AIR_QUALITY_METRICS: "airQualityMetrics",
    EventMeshtasticApiTelemetryType.HEALTH_METRICS: "healthMetrics",
    EventMeshtasticApiTelemetryType.HOST_METRICS: "hostMetrics",
    EventMeshtasticApiTelemetryType.TRAFFIC_MANAGEMENT_STATS: "trafficManagementStats",
}


def meshtastic_api_event_callback(f):  # noqa: ANN001, ANN201
    @wraps(f)
    async def wrapper(self: MeshtasticDataUpdateCoordinator, event: Event[_DataT]):  # noqa: ANN202, PLR0911
        try:
            if self.config_entry is None:
                return None

            event_data = deepcopy(event.data)
            config_entry_id = event_data.pop(ATTR_EVENT_MESHTASTIC_API_CONFIG_ENTRY_ID, None)
            if config_entry_id != self.config_entry.entry_id:
                return None

            if not self.data:
                self._logger.debug("Received event but coordinator is not yet initialized")
                return None

            node_id = event_data.get(ATTR_EVENT_MESHTASTIC_API_NODE, None)
            if node_id is None:
                return None

            if not self._ensure_tracked_node(node_id):
                self._logger.debug("Node %s not tracked by config entry, ignoring event", node_id)
                return None

            data = event_data.get(ATTR_EVENT_MESHTASTIC_API_DATA, None)
            if data is None:
                self._logger.debug("Event did not contain data")
                return None

            additional_event_data = {
                k: v
                for k, v in event_data.items()
                if k not in [ATTR_EVENT_MESHTASTIC_API_NODE, ATTR_EVENT_MESHTASTIC_API_DATA]
            }

            return await f(self, node_id, data, **additional_event_data)
        except:  # noqa: E722
            self._logger.warning("Failed to handle meshtastic api event", exc_info=True)

    return wrapper


class MeshtasticDataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    config_entry: MeshtasticConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self._logger = LOGGER.getChild(self.__class__.__name__)
        self._hass = hass
        self._discovery_cache: DiscoveredFieldsCache | None = None
        self._remove_event_listeners = []
        self._remove_event_listeners.append(
            hass.bus.async_listen(EVENT_MESHTASTIC_API_NODE_UPDATED, self._api_node_updated)
        )
        self._remove_event_listeners.append(hass.bus.async_listen(EVENT_MESHTASTIC_API_TELEMETRY, self._api_telemetry))
        self._remove_event_listeners.append(hass.bus.async_listen(EVENT_MESHTASTIC_API_POSITION, self._api_position))

    async def async_setup_discovery_cache(self) -> None:
        """
        Load the persistent discovered-fields cache.

        Must be called once config_entry has been assigned and before the first
        coordinator refresh, so _async_update_data() can merge cached field
        placeholders into the first batch of node data.
        """
        self._discovery_cache = DiscoveredFieldsCache(self._hass, self.config_entry.entry_id)
        await self._discovery_cache.async_load()

    async def async_shutdown(self) -> None:
        await super().async_shutdown()

        if self._discovery_cache is not None:
            try:
                await self._discovery_cache.async_save_now()
            except Exception:  # noqa: BLE001
                self._logger.debug("Could not flush discovered field cache", exc_info=True)

        for remove_listener in self._remove_event_listeners:
            try:
                remove_listener()
            except:  # noqa: E722
                self._logger.debug("Could not remove event listeners", exc_info=True)

    def _tracked_node_ids(self) -> set[int]:
        filter_nodes = self.config_entry.options.get(CONF_OPTION_FILTER_NODES, [])
        return {el["id"] for el in filter_nodes}

    def _ensure_tracked_node(self, node_id: int) -> bool:
        """
        Ensure `node_id` has at least a minimal record in coordinator data.

        Returns False if the node isn't among the config entry's selected nodes, in
        which case the caller must ignore the event: a packet from some other node
        on the mesh must not silently auto-import it as a tracked node -
        CONF_OPTION_FILTER_NODES is the single source of truth for that (see
        _setup_meshtastic_devices in __init__.py, which uses the same option).
        """
        if node_id in self.data:
            return True

        if node_id not in self._tracked_node_ids():
            return False

        self._logger.debug("Creating minimal coordinator record for tracked node %s", node_id)
        self.data[node_id] = {"num": node_id}
        return True

    def _record_discovery(self, node_id: int, node_data: Mapping[str, Any]) -> None:
        if self._discovery_cache is None:
            return
        if self._discovery_cache.record(node_id, node_data):
            self._discovery_cache.async_save_debounced()

    @meshtastic_api_event_callback
    async def _api_node_updated(self, node_id: int, node_data: Mapping[str, Any], **kwargs) -> None:  # noqa: ANN003, ARG002
        if self.data[node_id] != node_data:
            data = deepcopy(self.data)
            data[node_id].update(node_data)
            self._record_discovery(node_id, data[node_id])
            self.async_set_updated_data(data)

    @meshtastic_api_event_callback
    async def _api_telemetry(
        self,
        node_id: int,
        data: Mapping[str, Any],
        *,
        telemetry_type: EventMeshtasticApiTelemetryType,
        **kwargs,  # noqa: ANN003, ARG002
    ) -> None:
        metric_type = TELEMETRY_TYPE_TO_DATA_KEY.get(telemetry_type)
        if metric_type is None:
            self._logger.warning("Unsupported telemetry type %s", telemetry_type)
            return

        new_metrics = data
        existing_metrics = self.data[node_id].get(metric_type, None)
        if existing_metrics == new_metrics:
            self._logger.debug("Received telemetry identical to existing metrics, ignoring event")
            return

        updated = deepcopy(self.data)
        updated[node_id][metric_type] = new_metrics
        self._logger.debug("Updating coordinator %s for node %s", metric_type, node_id)
        self._record_discovery(node_id, updated[node_id])
        self.async_set_updated_data(updated)

    @meshtastic_api_event_callback
    async def _api_position(
        self,
        node_id: int,
        data: Mapping[str, Any],
        **kwargs,  # noqa: ANN003, ARG002
    ) -> None:
        new_position = data
        existing_position = self.data[node_id].get("position", {})
        if existing_position == new_position:
            self._logger.debug("Received position identical to existing position, ignoring event")
            return

        updated = deepcopy(self.data)
        updated[node_id]["position"] = new_position
        self._logger.debug("Updating coordinator position for node %s", node_id)
        self._record_discovery(node_id, updated[node_id])
        self.async_set_updated_data(updated)

    async def _async_update_data(self) -> Any:
        if self.config_entry is None or self.config_entry.runtime_data is None:
            self._logger.warning("Update data requested but config entry is empty")
            return None

        try:
            node_infos = await self.config_entry.runtime_data.client.async_get_all_nodes()

            tracked_node_ids = self._tracked_node_ids()
            data: dict[int, dict[str, Any]] = {
                node_num: dict(deepcopy(node_info))
                for node_num, node_info in node_infos.items()
                if node_num in tracked_node_ids
            }

            # A node selected in the config entry may not have sent anything yet
            # this session (e.g. right after a Home Assistant restart) - seed a
            # minimal record for it anyway so its baseline entities (battery,
            # SNR, RSSI, ...) exist as `unavailable` rather than not at all.
            for node_num in tracked_node_ids:
                if node_num not in data:
                    self._logger.debug("Seeding minimal record for tracked node %s not yet in node database", node_num)
                    data[node_num] = {"num": node_num}

            if self._discovery_cache is not None:
                for node_num in tracked_node_ids:
                    self._discovery_cache.merge_into(node_num, data[node_num])
                if self._discovery_cache.prune_untracked(tracked_node_ids):
                    self._discovery_cache.async_save_debounced()
        except MeshtasticApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return data
