"""Event entities for the HealthSync integration.

`WorkoutCompletedEvent` fires once per genuinely new (in-order, non-replayed)
workout, so it's a clean automation trigger ("when a workout is
completed...") and shows every workout in HA's Logbook — full history, not
just a snapshot of the latest one. Added 11 Aug 2026 alongside the separate
"HealthSync Workouts" device.

`MetricReadingEvent` (added 13 Aug 2026) does the same job for heart rate,
HRV, VO2 max, and weight: the "current value" sensor for these only ever
reflects whichever reading happened to arrive last in a webhook batch, so
when several readings land in one sync, the earlier ones in that batch are
never individually recorded anywhere — not in the sensor's state, not in its
History. These event entities fire once per *individual* reading regardless
of batching, so every value + Apple's own timestamp is genuinely preserved
and queryable (via Logbook/recorder), even though — like all event entities
— they don't produce a graphable History line the way a regular sensor does.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HealthSyncConfigEntry, HealthSyncData
from .const import (
    METRIC_HEART_RATE,
    METRIC_HRV,
    METRIC_VO2_MAX,
    METRIC_WEIGHT,
    SIGNAL_METRIC_READING,
    SIGNAL_WORKOUT,
    WORKOUT_EVENT_TYPES,
    WORKOUT_TYPE_ICONS,
)
from .sensor import main_device_info, workout_device_info

# (metric key, entity name, icon) — mirrors the LatestValueSensor
# instantiations in sensor.py so each reading-event entity sits alongside
# its corresponding "current value" sensor with a matching name/icon.
READING_METRICS = (
    (METRIC_HEART_RATE, "Heart rate reading", "mdi:heart-pulse"),
    (METRIC_HRV, "Heart rate variability reading", "mdi:heart-flash"),
    (METRIC_VO2_MAX, "VO2 max reading", "mdi:lungs"),
    (METRIC_WEIGHT, "Weight reading", "mdi:scale-bathroom"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthSyncConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HealthSync event entities."""
    data = entry.runtime_data
    async_add_entities(
        [
            WorkoutCompletedEvent(entry, data),
            *(
                MetricReadingEvent(entry, data, metric, name, icon)
                for metric, name, icon in READING_METRICS
            ),
        ]
    )


class WorkoutCompletedEvent(EventEntity):
    """Fires each time a new workout sample arrives.

    Deliberately doesn't restore its last state across HA restarts — an
    event entity is a "did this just happen" signal, not a snapshot, and the
    full history is what the Logbook and the "Recent workouts" sensor's
    attributes are for.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Workout completed"
    # One event_type per workout activity (running, cycling, ...) rather
    # than a single generic "workout_completed" for everything — so the
    # Logbook line and the entity's own event history are distinguishable
    # per entry instead of reading identically for every workout.
    _attr_event_types = WORKOUT_EVENT_TYPES

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_workout_completed"
        self._attr_device_info = workout_device_info(entry)
        # Icon matches whichever activity fired most recently (added
        # 12 Aug 2026) rather than one fixed icon for every workout type —
        # see WORKOUT_TYPE_ICONS. Starts at the generic fallback until the
        # first event fires.
        self._last_event_type = "other"

    @property
    def icon(self) -> str:
        return WORKOUT_TYPE_ICONS.get(self._last_event_type, WORKOUT_TYPE_ICONS["other"])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WORKOUT.format(entry_id=self._entry.entry_id),
                self._handle_workout,
            )
        )

    @callback
    def _handle_workout(self, workout: dict[str, Any]) -> None:
        # Fall back to "other" for anything not in WORKOUT_EVENT_TYPES —
        # e.g. a new HealthKit activity type the app maps but this list
        # hasn't been updated for yet. _trigger_event raises ValueError for
        # any type not in _attr_event_types, so this guards against a typo
        # or drift silently breaking every future sync.
        event_type = workout.get("workout_type")
        if event_type not in WORKOUT_EVENT_TYPES:
            event_type = "other"
        self._last_event_type = event_type
        self._trigger_event(event_type, workout)
        self.async_write_ha_state()


class MetricReadingEvent(EventEntity):
    """Fires once per individual heart rate / HRV / VO2 max / weight
    reading, independent of how many arrive in the same webhook batch — see
    the module docstring for why this exists alongside the plain "current
    value" sensor rather than replacing it.

    Same "don't restore across restarts" reasoning as WorkoutCompletedEvent —
    this is a "did this reading just arrive" signal, not a snapshot.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_event_types = ["reading"]

    def __init__(
        self,
        entry: HealthSyncConfigEntry,
        data: HealthSyncData,
        metric: str,
        name: str,
        icon: str,
    ) -> None:
        self._entry = entry
        self._data = data
        self._metric = metric
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{metric}_reading"
        self._attr_device_info = main_device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_METRIC_READING.format(entry_id=self._entry.entry_id),
                self._handle_reading,
            )
        )

    @callback
    def _handle_reading(self, metric: str, sample: dict[str, Any]) -> None:
        if metric != self._metric:
            return
        self._trigger_event(
            "reading",
            {
                "value": sample.get("value"),
                "unit": sample.get("unit"),
                "start_date": sample.get("start_date"),
                "end_date": sample.get("end_date"),
            },
        )
        self.async_write_ha_state()
