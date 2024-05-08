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
                # Can there even be no IP?
                if not ip:
                    continue

                # Check IPs are unique
                user_input_c = user_input.copy()
                user_input_c.pop(key)
                if ip in user_input_c.values():
                    errors[key] = "not_unique"
                    continue
                try:
                    ipaddress.IPv4Address(ip)
                except ipaddress.AddressValueError:
                    errors[key] = "invalid_ip"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors[key] = "unknown"

            if len(errors):
                return self.build_form(errors, user_input)

            return await self.async_step_connect(user_input)

        return self.build_form()

    async def async_step_connect(self, zones):
        """Connect to VSSL"""

        # First lets try and get the zone serial number and ID so we can validate
        # that this is actually a valid VSSL zone IP
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
            except Exception as e:
                errors[key] = "fetch_zone"

        # If we have any errors we need to display them
        if len(errors):
            return self.build_form(errors, zones)

        # Check our zones are valid, lets try to init a VSSL device
        # we scope to a single serial number
        try:
            vssl = Vssl()

            # Add zones to VSSL device
            for zone_id, host in valid_zones[vssl_serial].items():
                vssl.add_zone(int(zone_id), host)

            await vssl.initialise()

            name = vssl.settings.name
            data = {SERIAL: vssl_serial, ZONES: valid_zones[vssl_serial]}

            await self.async_set_unique_id(vssl_serial)

            # Check if VSSL device already exists and update any zones if need be
            for entry in self._async_current_entries():
                if entry.data[SERIAL] == vssl_serial:
                    # We need to merge an update the zones, we will make them unique with the
                    # newer IP taking preference
                    merged_data = entry.data.copy()
                    # Update zones, overwriting values
                    merged_data[ZONES].update(data[ZONES])
                    self.hass.config_entries.async_update_entry(
                        entry,
                        title=name,
                        data=merged_data,
                        minor_version=entry.minor_version + 1,
                    )
                    # Reload the current config
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                    # Abort with reason
                    return self.async_abort(reason="updated_vssl")

        except Exception as e:
            _LOGGER.exception(e)
            return self.async_abort(reason="zone_initialisation")
        finally:
            await vssl.shutdown()

        # Create a new entry
        return self.async_create_entry(title=name, data=data)

    def build_form(self, errors: Dict = {}, user_input={}, step: str = "user"):
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required(INPUT_1, default=user_input.get(INPUT_1, "")): str,
                    vol.Optional(INPUT_2, default=user_input.get(INPUT_2, "")): str,
                    vol.Optional(INPUT_3, default=user_input.get(INPUT_3, "")): str,
                    vol.Optional(INPUT_4, default=user_input.get(INPUT_4, "")): str,
                    vol.Optional(INPUT_5, default=user_input.get(INPUT_5, "")): str,
                    vol.Optional(INPUT_6, default=user_input.get(INPUT_6, "")): str,
                }
            ),
            errors=errors,
        )
