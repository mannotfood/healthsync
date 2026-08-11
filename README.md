# HealthSync for Home Assistant

Companion integration for the **HealthSync** iOS app. The app reads Apple
Health data (steps, heart rate, HRV, sleep, active calories, workouts) and
pushes it to Home Assistant; this integration receives those pushes on a
webhook and exposes them as sensor entities. Local push only — no cloud, no
polling, no external dependencies.

## Get the iOS app

**HealthSync for Home Assistant** — iOS 17+, one-time purchase to unlock
automatic background syncing (manual sync is free forever, no subscription),
local-first with no third-party servers.

**[Download on the App Store](https://apps.apple.com/app/healthsync-for-home-assistant/id6794884113)**
— note there are several unrelated apps also named "HealthSync"; the link
above is this project specifically.

## Entities

The integration creates two devices: **HealthSync** (steps, heart rate,
HRV, sleep, sync status) and **HealthSync Workouts** (everything
workout-related, listed as a related device on the HealthSync device page).

| Entity | Meaning |
|---|---|
| Steps today | Steps accumulated since local midnight |
| Active calories today | Active energy (kcal) since local midnight |
| Heart rate | Most recent heart-rate sample (bpm) |
| Heart rate variability | Most recent HRV SDNN sample (ms) |
| Sleep last night | Hours asleep over the last 24 hours; per-stage breakdown (`deep_minutes`, `rem_minutes`, `core_minutes`, `awake_minutes`) as attributes |
| Fell asleep | Local clock time the night's sleep began ("23:41"); full ISO datetime in the `timestamp` attribute |
| Woke up | Local clock time the night's sleep ended ("07:12"); full ISO datetime in the `timestamp` attribute |
| Last sync | When the last payload arrived from the app |

**HealthSync Workouts** device:

| Entity | Meaning |
|---|---|
| Last workout type | Activity of the most recent workout (e.g. "running"); start/end datetimes in `started_at`/`ended_at` attributes |
| Last workout duration | Minutes, derived from the workout's start/end |
| Last workout distance | Meters — null for workouts without a meaningful distance (yoga, strength training, ...) |
| Last workout calories | Active energy burned (kcal) |
| Recent workouts | State is a count; the last 10 workouts (type, start/end, duration, distance, calories) are in the `workouts` attribute — for history cards, templates, or catching up on anything missed |
| Workout completed | Event entity — fires once per new workout with the same details as an attribute, so it shows in the Logbook and works as a clean automation trigger ("when a workout is completed...") |

Every sample also fires a `healthsync_sample` event on the bus (raw payload,
secret stripped) for your own automations; the app's Test Connection button
fires `healthsync_test` and a confirmation notification.

## Install

**HACS:** HACS → Integrations → search "HealthSync" → install → restart HA.
(Listed in HACS's default repositories as of 1 Aug 2026 — no custom
repository step needed.)

**Manual:** copy `custom_components/healthsync/` into your HA `config/custom_components/` and restart.

## Setup

1. Settings → Devices & Services → Add Integration → **HealthSync**.
2. Optionally set a shared secret (recommended if your HA is reachable from
   the internet). Payloads without the correct secret are rejected with 401.
3. After setup, a notification shows the generated webhook URL. Paste it
   into the HealthSync app (Settings → Home Assistant), and enter the same
   secret there if you set one. That URL already includes everything
   needed — paste it whole, don't split it up. Leave "Shared secret" blank
   unless you explicitly set one in step 2.
4. Tap **Test Connection** in the app — you should get a "HealthSync test
   successful" notification in HA.

## Notes

- The app deliberately re-sends a whole batch if any sample in it failed to
  deliver. The integration deduplicates replayed samples (keyed on
  metric + dates + value) so daily totals don't overcount.
- The app needs an **https** webhook URL unless HA is on your local
  network — a Nabu Casa cloudhook works well.
- Daily totals reset at HA's local midnight and survive HA restarts
  mid-day.
- Heart-rate history can grow quickly with an Apple Watch. Consider
  excluding the heart-rate sensor from `recorder` long-term statistics if
  database size matters to you.
