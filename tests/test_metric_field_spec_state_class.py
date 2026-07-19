# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT
"""
Guard against reintroducing the locationSource/altitudeSource crash.

_MetricFieldSpec defaults state_class to SensorStateClass.MEASUREMENT, so any field
spec for a textual/enum value that forgets to override it back to None makes Home
Assistant try to parse that string as a number and raise ValueError on every
coordinator update (see sensor.py's _POSITION_FIELDS docstring / PR history).
"""

from __future__ import annotations

from custom_components.meshtastic.sensor import (
    _HEALTH_METRICS_FIELDS,
    _HOST_METRICS_FIELDS,
    _POSITION_FIELDS,
    _TRAFFIC_MANAGEMENT_STATS_FIELDS,
    _MetricFieldSpec,
)

_ALL_FIELD_SPECS: tuple[_MetricFieldSpec, ...] = (
    *_HEALTH_METRICS_FIELDS,
    *_HOST_METRICS_FIELDS,
    *_TRAFFIC_MANAGEMENT_STATS_FIELDS,
    *_POSITION_FIELDS,
)

# Fields known today to carry a textual/enum value rather than a number.
_KNOWN_TEXT_FIELDS = {"userString", "locationSource", "altitudeSource"}

# Any newly-added field whose protobuf name ends with one of these looks textual
# (enum/status/identifier), matching the pattern the task explicitly calls out:
# role, source, status, mode, and free-text strings.
_TEXT_LIKE_FIELD_NAME_SUFFIXES = ("Source", "String", "Role", "Status", "Mode")


def test_known_text_fields_declare_no_numeric_state() -> None:
    specs_by_field = {spec.field: spec for spec in _ALL_FIELD_SPECS}

    for field in _KNOWN_TEXT_FIELDS:
        assert field in specs_by_field, f"expected _MetricFieldSpec for {field!r} to still exist"
        spec = specs_by_field[field]
        assert spec.state_class is None, (
            f"{field!r} returns a textual value but declares state_class={spec.state_class!r}; "
            "Home Assistant will raise ValueError trying to parse it as a number"
        )
        assert spec.unit is None, f"{field!r} is textual but declares a unit of measurement"
        assert spec.device_class is None, f"{field!r} is textual but declares a numeric device_class"


def test_text_like_field_names_declare_no_numeric_state() -> None:
    """Catches future role/source/status/mode fields that forget state_class=None."""
    offenders = [
        spec.field
        for spec in _ALL_FIELD_SPECS
        if spec.field.endswith(_TEXT_LIKE_FIELD_NAME_SUFFIXES) and spec.state_class is not None
    ]
    assert not offenders, (
        f"these fields look textual by name but declare a numeric state_class: {offenders}; "
        "add state_class=None to their _MetricFieldSpec"
    )


def test_location_and_altitude_source_map_unset_enum_to_none() -> None:
    specs_by_field = {spec.field: spec for spec in _POSITION_FIELDS}

    for field, unset_value in (("locationSource", "LOC_UNSET"), ("altitudeSource", "ALT_UNSET")):
        spec = specs_by_field[field]
        assert spec.transform is not None, f"{field!r} must map its *_UNSET enum value to None"
        assert spec.transform(unset_value) is None
        # A real source value must pass through unchanged.
        assert spec.transform("LOC_MANUAL" if field == "locationSource" else "ALT_GPS") is not None
