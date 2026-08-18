"""Constants for the HealthSync integration."""

DOMAIN = "healthsync"

CONF_WEBHOOK_ID = "webhook_id"
CONF_SECRET = "secret"
# Optional per-entry label (added 11 Aug 2026 to support more than one
# person — e.g. a family, each with their own phone/webhook — under the
# same HA instance). Folded straight into the config entry's title rather
# than stored separately; device names are derived from entry.title.
CONF_NAME = "name"

# entry.options flag: has the one-time "paste this webhook URL into the app"
# notification already been shown for this entry? Lives in options rather
# than data since it's internal setup-progress state, not a config-flow
# answer. Without this, async_setup_entry (which runs on every HA restart,
# not just first-ever setup) re-creates the notification every time —
# resurrecting it even after the user dismissed it.
OPT_WEBHOOK_NOTIFIED = "webhook_notified"

# Metric names as sent by the iOS app (HealthMetricType raw values).
METRIC_STEPS = "steps"
METRIC_HEART_RATE = "heartRate"
METRIC_HRV = "heartRateVariability"
METRIC_SLEEP = "sleep"
METRIC_ACTIVE_CALORIES = "activeCalories"
METRIC_WORKOUTS = "workouts"
# Added 12 Aug 2026 — same wire format/ingestion pattern as the metrics
# above, no special-casing needed beyond being listed in the right set below.
METRIC_FLIGHTS_CLIMBED = "flightsClimbed"
METRIC_EXERCISE_TIME = "exerciseTime"
METRIC_RESTING_ENERGY = "restingEnergy"
METRIC_DISTANCE = "distanceWalkingRunning"
METRIC_VO2_MAX = "vo2Max"
METRIC_WEIGHT = "weight"
# Added 18 Aug 2026 — same generic quantity-metric pipeline as everything
# else here, no special-casing needed (see sensor.py/iOS's HealthMetricType
# for the matching addition).
METRIC_RESTING_HEART_RATE = "restingHeartRate"
# Added 18 Aug 2026 — requested via GitHub #15 (blood pressure) plus a
# broader "what else is missing" pass. Same generic quantity-metric
# pipeline as everything above; see iOS's HealthMetricType for the matching
# cases and HistoryBackfillEngine for why every one of these (like every
# other metric except workouts) can also be manually backfilled.
METRIC_BLOOD_PRESSURE_SYSTOLIC = "bloodPressureSystolic"
METRIC_BLOOD_PRESSURE_DIASTOLIC = "bloodPressureDiastolic"
METRIC_WALKING_HEART_RATE = "walkingHeartRateAverage"
METRIC_HEART_RATE_RECOVERY = "heartRateRecoveryOneMinute"
METRIC_AFIB_BURDEN = "atrialFibrillationBurden"
METRIC_OXYGEN_SATURATION = "oxygenSaturation"
METRIC_RESPIRATORY_RATE = "respiratoryRate"
METRIC_BODY_TEMPERATURE = "bodyTemperature"
METRIC_BLOOD_GLUCOSE = "bloodGlucose"
METRIC_BODY_MASS_INDEX = "bodyMassIndex"
METRIC_BODY_FAT_PERCENTAGE = "bodyFatPercentage"
METRIC_LEAN_BODY_MASS = "leanBodyMass"
METRIC_HEIGHT = "height"
METRIC_WAIST_CIRCUMFERENCE = "waistCircumference"
METRIC_TEST = "test_connection"

QUANTITY_METRICS = {
    METRIC_STEPS,
    METRIC_HEART_RATE,
    METRIC_HRV,
    METRIC_ACTIVE_CALORIES,
    METRIC_FLIGHTS_CLIMBED,
    METRIC_EXERCISE_TIME,
    METRIC_RESTING_ENERGY,
    METRIC_DISTANCE,
    METRIC_VO2_MAX,
    METRIC_WEIGHT,
    METRIC_RESTING_HEART_RATE,
    METRIC_BLOOD_PRESSURE_SYSTOLIC,
    METRIC_BLOOD_PRESSURE_DIASTOLIC,
    METRIC_WALKING_HEART_RATE,
    METRIC_HEART_RATE_RECOVERY,
    METRIC_AFIB_BURDEN,
    METRIC_OXYGEN_SATURATION,
    METRIC_RESPIRATORY_RATE,
    METRIC_BODY_TEMPERATURE,
    METRIC_BLOOD_GLUCOSE,
    METRIC_BODY_MASS_INDEX,
    METRIC_BODY_FAT_PERCENTAGE,
    METRIC_LEAN_BODY_MASS,
    METRIC_HEIGHT,
    METRIC_WAIST_CIRCUMFERENCE,
}
# Metrics accumulated into a daily total (the app sends incremental samples,
# not running totals).
DAILY_TOTAL_METRICS = {
    METRIC_STEPS,
    METRIC_ACTIVE_CALORIES,
    METRIC_FLIGHTS_CLIMBED,
    METRIC_EXERCISE_TIME,
    METRIC_RESTING_ENERGY,
    METRIC_DISTANCE,
}
# Metrics whose state is just "the most recent sample" (a discrete,
# infrequent reading) rather than a running daily total.
LATEST_VALUE_METRICS = {
    METRIC_HEART_RATE, METRIC_HRV, METRIC_VO2_MAX, METRIC_WEIGHT, METRIC_RESTING_HEART_RATE,
    METRIC_BLOOD_PRESSURE_SYSTOLIC, METRIC_BLOOD_PRESSURE_DIASTOLIC, METRIC_WALKING_HEART_RATE,
    METRIC_HEART_RATE_RECOVERY, METRIC_AFIB_BURDEN, METRIC_OXYGEN_SATURATION,
    METRIC_RESPIRATORY_RATE, METRIC_BODY_TEMPERATURE, METRIC_BLOOD_GLUCOSE,
    METRIC_BODY_MASS_INDEX, METRIC_BODY_FAT_PERCENTAGE, METRIC_LEAN_BODY_MASS,
    METRIC_HEIGHT, METRIC_WAIST_CIRCUMFERENCE,
}

SLEEP_STAGES = [
    "inBed",
    "asleepUnspecified",
    "awake",
    "asleepCore",
    "asleepDeep",
    "asleepREM",
]

EVENT_SAMPLE = "healthsync_sample"
EVENT_TEST = "healthsync_test"
# Distinct from EVENT_SAMPLE (which fires for *every* metric, including
# high-volume ones like steps, and has no Logbook describer registered —
# deliberately silent there) — this one is scoped to just the four
# latest-value metrics specifically so its logbook.py describer only ever
# affects those, not the rest of the integration's Logbook behaviour.
EVENT_METRIC_READING = "healthsync_metric_reading"

SIGNAL_UPDATE = "healthsync_update_{entry_id}"
# Fired only when a genuinely new (non-replayed, in-order) workout lands —
# distinct from SIGNAL_UPDATE so the workout event entity doesn't fire on
# every unrelated sample (steps, heart rate, ...).
SIGNAL_WORKOUT = "healthsync_workout_{entry_id}"

# Fired once per individual latest-value sample (heart rate, HRV, VO2 max,
# weight) as it's processed — added 13 Aug 2026 so every reading gets its own
# recorded event, not just whichever one happens to be last when a batch of
# several arrives in one webhook call. SIGNAL_UPDATE only fires once per
# whole webhook POST, so the "current value" sensor it drives can only ever
# reflect the batch's final reading — real per-reading data (accurate value
# + Apple's own timestamp for each one) needs this separate, per-sample
# signal instead.
SIGNAL_METRIC_READING = "healthsync_metric_reading_{entry_id}"

# How many recent workouts the "Recent workouts" sensor keeps as attributes.
MAX_RECENT_WORKOUTS = 10

# healthsync.get_readings — returns every individual reading archived in a
# config entry's ReadingsStore (db.py) for one metric, exactly as received,
# optionally bounded to a date range. Registered once for the whole domain
# (see async_setup in __init__.py), not per config entry.
SERVICE_GET_READINGS = "get_readings"
# Every metric a reading can legitimately be archived under — built from the
# same sets the rest of the integration already uses, so this can't drift
# out of sync with what _ingest_sample actually accepts.
ALL_READING_METRICS = sorted(QUANTITY_METRICS | {METRIC_SLEEP, METRIC_WORKOUTS})

# Mirrors the iOS app's WorkoutType.swift raw values exactly (including
# "other", its own fallback case) — the closed set of event_types the
# workout_completed event entity can fire. Kept in sync manually; a workout
# type added to WorkoutType.swift needs the matching string added here too,
# or it'll fall back to "other" rather than erroring.
WORKOUT_EVENT_TYPES = [
    "americanFootball",
    "archery",
    "australianFootball",
    "badminton",
    "baseball",
    "basketball",
    "bowling",
    "boxing",
    "climbing",
    "cricket",
    "crossTraining",
    "curling",
    "cycling",
    "elliptical",
    "equestrianSports",
    "fencing",
    "fishing",
    "functionalStrengthTraining",
    "golf",
    "gymnastics",
    "handball",
    "handCycling",
    "hiking",
    "hockey",
    "hunting",
    "jumpRope",
    "kickboxing",
    "lacrosse",
    "martialArts",
    "mindAndBody",
    "mixedCardio",
    "paddleSports",
    "pickleball",
    "pilates",
    "play",
    "racquetball",
    "rowing",
    "rugby",
    "running",
    "sailing",
    "skatingSports",
    "snowSports",
    "soccer",
    "softball",
    "squash",
    "stairClimbing",
    "surfingSports",
    "swimming",
    "tableTennis",
    "taiChi",
    "tennis",
    "trackAndField",
    "traditionalStrengthTraining",
    "volleyball",
    "walking",
    "waterFitness",
    "waterPolo",
    "waterSports",
    "wheelchairRunPace",
    "wheelchairWalkPace",
    "wrestling",
    "yoga",
    "highIntensityIntervalTraining",
    "coreTraining",
    "flexibility",
    "barre",
    "other",
]

# Per-activity icon for the workout entities (added 12 Aug 2026) — best
# effort across all 67 types; a handful of the less common ones (curling,
# lacrosse, wrestling) don't have a perfect dedicated MDI icon and use the
# closest reasonable stand-in. Every key here must exist in
# WORKOUT_EVENT_TYPES (including "other", used as the fallback for
# anything missing from this map).
WORKOUT_TYPE_ICONS = {
    "americanFootball": "mdi:football-helmet",
    "archery": "mdi:target",
    "australianFootball": "mdi:football-australian",
    "badminton": "mdi:badminton",
    "baseball": "mdi:baseball",
    "basketball": "mdi:basketball",
    "bowling": "mdi:bowling",
    "boxing": "mdi:boxing-glove",
    "climbing": "mdi:carabiner",
    "cricket": "mdi:cricket",
    "crossTraining": "mdi:weight-lifter",
    "curling": "mdi:snowflake-variant",
    "cycling": "mdi:bike",
    "elliptical": "mdi:run-fast",
    "equestrianSports": "mdi:horse",
    "fencing": "mdi:fencing",
    "fishing": "mdi:fish",
    "functionalStrengthTraining": "mdi:dumbbell",
    "golf": "mdi:golf",
    "gymnastics": "mdi:gymnastics",
    "handball": "mdi:handball",
    "handCycling": "mdi:bike",
    "hiking": "mdi:hiking",
    "hockey": "mdi:hockey-sticks",
    "hunting": "mdi:target",
    "jumpRope": "mdi:jump-rope",
    "kickboxing": "mdi:karate",
    "lacrosse": "mdi:hockey-sticks",
    "martialArts": "mdi:karate",
    "mindAndBody": "mdi:meditation",
    "mixedCardio": "mdi:heart-pulse",
    "paddleSports": "mdi:kayaking",
    "pickleball": "mdi:tennis",
    "pilates": "mdi:yoga",
    "play": "mdi:emoticon-happy-outline",
    "racquetball": "mdi:racquetball",
    "rowing": "mdi:rowing",
    "rugby": "mdi:rugby",
    "running": "mdi:run",
    "sailing": "mdi:sail-boat",
    "skatingSports": "mdi:skate",
    "snowSports": "mdi:ski",
    "soccer": "mdi:soccer",
    "softball": "mdi:baseball",
    "squash": "mdi:racquetball",
    "stairClimbing": "mdi:stairs",
    "surfingSports": "mdi:surfing",
    "swimming": "mdi:swim",
    "tableTennis": "mdi:table-tennis",
    "taiChi": "mdi:yin-yang",
    "tennis": "mdi:tennis",
    "trackAndField": "mdi:run-fast",
    "traditionalStrengthTraining": "mdi:weight-lifter",
    "volleyball": "mdi:volleyball",
    "walking": "mdi:walk",
    "waterFitness": "mdi:pool",
    "waterPolo": "mdi:pool",
    "waterSports": "mdi:water",
    "wheelchairRunPace": "mdi:wheelchair-accessibility",
    "wheelchairWalkPace": "mdi:wheelchair-accessibility",
    "wrestling": "mdi:wrestling",
    "yoga": "mdi:yoga",
    "highIntensityIntervalTraining": "mdi:lightning-bolt",
    "coreTraining": "mdi:arm-flex",
    "flexibility": "mdi:yoga",
    "barre": "mdi:dance-ballroom",
    "other": "mdi:run",
}
