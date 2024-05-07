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
from vsslctrl.discovery import fetch_zone_id_serial
from vsslctrl.exceptions import VsslCtrlException

from .const import (
    DOMAIN,
    SERIAL,
    ZONES,
    INPUT_1,
    INPUT_2,
    INPUT_3,
    INPUT_4,
    INPUT_5,
    INPUT_6,
)


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(INPUT_1, default="10.10.30.10"): str,
        vol.Optional(INPUT_2): str,
        vol.Optional(INPUT_3): str,
        vol.Optional(INPUT_4): str,
        vol.Optional(INPUT_5): str,
        vol.Optional(INPUT_6): str,
    }
)


#
#
# TODO, a reset button is requred for each zone
#
# Discovery
#
#


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
                                INPUT_1, default=user_input.get(INPUT_1, "")
                            ): str,
                            vol.Optional(
                                INPUT_2, default=user_input.get(INPUT_2, "")
                            ): str,
                            vol.Optional(
                                INPUT_3, default=user_input.get(INPUT_3, "")
                            ): str,
                            vol.Optional(
                                INPUT_4, default=user_input.get(INPUT_4, "")
                            ): str,
                            vol.Optional(
                                INPUT_5, default=user_input.get(INPUT_5, "")
                            ): str,
                            vol.Optional(
                                INPUT_6, default=user_input.get(INPUT_6, "")
                            ): str,
                        }
                    ),
                    errors=errors,
                )

            return await self.async_step_connect(user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_connect(self, zones):
        """Connect to VSSL"""

        # First lets try and get the zone serial number and ID so we can validate
        valid_zones = {}
        errors = {}
        vssl_serial = None  # jsut limit to one VSSL device
        for key, host in zones.items():
            try:
                if host:
                    zone_id, serial = await fetch_zone_id_serial(host)
                    if zone_id and serial:
                        if serial not in valid_zones:
                            valid_zones[serial] = {}
                        if vssl_serial is None:
                            vssl_serial = serial

                        valid_zones[serial][zone_id] = host
                    else:
                        raise VsslCtrlException
            except VsslCtrlException as e:
                errors[key] = f"Error fetching zone info for {host}"

        if errors:
            print(errors)
            # SHOW ERROR FORM
            pass

        try:
            vssl = Vssl()

            # Add zones to VSSL device
            for zone_id, host in valid_zones[vssl_serial].items():
                vssl.add_zone(int(zone_id), host)

            await vssl.initialise()

            name = vssl.settings.name
            data = {SERIAL: vssl_serial, ZONES: valid_zones[vssl_serial]}

            await self.async_set_unique_id(vssl_serial)

        except Exception as e:
            _LOGGER.exception(e)
            return self.async_abort(reason="zone_initialisation")
        finally:
            await vssl.shutdown()

        return self.async_create_entry(title=name, data=data)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        print(discovery_info)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidIP(HomeAssistantError):
    """Error to indicate there is invalid IP Address."""
