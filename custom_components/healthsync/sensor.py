"""Sensor entities for the HealthSync integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HealthSyncConfigEntry, HealthSyncData
from .const import (
    DOMAIN,
    METRIC_ACTIVE_CALORIES,
    METRIC_HEART_RATE,
    METRIC_HRV,
    METRIC_STEPS,
    SIGNAL_UPDATE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HealthSyncConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HealthSync sensors."""
    data = entry.runtime_data

    # The "Sleep stage" sensor was removed in 0.6.0 (a latest-stage value is
    # frozen at whatever the user woke from — the per-stage breakdown lives
    # as attributes on "Sleep last night" now). Clean up the old entity.
    registry = er.async_get(hass)
    stale = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_sleep_stage")
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
            SleepDurationSensor(entry, data),
            SleepTimestampSensor(entry, data, "onset", "Fell asleep", "mdi:weather-night"),
            SleepTimestampSensor(entry, data, "wake", "Woke up", "mdi:weather-sunset-up"),
            LastSyncSensor(entry, data),
        ]
    )


class HealthSyncSensor(SensorEntity):
    """Base: dispatcher-driven updates, shared device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: HealthSyncConfigEntry, data: HealthSyncData) -> None:
        self._data = data
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="HealthSync",
            manufacturer="HealthSync",
            model="Apple Health bridge",
            entry_type=DeviceEntryType.SERVICE,
        )

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


class DailyTotalSensor(HealthSyncSensor, RestoreSensor):
    """Steps / active calories accumulated for the current local day."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        entry: HealthSyncConfigEntry,
        data: HealthSyncData,
        metric: str,
        name: str,
        unit: str,
        icon: str,
    ) -> None:
        super().__init__(entry, data)
        self._metric = metric
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{metric}_today"

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
    """Most recent heart rate / HRV sample."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: HealthSyncConfigEntry,
        data: HealthSyncData,
        metric: str,
        name: str,
        unit: str,
        icon: str,
    ) -> None:
        super().__init__(entry, data)
        self._metric = metric
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{metric}"

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
