# HealthSync Privacy Policy

_Last updated: 26 July 2026_

HealthSync is a local-first iOS app. This policy covers both the iOS app and its optional Home Assistant companion integration in this repository.

## What the app does

HealthSync reads the Health metrics you enable (steps, heart rate, heart rate variability, sleep, and active calories) from Apple HealthKit and sends them directly from your device to the Home Assistant webhook URL you configure in the app's Settings screen. That's the entire data flow.

## What we don't do

There are no third-party servers, no analytics, no crash-reporting SDKs, and no user accounts. The developer does not receive, store, or have access to any of your health data at any point. The app's local sync log (used for troubleshooting) is stored only on your device and is never transmitted anywhere.

## Third parties

None. Your data goes only to the webhook URL you provide — your own Home Assistant instance, which you control.

## Your control

Removing the webhook URL, disabling a specific metric, or revoking Health access from the iOS Health app stops all syncing immediately. Uninstalling the app removes all locally stored settings and logs.

## Security of your own Home Assistant connection

HealthSync treats the webhook URL you provide as opaque and does not enforce a particular network setup. You are responsible for securing the receiving end — using `https` or a private tunnel (VPN, Tailscale, Nabu Casa Cloud) for any connection that crosses the public internet is strongly recommended. Plain `http` is only appropriate on networks you trust (e.g. your home LAN).

## The Home Assistant companion integration

The optional custom integration in this repository (`custom_components/healthsync/`) receives the webhook payload from the app and exposes it as sensor entities inside your own Home Assistant instance. It runs entirely within your Home Assistant installation — it does not communicate with any server operated by the developer.

## Changes to this policy

If this policy changes, the update will be posted here with a new "Last updated" date.

## Contact

Questions about this policy can be raised via [GitHub Issues](https://github.com/mannotfood/healthsync/issues) on this repository.
