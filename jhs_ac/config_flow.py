"""Config flow for JHS AC integration."""
import voluptuous as vol
import aiohttp
import asyncio

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
})


class JHSACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JHS AC."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Test connection to Tasmota device
            host_ok = await self._test_connection(user_input[CONF_HOST])
            
            if host_ok:
                return self.async_create_entry(
                    title=f"JHS AC ({user_input[CONF_HOST]})",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )
            else:
                errors[CONF_HOST] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _test_connection(self, host):
        """Test if we can connect to the Tasmota device."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{host}/cm?cmnd=Status", 
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except:
            return False