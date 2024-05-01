"""The VSSL Controller integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from vsslctrl import Vssl
from vsslctrl.exceptions import VsslCtrlException

from .const import DOMAIN, SERIAL, ZONES

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


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




            #
            #
            # TODO handle proper unloading when cant connect
            #
            #
            #
            # If vssl needs to be reinit because startup failed, we will get 
            # an ereror that event_bus or queue is in different event loop
            #
            #


    except Exception as e:
        raise ConfigEntryNotReady from e

    hass.data[DOMAIN][entry.entry_id] = vssl

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        vssl = hass.data[DOMAIN].pop(entry.entry_id)
        await vssl.disconnect()

    return unload_ok
