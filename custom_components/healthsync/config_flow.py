"""Config flow for the HealthSync integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_NAME, CONF_SECRET, CONF_WEBHOOK_ID, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=""): str,
        vol.Optional(CONF_SECRET, default=""): str,
    }
)


class HealthSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the HealthSync config flow: generate a webhook, optional secret.

    Deliberately allows more than one entry (no unique_id gate) — added 11
    Aug 2026 so a family can add HealthSync once per person, each with their
    own webhook URL and their own phone running the app. The optional
    "name" field (e.g. "Dad") becomes the entry's title, which every device
    name derives from — leave it blank and everything looks exactly like a
    single-person setup always has, so existing installs are unaffected.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single-step setup."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        name = user_input.get(CONF_NAME, "").strip()
        secret = user_input.get(CONF_SECRET, "").strip()
        data: dict[str, Any] = {CONF_WEBHOOK_ID: webhook.async_generate_id()}
        if secret:
            data[CONF_SECRET] = secret
        if name:
            data[CONF_NAME] = name

        title = f"HealthSync ({name})" if name else "HealthSync"
        return self.async_create_entry(title=title, data=data)
