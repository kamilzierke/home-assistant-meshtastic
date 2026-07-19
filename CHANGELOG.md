<!--
SPDX-FileCopyrightText: 2026 Kamil Zierke @kamilzierke

SPDX-License-Identifier: MIT
-->

# Changelog

All notable changes to this integration are documented in this file.

## [0.8.0] - 2026-07-19

### Added

- **RSSI sensor** (`Last packet RSSI at gateway`) for every non-gateway node, reflecting the
  signal strength of the last packet received locally by this gateway.
- **GNSS sensors** beyond the existing device tracker: satellites in view, altitude (incl. HAE
  and geoidal separation), ground speed/track, PDOP/HDOP/VDOP, GPS accuracy, fix quality/type,
  precision bits, location/altitude source, position timestamp, and a derived estimated
  horizontal accuracy sensor.
- **New environment sensors**: voltage, current, radiation, rainfall (1h/24h), soil moisture,
  soil temperature, one-wire temperature.
- **Health, host and traffic-management telemetry sensors** (heart rate/SpO2/body temperature;
  host uptime/memory/disk/load; mesh traffic-management counters).
- Additional local-stats sensors: free/total heap memory, noise floor, dropped TX packets.
- Power metrics now cover all 8 channels reported by the protocol (previously 3).
- Sensors discovered at least once now persist across a Home Assistant restart (as
  `unavailable`) instead of disappearing until the next matching packet arrives.

### Fixed

- Telemetry and position packets received before a node's `NodeInfo` are no longer dropped.
- Manually calling the `meshtastic.request_telemetry` / `meshtastic.request_position` services
  now updates the corresponding entities, not just the service response.
- `airQualityMetrics` (and other telemetry variants) now reliably reach the coordinator and
  create/update their sensors.
- Environment sensor field names (`whiteLux`, `irLux`, `uvLux`, `windDirection`, `windSpeed`,
  `windGust`, `windLull`) now match the real payload instead of silently never matching.
- Legitimate zero-valued telemetry readings (e.g. battery level 0, zero satellites in view) are
  no longer mistaken for "field not reported".
- `windDirection` now uses the correct device class/unit (degrees, not wind speed); gas
  resistance no longer uses a pressure unit.
- A packet without a measured RSSI (e.g. relayed via MQTT) no longer clobbers the last known
  good RSSI value.

## Earlier versions

See the [GitHub releases](https://github.com/kamilzierke/home-assistant-meshtastic/releases) for
the history prior to this changelog.
