"""The VSSL Controller integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from vsslctrl import Vssl
from vsslctrl.exceptions import VsslCtrlException

from .const import DOMAIN, SERIAL, ZONES

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.BUTTON, Platform.SWITCH]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VSSL Controller from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    try:
        vssl = Vssl()
        zones = entry.data.get(ZONES)

        for zone_id, zone_ip in zones.items():
            vssl.add_zone(int(zone_id), zone_ip)
\
        await vssl.initialise()

        if vssl.serial != entry.data.get(SERIAL):
            raise VsslCtrlException

    except Exception as e:
        _LOGGER.exception(e)
        await vssl.shutdown() 
        raise ConfigEntryNotReady from e

    hass.data[DOMAIN][entry.entry_id] = vssl

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        vssl = hass.data[DOMAIN].pop(entry.entry_id)
        await vssl.shutdown() 

    return unload_ok
