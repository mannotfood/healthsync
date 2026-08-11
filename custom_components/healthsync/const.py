"""Constants for the HealthSync integration."""

DOMAIN = "healthsync"

CONF_WEBHOOK_ID = "webhook_id"
CONF_SECRET = "secret"

# Metric names as sent by the iOS app (HealthMetricType raw values).
METRIC_STEPS = "steps"
METRIC_HEART_RATE = "heartRate"
METRIC_HRV = "heartRateVariability"
METRIC_SLEEP = "sleep"
METRIC_ACTIVE_CALORIES = "activeCalories"
METRIC_WORKOUTS = "workouts"
METRIC_TEST = "test_connection"

QUANTITY_METRICS = {METRIC_STEPS, METRIC_HEART_RATE, METRIC_HRV, METRIC_ACTIVE_CALORIES}
# Metrics accumulated into a daily total (the app sends incremental samples,
# not running totals).
DAILY_TOTAL_METRICS = {METRIC_STEPS, METRIC_ACTIVE_CALORIES}

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
