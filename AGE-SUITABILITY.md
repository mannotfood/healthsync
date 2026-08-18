# HealthSync — Age Suitability

HealthSync's App Store age rating flags "Health or Wellness Topics" because
the app reads Apple Health data — the metrics you individually enable in
Settings, currently spanning activity (steps, active calories, workouts,
and more), heart & vitals (heart rate, HRV, blood pressure, blood oxygen,
blood glucose, and more), sleep, and body measurements (weight, height,
and more). That flag covers apps that *handle* health data — it does not
mean the app offers self-care or lifestyle advice, and that remains true
regardless of how many metrics the app supports.

## What the app does

HealthSync is a one-way data relay: it reads the Health metrics you enable
and forwards them, unmodified, to a Home Assistant webhook URL you provide
and control. That's the entire feature set.

## What the app does not do

- No medical advice, diagnosis, or treatment suggestions.
- No self-care, lifestyle, dieting, or exercise recommendations.
- No scoring, coaching, goal-setting, or interpretation of your health data.
- No social features, content feed, or user-generated content.

Any recommendations or coaching a user sees come entirely from Home
Assistant automations *they* build themselves, outside this app — HealthSync
has no part in that.

## Contact

Questions can be raised via [GitHub Issues](https://github.com/mannotfood/healthsync/issues)
on this repository.
