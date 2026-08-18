"""Sensor entities for the HealthSync integration."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HealthSyncConfigEntry, HealthSyncData
from .const import (
    DOMAIN,
    MAX_RECENT_WORKOUTS,
    METRIC_ACTIVE_CALORIES,
    METRIC_AFIB_BURDEN,
    METRIC_BLOOD_GLUCOSE,
    METRIC_BLOOD_PRESSURE_DIASTOLIC,
    METRIC_BLOOD_PRESSURE_SYSTOLIC,
    METRIC_BODY_FAT_PERCENTAGE,
    METRIC_BODY_MASS_INDEX,
    METRIC_BODY_TEMPERATURE,
    METRIC_DISTANCE,
    METRIC_EXERCISE_TIME,
    METRIC_FLIGHTS_CLIMBED,
    METRIC_HEART_RATE,
    METRIC_HEART_RATE_RECOVERY,
    METRIC_HEIGHT,
    METRIC_HRV,
    METRIC_LEAN_BODY_MASS,
    METRIC_OXYGEN_SATURATION,
    METRIC_RESPIRATORY_RATE,
    METRIC_RESTING_ENERGY,
    METRIC_RESTING_HEART_RATE,
    METRIC_STEPS,
    METRIC_VO2_MAX,
    METRIC_WAIST_CIRCUMFERENCE,
    METRIC_WALKING_HEART_RATE,
    METRIC_WEIGHT,
    SIGNAL_UPDATE,
    SIGNAL_WORKOUT,
    WORKOUT_TYPE_ICONS,
)

_CAMEL_SPLIT = re.compile(r"(?<!^)(?=[A-Z])")


def _title_case_workout_type(raw: str) -> str:
    """"crossTraining" -> "Cross Training". HealthKit's raw type strings
    are camelCase; HA display strings should read like normal English."""
    return _CAMEL_SPLIT.sub(" ", raw).title()


def _workout_label(hass: HomeAssistant, workout: dict[str, Any]) -> str:
    """Build a human name for a workout, e.g. "Walking 11-08-2026 11:55
    13.1 mi" (added 12 Aug 2026, replacing plain "Workout 3"-style slot
    names) — so each entity reads as what it actually is at a glance.
    Distance is converted via HA's own unit system setting (Settings ->
    General -> Unit system), so it shows km or mi to match the user's
    configured preference rather than always meters.
    """
    kind = _title_case_workout_type(workout.get("workout_type") or "Workout")
    started = dt_util.parse_datetime(workout.get("started_at") or "")
    when = dt_util.as_local(started).strftime("%d-%m-%Y %H:%M") if started else ""
    distance_m = workout.get("distance_m")
    distance = ""
    if isinstance(distance_m, (int, float)):
        converted = hass.config.units.length(distance_m, UnitOfLength.METERS)
        distance = f" {converted:.1f} {hass.config.units.length_unit}"
    label = " ".join(p for p in (kind, when) if p)
    return f"{label}{distance}".strip()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthSyncConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HealthSync sensors."""
    data = entry.runtime_data

    # The "Sleep stage" sensor was removed in 0.6.0 (a latest-stage value is
    # frozen at whatever the user woke from — the per-stage breakdown lives
    # as attributes on "Sleep last night" now). "Recent workouts" was
    # removed in 0.11.0, replaced by the WorkoutSlotSensor entities below.
    # Clean up both old entities.
    registry = er.async_get(hass)
    for old_unique_id in (
        f"{entry.entry_id}_sleep_stage",
        f"{entry.entry_id}_recent_workouts",
    ):
        stale = registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        if stale:
            registry.async_remove(stale)

    async_add_entities(
        [
            DailyTotalSensor(entry, data, METRIC_STEPS, "Steps today", "steps", "mdi:walk"),
            DailyTotalSensor(
                entry, data, METRIC_ACTIVE_CALORIES, "Active calories today", "kcal", "mdi:fire"
            ),
            LatestValueSensor(
                entry, data, METRIC_HEART_RATE, "Heart rate", "bpm", "mdi:heart-pulse"
            ),
            LatestValueSensor(
                entry, data, METRIC_HRV, "Heart rate variability", "ms", "mdi:heart-flash"
            ),
            # Added 18 Aug 2026 — requested via GitHub #15. Same
            # generic LatestValueSensor pattern as heart rate/HRV above.
            LatestValueSensor(
                entry, data, METRIC_RESTING_HEART_RATE, "Resting heart rate", "bpm", "mdi:heart-outline"
            ),
            # Added 18 Aug 2026 — requested via GitHub #15 (blood pressure)
            # plus a broader "what else is missing" pass. Same generic
            # LatestValueSensor pattern as everything above; device_class is
            # only set where the class is long-standing enough in HA core to
            # be safe against this integration's declared minimum HA version
            # (2024.4.0) — newer/less-certain device classes are left unset
            # rather than risk an AttributeError breaking this whole module.
            LatestValueSensor(
                entry, data, METRIC_BLOOD_PRESSURE_SYSTOLIC, "Blood pressure (systolic)", "mmHg",
                "mdi:gauge", device_class=SensorDeviceClass.PRESSURE,
            ),
            LatestValueSensor(
                entry, data, METRIC_BLOOD_PRESSURE_DIASTOLIC, "Blood pressure (diastolic)", "mmHg",
                "mdi:gauge", device_class=SensorDeviceClass.PRESSURE,
            ),
            LatestValueSensor(
                entry, data, METRIC_WALKING_HEART_RATE, "Walking heart rate", "bpm", "mdi:walk"
            ),
            LatestValueSensor(
                entry, data, METRIC_HEART_RATE_RECOVERY, "Heart rate recovery", "bpm", "mdi:heart-cog-outline"
            ),
            LatestValueSensor(
                entry, data, METRIC_AFIB_BURDEN, "AFib burden", "%", "mdi:heart-pulse"
            ),
            LatestValueSensor(
                entry, data, METRIC_OXYGEN_SATURATION, "Blood oxygen", "%", "mdi:water-percent"
            ),
            LatestValueSensor(
                entry, data, METRIC_RESPIRATORY_RATE, "Respiratory rate", "breaths/min", "mdi:lungs"
            ),
            LatestValueSensor(
                entry, data, METRIC_BODY_TEMPERATURE, "Body temperature", UnitOfTemperature.CELSIUS,
                "mdi:thermometer", device_class=SensorDeviceClass.TEMPERATURE,
            ),
            LatestValueSensor(
                entry, data, METRIC_BLOOD_GLUCOSE, "Blood glucose", "mg/dL", "mdi:diabetes"
            ),
            LatestValueSensor(
                entry, data, METRIC_BODY_MASS_INDEX, "Body mass index", None, "mdi:human"
            ),
            LatestValueSensor(
                entry, data, METRIC_BODY_FAT_PERCENTAGE, "Body fat percentage", "%", "mdi:percent"
            ),
            LatestValueSensor(
                entry, data, METRIC_LEAN_BODY_MASS, "Lean body mass", "kg", "mdi:scale-bathroom",
                device_class=SensorDeviceClass.WEIGHT,
            ),
            LatestValueSensor(
                entry, data, METRIC_HEIGHT, "Height", "m", "mdi:human-male-height",
                device_class=SensorDeviceClass.DISTANCE,
            ),
            LatestValueSensor(
                entry, data, METRIC_WAIST_CIRCUMFERENCE, "Waist circumference", "m", "mdi:tape-measure",
                device_class=SensorDeviceClass.DISTANCE,
            ),
            # Added 12 Aug 2026 — same generic DailyTotalSensor/
            # LatestValueSensor classes as everything above, just more of
            # them, now that the ingestion pipeline is fully metric-agnostic.
            DailyTotalSensor(
                entry, data, METRIC_FLIGHTS_CLIMBED, "Flights climbed today", "flights", "mdi:stairs"
            ),
            DailyTotalSensor(
                entry, data, METRIC_EXERCISE_TIME, "Exercise time today", "min", "mdi:timer-outline",
                device_class=SensorDeviceClass.DURATION,
            ),
            DailyTotalSensor(
                entry, data, METRIC_RESTING_ENERGY, "Resting energy today", "kcal", "mdi:fire",
                device_class=SensorDeviceClass.ENERGY,
            ),
            DailyTotalSensor(
                entry, data, METRIC_DISTANCE, "Walking + running distance today", "m",
                "mdi:map-marker-distance", device_class=SensorDeviceClass.DISTANCE,
            ),
            LatestValueSensor(entry, data, METRIC_VO2_MAX, "VO2 max", "mL/(kg·min)", "mdi:lungs"),
            LatestValueSensor(
                entry, data, METRIC_WEIGHT, "Weight", "kg", "mdi:scale-bathroom",
                device_class=SensorDeviceClass.WEIGHT,
            ),
            SleepDurationSensor(entry, data),
            SleepTimestampSensor(entry, data, "onset", "Fell asleep", "mdi:weather-night"),
            SleepTimestampSensor(entry, data, "wake", "Woke up", "mdi:weather-sunset-up"),
            WorkoutTypeSensor(entry, data),
            WorkoutDurationSensor(entry, data),
            WorkoutDistanceSensor(entry, data),
            WorkoutCaloriesSensor(entry, data),
            LastSyncSensor(entry, data),
        ]
    )

    # Recent-workout slots (added 12 Aug 2026, replacing the old single
    # "Recent workouts" list-attribute sensor — its detail was buried in an
    # attribute with no per-workout UI). These grow one entity at a time as
    # real workouts arrive, up to MAX_RECENT_WORKOUTS, rather than being
    # pre-created empty. Once created a slot is never removed; its value and
    # name just get overwritten as newer workouts push older ones down —
    # same pattern the "last workout" sensors have always used. On restart,
    # re-add whichever slots already existed from a previous run first (each
    # restores its own data via RestoreSensor); only new workouts beyond
    # that create further slots. The unbounded, all-time history of every
    # workout ever synced already lives permanently in HA's Logbook/History
    # via the "Workout completed" event entity, so nothing above the cap is
    # ever lost — these slots are just a device-page-visible shortlist.
    existing_slots = sorted(
        int(e.unique_id.rsplit("_", 1)[-1])
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id.startswith(f"{entry.entry_id}_workout_slot_")
    )
    if existing_slots:
        async_add_entities(WorkoutSlotSensor(entry, data, slot) for slot in existing_slots)
    data.workout_slots_created = len(existing_slots)

    @callback
    def _maybe_add_workout_slot(_workout: dict[str, Any]) -> None:
        filled = sum(1 for w in data.recent_workouts if w is not None)
        if filled > data.workout_slots_created:
            new_slot = data.workout_slots_created
            data.workout_slots_created += 1
            async_add_entities([WorkoutSlotSensor(entry, data, new_slot)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_WORKOUT.format(entry_id=entry.entry_id), _maybe_add_workout_slot
        )
    )


def main_device_info(entry: HealthSyncConfigEntry) -> DeviceInfo:
    # Device name comes straight from the config entry's title (plain
    # "HealthSync" unless the user gave this entry a name at setup, e.g.
    # "HealthSync (Dad)") — added 11 Aug 2026 so multiple entries (a family,
    # each with their own webhook) show up as distinguishable devices
    # instead of several identically-named "HealthSync" entries.
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="HealthSync",
        model="Apple Health bridge",
        entry_type=DeviceEntryType.SERVICE,
    )


def workout_device_info(entry: HealthSyncConfigEntry) -> DeviceInfo:
    """Workouts get their own device (added 11 Aug 2026) — there's enough
    workout-specific data (type, duration, distance, calories, history) that
    lumping it into the single flat HealthSync device got crowded. Linked via
    `via_device` so it still shows as related to the main HealthSync device
    in the UI rather than as an unrelated integration.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_workouts")},
        name=f"{entry.title} Workouts",
        manufacturer="HealthSync",
        model="Apple Health bridge",
        entry_type=DeviceEntryType.SERVICE,
        via_device=(DOMAIN, entry.entry_id),
    )


class HealthSyncSensor(SensorEntity):
    """Base: dispatcher-driven updates, shared device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        self._data = data
        self._entry = entry
        self._attr_device_info = main_device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class HealthSyncWorkoutSensor(HealthSyncSensor):
    """Same dispatcher-driven behaviour as HealthSyncSensor, but attached to
    the separate "HealthSync Workouts" device."""

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_device_info = workout_device_info(entry)


class DailyTotalSensor(HealthSyncSensor, RestoreSensor):
    """Steps / active calories / flights climbed / exercise time / resting
    energy / distance accumulated for the current local day."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        entry: HealthSyncConfigEntry,
        data: HealthSyncData,
        metric: str,
        name: str,
        unit: str,
        icon: str,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        super().__init__(entry, data)
        self._metric = metric
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{metric}_today"
        if device_class is not None:
            self._attr_device_class = device_class

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Survive HA restarts mid-day: restore the running total unless the
        # day has rolled over since the state was saved.
        if self._metric in self._data.daily_totals:
            return
        last = await self.async_get_last_sensor_data()
        last_state = await self.async_get_last_state()
        if (
            last is not None
            and last.native_value is not None
            and last_state is not None
            and dt_util.as_local(last_state.last_updated).date()
            == dt_util.now().date()
        ):
            try:
                self._data.daily_totals[self._metric] = float(last.native_value)
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        value = self._data.daily_totals.get(self._metric)
        return round(value, 1) if value is not None else None


class LatestValueSensor(HealthSyncSensor, RestoreSensor):
    """Most recent heart rate / HRV / VO2 max / weight sample."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: HealthSyncConfigEntry,
        data: HealthSyncData,
        metric: str,
        name: str,
        # `None` for unitless metrics (Body Mass Index is a bare ratio, not
        # a physical quantity with a unit) — added 18 Aug 2026, matches how
        # the Health app itself shows BMI with no unit label.
        unit: str | None,
        icon: str,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        super().__init__(entry, data)
        self._metric = metric
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{metric}"
        if device_class is not None:
            self._attr_device_class = device_class

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._metric in self._data.latest_values:
            return
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._data.latest_values[self._metric] = float(last.native_value)
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        value = self._data.latest_values.get(self._metric)
        return round(value, 1) if value is not None else None


STAGE_ATTRIBUTES = {
    "asleepDeep": "deep_minutes",
    "asleepREM": "rem_minutes",
    "asleepCore": "core_minutes",
    "awake": "awake_minutes",
    "asleepUnspecified": "unspecified_minutes",
}


class SleepDurationSensor(HealthSyncSensor, RestoreSensor):
    """Hours asleep over the last 24 hours, with per-stage minutes as attributes."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "h"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:sleep"
    _attr_name = "Sleep last night"

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_unique_id = f"{entry.entry_id}_sleep_duration"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.sleep_duration_min is not None:
            return
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                # Stored in hours (native unit); runtime state is minutes.
                self._data.sleep_duration_min = float(last.native_value) * 60
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        if self._data.sleep_duration_min is None:
            return None
        return round(self._data.sleep_duration_min / 60, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            attribute: self._data.sleep_stage_minutes.get(stage)
            for stage, attribute in STAGE_ATTRIBUTES.items()
        }


class SleepTimestampSensor(HealthSyncSensor, RestoreSensor):
    """Fell-asleep / woke-up time from the sleep snapshot.

    State is the local clock time ("23:41") — that's what people want on a
    dashboard. The full ISO timestamp rides along as a `timestamp` attribute
    for automations that need real datetime math.
    """

    def __init__(
        self, entry: HealthSyncConfigEntry, data: HealthSyncData, kind: str, name: str, icon: str
    ) -> None:
        super().__init__(entry, data)
        self._kind = kind
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_sleep_{kind}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._current is not None:
            return
        # State is just "HH:MM", so restore from the full-precision attribute.
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        restored = dt_util.parse_datetime(str(last_state.attributes.get("timestamp", "")))
        if restored is None:
            return
        if self._kind == "onset":
            self._data.sleep_onset = restored
        else:
            self._data.sleep_wake = restored

    @property
    def _current(self):
        return self._data.sleep_onset if self._kind == "onset" else self._data.sleep_wake

    @property
    def native_value(self) -> str | None:
        if self._current is None:
            return None
        return dt_util.as_local(self._current).strftime("%H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"timestamp": self._current}


class WorkoutTypeSensor(HealthSyncWorkoutSensor, RestoreSensor):
    """Activity type of the most recent workout (added 11 Aug 2026).

    State is a string (e.g. "running") rather than a typed value, so restore
    goes through the plain `async_get_last_state()` path and reads
    start/end back out of attributes — same pattern as `SleepTimestampSensor`.
    """

    _attr_name = "Last workout type"

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_unique_id = f"{entry.entry_id}_last_workout_type"

    @property
    def icon(self) -> str:
        # Matches the actual activity (added 12 Aug 2026) rather than one
        # fixed icon for every workout — see WORKOUT_TYPE_ICONS.
        return WORKOUT_TYPE_ICONS.get(self._data.last_workout_type or "", WORKOUT_TYPE_ICONS["other"])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.last_workout_type is not None:
            return
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (None, "unknown", "unavailable"):
            return
        self._data.last_workout_type = last_state.state
        started = dt_util.parse_datetime(str(last_state.attributes.get("started_at", "")))
        ended = dt_util.parse_datetime(str(last_state.attributes.get("ended_at", "")))
        if started:
            self._data.last_workout_start = started
        if ended:
            self._data.last_workout_end = ended

    @property
    def native_value(self) -> str | None:
        return self._data.last_workout_type

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "started_at": self._data.last_workout_start,
            "ended_at": self._data.last_workout_end,
        }


class WorkoutDurationSensor(HealthSyncWorkoutSensor, RestoreSensor):
    """Duration of the most recent workout, in minutes."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Last workout duration"

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_unique_id = f"{entry.entry_id}_last_workout_duration"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.last_workout_duration_min is not None:
            return
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._data.last_workout_duration_min = float(last.native_value)
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        value = self._data.last_workout_duration_min
        return round(value, 1) if value is not None else None


class WorkoutDistanceSensor(HealthSyncWorkoutSensor, RestoreSensor):
    """Distance of the most recent workout, in meters.

    Wire format sends raw meters with no conversion — `device_class:
    distance` lets Home Assistant's own unit system (and per-entity display
    overrides) handle presentation. Null for workouts without a meaningful
    distance (yoga, strength training, ...).
    """

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "m"
    _attr_icon = "mdi:map-marker-distance"
    _attr_name = "Last workout distance"

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_unique_id = f"{entry.entry_id}_last_workout_distance"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.last_workout_distance_m is not None:
            return
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._data.last_workout_distance_m = float(last.native_value)
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        value = self._data.last_workout_distance_m
        return round(value, 1) if value is not None else None


class WorkoutCaloriesSensor(HealthSyncWorkoutSensor, RestoreSensor):
    """Active energy burned during the most recent workout."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "kcal"
    _attr_icon = "mdi:fire"
    _attr_name = "Last workout calories"

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_unique_id = f"{entry.entry_id}_last_workout_calories"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.last_workout_calories is not None:
            return
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._data.last_workout_calories = float(last.native_value)
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        value = self._data.last_workout_calories
        return round(value, 1) if value is not None else None


class WorkoutSlotSensor(HealthSyncWorkoutSensor, RestoreSensor):
    """One of up to MAX_RECENT_WORKOUTS individually-browsable recent-workout
    entities (added 12 Aug 2026, replacing the old single "Recent workouts"
    list-attribute sensor). Slot 0 is the most recent workout, slot 1 the
    one before that, etc. Slots are created progressively — see
    `async_setup_entry` — rather than all MAX_RECENT_WORKOUTS existing from
    the start.

    Named after the workout itself (e.g. "Walking 11-08-2026 11:55 13.1 mi")
    rather than "Workout 3": `name` is a live property, recomputed on every
    dispatcher-driven state write, so as newer workouts shift into this slot
    the displayed name updates to match — same as the state and attributes.
    The icon (added 12 Aug 2026) is likewise live and matches whichever
    activity currently occupies this slot — see WORKOUT_TYPE_ICONS.
    """

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData, slot: int) -> None:
        super().__init__(entry, data)
        self._slot = slot
        self._attr_unique_id = f"{entry.entry_id}_workout_slot_{slot}"

    @property
    def icon(self) -> str:
        workout = self._data.recent_workouts[self._slot]
        workout_type = workout["workout_type"] if workout else ""
        return WORKOUT_TYPE_ICONS.get(workout_type or "", WORKOUT_TYPE_ICONS["other"])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.recent_workouts[self._slot] is not None:
            return
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (None, "unknown", "unavailable"):
            return
        self._data.recent_workouts[self._slot] = {
            "workout_type": last_state.state,
            "started_at": last_state.attributes.get("started_at"),
            "ended_at": last_state.attributes.get("ended_at"),
            "duration_min": last_state.attributes.get("duration_min"),
            "distance_m": last_state.attributes.get("distance_m"),
            "calories": last_state.attributes.get("calories"),
        }

    @property
    def name(self) -> str:
        workout = self._data.recent_workouts[self._slot]
        if not workout:
            return f"Workout {self._slot + 1}"
        return _workout_label(self.hass, workout)

    @property
    def native_value(self) -> str | None:
        workout = self._data.recent_workouts[self._slot]
        return workout["workout_type"] if workout else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        workout = self._data.recent_workouts[self._slot]
        if not workout:
            return {}
        return {k: v for k, v in workout.items() if k != "workout_type"}


class LastSyncSensor(HealthSyncSensor):
    """When the last payload arrived from the app."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Last sync"
    _attr_icon = "mdi:sync"

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        super().__init__(entry, data)
        self._attr_unique_id = f"{entry.entry_id}_last_sync"

    @property
    def native_value(self):
        return self._data.last_sync
