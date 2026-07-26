"""Config flow for the HealthSync integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_SECRET, CONF_WEBHOOK_ID, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SECRET, default=""): str,
    }
)


class HealthSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the HealthSync config flow: generate a webhook, optional secret."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single-step setup."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        secret = user_input.get(CONF_SECRET, "").strip()
        data: dict[str, Any] = {CONF_WEBHOOK_ID: webhook.async_generate_id()}
        if secret:
            data[CONF_SECRET] = secret

        return self.async_create_entry(title="HealthSync", data=data)
