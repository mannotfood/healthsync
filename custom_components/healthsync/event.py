"""Event entity for the HealthSync integration.

Fires once per genuinely new (in-order, non-replayed) workout, so it's a
clean automation trigger ("when a workout is completed...") and shows every
workout in HA's Logbook — full history, not just a snapshot of the latest
one. Added 11 Aug 2026 alongside the separate "HealthSync Workouts" device.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HealthSyncConfigEntry, HealthSyncData
from .const import SIGNAL_WORKOUT
from .sensor import workout_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthSyncConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HealthSync event entities."""
    async_add_entities([WorkoutCompletedEvent(entry, entry.runtime_data)])


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
    _attr_icon = "mdi:run-fast"
    _attr_event_types = ["workout_completed"]

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_workout_completed"
        self._attr_device_info = workout_device_info(entry)

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
        self._trigger_event("workout_completed", workout)
        self.async_write_ha_state()
