"""
Media-player entity functions (zone aware).

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from ucapi import EntityTypes, MediaPlayer, StatusCodes
from ucapi.media_player import (
    Attributes,
    Commands,
    DeviceClasses,
    Features,
    Options,
    States,
)

import avr
from config import DeviceInstance, SonyEntity, create_entity_id
from const import SIMPLE_COMMANDS, ZONE_NAMES
from za_protocol import Zone

_LOG = logging.getLogger(__name__)

ZONE_SUFFIX = {Zone.MAIN: "", Zone.ZONE2: ".zone2", Zone.ZONE3: ".zone3"}


class SonyMediaPlayer(MediaPlayer, SonyEntity):
    """Representation of a Sony Media Player entity for one zone."""

    def __init__(
        self,
        device_config: DeviceInstance,
        receiver: avr.SonyDevice,
        zone: Zone = Zone.MAIN,
    ):
        """Initialize the class."""
        self._receiver: avr.SonyDevice = receiver
        self._device_config = device_config
        self.zone: Zone = zone

        entity_id = create_entity_id(device_config.id, EntityTypes.MEDIA_PLAYER) + ZONE_SUFFIX[zone]
        features = [
            Features.ON_OFF,
            Features.VOLUME,
            Features.VOLUME_UP_DOWN,
            Features.MUTE_TOGGLE,
            Features.SELECT_SOURCE,
        ]
        options = {}
        if zone == Zone.MAIN:
            features.append(Features.SELECT_SOUND_MODE)
            options[Options.SIMPLE_COMMANDS] = SIMPLE_COMMANDS

        attributes = receiver.attributes_for_zone(zone)
        name = device_config.name if zone == Zone.MAIN else f"{device_config.name} {ZONE_NAMES[int(zone)]}"

        super().__init__(
            entity_id,
            name,
            features,
            attributes,
            device_class=DeviceClasses.RECEIVER,
            options=options,
        )

    @property
    def deviceid(self) -> str:
        """Return the device identifier."""
        return self._device_config.id

    async def command(
        self,
        cmd_id: str,
        params: dict[str, Any] | None = None,
        *,
        websocket: Any = None,
    ) -> StatusCodes:
        """
        Execute entity command.

        :param cmd_id: the command
        :param params: optional command parameters
        :return: command status code to acknowledge to the remote
        """
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._receiver is None:
            _LOG.warning("No AVR instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE
        params = params or {}
        zone = self.zone
        res: StatusCodes = StatusCodes.NOT_IMPLEMENTED
        if cmd_id == Commands.VOLUME:
            res = await self._receiver.set_volume_level(params.get("volume"), zone)
        elif cmd_id == Commands.VOLUME_UP:
            res = await self._receiver.volume_up(zone)
        elif cmd_id == Commands.VOLUME_DOWN:
            res = await self._receiver.volume_down(zone)
        elif cmd_id == Commands.MUTE_TOGGLE:
            res = await self._receiver.mute(not self.attributes.get(Attributes.MUTED, False), zone)
        elif cmd_id == Commands.MUTE:
            res = await self._receiver.mute(True, zone)
        elif cmd_id == Commands.UNMUTE:
            res = await self._receiver.mute(False, zone)
        elif cmd_id == Commands.ON:
            res = await self._receiver.power_on(zone)
        elif cmd_id == Commands.OFF:
            res = await self._receiver.power_off(zone)
        elif cmd_id == Commands.TOGGLE:
            if self.attributes.get(Attributes.STATE) == States.ON:
                res = await self._receiver.power_off(zone)
            else:
                res = await self._receiver.power_on(zone)
        elif cmd_id == Commands.SELECT_SOURCE:
            res = await self._receiver.select_source(params.get("source"), zone)
        elif cmd_id == Commands.SELECT_SOUND_MODE:
            res = await self._receiver.select_sound_mode(params.get("mode"))
        elif cmd_id in SIMPLE_COMMANDS:
            res = await self._receiver.send_simple_command(cmd_id)
        else:
            return StatusCodes.NOT_IMPLEMENTED

        return res

    def filter_changed_attributes(self, update: dict[str, Any]) -> dict[str, Any]:
        """
        Filter the given attributes and return only the changed values.

        Zone entities extract their own sub-dictionary from the update.

        :param update: dictionary with attributes.
        :return: filtered entity attributes containing changed attributes only.
        """
        if self.zone == Zone.ZONE2:
            update = update.get("zone2", {})
        elif self.zone == Zone.ZONE3:
            update = update.get("zone3", {})

        attributes = {}

        for attr in [
            Attributes.STATE,
            Attributes.MUTED,
            Attributes.SOURCE,
            Attributes.VOLUME,
        ]:
            if attr in update:
                attributes = self._key_update_helper(attr, update[attr], attributes)

        if Attributes.SOURCE_LIST in update:
            if update[Attributes.SOURCE_LIST] != self.attributes.get(Attributes.SOURCE_LIST):
                attributes[Attributes.SOURCE_LIST] = update[Attributes.SOURCE_LIST]

        if Features.SELECT_SOUND_MODE in self.features:
            if Attributes.SOUND_MODE in update:
                attributes = self._key_update_helper(Attributes.SOUND_MODE, update[Attributes.SOUND_MODE], attributes)
            if Attributes.SOUND_MODE_LIST in update:
                if update[Attributes.SOUND_MODE_LIST] != self.attributes.get(Attributes.SOUND_MODE_LIST):
                    attributes[Attributes.SOUND_MODE_LIST] = update[Attributes.SOUND_MODE_LIST]

        return attributes

    def _key_update_helper(self, key: str, value: str | None, attributes):
        if value is None:
            return attributes

        if key in self.attributes:
            if self.attributes[key] != value:
                attributes[key] = value
        else:
            attributes[key] = value

        return attributes
