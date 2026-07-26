# HealthSync for Home Assistant

Companion integration for the **HealthSync** iOS app. The app reads Apple
Health data (steps, heart rate, HRV, sleep, active calories) and pushes it
to Home Assistant; this integration receives those pushes on a webhook and
exposes them as sensor entities. Local push only — no cloud, no polling,
no external dependencies.

## Entities

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

Every sample also fires a `healthsync_sample` event on the bus (raw payload,
secret stripped) for your own automations; the app's Test Connection button
fires `healthsync_test` and a confirmation notification.

## Install

**HACS (custom repository):** HACS → Integrations → ⋮ → Custom
repositories → add this repo (category: Integration) → install → restart HA.

**Manual:** copy `custom_components/healthsync/` into your HA `config/custom_components/` and restart.

## Setup

1. Settings → Devices & Services → Add Integration → **HealthSync**.
2. Optionally set a shared secret (recommended if your HA is reachable from
   the internet). Payloads without the correct secret are rejected with 401.
3. After setup, a notification shows the generated webhook URL. Paste it
   into the HealthSync app (Settings → Home Assistant), and enter the same
   secret there if you set one.
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
