"""The VSSL integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from vsslctrl import Vssl
from vsslctrl.exceptions import VsslCtrlException
from vsslctrl.device import Models as DeviceModels

from .const import DOMAIN, SERIAL_KEY, ZONES_KEY, MODEL_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.BUTTON, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VSSL from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    try:
        vssl_core = Vssl()

        zones = entry.data.get(ZONES_KEY)

        for host in zones.values():
            vssl_core.add_zone(host)

        await vssl_core.initialise()

        if vssl_core.serial != entry.data.get(SERIAL_KEY):
            raise VsslCtrlException(
                f"vssl serial {vssl_core.serial} and entry serial {entry.data.get(SERIAL_KEY)} do not match"
            )

    except Exception as e:
        _LOGGER.exception(e)
        await vssl_core.shutdown()
        raise ConfigEntryNotReady from e

    hass.data[DOMAIN][entry.entry_id] = vssl_core

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        vssl_core = hass.data[DOMAIN].pop(entry.entry_id)
        await vssl_core.shutdown()

    return unload_ok
