# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
import typing
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config import callback
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfLength,
    UnitOfMass,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)

from . import LOGGER, helpers
from .entity import MeshtasticNodeEntity

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .coordinator import MeshtasticDataUpdateCoordinator
    from .data import MeshtasticConfigEntry, MeshtasticData


def _build_sensors(nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData) -> Iterable[MeshtasticSensor]:
    entities = []
    entities += _build_node_sensors(nodes, runtime_data)
    entities += _build_device_sensors(nodes, runtime_data)
    entities += _build_local_stats_sensors(nodes, runtime_data)
    entities += _build_power_metrics_sensors(nodes, runtime_data)
    entities += _build_environment_metrics_sensors(nodes, runtime_data)
    entities += _build_air_quality_metrics_sensors(nodes, runtime_data)
    entities += _build_health_metrics_sensors(nodes, runtime_data)
    entities += _build_host_metrics_sensors(nodes, runtime_data)
    entities += _build_traffic_management_stats_sensors(nodes, runtime_data)
    entities += _build_position_sensors(nodes, runtime_data)
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    await helpers.setup_platform_entry(hass, entry, async_add_entities, _build_sensors)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
) -> bool:
    return await helpers.async_unload_entry(hass, entry)


@dataclass(kw_only=True)
class MeshtasticSensorEntityDescription(SensorEntityDescription):
    exists_fn: Callable[[MeshtasticSensor], bool] = lambda _: True
    value_fn: Callable[[MeshtasticSensor], StateType]


class MeshtasticSensor(MeshtasticNodeEntity, SensorEntity):
    entity_description: MeshtasticSensorEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticDataUpdateCoordinator,
        entity_description: MeshtasticSensorEntityDescription,
        gateway: typing.Mapping[str, typing.Any],
        node_id: int,
    ) -> None:
        super().__init__(coordinator, gateway, node_id, SENSOR_DOMAIN, entity_description)

    @callback
    def _async_update_attrs(self) -> None:
        LOGGER.debug("Updating sensor attributes: %s", self)
        self._attr_native_value = self.entity_description.value_fn(self)
        self._attr_available = self._attr_native_value is not None


def _build_node_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    entities = []
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()

    def last_heard(device: MeshtasticNodeEntity) -> datetime.datetime | None:
        last_heard_int = device.coordinator.data[device.node_id].get("lastHeard")
        if last_heard_int is None:
            return None
        return datetime.datetime.fromtimestamp(last_heard_int, tz=datetime.UTC)

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_last_heard",
                name="Last Heard",
                icon="mdi:timeline-clock",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=last_heard,
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
        if node_id != runtime_data.gateway_node["num"]
    ]

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_snr",
                name="Signal to Noise Ratio",
                icon="mdi:signal",
                native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda device: device.coordinator.data[device.node_id].get("snr", None),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
        if node_id != runtime_data.gateway_node["num"]
    ]

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_rssi",
                name="Last packet RSSI at gateway",
                icon="mdi:signal",
                native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda device: device.coordinator.data[device.node_id].get("rssi", None),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
        if node_id != runtime_data.gateway_node["num"]
    ]

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_hops_away",
                name="Hops away",
                icon="mdi:rabbit",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda device: device.coordinator.data[device.node_id].get("hopsAway", None),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
        if node_id != runtime_data.gateway_node["num"]
    ]

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_role",
                name="Role",
                icon="mdi:card-account-details",
                value_fn=lambda device: device.coordinator.data[device.node_id].get("user", {}).get("role", None),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
        if node_id != runtime_data.gateway_node["num"]
    ]
    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_short_name",
                name="Short Name",
                icon="mdi:card-account-details",
                value_fn=lambda device: device.coordinator.data[device.node_id].get("user", {}).get("shortName", None),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="node_long_name",
                name="Long Name",
                icon="mdi:card-account-details",
                value_fn=lambda device: device.coordinator.data[device.node_id].get("user", {}).get("longName", None),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]

    return entities


def _build_device_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    entities = []

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="device_uptime",
                name="Uptime",
                icon="mdi:progress-clock",
                native_unit_of_measurement=UnitOfTime.SECONDS,
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.TOTAL_INCREASING,
                value_fn=lambda device: (
                    device.coordinator.data[device.node_id].get("deviceMetrics", {}).get("uptimeSeconds", None)
                ),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]

    def battery_level(device: MeshtasticSensor) -> int | None:
        level = device.coordinator.data[device.node_id].get("deviceMetrics", {}).get("batteryLevel", None)
        if level is not None:
            return max(0, min(100, level))
        return level

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="device_battery_level",
                name="Battery Level",
                icon="mdi:battery",
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=battery_level,
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]

    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="device_voltage",
                name="Voltage",
                icon="mdi:lightning-bolt",
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda device: (
                    device.coordinator.data[device.node_id].get("deviceMetrics", {}).get("voltage", None)
                ),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]
    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="device_channel_utilization",
                name="Channel Utilization",
                icon="mdi:signal-distance-variant",
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda device: (
                    device.coordinator.data[device.node_id].get("deviceMetrics", {}).get("channelUtilization", None)
                ),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]
    entities += [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="device_airtime",
                name="Airtime",
                icon="mdi:timer",
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda device: (
                    device.coordinator.data[device.node_id].get("deviceMetrics", {}).get("airUtilTx", None)
                ),
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id, node_info in nodes.items()
    ]

    return entities


def _build_local_stats_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    nodes_with_local_stats = {node_id: node_info for node_id, node_info in nodes.items() if "localStats" in node_info}

    entities = []
    try:
        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_tx",
                    name="Packets sent",
                    icon="mdi:call-made",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numPacketsTx", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_rx",
                    name="Packets received",
                    icon="mdi:call-received",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numPacketsRx", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_rx_bad",
                    name="Malformed Packets received",
                    icon="mdi:call-missed",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numPacketsRxBad", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_rx_duplicate",
                    name="Duplicate Packets received",
                    icon="mdi:call-split",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numRxDupe", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_tx_relayed",
                    name="Packets relayed",
                    icon="mdi:call-missed",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numTxRelay", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_tx_relay_cancelled",
                    name="Packets relay canceled",
                    icon="mdi:call-missed",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numTxRelayCanceled", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_nodes_online",
                    name="Online Nodes",
                    icon="mdi:radio-handheld",
                    state_class=SensorStateClass.TOTAL,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numOnlineNodes", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_nodes_total",
                    name="Total Nodes",
                    icon="mdi:radio-handheld",
                    state_class=SensorStateClass.TOTAL,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numTotalNodes", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_packets_tx_dropped",
                    name="Packets dropped from send queue",
                    icon="mdi:call-missed",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("numTxDropped", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
            if "numTxDropped" in node_info["localStats"]
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_heap_free",
                    name="Free heap memory",
                    icon="mdi:memory",
                    native_unit_of_measurement=UnitOfInformation.BYTES,
                    device_class=SensorDeviceClass.DATA_SIZE,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("heapFreeBytes", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
            if "heapFreeBytes" in node_info["localStats"]
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_heap_total",
                    name="Total heap memory",
                    icon="mdi:memory",
                    native_unit_of_measurement=UnitOfInformation.BYTES,
                    device_class=SensorDeviceClass.DATA_SIZE,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("heapTotalBytes", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
            if "heapTotalBytes" in node_info["localStats"]
        ]

        entities += [
            MeshtasticSensor(
                coordinator=coordinator,
                entity_description=MeshtasticSensorEntityDescription(
                    key="stats_noise_floor",
                    name="Noise floor",
                    icon="mdi:signal",
                    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=lambda device: (
                        device.coordinator.data[device.node_id].get("localStats", {}).get("noiseFloor", None)
                    ),
                ),
                gateway=gateway,
                node_id=node_id,
            )
            for node_id, node_info in nodes_with_local_stats.items()
            if "noiseFloor" in node_info["localStats"]
        ]
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to create local stats entities", exc_info=True)

    return entities


def _build_power_metrics_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    nodes_with_power_metrics = {
        node_id: node_info for node_id, node_info in nodes.items() if "powerMetrics" in node_info
    }
    if not nodes_with_power_metrics:
        return []

    entities = []
    try:
        for node_id, node_info in nodes_with_power_metrics.items():
            power_metrics = node_info["powerMetrics"]
            for channel in range(1, 9):
                voltage_key = f"ch{channel}Voltage"
                current_key = f"ch{channel}Current"

                def power_metrics_value_fn(key: str) -> Callable[[MeshtasticSensor], str | None]:
                    return lambda device: device.coordinator.data[device.node_id].get("powerMetrics", {}).get(key, None)

                if voltage_key in power_metrics:
                    entities.append(
                        MeshtasticSensor(
                            coordinator=coordinator,
                            entity_description=MeshtasticSensorEntityDescription(
                                key=f"power_ch{channel}_voltage",
                                name=f"Channel {channel} Voltage",
                                icon="mdi:lightning-bolt",
                                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                                device_class=SensorDeviceClass.VOLTAGE,
                                state_class=SensorStateClass.MEASUREMENT,
                                value_fn=power_metrics_value_fn(voltage_key),
                            ),
                            gateway=gateway,
                            node_id=node_id,
                        )
                    )
                if current_key in power_metrics:
                    entities.append(
                        MeshtasticSensor(
                            coordinator=coordinator,
                            entity_description=MeshtasticSensorEntityDescription(
                                key=f"power_ch{channel}_current",
                                name=f"Channel {channel} Current",
                                icon="mdi:current-dc",
                                native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
                                device_class=SensorDeviceClass.CURRENT,
                                state_class=SensorStateClass.MEASUREMENT,
                                value_fn=power_metrics_value_fn(current_key),
                            ),
                            gateway=gateway,
                            node_id=node_id,
                        )
                    )

    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to create power metrics entities", exc_info=True)

    return entities


def _build_environment_metrics_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    nodes_with_environment_metrics = {
        node_id: node_info for node_id, node_info in nodes.items() if "environmentMetrics" in node_info
    }
    if not nodes_with_environment_metrics:
        return []

    entities = []

    def environment_metrics_value_fn(
        key: str, transform: Callable[[Any], StateType] | None = None
    ) -> Callable[[MeshtasticSensor], StateType]:
        def _value(device: MeshtasticSensor) -> StateType:
            raw = device.coordinator.data[device.node_id].get("environmentMetrics", {}).get(key, None)
            if raw is None or transform is None:
                return raw
            return transform(raw)

        return _value

    def add_sensor_base(  # noqa: PLR0913
        node_id: int,
        node_info: dict[str, Any],
        value_key: str,
        device_class: SensorDeviceClass | None,
        unit_of_measurement: str | None = None,
        state_class: SensorStateClass = SensorStateClass.MEASUREMENT,
        transform: Callable[[Any], StateType] | None = None,
    ) -> None:
        key = "".join(["_" + c.lower() if c.isupper() else c for c in value_key]).lstrip("_")
        if value_key in node_info["environmentMetrics"]:
            entities.append(
                MeshtasticSensor(
                    coordinator=coordinator,
                    entity_description=MeshtasticSensorEntityDescription(
                        key="environment_" + key,
                        translation_key="environment_" + key,
                        native_unit_of_measurement=unit_of_measurement,
                        device_class=device_class,
                        state_class=state_class,
                        value_fn=environment_metrics_value_fn(value_key, transform),
                    ),
                    gateway=gateway,
                    node_id=node_id,
                )
            )

    try:
        for node_id, node_info in nodes_with_environment_metrics.items():
            add_sensor = partial(add_sensor_base, node_id, node_info)

            add_sensor("temperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)
            add_sensor("relativeHumidity", SensorDeviceClass.HUMIDITY, PERCENTAGE)
            add_sensor("barometricPressure", SensorDeviceClass.ATMOSPHERIC_PRESSURE, UnitOfPressure.HPA)
            # Gas resistance (BME680) is reported in MOhm - not a pressure, and Home
            # Assistant has no dedicated "resistance" device class to attach.
            add_sensor("gasResistance", None, "MΩ")
            add_sensor("iaq", SensorDeviceClass.AQI, None)

            add_sensor("distance", SensorDeviceClass.DISTANCE, UnitOfLength.MILLIMETERS)

            add_sensor("lux", SensorDeviceClass.ILLUMINANCE, LIGHT_LUX)
            # MessageToDict() renders these as lowerCamelCase, not snake_case.
            add_sensor("whiteLux", SensorDeviceClass.ILLUMINANCE, LIGHT_LUX)
            add_sensor("irLux", SensorDeviceClass.ILLUMINANCE, LIGHT_LUX)
            add_sensor("uvLux", SensorDeviceClass.ILLUMINANCE, LIGHT_LUX)

            # Direction is an angle, not a speed: WIND_SPEED device class/state class
            # would be physically wrong here and MEASUREMENT averaging is meaningless
            # across the 359°/0° wraparound, hence MEASUREMENT_ANGLE.
            add_sensor(
                "windDirection",
                SensorDeviceClass.WIND_DIRECTION,
                DEGREE,
                state_class=SensorStateClass.MEASUREMENT_ANGLE,
            )
            add_sensor("windSpeed", SensorDeviceClass.WIND_SPEED, UnitOfSpeed.METERS_PER_SECOND)
            add_sensor("windGust", SensorDeviceClass.WIND_SPEED, UnitOfSpeed.METERS_PER_SECOND)
            add_sensor("windLull", SensorDeviceClass.WIND_SPEED, UnitOfSpeed.METERS_PER_SECOND)

            add_sensor("weight", SensorDeviceClass.WEIGHT, UnitOfMass.KILOGRAMS)

            # Legacy device power reading, superseded by PowerMetrics on newer firmware
            # but still sent by some environment sensor boards.
            add_sensor("voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT)
            add_sensor("current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.MILLIAMPERE)

            add_sensor("radiation", None, "µR/h")
            add_sensor("rainfall1h", SensorDeviceClass.PRECIPITATION, UnitOfPrecipitationDepth.MILLIMETERS)
            add_sensor("rainfall24h", SensorDeviceClass.PRECIPITATION, UnitOfPrecipitationDepth.MILLIMETERS)

            add_sensor("soilMoisture", SensorDeviceClass.MOISTURE, PERCENTAGE)
            add_sensor("soilTemperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)

            # Repeated field (multiple one-wire probes can be daisy-chained); only the
            # first reported probe is exposed as a sensor for now.
            add_sensor(
                "oneWireTemperature",
                SensorDeviceClass.TEMPERATURE,
                UnitOfTemperature.CELSIUS,
                transform=lambda values: values[0] if values else None,
            )

    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to create environment metric entities", exc_info=True)

    return entities


def _build_air_quality_metrics_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    nodes_with_environment_metrics = {
        node_id: node_info for node_id, node_info in nodes.items() if "airQualityMetrics" in node_info
    }
    if not nodes_with_environment_metrics:
        return []

    entities = []

    def air_quality_metrics_value_fn(key: str) -> Callable[[MeshtasticSensor], str | None]:
        return lambda device: device.coordinator.data[device.node_id].get("airQualityMetrics", {}).get(key, None)

    def add_sensor_base(  # noqa: PLR0913
        node_id: int,
        node_info: dict[str, Any],
        value_key: str,
        device_class: SensorDeviceClass | None,
        unit_of_measurement: str | None = None,
        state_class: SensorStateClass = SensorStateClass.MEASUREMENT,
    ) -> None:
        key = "".join(["_" + c.lower() if c.isupper() else c for c in value_key]).lstrip("_")
        if value_key in node_info["airQualityMetrics"]:
            entities.append(
                MeshtasticSensor(
                    coordinator=coordinator,
                    entity_description=MeshtasticSensorEntityDescription(
                        key="airquality_" + key,
                        translation_key="airquality_" + key,
                        native_unit_of_measurement=unit_of_measurement,
                        device_class=device_class,
                        state_class=state_class,
                        value_fn=air_quality_metrics_value_fn(value_key),
                    ),
                    gateway=gateway,
                    node_id=node_id,
                )
            )

    try:
        for node_id, node_info in nodes_with_environment_metrics.items():
            add_sensor = partial(add_sensor_base, node_id, node_info)

            add_sensor("pm10Standard", SensorDeviceClass.PM10, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("pm25Standard", SensorDeviceClass.PM25, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("pm100Standard", None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)

            add_sensor("pm10Environmental", SensorDeviceClass.PM10, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("pm25Environmental", SensorDeviceClass.PM25, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("pm100Environmental", None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)

            add_sensor("particles03um", None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("particles05um", None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("particles10um", SensorDeviceClass.PM10, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("particles25um", SensorDeviceClass.PM25, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("particles50um", None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
            add_sensor("particles100um", None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER)
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to create air quality metric entities", exc_info=True)

    return entities


@dataclass(frozen=True, kw_only=True)
class _MetricFieldSpec:
    """One field of a telemetry sub-category, mapped to a sensor definition."""

    field: str
    key: str
    name: str
    icon: str | None = None
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    transform: Callable[[Any], StateType] | None = None


def _build_category_sensors(
    nodes: Mapping[int, Mapping[str, Any]],
    runtime_data: MeshtasticData,
    *,
    category: str,
    key_prefix: str,
    fields: Iterable[_MetricFieldSpec],
) -> Iterable[MeshtasticSensor]:
    """Build sensors for a telemetry sub-category from a declarative field map."""
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    nodes_with_category = {node_id: node_info for node_id, node_info in nodes.items() if category in node_info}
    if not nodes_with_category:
        return []

    def value_fn_for(spec: _MetricFieldSpec) -> Callable[[MeshtasticSensor], StateType]:
        def _value(device: MeshtasticSensor) -> StateType:
            raw = device.coordinator.data[device.node_id].get(category, {}).get(spec.field, None)
            if raw is None or spec.transform is None:
                return raw
            return spec.transform(raw)

        return _value

    entities: list[MeshtasticSensor] = []
    try:
        for node_id, node_info in nodes_with_category.items():
            category_data = node_info[category]
            for spec in fields:
                if spec.field not in category_data:
                    continue
                entities.append(
                    MeshtasticSensor(
                        coordinator=coordinator,
                        entity_description=MeshtasticSensorEntityDescription(
                            key=f"{key_prefix}_{spec.key}",
                            name=spec.name,
                            icon=spec.icon,
                            native_unit_of_measurement=spec.unit,
                            device_class=spec.device_class,
                            state_class=spec.state_class,
                            value_fn=value_fn_for(spec),
                        ),
                        gateway=gateway,
                        node_id=node_id,
                    )
                )
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to create %s entities", category, exc_info=True)

    return entities


_HEALTH_METRICS_FIELDS: tuple[_MetricFieldSpec, ...] = (
    _MetricFieldSpec(field="heartBpm", key="heart_bpm", name="Heart Rate", icon="mdi:heart-pulse", unit="bpm"),
    _MetricFieldSpec(field="spO2", key="spo2", name="SpO2", icon="mdi:water-percent", unit=PERCENTAGE),
    _MetricFieldSpec(
        field="temperature",
        key="temperature",
        name="Body Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
    ),
)


def _build_health_metrics_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    return _build_category_sensors(
        nodes, runtime_data, category="healthMetrics", key_prefix="health", fields=_HEALTH_METRICS_FIELDS
    )


def _divide_by_100(value: float) -> float:
    return value / 100


_HOST_METRICS_FIELDS: tuple[_MetricFieldSpec, ...] = (
    _MetricFieldSpec(
        field="uptimeSeconds",
        key="uptime_seconds",
        name="Host Uptime",
        icon="mdi:progress-clock",
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    _MetricFieldSpec(
        field="freememBytes",
        key="freemem_bytes",
        name="Host Free Memory",
        icon="mdi:memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        unit=UnitOfInformation.BYTES,
    ),
    _MetricFieldSpec(
        field="diskfree1Bytes",
        key="diskfree1_bytes",
        name="Host Disk Free (/)",
        icon="mdi:harddisk",
        device_class=SensorDeviceClass.DATA_SIZE,
        unit=UnitOfInformation.BYTES,
    ),
    _MetricFieldSpec(
        field="diskfree2Bytes",
        key="diskfree2_bytes",
        name="Host Disk Free (2)",
        icon="mdi:harddisk",
        device_class=SensorDeviceClass.DATA_SIZE,
        unit=UnitOfInformation.BYTES,
    ),
    _MetricFieldSpec(
        field="diskfree3Bytes",
        key="diskfree3_bytes",
        name="Host Disk Free (3)",
        icon="mdi:harddisk",
        device_class=SensorDeviceClass.DATA_SIZE,
        unit=UnitOfInformation.BYTES,
    ),
    # load1/5/15 are reported in 1/100ths (e.g. 150 == a Linux load average of 1.50).
    _MetricFieldSpec(field="load1", key="load1", name="Host Load (1m)", icon="mdi:gauge", transform=_divide_by_100),
    _MetricFieldSpec(field="load5", key="load5", name="Host Load (5m)", icon="mdi:gauge", transform=_divide_by_100),
    _MetricFieldSpec(field="load15", key="load15", name="Host Load (15m)", icon="mdi:gauge", transform=_divide_by_100),
    _MetricFieldSpec(
        field="userString",
        key="user_string",
        name="Host Info",
        icon="mdi:information-outline",
        state_class=None,
    ),
)


def _build_host_metrics_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    return _build_category_sensors(
        nodes, runtime_data, category="hostMetrics", key_prefix="host", fields=_HOST_METRICS_FIELDS
    )


_TRAFFIC_MANAGEMENT_STATS_FIELDS: tuple[_MetricFieldSpec, ...] = tuple(
    _MetricFieldSpec(
        field=field, key=key, name=name, icon="mdi:router-network", state_class=SensorStateClass.TOTAL_INCREASING
    )
    for field, key, name in (
        ("packetsInspected", "packets_inspected", "Packets Inspected"),
        ("positionDedupDrops", "position_dedup_drops", "Position Dedup Drops"),
        ("nodeinfoCacheHits", "nodeinfo_cache_hits", "NodeInfo Cache Hits"),
        ("rateLimitDrops", "rate_limit_drops", "Rate Limit Drops"),
        ("unknownPacketDrops", "unknown_packet_drops", "Unknown Packet Drops"),
        ("hopExhaustedPackets", "hop_exhausted_packets", "Hop Exhausted Packets"),
        ("routerHopsPreserved", "router_hops_preserved", "Router Hops Preserved"),
    )
)


def _build_traffic_management_stats_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    return _build_category_sensors(
        nodes,
        runtime_data,
        category="trafficManagementStats",
        key_prefix="traffic",
        fields=_TRAFFIC_MANAGEMENT_STATS_FIELDS,
    )


def _epoch_to_datetime(value: int) -> datetime.datetime | None:
    if not value:
        return None
    return datetime.datetime.fromtimestamp(value, tz=datetime.UTC)


_POSITION_FIELDS: tuple[_MetricFieldSpec, ...] = (
    _MetricFieldSpec(
        field="satsInView",
        key="satellites_in_view",
        name="Satellites In View",
        icon="mdi:satellite-variant",
    ),
    _MetricFieldSpec(
        field="altitude",
        key="altitude",
        name="Altitude",
        icon="mdi:altimeter",
        device_class=SensorDeviceClass.DISTANCE,
        unit=UnitOfLength.METERS,
    ),
    _MetricFieldSpec(
        field="altitudeHae",
        key="altitude_hae",
        name="Altitude (HAE)",
        icon="mdi:altimeter",
        device_class=SensorDeviceClass.DISTANCE,
        unit=UnitOfLength.METERS,
    ),
    _MetricFieldSpec(
        field="altitudeGeoidalSeparation",
        key="geoidal_separation",
        name="Geoidal Separation",
        icon="mdi:altimeter",
        device_class=SensorDeviceClass.DISTANCE,
        unit=UnitOfLength.METERS,
    ),
    _MetricFieldSpec(
        field="groundSpeed",
        key="ground_speed",
        name="Ground Speed",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.SPEED,
        unit=UnitOfSpeed.METERS_PER_SECOND,
    ),
    _MetricFieldSpec(
        field="groundTrack",
        key="ground_track",
        name="Ground Track",
        icon="mdi:compass-outline",
        unit=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        transform=_divide_by_100,
    ),
    _MetricFieldSpec(field="PDOP", key="pdop", name="PDOP", icon="mdi:crosshairs-gps", transform=_divide_by_100),
    _MetricFieldSpec(field="HDOP", key="hdop", name="HDOP", icon="mdi:crosshairs-gps", transform=_divide_by_100),
    _MetricFieldSpec(field="VDOP", key="vdop", name="VDOP", icon="mdi:crosshairs-gps", transform=_divide_by_100),
    _MetricFieldSpec(
        field="gpsAccuracy",
        key="gps_accuracy",
        name="GPS Accuracy",
        icon="mdi:crosshairs-gps",
        device_class=SensorDeviceClass.DISTANCE,
        unit=UnitOfLength.MILLIMETERS,
    ),
    _MetricFieldSpec(field="fixQuality", key="fix_quality", name="Fix Quality", icon="mdi:crosshairs-gps"),
    _MetricFieldSpec(field="fixType", key="fix_type", name="Fix Type", icon="mdi:crosshairs-gps"),
    _MetricFieldSpec(field="precisionBits", key="precision_bits", name="Precision Bits", icon="mdi:crosshairs-gps"),
    _MetricFieldSpec(field="locationSource", key="location_source", name="Location Source", icon="mdi:map-marker"),
    _MetricFieldSpec(field="altitudeSource", key="altitude_source", name="Altitude Source", icon="mdi:altimeter"),
    _MetricFieldSpec(
        field="timestamp",
        key="timestamp",
        name="Position Timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,
        transform=_epoch_to_datetime,
    ),
    _MetricFieldSpec(
        field="seqNumber",
        key="seq_number",
        name="Position Sequence Number",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


def _build_position_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    entities = list(
        _build_category_sensors(
            nodes, runtime_data, category="position", key_prefix="position", fields=_POSITION_FIELDS
        )
    )
    entities += _build_position_estimated_accuracy_sensors(nodes, runtime_data)
    return entities


def _build_position_estimated_accuracy_sensors(
    nodes: Mapping[int, Mapping[str, Any]], runtime_data: MeshtasticData
) -> Iterable[MeshtasticSensor]:
    """
    Build the (optional) estimated horizontal accuracy sensor.

    gpsAccuracy is a hardware-reported accuracy *factor*, only meaningful combined
    with HDOP - it is not itself a horizontal accuracy, hence this is its own
    clearly-named derived sensor rather than relabeling gpsAccuracy.
    """
    coordinator = runtime_data.coordinator
    gateway = runtime_data.client.get_own_node()
    nodes_with_both = {
        node_id: node_info
        for node_id, node_info in nodes.items()
        if "gpsAccuracy" in node_info.get("position", {}) and "HDOP" in node_info.get("position", {})
    }
    if not nodes_with_both:
        return []

    def estimated_horizontal_accuracy_m(device: MeshtasticSensor) -> float | None:
        position = device.coordinator.data[device.node_id].get("position", {})
        gps_accuracy_mm = position.get("gpsAccuracy")
        hdop = position.get("HDOP")
        if gps_accuracy_mm is None or hdop is None:
            return None
        return (gps_accuracy_mm * (hdop / 100)) / 1000

    return [
        MeshtasticSensor(
            coordinator=coordinator,
            entity_description=MeshtasticSensorEntityDescription(
                key="position_estimated_horizontal_accuracy",
                name="Estimated Horizontal Accuracy",
                icon="mdi:crosshairs-question",
                device_class=SensorDeviceClass.DISTANCE,
                native_unit_of_measurement=UnitOfLength.METERS,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=estimated_horizontal_accuracy_m,
            ),
            gateway=gateway,
            node_id=node_id,
        )
        for node_id in nodes_with_both
    ]
