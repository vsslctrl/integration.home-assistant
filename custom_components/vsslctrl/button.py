from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .base import VsslBaseEntity

from vsslctrl import Vssl, Zone, VSSL_NAME


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    vssl = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([RebootButton(vssl)])


class RebootButton(VsslBaseEntity, ButtonEntity):
    """Defines a ONVIF reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, vssl: Vssl) -> None:
        """Initialize the button entity."""
        super().__init__(vssl)
        self._attr_name = f"{self.vssl.settings.name} Reboot"
        self._attr_unique_id = f"{self.vssl.serial}_reboot"

    async def async_press(self) -> None:
        """Reboot all zones."""
        self.vssl.reboot()
