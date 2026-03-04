import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_ENABLE_NEWS, CONF_DEBUG_MODE

class L1WeerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="L1 Weer & Nieuws", data=user_input)

        schema = vol.Schema({
            vol.Optional(CONF_ENABLE_NEWS, default=True): bool,
            vol.Optional(CONF_DEBUG_MODE, default=False): bool,
        })

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return L1WeerOptionsFlowHandler(config_entry)

class L1WeerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        # Changed to _config_entry to avoid conflicting with HA's built-in property
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Pull existing settings or default to True/False
        enable_news = self._config_entry.options.get(
            CONF_ENABLE_NEWS, 
            self._config_entry.data.get(CONF_ENABLE_NEWS, True)
        )
        debug_mode = self._config_entry.options.get(
            CONF_DEBUG_MODE, 
            self._config_entry.data.get(CONF_DEBUG_MODE, False)
        )

        schema = vol.Schema({
            vol.Optional(CONF_ENABLE_NEWS, default=enable_news): bool,
            vol.Optional(CONF_DEBUG_MODE, default=debug_mode): bool,
        })

        return self.async_show_form(step_id="init", data_schema=schema)