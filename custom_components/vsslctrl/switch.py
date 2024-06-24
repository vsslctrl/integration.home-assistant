import logging
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .base import VsslBaseEntity
from vsslctrl import Vssl

_LOGGER = logging.getLogger(__name__)
VSSLCTRL_LOGGER = logging.getLogger("vsslctrl")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set switches for device."""
    vssl = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([DebugSwitch(vssl)])


class DebugSwitch(VsslBaseEntity, SwitchEntity):
    """Defines a debug switch."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, vssl: Vssl) -> None:
        """Initialize the switch entity."""
        super().__init__(vssl)
        self._attr_name = "Debug vsslctrl"
        self._attr_unique_id = f"{self.vssl.serial}_debug"

    @property
    def icon(self) -> bool:
        return "mdi:bug-stop" if self.is_on else "mdi:bug-play"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return VSSLCTRL_LOGGER.level == logging.DEBUG

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_logging_level(logging.DEBUG)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_logging_level(logging.INFO)

    async def _set_logging_level(self, logging_level: int) -> None:
        """Set the logging level for the dependency logger."""
        VSSLCTRL_LOGGER.setLevel(logging_level)
        for handler in VSSLCTRL_LOGGER.handlers:
            handler.setLevel(logging_level)
        self.schedule_update_ha_state()
