"""The HealthSync integration.

Receives health samples POSTed by the HealthSync iOS app (one flat JSON
object per sample) on a Home Assistant webhook and exposes them as sensor
entities. Local push only — no polling, no cloud.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from typing import Any

from aiohttp import web

from homeassistant.components import cloud, persistent_notification, webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NAME,
    CONF_SECRET,
    CONF_WEBHOOK_ID,
    DAILY_TOTAL_METRICS,
    DOMAIN,
    EVENT_SAMPLE,
    EVENT_TEST,
    MAX_RECENT_WORKOUTS,
    METRIC_HEART_RATE,
    METRIC_HRV,
    METRIC_SLEEP,
    METRIC_TEST,
    METRIC_WORKOUTS,
    QUANTITY_METRICS,
    SIGNAL_UPDATE,
    SIGNAL_WORKOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "event"]

HealthSyncConfigEntry = ConfigEntry["HealthSyncData"]


@dataclass
class HealthSyncData:
    """Runtime state shared with the sensor platform."""

    # Daily totals (steps, active calories), keyed by metric.
    daily_totals: dict[str, float] = field(default_factory=dict)
    # The local date the daily totals belong to.
    totals_date: str = ""
    # Latest point-in-time values (heart rate, HRV), keyed by metric.
    latest_values: dict[str, float] = field(default_factory=dict)
    # End date of the newest sample seen per metric, to ignore out-of-order
    # deliveries (the app re-sends whole batches after a failed sync).
    latest_end: dict[str, datetime] = field(default_factory=dict)
    # Most recent sleep stage + its sample window.
    sleep_stage: str | None = None
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    # Minutes asleep in the last 24h, from the app's daily_total snapshot.
    sleep_duration_min: float | None = None
    # Sleep onset / wake time carried in the snapshot's start/end dates
    # (first asleep sample's start, last asleep sample's end).
    sleep_onset: datetime | None = None
    sleep_wake: datetime | None = None
    # Per-stage minutes last night (keys: asleepDeep/asleepREM/asleepCore/
    # awake/asleepUnspecified), from per-stage daily_total snapshots.
    sleep_stage_minutes: dict[str, float] = field(default_factory=dict)
    # Most recent workout (added 11 Aug 2026). `duration` is derived from
    # start/end rather than sent over the wire — the app doesn't send a
    # separate duration field, same rationale as everywhere else here.
    last_workout_type: str | None = None
    last_workout_start: datetime | None = None
    last_workout_end: datetime | None = None
    last_workout_duration_min: float | None = None
    last_workout_distance_m: float | None = None
    last_workout_calories: float | None = None
    # Bounded log of recent workouts, newest first (added for the "separate
    # device + richer history" restructure, 11 Aug 2026). Dates are stored
    # as ISO strings rather than datetimes so the list round-trips cleanly
    # through the recorder/restore path as sensor attributes.
    recent_workouts: list[dict] = field(default_factory=list)
    # Timestamp of the last received (valid) payload.
    last_sync: datetime | None = None
    # Recently seen sample keys, to drop replays: the app re-sends a whole
    # batch if any part of it failed, so duplicates are expected by design
    # and must not double-count daily totals.
    seen: set[tuple] = field(default_factory=set)
    seen_order: list[tuple] = field(default_factory=list)

    def mark_seen(self, key: tuple, max_entries: int = 5000) -> bool:
        """Record a sample key; returns False if it was already seen."""
        if key in self.seen:
            return False
        self.seen.add(key)
        self.seen_order.append(key)
        if len(self.seen_order) > max_entries:
            oldest = self.seen_order.pop(0)
            self.seen.discard(oldest)
        return True


async def async_setup_entry(hass: HomeAssistant, entry: HealthSyncConfigEntry) -> bool:
    """Set up HealthSync from a config entry."""
    entry.runtime_data = HealthSyncData(totals_date=dt_util.now().date().isoformat())

    webhook_id = entry.data[CONF_WEBHOOK_ID]
    webhook.async_register(
        hass,
        DOMAIN,
        entry.title,
        webhook_id,
        _make_webhook_handler(entry),
        allowed_methods=["POST"],
    )
    entry.async_on_unload(lambda: webhook.async_unregister(hass, webhook_id))

    # Reset daily totals at local midnight even if no sample arrives.
    @callback
    def _midnight_reset(now: datetime) -> None:
        data = entry.runtime_data
        data.daily_totals = {metric: 0.0 for metric in data.daily_totals}
        data.totals_date = dt_util.now().date().isoformat()
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry_id=entry.entry_id))

    entry.async_on_unload(
        async_track_time_change(hass, _midnight_reset, hour=0, minute=0, second=0)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # One-time pointer to the webhook URL the user needs to paste into the
    # app. With an active Nabu Casa subscription, mint the https cloudhook
    # ourselves (same pattern as the official companion app) instead of
    # handing the user an http URL and a manual Cloud → Webhooks dance.
    webhook_url: str | None = None
    if cloud.async_active_subscription(hass):
        try:
            webhook_url = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
        except cloud.CloudNotAvailable:
            webhook_url = None
    if webhook_url is None:
        webhook_url = webhook.async_generate_url(hass, webhook_id, prefer_external=True)

    person_name = entry.data.get(CONF_NAME)
    target_phrase = f"on {person_name}'s phone" if person_name else "on your phone"
    persistent_notification.async_create(
        hass,
        (
            f"Paste this webhook URL into the HealthSync app {target_phrase} "
            f"(Settings → Home Assistant):\n\n`{webhook_url}`"
            "\n\nNote: iOS requires https for remote addresses. Plain http is "
            "fine for local network and VPN/tunnel IP addresses "
            "(e.g. 192.168.x.x or a Tailscale 100.x address)."
        ),
        title=f"{entry.title} webhook ready",
        notification_id=f"{DOMAIN}_{entry.entry_id}",
    )

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up the cloudhook when the integration is removed."""
    if cloud.async_active_subscription(hass):
        try:
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass


async def async_unload_entry(hass: HomeAssistant, entry: HealthSyncConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _make_webhook_handler(entry: HealthSyncConfigEntry):
    """Build the webhook handler bound to this config entry."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        try:
            payload: dict[str, Any] = await request.json()
        except ValueError:
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="invalid JSON")

        if not isinstance(payload, dict):
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="expected object")

        # Shared-secret check (optional; configured in the config flow and
        # mirrored in the app's Settings).
        secret = entry.data.get(CONF_SECRET)
        if secret and payload.get("secret") != secret:
            _LOGGER.warning("HealthSync webhook: rejected payload with bad secret")
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="bad secret")

        data = entry.runtime_data

        # Batch format ({"samples": [...]}) is what the app sends;
        # single-object payloads are still accepted for hand-rolled setups.
        if isinstance(payload.get("samples"), list):
            samples = [item for item in payload["samples"] if isinstance(item, dict)]
        else:
            samples = [payload]

        handled = 0
        for sample in samples:
            metric = sample.get("metric")
            if not isinstance(metric, str):
                continue

            if metric == METRIC_TEST:
                data.last_sync = dt_util.utcnow()
                hass.bus.async_fire(EVENT_TEST, _event_payload(sample))
                persistent_notification.async_create(
                    hass,
                    "Test payload received from the HealthSync app — the connection works.",
                    title="HealthSync test successful",
                    notification_id=f"{DOMAIN}_test_{entry.entry_id}",
                )
                handled += 1
                continue

            # Drop replays (failed-batch re-sends) before they can
            # double-count daily totals or spam the event bus.
            key = (
                metric,
                sample.get("start_date"),
                sample.get("end_date"),
                sample.get("value"),
                sample.get("sleep_stage"),
            )
            if not data.mark_seen(key):
                continue

            data.last_sync = dt_util.utcnow()
            new_workout = _ingest_sample(hass, data, metric, sample)
            hass.bus.async_fire(EVENT_SAMPLE, _event_payload(sample))
            if new_workout is not None:
                async_dispatcher_send(
                    hass, SIGNAL_WORKOUT.format(entry_id=entry.entry_id), new_workout
                )
            handled += 1

        if handled == 0 and samples:
            # Everything was a duplicate — still fine, still 200.
            data.last_sync = dt_util.utcnow()

        async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry_id=entry.entry_id))
        return web.Response(status=HTTPStatus.OK)

    return handle_webhook


def _event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Payload for the HA event bus, without the shared secret."""
    return {key: value for key, value in payload.items() if key != "secret"}


def _ingest_sample(
    hass: HomeAssistant,
    data: HealthSyncData,
    metric: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Fold one sample into the runtime state.

    Returns the new workout dict when this sample was a genuinely new
    (in-order) workout, so the caller can fire SIGNAL_WORKOUT for the event
    entity. None otherwise.
    """
    start = _parse_date(payload.get("start_date"))
    end = _parse_date(payload.get("end_date"))

    if metric == METRIC_SLEEP:
        # Snapshot: minutes asleep over the last 24h (authoritative, set not
        # summed — same semantics as the steps/calories snapshots).
        if payload.get("daily_total"):
            duration = payload.get("value")
            stage = payload.get("sleep_stage")
            if isinstance(stage, str):
                # Per-stage snapshot (deep/REM/core/awake minutes).
                if isinstance(duration, (int, float)):
                    data.sleep_stage_minutes[stage] = float(duration)
                return
            if isinstance(duration, (int, float)):
                data.sleep_duration_min = float(duration)
            # Snapshot start/end double as fell-asleep / woke-up times.
            data.sleep_onset = start or data.sleep_onset
            data.sleep_wake = end or data.sleep_wake
            return
        stage = payload.get("sleep_stage")
        if not isinstance(stage, str):
            return
        # Only move forward in time; batch retries can replay old samples.
        if end and data.sleep_end and end < data.sleep_end:
            return
        data.sleep_stage = stage
        data.sleep_start = start
        data.sleep_end = end
        return

    if metric == METRIC_WORKOUTS:
        # Whether this is the newest workout seen so far governs the "last
        # workout" *snapshot* fields only — it must NOT gate whether the
        # workout gets recorded at all. A normal incremental sync only ever
        # delivers one or two workouts, roughly in order, so the two things
        # were previously conflated (an out-of-order arrival just returned
        # early). But "Sync All Workout History" delivers dozens/hundreds of
        # workouts in one batch, in whatever order HealthKit's anchored
        # query happens to return them — NOT guaranteed chronological — so
        # treating "older than the last-processed one" as "reject entirely"
        # silently dropped almost everything except whichever workout
        # happened to be processed first (e.g. 40 synced from the app, only
        # 1 landing in HA). Every workout that reaches here already passed
        # the replay-dedup check in the webhook handler, so it's always
        # legitimate to log it — only the scalar "latest" fields need the
        # ordering guard.
        is_newest = not (end and (previous := data.latest_end.get(metric)) and end < previous)

        value = payload.get("value")
        workout_type = payload.get("workout_type")
        duration_min = (end - start).total_seconds() / 60 if start and end else None
        distance = payload.get("distance")
        distance_m = float(distance) if isinstance(distance, (int, float)) else None
        calories = float(value) if isinstance(value, (int, float)) else None

        if is_newest:
            data.last_workout_type = workout_type
            data.last_workout_start = start
            data.last_workout_end = end
            data.last_workout_duration_min = duration_min
            data.last_workout_distance_m = distance_m
            data.last_workout_calories = calories
            if end:
                data.latest_end[metric] = end

        workout = {
            "workout_type": workout_type,
            "started_at": start.isoformat() if start else None,
            "ended_at": end.isoformat() if end else None,
            "duration_min": round(duration_min, 1) if duration_min is not None else None,
            "distance_m": distance_m,
            "calories": calories,
        }
        data.recent_workouts.insert(0, workout)
        del data.recent_workouts[MAX_RECENT_WORKOUTS:]
        return workout

    if metric not in QUANTITY_METRICS:
        _LOGGER.debug("HealthSync: ignoring unknown metric %r", metric)
        return None

    value = payload.get("value")
    if not isinstance(value, (int, float)):
        return None

    if metric in DAILY_TOTAL_METRICS:
        # State comes ONLY from daily-total snapshots ("daily_total": true),
        # which carry today's cumulative value straight from Apple Health.
        # Incremental samples are deliberately NOT summed — accumulation is
        # fragile (batch replays, HA restarts, and restores all corrupt a
        # running sum) — but they still fire healthsync_sample events for
        # automations.
        if payload.get("daily_total"):
            data.daily_totals[metric] = float(value)
            data.totals_date = dt_util.now().date().isoformat()
        return None

    if metric in (METRIC_HEART_RATE, METRIC_HRV):
        if end and (previous := data.latest_end.get(metric)) and end < previous:
            return None
        data.latest_values[metric] = float(value)
        if end:
            data.latest_end[metric] = end
    return None


def _parse_date(raw: Any) -> datetime | None:
    """Parse the app's ISO8601 date strings."""
    if not isinstance(raw, str):
        return None
    return dt_util.parse_datetime(raw)
