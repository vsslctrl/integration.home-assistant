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
from vsslctrl.event_bus import EventBus
from vsslctrl.api_base import APIBase


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    vssl = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Zone Reboot
    for zone in vssl.zones.values():
        entity = ZoneRestartButton(zone)
        entities.append(entity)

    # Device Reboot
    entities.append(DeviceRestartButton(vssl))

    async_add_entities(entities)


class DeviceRestartButton(VsslBaseEntity, ButtonEntity):
    """Defines a device reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, vssl: Vssl) -> None:
        """Initialize the button entity."""
        super().__init__(vssl)
        self._attr_name = f"Reboot Device"
        self._attr_unique_id = f"{self.vssl.serial}_DEVICE_REBOOT"

        # Subscribe to all zone the connection events
        self.vssl.event_bus.subscribe(
            APIBase.Events.PREFIX + EventBus.WILDCARD, self._check_entity_availability
        )

    async def async_press(self) -> None:
        """Reboot all zones."""
        self.vssl.reboot()

    @property
    def available(self):
        return self.vssl.connected


class ZoneRestartButton(VsslBaseEntity, ButtonEntity):
    """Defines a zone reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, zone: Zone) -> None:
        """Initialize the button entity."""
        super().__init__(zone.vssl)
        self.zone = zone
        self._attr_name = f"Restart {self.zone.settings.name}"
        self._attr_unique_id = f"{self.zone.serial}_ZONE_{self.zone.id}_RESTART"

        # # Subscribe to only this zones connection events
        self.vssl.event_bus.subscribe(
            APIBase.Events.PREFIX + EventBus.WILDCARD,
            self._check_entity_availability,
            self.zone.id,
        )

    async def async_press(self) -> None:
        """Reboot all zones."""
        self.zone.reboot()

    @property
    def available(self):
        return self.zone.connected
