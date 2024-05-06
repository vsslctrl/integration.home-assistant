"""Config flow for VSSL Controller integration."""

from __future__ import annotations
import re
import logging
from typing import Any
import ipaddress
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from vsslctrl import Vssl

from .const import DOMAIN, SERIAL, ZONES, ZONE_1, ZONE_2, ZONE_3, ZONE_4, ZONE_5, ZONE_6


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(ZONE_1, default="10.10.30.10"): str,
        vol.Optional(ZONE_2, default="10.10.30.11"): str,
        vol.Optional(ZONE_3, default="10.10.30.12"): str,
        vol.Optional(ZONE_4): str,
        vol.Optional(ZONE_5): str,
        vol.Optional(ZONE_6): str,
    }
)


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VSSL Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate IP addresses
            for key, ip in user_input.items():
                if not ip:
                    continue

                try:
                    ipaddress.IPv4Address(ip)
                except ipaddress.AddressValueError:
                    errors[key] = "invalid_ip"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors[key] = "unknown"

            if len(errors):
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                ZONE_1, default=user_input.get(ZONE_1, "")
                            ): str,
                            vol.Optional(
                                ZONE_2, default=user_input.get(ZONE_2, "")
                            ): str,
                            vol.Optional(
                                ZONE_3, default=user_input.get(ZONE_3, "")
                            ): str,
                            vol.Optional(
                                ZONE_4, default=user_input.get(ZONE_4, "")
                            ): str,
                            vol.Optional(
                                ZONE_5, default=user_input.get(ZONE_5, "")
                            ): str,
                            vol.Optional(
                                ZONE_6, default=user_input.get(ZONE_6, "")
                            ): str,
                        }
                    ),
                    errors=errors,
                )

            return await self.async_step_connect(user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_connect(self, zones):
        """Connect to VSSL"""
        zone_list = {}
        try:
            vssl = Vssl()

            for key, zone_ip in zones.items():
                if zone_ip:
                    zone_id = int(key.lstrip("ZONE_"))
                    vssl.add_zone(zone_id, zone_ip)
                    zone_list[zone_id] = zone_ip

            await vssl.initialise()

            name = vssl.settings.name
            data = {SERIAL: vssl.serial, ZONES: zone_list}

            await self.async_set_unique_id(vssl.serial)

            await vssl.shutdown()

        except Exception as e:
            _LOGGER.exception(e)
            return self.async_abort(reason="zone_initialisation")

        return self.async_create_entry(title=name, data=data)

    @staticmethod
    def construct_unique_id(serial: str, zone_id: int) -> str:
        """Construct the unique id"""
        return f"{serial}-{zone_id}"


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidIP(HomeAssistantError):
    """Error to indicate there is invalid IP Address."""
