"""Config flow for VSSL Controller integration."""

from __future__ import annotations
import re
import logging
from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from vsslctrl import Vssl
from vsslctrl.device import Models as DeviceModels
from vsslctrl.discovery import fetch_zone_info
from vsslctrl.exceptions import VsslCtrlException
from vsslctrl.utils import is_ipv4

from .const import DOMAIN, SERIAL_KEY, ZONES_KEY, MODEL_KEY, INPUT_PREFIX


_LOGGER = logging.getLogger(__name__)

VSSL_MODELS_LIST = DeviceModels.get_model_names()


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VSSL Controller."""

    VERSION = 1

    ##########################################################
    #
    # Step 1
    #
    ##########################################################
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Get the model from the user input
            model_name = next(iter(user_input.values()))

            # find the model
            device_model = DeviceModels.find(model_name)
            if DeviceModels.is_valid(device_model):
                self.vssl_device_model = device_model
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

    ##########################################################
    #
    # Step 2
    #
    ##########################################################
    async def async_step_addressing(self, user_input: dict[str, Any] | None = None):
        """Handle the IP Addressing step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            # validate ip addresses
            for key, ip in user_input.items():
                if ip and not is_ipv4(ip):
                    errors[key] = "invalid_ip"
                    continue

                # Check IPs are unique
                user_input_c = user_input.copy()
                user_input_c.pop(key)
                if ip and ip in user_input_c.values():
                    errors[key] = "not_unique"
                    continue

            if len(errors):
                return self.build_addressing_form(errors, user_input)

            # We have IPs, so lets try and connect
            return await self.async_step_connect(user_input)

        # Show blank addressing form
        return self.build_addressing_form()

    #
    # Build a dynamic scheme based on VSSL model zone count
    #
    def build_addressing_form(self, errors: Dict = {}, user_input={}):
        # Initialize the schema dict with the required first input
        required_field = f"{INPUT_PREFIX}{1}"
        schema_dict = {
            vol.Required(
                required_field, default=user_input.get(required_field, "")
            ): str
        }

        # Add additional optional inputs based on num_inputs
        for i in range(2, self.vssl_device_model.zone_count + 1):
            input_field = f"{INPUT_PREFIX}{i}"

            schema_dict[
                vol.Optional(
                    input_field,
                    default=user_input.get(input_field, ""),
                )
            ] = str

        return self.async_show_form(
            step_id="addressing",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"vssl_model": self.vssl_device_model.name},
        )

    ##########################################################
    #
    # Step 3
    #
    ##########################################################
    async def async_step_connect(self, zones):
        """Connect to VSSL"""

        # Probing the zones will allow us to show if we have errors
        valid_zones = {}
        errors = {}

        # scope to one serial number
        device_serial = None

        # Fetch Zone Info
        for key, host in zones.items():
            try:
                if not host:
                    continue

                info = await fetch_zone_info(host)
                serial = info["serial"]

                if serial not in valid_zones:
                    valid_zones[serial] = {}

                if device_serial is None:
                    device_serial = serial

                # Aviod duplicates
                valid_zones[serial][host] = host

            except Exception:
                errors[key] = "fetch_zone"

        # If we have any errors we need to display them and take us back to addressing form
        if len(errors):
            return self.build_addressing_form(errors, zones)

        # scope to first serial - do this after errors returned
        valid_zones = valid_zones[device_serial]

        # Start the vssl core so we can get all the required info
        # and will also do more sanitary checks
        try:
            vssl_core = Vssl()

            # Add zones
            for host in valid_zones.values():
                vssl_core.add_zone(host)

            _LOGGER.info("awaiting VSSL initialisation")
            await vssl_core.initialise()

            name = vssl_core.settings.name
            data = {
                SERIAL_KEY: vssl_core.serial,
                ZONES_KEY: valid_zones,
                MODEL_KEY: vssl_core.model.name,
            }

            await self.async_set_unique_id(vssl_core.serial)

            # Check if VSSL device already exists and update any zones if need be
            for entry in self._async_current_entries():
                if entry.data[SERIAL_KEY] == vssl_core.serial:
                    # We need to merge and update the zones, newer IP taking preference
                    merged_data = entry.data.copy()
                    merged_data[MODEL_KEY] = data[MODEL_KEY]
                    # Update zones, overwriting values
                    merged_data[ZONES_KEY].update(data[ZONES_KEY])

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

            # Create a new entry
            return self.async_create_entry(title=name, data=data)

        except Exception as e:
            _LOGGER.exception(e)
            return self.async_abort(reason="zone_initialisation")
        finally:
            await vssl_core.shutdown()
