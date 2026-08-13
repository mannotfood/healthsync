"""Logbook description for HealthSync's per-reading events.

Gives each individual heart rate / HRV / VO2 max / weight reading a
readable Logbook line (e.g. "Heart rate reading recorded 84 bpm") instead
of the generic "X reading triggered" text event-domain entities get by
default.

Why this is a separate file/mechanism from the reading event *entities* in
event.py, rather than one thing doing both jobs: HA's Logbook describer
system (`async_describe_events` / `async_describe_event`) only applies to
genuine bus events (`hass.bus.async_fire(...)`), not to entity-domain state
changes. Confirmed directly against HA core's own source before building
this — there is no `homeassistant/components/event/logbook.py` (no built-in
describer support for the `event` domain at all), and
`EXPOSED_STATE_ATTRIBUTES` (the only attributes a state-change-based Logbook
row can surface) is hardcoded in HA core to just `event_type` — an
integration cannot extend it. So the entity (event.py) gives you a proper,
automatable, filterable entity in the entity list; this file, hooking the
separate `EVENT_METRIC_READING` bus event fired alongside it, gives you the
readable Logbook text. Same underlying reading, two different HA mechanisms,
because neither alone does both jobs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LazyEventPartialState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_METRIC_READING
from .event import READING_METRICS

_METRIC_NAMES = {metric: name for metric, name, _icon in READING_METRICS}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None
    ],
) -> None:
    """Describe HealthSync's per-reading Logbook events."""

    @callback
    def async_describe_reading_event(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        metric = data.get("metric")
        entry_id = data.get("entry_id")
        value = data.get("value")
        unit = data.get("unit") or ""
        name = _METRIC_NAMES.get(metric, "Reading")

        entity_id = None
        if entry_id and metric:
            entity_id = er.async_get(hass).async_get_entity_id(
                "event", DOMAIN, f"{entry_id}_{metric}_reading"
            )

        return {
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: f"recorded {value} {unit}".strip(),
            LOGBOOK_ENTRY_ENTITY_ID: entity_id,
        }

    async_describe_event(DOMAIN, EVENT_METRIC_READING, async_describe_reading_event)
