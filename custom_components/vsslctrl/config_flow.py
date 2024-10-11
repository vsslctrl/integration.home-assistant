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
from vsslctrl.device import Models as DeviceModels
from vsslctrl.discovery import fetch_zone_id_serial
from vsslctrl.exceptions import VsslCtrlException

from .const import (
    DOMAIN,
    SERIAL,
    ZONES,
    MODEL,
    INPUT_MODEL,
    INPUT_ZONE_IP_1,
    INPUT_ZONE_IP_2,
    INPUT_ZONE_IP_3,
    INPUT_ZONE_IP_4,
    INPUT_ZONE_IP_5,
    INPUT_ZONE_IP_6,
)


_LOGGER = logging.getLogger(__name__)

VSSL_MODELS_LIST = DeviceModels.get_model_names()


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VSSL Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Get the model from the user input
            model_name = next(iter(user_input.values()))
            self.vssl_device_model = DeviceModels.get_model_by_name(model_name)

            return await self.async_step_addressing()

        # Show empty model selection dropdown
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "dropdown",
                        DeviceModels.A1X.value.name,
                    ): vol.In(VSSL_MODELS_LIST)
                }
            ),
            errors=errors,
        )

    async def async_step_addressing(self, user_input: dict[str, Any] | None = None):
        """Handle the IP Addressing step."""

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
                return self.build_addressing_form(errors, user_input)

            # We have IPs, so lets try and connect
            return await self.async_step_connect(user_input)

        # Show blank addressing form
        return self.build_addressing_form()

    # Build a dynamic scheme based on VSSL model zone count
    def build_addressing_form(self, errors: Dict = {}, user_input={}):
        # Initialize the schema dict with the required first input
        schema_dict = {
            vol.Required(
                "INPUT_ZONE_IP_1", default=user_input.get("INPUT_ZONE_IP_1", "")
            ): str
        }

        # Add additional optional inputs based on num_inputs
        for i in range(2, self.vssl_device_model.zone_count + 1):
            schema_dict[
                vol.Optional(
                    f"INPUT_ZONE_IP_{i}",
                    default=user_input.get(f"INPUT_ZONE_IP_{i}", ""),
                )
            ] = str

        return self.async_show_form(
            step_id="addressing",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"vssl_model": self.vssl_device_model.name},
        )

    async def async_step_connect(self, zones):
        """Connect to VSSL"""

        # First lets try and get the zone serial number and ID so we can validate
        # that this is actually a valid VSSL zone IP
        valid_zones = {}
        errors = {}
        vssl_serial = None  # limit to one VSSL device
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

        # If we have any errors we need to display them and take us back to addressing form
        if len(errors):
            return self.build_addressing_form(errors, zones)

        # Check our zones are valid, lets try to init a VSSL device
        # so we scope to a single serial number
        try:
            vssl = Vssl(self.vssl_device_model)

            # Add zones to VSSL device
            for zone_id, host in valid_zones[vssl_serial].items():
                vssl.add_zone(int(zone_id), host)

            _LOGGER.info("Awaiting VSSL initialization")
            await vssl.initialise()

            name = vssl.settings.name
            data = {
                SERIAL: vssl_serial,
                ZONES: valid_zones[vssl_serial],
                MODEL: self.vssl_device_model.name,
            }

            await self.async_set_unique_id(vssl_serial)

            # Check if VSSL device already exists and update any zones if need be
            for entry in self._async_current_entries():
                if entry.data[SERIAL] == vssl_serial:
                    # We need to merge an update the zones, we will make them unique with the
                    # newer IP taking preference
                    merged_data = entry.data.copy()
                    merged_data[MODEL] = data[MODEL]
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
