import asyncio
import logging
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerDeviceClass,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.util import dt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as entity_registry_get
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN

from homeassistant.helpers import entity_registry as er
from typing import cast

from .const import DOMAIN
from .base import VsslBaseEntity

from vsslctrl import Vssl, Zone, VSSL_NAME
from vsslctrl.transport import ZoneTransport
from vsslctrl.track import TrackMetadata
from vsslctrl.group import ZoneGroup
from vsslctrl.io import InputRouter

_LOGGER = logging.getLogger(__name__)

SOURCES = {
    InputRouter.Sources.STREAM: "Stream",
    InputRouter.Sources.ANALOG_IN_1: "Analog Input 1",
    InputRouter.Sources.ANALOG_IN_2: "Analog Input 2",
    InputRouter.Sources.ANALOG_IN_3: "Analog Input 3",
    InputRouter.Sources.ANALOG_IN_4: "Analog Input 4",
    InputRouter.Sources.ANALOG_IN_5: "Analog Input 5",
    InputRouter.Sources.ANALOG_IN_6: "Analog Input 6",
    InputRouter.Sources.OPTICAL_IN: "Optical Input",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VSSL controller entry."""
    vssl = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for zone in vssl.zones.values():
        entity = VSSLZoneEntity(hass, zone, vssl)
        entities.append(entity)

    async_add_entities(entities)


class VSSLZoneEntity(VsslBaseEntity, MediaPlayerEntity):
    _attr_should_poll = False
    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_volume_step = 0.2
    _attr_media_image_remotely_accessible = False

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, hass: HomeAssistant, zone: Zone, vssl: Vssl):
        """Initialize the zone entity."""
        super().__init__(vssl)

        self.zone = zone

        self._attr_unique_id = self.construct_unique_id(zone.serial, zone.id)
        self._attr_group_members = []
        self.media_position_updated_at = dt.utcnow()

        # Filter the sources based on the device
        self._supported_sources = {
            key: value
            for key, value in SOURCES.items()
            if key in self.vssl.model.input_sources
        }
        self._attr_source_list = list(self._supported_sources.values())

        # Subscribe to events for this zone
        vssl.event_bus.subscribe(Vssl.Events.ALL, self._update_ha_state, zone.id)

    @staticmethod
    def construct_unique_id(serial: str, zone_id: int) -> str:
        """Construct the unique id"""
        return f"{serial}_ZONE_{zone_id}"

    #
    # Wrapper for the event bus events to update state-machine
    #
    async def _update_ha_state(self, data, entity, event_type) -> None:
        _LOGGER.debug(f"Event: {event_type} : {entity} : {data}")

        if event_type == TrackMetadata.Events.PROGRESS_CHANGE:
            await self._update_progress_timestamp(data)
        else:
            self.async_write_ha_state()

    #
    # Decorate Helper to check if zone is connected when issuing commands
    #
    def error_if_disconnected(func):
        async def wrapper(self, *args, **kwargs):
            if self.zone.connected:
                return await func(self, *args, **kwargs)
            else:
                raise HomeAssistantError(
                    f"Zone is disconnected: {self.zone.settings.name}"
                )

        return wrapper

    @property
    def name(self):
        return self.zone.settings.name

    @property
    def state(self):
        if self.zone.transport.is_playing:
            return MediaPlayerState.PLAYING
        elif self.zone.transport.is_paused:
            return MediaPlayerState.PAUSED
        else:
            return MediaPlayerState.IDLE

    @error_if_disconnected
    async def async_media_pause(self) -> None:
        """Send pause command."""
        self.zone.transport.pause()

    @error_if_disconnected
    async def async_media_play(self) -> None:
        """Send play command."""
        self.zone.transport.play()

    @error_if_disconnected
    async def async_media_stop(self) -> None:
        """Send stop command."""
        self.zone.transport.stop()

    @error_if_disconnected
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        self.zone.transport.next()

    @error_if_disconnected
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        self.zone.transport.prev()

    @property
    def repeat(self):
        """Return repeat mode."""
        mode = self.zone.transport.is_repeat
        if mode == ZoneTransport.Repeat.ONE:
            return RepeatMode.ONE
        elif mode == ZoneTransport.Repeat.ALL:
            return RepeatMode.ALL
        else:
            return RepeatMode.OFF

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        return self.zone.transport.is_shuffle

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self.zone.mute

    @error_if_disconnected
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self.zone.mute = mute

    @property
    def volume_level(self):
        """Return the volume level of the client (0..1)."""
        return self.zone.volume / 100

    @error_if_disconnected
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self.zone.volume = int(volume * 100)

    @error_if_disconnected
    async def async_volume_up(self) -> None:
        self.zone.volume_raise(self.volume_step * 10)

    @error_if_disconnected
    async def async_volume_down(self) -> None:
        self.zone.volume_lower(self.volume_step * 10)

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.zone.track.title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.zone.track.artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.zone.track.album

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self.zone.track.artist

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.zone.track.cover_art_url

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self.zone.track.duration:
            return self.zone.track.duration / 1000

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self.zone.track.progress:
            return self.zone.track.progress / 1000

    async def _update_progress_timestamp(self, data, *args) -> None:
        if data is not None:
            self.media_position_updated_at = dt.utcnow()
        else:
            self.media_position_updated_at = None

    @property
    def source(self):
        """Current source"""
        source = self.zone.input.source.value
        if source in self._supported_sources:
            return self._supported_sources[source]

        return SOURCES[InputRouter.Sources.STREAM]

    def _get_real_source(self, source_str):
        for key, val in self._supported_sources.items():
            if val == source_str:
                return key
        return None

    async def async_select_source(self, source):
        """Select input source."""
        real_source = self._get_real_source(source)
        if real_source is not None:
            if real_source == InputRouter.Sources.STREAM:
                self.zone.input.priority = InputRouter.Priorities.STREAM
            else:
                self.zone.input.priority = InputRouter.Priorities.LOCAL

            self.zone.input.source = real_source

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing image."""

        # Prevent HA caching default cover art between songs
        if self.zone.track.source == TrackMetadata.Sources.AIRPLAY:
            await asyncio.sleep(1)

        return await super().async_get_media_image()
