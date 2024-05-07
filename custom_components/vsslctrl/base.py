from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

from vsslctrl import Vssl, Zone, VSSL_NAME


class VsslBaseEntity(Entity):
    """Base class common to all VSSL entities."""

    def __init__(self, vssl: Vssl) -> None:
        """Initialize the VSSL entity."""
        self.vssl = vssl

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.vssl.serial)},
            name=self.vssl.settings.name,
            manufacturer=VSSL_NAME,
            sw_version=self.vssl.sw_version,
            serial_number=self.vssl.serial,
        )
