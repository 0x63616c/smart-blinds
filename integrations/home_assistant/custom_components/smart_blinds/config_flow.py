"""Explicit bridge-mode selection; credentials remain in HA config storage."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import BridgeAuthError, BridgeClient, BridgeError
from .const import CONF_BASE_URL, CONF_TOKEN, DOMAIN

_SCHEMA = vol.Schema({
    vol.Required(CONF_BASE_URL, default="http://127.0.0.1:8765"): str,
    vol.Required("mode", default="simulation"): vol.In({"simulation": "Simulator", "physical_read_only": "Physical telemetry (read only)"}),
    vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
})


class SmartBlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                client = BridgeClient(async_get_clientsession(self.hass),
                                      user_input[CONF_BASE_URL], user_input[CONF_TOKEN], user_input.get("mode", "simulation"))
                state = await client.async_state()
                await self.async_set_unique_id(state["bridge_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Smart Blinds simulator" if client.mode == "simulation" else "Smart Blinds telemetry", data={
                    CONF_BASE_URL: client.base_url, CONF_TOKEN: user_input[CONF_TOKEN], "mode": client.mode})
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except BridgeError:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_config"
        return self.async_show_form(step_id="user", data_schema=_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            entry = self._get_reauth_entry()
            try:
                client = BridgeClient(async_get_clientsession(self.hass),
                                      entry.data[CONF_BASE_URL], user_input[CONF_TOKEN], entry.data.get("mode", "simulation"))
                state = await client.async_state()
                if state["bridge_id"] != entry.unique_id:
                    return self.async_abort(reason="wrong_bridge")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]})
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except BridgeError:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_config"
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({
            vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors)
