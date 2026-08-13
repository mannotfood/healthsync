"""Constants for the HealthSync integration."""

DOMAIN = "healthsync"

CONF_WEBHOOK_ID = "webhook_id"
CONF_SECRET = "secret"
# Optional per-entry label (added 11 Aug 2026 to support more than one
# person — e.g. a family, each with their own phone/webhook — under the
# same HA instance). Folded straight into the config entry's title rather
# than stored separately; device names are derived from entry.title.
CONF_NAME = "name"

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
LATEST_VALUE_METRICS = {METRIC_HEART_RATE, METRIC_HRV, METRIC_VO2_MAX, METRIC_WEIGHT}

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

SIGNAL_UPDATE = "healthsync_update_{entry_id}"
# Fired only when a genuinely new (non-replayed, in-order) workout lands —
# distinct from SIGNAL_UPDATE so the workout event entity doesn't fire on
# every unrelated sample (steps, heart rate, ...).
SIGNAL_WORKOUT = "healthsync_workout_{entry_id}"

# How many recent workouts the "Recent workouts" sensor keeps as attributes.
MAX_RECENT_WORKOUTS = 10

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
