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

The integration creates two devices: **HealthSync** (steps, heart rate and
related vitals, sleep, body measurements, activity totals, and sync status
— see the table below for the full list) and **HealthSync Workouts**
(everything workout-related, listed as a related device on the HealthSync
device page).

| Entity | Meaning |
|---|---|
| Steps today | Steps accumulated since local midnight |
| Active calories today | Active energy (kcal) since local midnight |
| Heart rate | Most recent heart-rate sample (bpm) |
| Resting heart rate | Most recent resting heart-rate sample (bpm) |
| Heart rate variability | Most recent HRV SDNN sample (ms) |
| Blood pressure (systolic) / (diastolic) | Most recent blood-pressure reading (mmHg) — two separate entities, since HealthKit tracks them as two quantities |
| Walking heart rate | Most recent walking heart-rate average (bpm) |
| Heart rate recovery | Most recent 1-minute post-exercise heart rate recovery (bpm) |
| AFib burden | Most recent atrial fibrillation burden estimate (%) |
| Blood oxygen | Most recent SpO2 reading (%) |
| Respiratory rate | Most recent respiratory rate (breaths/min) |
| Body temperature | Most recent body temperature reading (°C, or °F to match your Home Assistant unit system) |
| Blood glucose | Most recent blood glucose reading (mg/dL) |
| Flights climbed today | Flights climbed since local midnight |
| Exercise time today | Apple's "Exercise" minutes since local midnight |
| Resting energy today | Basal/resting energy (kcal) since local midnight |
| Walking + running distance today | Meters since local midnight — shown in km or mi to match your Home Assistant unit system |
| VO2 max | Most recent VO2 max reading (mL/(kg·min)) |
| Weight | Most recent weight sample — shown in kg or lb to match your Home Assistant unit system |
| Body mass index | Most recent BMI reading (unitless) |
| Body fat percentage | Most recent body fat reading (%) |
| Lean body mass | Most recent lean body mass reading — shown in kg or lb to match your Home Assistant unit system |
| Height | Most recent height reading — shown in m or ft to match your Home Assistant unit system |
| Waist circumference | Most recent waist circumference reading — shown in m or ft to match your Home Assistant unit system |
| Heart rate reading / Heart rate variability reading / VO2 max reading / Weight reading | Event entities — fire once per *individual* reading, regardless of how many arrive in the same sync. The "current value" sensors above only ever reflect whichever reading happened to be last in a batch; these guarantee every reading's exact value + Apple's own timestamp is genuinely recorded (value/unit/start_date/end_date attributes) — zero rounding or averaging, even for readings a batch would otherwise have silently overwritten. Shows a readable Logbook line (e.g. "Heart rate reading recorded 84 bpm"), and is fully queryable via History/Logbook, automations, or exports. Not a graphable History *line chart* the way a regular sensor is, though — this is the exact record, not the visual one |
| Sleep last night | Hours asleep over the last 24 hours; per-stage breakdown (`deep_minutes`, `rem_minutes`, `core_minutes`, `awake_minutes`) as attributes |
| Fell asleep | Local clock time the night's sleep began ("23:41"); full ISO datetime in the `timestamp` attribute |
| Woke up | Local clock time the night's sleep ended ("07:12"); full ISO datetime in the `timestamp` attribute |
| Last sync | When the last payload arrived from the app |

### Viewing accurate history for heart rate, HRV, VO2 max, and weight

These four also get proper Home Assistant long-term statistics in the
background — every individual reading Apple recorded is rolled into an
hourly min/max/mean, dated to the hour it actually happened in (not
whenever HealthSync happened to sync). Home Assistant's statistics engine
only supports hourly resolution, so this is the finest-grained
*accurately-dated* history it can produce.

**Important:** the default entity card / History panel in Home Assistant
usually graphs raw state changes, not this statistics data — so it can
still look like one flat value that jumps once per sync, especially
across a long gap (e.g. overnight). That's the default Home Assistant view
being low-resolution, not a broken integration — the accurate hourly data
is there regardless, in the statistics store.

To actually see it, add a **Statistics Graph** card to a dashboard,
pointed at the entity, e.g.:

```yaml
type: statistics-graph
title: Heart rate
entities:
  - sensor.healthsync_heart_rate
stat_types:
  - min
  - mean
  - max
period:
  hour: 1
```

Swap the entity for HRV, VO2 max, or weight as needed (adjust `-` naming
to match your actual entity IDs, and add `(Name)` suffixes if you've set
up more than one family member).

### Reducing Logbook noise

A couple of entities update often enough that they can dominate the
Logbook feed — notably **Last sync** (fires on every sync) and the four
**reading** event entities above (heart rate especially can fire many
times an hour; each shows a readable line like "Heart rate reading
recorded 84 bpm", but volume alone can still feel busy). This is purely
about Logbook clutter — it doesn't affect their recorded data, History, or
any automations either way. If you'd rather quiet them down, exclude them
in `configuration.yaml`:

```yaml
logbook:
  exclude:
    entities:
      - sensor.healthsync_last_sync
      - event.healthsync_heart_rate_reading
      - event.healthsync_heart_rate_variability_reading
      - event.healthsync_vo2_max_reading
      - event.healthsync_weight_reading
```

(Adjust entity IDs to match your actual ones, especially if you've set up
more than one family member.)

**HealthSync Workouts** device:

| Entity | Meaning |
|---|---|
| Last workout type | Activity of the most recent workout (e.g. "running"); start/end datetimes in `started_at`/`ended_at` attributes |
| Last workout duration | Minutes, derived from the workout's start/end |
| Last workout distance | Meters — null for workouts without a meaningful distance (yoga, strength training, ...) |
| Last workout calories | Active energy burned (kcal) |
| Walking 11-08-2026 11:55 13.1 mi (×10) | Individual entities for your 10 most recent workouts, named after the workout itself (type, date/time, distance — distance shown in km or mi to match your Home Assistant unit system). Full detail (start/end, duration, distance, calories) in attributes. These appear one at a time as real workouts sync in, rather than all 10 existing upfront, and are never removed — older ones just get overwritten as newer workouts push them down |
| Workout completed | Event entity — fires once per new workout with the same details as an attribute, so it shows in the Logbook and works as a clean automation trigger ("when a workout is completed..."). Browsable via Home Assistant's Logbook/History pages, filterable by type or date — but note this is subject to Home Assistant's normal recorder purge (10 days by default), so it isn't a permanent record on its own. For genuinely unlimited, permanent workout history, see the readings database below — every workout ever synced (not just the 10 slots above) is archived there indefinitely |

Every sample also fires a `healthsync_sample` event on the bus (raw payload,
secret stripped) for your own automations; the app's Test Connection button
fires `healthsync_test` and a confirmation notification.

### Complete, unaveraged history — every reading, every metric

Every sample the app sends — not just heart rate/HRV/VO2 max/weight, all
twelve metrics — is separately archived exactly as Apple Health produced it:
the real value and Apple's own timestamp, never rounded, averaged, or
bucketed into anything coarser. This lives in its own small database
alongside the rest of Home Assistant's storage (so it's included in HA
backups automatically), independent of the entities and statistics above —
those exist to give you a live dashboard value and an hourly graph; this is
the underlying exact record, kept in full regardless of what the entities
show.

Query it with the **`healthsync.get_readings`** action (Developer Tools →
Actions, or from an automation/template):

```yaml
action: healthsync.get_readings
data:
  device_id: <your HealthSync device>
  metric: heartRate
  start: "2026-08-01T00:00:00"
  end: "2026-08-13T00:00:00"
```

`start`/`end` are optional — omit both for the full history. Returns a list
of readings (value, unit, exact start/end timestamps, source, and a few
metric-specific fields like `sleep_stage` or `distance` where relevant).
Handy for a custom chart card (e.g. ApexCharts) or your own export/analysis,
without being limited to HA's hourly-statistics resolution.

This also covers workouts (`metric: workouts`) — every workout ever synced,
with its exact type, distance, calories, and start/end times, kept
permanently and not subject to the Logbook/recorder purge mentioned above.
This is the one to use if you want workout history that's genuinely
unlimited rather than bounded by your recorder settings.

## Install

**HACS:** HACS → Integrations → search "HealthSync" → install → restart HA.
(Listed in HACS's default repositories as of 1 Aug 2026 — no custom
repository step needed.)

**Manual:** copy `custom_components/healthsync/` into your HA `config/custom_components/` and restart.

## Setup

1. Settings → Devices & Services → Add Integration → **HealthSync**.
2. Optionally give this entry a name (e.g. "Dad") and/or set a shared secret
   (recommended if your HA is reachable from the internet). Payloads without
   the correct secret are rejected with 401.
3. After setup, a notification shows the generated webhook URL. Paste it
   into the HealthSync app (Settings → Home Assistant), and enter the same
   secret there if you set one. That URL already includes everything
   needed — paste it whole, don't split it up. Leave "Shared secret" blank
   unless you explicitly set one in step 2.
4. Tap **Test Connection** in the app — you should get a "HealthSync test
   successful" notification in HA.

### More than one person

Add HealthSync again (Settings → Devices & Services → Add Integration →
**HealthSync**) once per person — each entry gets its own webhook URL, so
everyone points their own phone at their own URL. Name each entry (step 2
above) so the devices are distinguishable — e.g. "HealthSync (Dad)" and
"HealthSync (Dad) Workouts" rather than several identically-named
"HealthSync" devices.

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
