"""
Receiver communication for the Sony ES (ZA platform) Remote integration driver.

Replaces the original songpal-based backend with the native Sony ES IP
control protocol (TCP 33335), which is what the STR-AV7000ES / ZA-series
actually speaks. Adds zone 2 / zone 3 support.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from enum import StrEnum
from typing import Any

import ucapi
from pyee.asyncio import AsyncIOEventEmitter
from ucapi.media_player import Attributes as MediaAttr
from ucapi.media_player import States
from ucapi.select import Attributes as SelectAttr
from ucapi.select import States as SelectStates

from config import DeviceInstance
from const import (
    HDMI_OUTPUT_CODES,
    INPUT_CODES,
    INPUT_NAMES,
    SOUND_FIELD_CODES,
    SOUND_FIELD_NAMES,
    WEB_SETTING_COMMANDS,
    SonySelects,
    SonySensors,
)
from web_api import SonyWebApi
from za_protocol import SonyZaConnection, Zone, ZaEvents, frame

_LOG = logging.getLogger(__name__)

POLL_INTERVAL = 20.0


class Events(StrEnum):
    """Internal driver events."""

    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    UPDATE = "UPDATE"


ZONE_KEYS = {Zone.MAIN: "main", Zone.ZONE2: "zone2", Zone.ZONE3: "zone3"}


class SonyDevice:
    """Representation of a Sony ES receiver (main zone + zones 2/3)."""

    def __init__(self, device: DeviceInstance, loop: AbstractEventLoop | None = None):
        """Create instance."""
        self._device: DeviceInstance = device
        self._loop: AbstractEventLoop = loop or asyncio.get_event_loop()
        self.events = AsyncIOEventEmitter(self._loop)
        self.id: str = device.id
        self._conn = SonyZaConnection(self._host_from_address(device.address), loop=self._loop)
        self._conn.events.on(ZaEvents.CONNECTED, self._on_connected)
        self._conn.events.on(ZaEvents.DISCONNECTED, self._on_disconnected)
        self._conn.events.on(ZaEvents.ZONE_UPDATE, self._on_zone_update)
        self._conn.events.on(ZaEvents.SOUND_FIELD, self._on_sound_field)
        self._conn.events.on(ZaEvents.TUNER_UPDATE, self._on_tuner_update)
        self._available: bool = False
        self._connecting: bool = False
        self._poll_task: asyncio.Task | None = None
        # Assume zones are on when we get activity; refined by status polling
        self._zone_power: dict[Zone, bool | None] = {z: None for z in Zone}
        self._web_api = SonyWebApi(self._conn.host)
        # display name -> default name (custom input names from the web config)
        self._input_display_names: dict[str, str] = {}
        self._display_to_default: dict[str, str] = {}
        # Zone 2 sync state
        self._zone2_volume_linked: bool = False
        self._zone2_input_follow: bool = False
        self._last_main_volume: int | None = None

    @staticmethod
    def _host_from_address(address: str) -> str:
        """Extract plain host from a possibly URL-formatted address."""
        host = address
        if "://" in host:
            host = host.split("://", 1)[1]
        host = host.split("/", 1)[0]
        host = host.split(":", 1)[0]
        return host

    # ------------------------------------------------------------ properties

    @property
    def device_config(self) -> DeviceInstance:
        """Return the device configuration."""
        return self._device

    @property
    def address(self) -> str | None:
        """Return the configured address."""
        return self._device.address

    @property
    def name(self) -> str | None:
        """Return the device name."""
        return self._device.name

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @available.setter
    def available(self, value: bool) -> None:
        self._available = value

    @property
    def receiver(self) -> SonyZaConnection:
        """Return the underlying protocol connection."""
        return self._conn

    def zone_state(self, zone: Zone):
        """Return protocol state for a zone."""
        return self._conn.zones[zone]

    def state_for_zone(self, zone: Zone) -> States:
        """Return media-player state for a zone."""
        if not self._available:
            return States.UNAVAILABLE
        power = self._zone_power.get(zone)
        if power is None:
            return States.UNKNOWN
        return States.ON if power else States.OFF

    @property
    def state(self) -> States:
        """Return main zone state."""
        return self.state_for_zone(Zone.MAIN)

    def _display_name(self, default_name: str) -> str:
        """Map a default input name to the user-assigned display name."""
        return self._input_display_names.get(default_name, default_name)

    def source_for_zone(self, zone: Zone) -> str:
        """Return current input name for a zone."""
        code = self._conn.zones[zone].input_code
        if code is None:
            return ""
        return self._display_name(INPUT_NAMES.get(code, f"input_{code:02x}"))

    @property
    def source(self) -> str:
        """Return main zone input name."""
        return self.source_for_zone(Zone.MAIN)

    @property
    def source_list(self) -> list[str]:
        """Return the list of input names."""
        return [self._display_name(name) for name in INPUT_CODES if name != "SOURCE"]

    def source_list_for_zone(self, zone: Zone) -> list[str]:
        """Return the list of input names for a zone."""
        if zone == Zone.MAIN:
            return self.source_list
        return [self._display_name(name) for name in INPUT_CODES]

    @property
    def sound_mode(self) -> str:
        """Return current sound field name."""
        code = self._conn.sound_field_code
        if code is None:
            return ""
        return SOUND_FIELD_NAMES.get(code, f"sound_field_{code:02x}")

    @property
    def sound_mode_list(self) -> list[str]:
        """Return the list of sound field names."""
        return list(SOUND_FIELD_CODES.keys())

    def volume_level_for_zone(self, zone: Zone) -> float | None:
        """Return volume level of a zone (0..100 device steps)."""
        return self._conn.zones[zone].volume

    @property
    def volume_level(self) -> float | None:
        """Return main zone volume level."""
        return self.volume_level_for_zone(Zone.MAIN)

    def is_volume_muted_for_zone(self, zone: Zone) -> bool:
        """Return mute state of a zone."""
        return bool(self._conn.zones[zone].muted)

    @property
    def is_volume_muted(self) -> bool:
        """Return main zone mute state."""
        return self.is_volume_muted_for_zone(Zone.MAIN)

    def attributes_for_zone(self, zone: Zone) -> dict[str, Any]:
        """Return media-player attributes for one zone."""
        return {
            MediaAttr.STATE: self.state_for_zone(zone),
            MediaAttr.MUTED: self.is_volume_muted_for_zone(zone),
            MediaAttr.VOLUME: self.volume_level_for_zone(zone) or 0,
            MediaAttr.SOURCE_LIST: self.source_list_for_zone(zone),
            MediaAttr.SOURCE: self.source_for_zone(zone),
            MediaAttr.SOUND_MODE_LIST: self.sound_mode_list if zone == Zone.MAIN else [],
            MediaAttr.SOUND_MODE: self.sound_mode if zone == Zone.MAIN else "",
        }

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the device attributes (main zone plus zone sub-dicts)."""
        updated_data = self.attributes_for_zone(Zone.MAIN)
        updated_data.update(
            {
                SonySensors.SENSOR_VOLUME: self.volume_level or 0,
                SonySensors.SENSOR_INPUT: self.source,
                SonySensors.SENSOR_MUTED: "on" if self.is_volume_muted else "off",
                SonySensors.SENSOR_SOUND_MODE: self.sound_mode,
                SonySensors.SENSOR_TUNER: str(self._conn.tuner),
                SonySelects.SELECT_INPUT_SOURCE: {
                    SelectAttr.CURRENT_OPTION: self.source,
                    SelectAttr.OPTIONS: self.source_list,
                    SelectAttr.STATE: SelectStates.ON,
                },
                SonySelects.SELECT_SOUND_MODE: {
                    SelectAttr.CURRENT_OPTION: self.sound_mode,
                    SelectAttr.OPTIONS: self.sound_mode_list,
                    SelectAttr.STATE: SelectStates.ON,
                },
                "zone2": self.attributes_for_zone(Zone.ZONE2),
                "zone3": self.attributes_for_zone(Zone.ZONE3),
            }
        )
        return updated_data

    # ---------------------------------------------------------- connection

    async def connect_event(self) -> None:
        """Re-emit connection state for an already-connected device."""
        if self._available:
            self.events.emit(Events.CONNECTED, self.id)
            self.events.emit(Events.UPDATE, self.id, self.attributes)

    async def connect(self) -> None:
        """Connect to the receiver."""
        if self._connecting or self._available:
            return
        self._connecting = True
        self.events.emit(Events.CONNECTING, self.id)
        try:
            await self._conn.connect()
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.warning("[%s] initial connection failed: %s", self.id, ex)
            self.events.emit(Events.ERROR, self.id, str(ex))
            # background reconnect
            self._conn._schedule_reconnect()  # pylint: disable=protected-access
        finally:
            self._connecting = False

    async def disconnect(self) -> None:
        """Disconnect from the receiver."""
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        await self._conn.disconnect()
        self._available = False
        self.events.emit(Events.DISCONNECTED, self.id)

    def _on_connected(self) -> None:
        self._available = True
        self.events.emit(Events.CONNECTED, self.id)
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = self._loop.create_task(self._poll_loop())
        self._loop.create_task(self._load_input_names())

    async def _load_input_names(self) -> None:
        """Fetch user-assigned input names from the receiver web config."""
        names = await self._web_api.get_input_names()
        if not names:
            return
        self._input_display_names = names
        self._display_to_default = {v: k for k, v in names.items()}
        _LOG.debug("[%s] input names: %s", self.id, names)
        self.events.emit(Events.UPDATE, self.id, self.attributes)

    def _on_disconnected(self) -> None:
        self._available = False
        self.events.emit(Events.DISCONNECTED, self.id)

    async def _poll_loop(self) -> None:
        """Periodically refresh zone status (protocol also pushes changes)."""
        try:
            while self._conn.connected:
                await asyncio.sleep(POLL_INTERVAL)
                try:
                    await self._conn.query_all()
                except Exception as ex:  # pylint: disable=broad-except
                    _LOG.debug("[%s] poll failed: %s", self.id, ex)
        except asyncio.CancelledError:
            return

    def _on_zone_update(self, zone: Zone, _state) -> None:
        power = self._conn.zones[zone].power
        if power is not None:
            self._zone_power[zone] = power
        update: dict[str, Any] = {}
        if zone == Zone.MAIN:
            # Trigger Zone 2 sync if main zone volume or input changed
            main_vol = self.volume_level
            if main_vol is not None:
                self._loop.create_task(self._sync_zone2_volume(main_vol))
            main_input = self._conn.zones[Zone.MAIN].input_code
            if main_input is not None:
                self._loop.create_task(self._sync_zone2_input(main_input))

            update.update(
                {
                    MediaAttr.STATE: self.state_for_zone(zone),
                    MediaAttr.MUTED: self.is_volume_muted_for_zone(zone),
                    MediaAttr.VOLUME: self.volume_level_for_zone(zone) or 0,
                    MediaAttr.SOURCE: self.source_for_zone(zone),
                    SonySensors.SENSOR_VOLUME: self.volume_level or 0,
                    SonySensors.SENSOR_INPUT: self.source,
                    SonySensors.SENSOR_MUTED: "on" if self.is_volume_muted else "off",
                    SonySelects.SELECT_INPUT_SOURCE: {
                        SelectAttr.CURRENT_OPTION: self.source,
                        SelectAttr.OPTIONS: self.source_list,
                        SelectAttr.STATE: SelectStates.ON,
                    },
                }
            )
        else:
            update[ZONE_KEYS[zone]] = self.attributes_for_zone(zone)
        self.events.emit(Events.UPDATE, self.id, update)

    def _on_tuner_update(self, tuner) -> None:
        self.events.emit(Events.UPDATE, self.id, {SonySensors.SENSOR_TUNER: str(tuner)})

    def _on_sound_field(self, _code: int) -> None:
        update = {
            MediaAttr.SOUND_MODE: self.sound_mode,
            SonySensors.SENSOR_SOUND_MODE: self.sound_mode,
            SonySelects.SELECT_SOUND_MODE: {
                SelectAttr.CURRENT_OPTION: self.sound_mode,
                SelectAttr.OPTIONS: self.sound_mode_list,
                SelectAttr.STATE: SelectStates.ON,
            },
        }
        self.events.emit(Events.UPDATE, self.id, update)

    # ------------------------------------------------------------ commands

    async def _cmd(self, coro) -> ucapi.StatusCodes:
        try:
            ok = await coro
            return ucapi.StatusCodes.OK if ok else ucapi.StatusCodes.BAD_REQUEST
        except ConnectionError:
            return ucapi.StatusCodes.SERVICE_UNAVAILABLE
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("[%s] command failed: %s", self.id, ex)
            return ucapi.StatusCodes.SERVER_ERROR

    async def power_on(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Turn a zone on."""
        return await self._cmd(self._conn.power(zone, True))

    async def power_off(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Turn a zone off."""
        return await self._cmd(self._conn.power(zone, False))

    async def set_volume_level(self, volume: float | None, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Set volume level 0..100 (raw device steps)."""
        if volume is None:
            return ucapi.StatusCodes.BAD_REQUEST
        return await self._cmd(self._conn.set_volume(zone, int(volume)))

    async def volume_up(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Volume up one step."""
        return await self._cmd(self._conn.volume_up(zone))

    async def volume_down(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Volume down one step."""
        return await self._cmd(self._conn.volume_down(zone))

    async def mute(self, muted: bool, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Set mute state."""
        return await self._cmd(self._conn.mute(zone, muted))

    async def select_source(self, source: str | None, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Select input source by (display or default) name."""
        if not source:
            return ucapi.StatusCodes.BAD_REQUEST
        default_name = self._display_to_default.get(source, source)
        if default_name not in INPUT_CODES:
            return ucapi.StatusCodes.BAD_REQUEST
        return await self._cmd(self._conn.select_input(zone, INPUT_CODES[default_name]))

    async def select_sound_mode(self, sound_mode: str | None) -> ucapi.StatusCodes:
        """Select sound field by name (main zone)."""
        if not sound_mode or sound_mode not in SOUND_FIELD_CODES:
            return ucapi.StatusCodes.BAD_REQUEST
        return await self._cmd(self._conn.select_sound_field(SOUND_FIELD_CODES[sound_mode]))

    async def set_sound_settings(self, setting: str, value: str) -> ucapi.StatusCodes:
        """Handle HDMI output simple commands (kept for API compatibility)."""
        if setting == "hdmiOutput":
            mapping = {
                "hdmi_AB": "ZONE_HDMI_OUTPUT_AB",
                "hdmi_A": "ZONE_HDMI_OUTPUT_A",
                "hdim_B": "ZONE_HDMI_OUTPUT_B",
                "hdmi_B": "ZONE_HDMI_OUTPUT_B",
                "off": "ZONE_HDMI_OUTPUT_OFF",
            }
            cmd = mapping.get(value)
            if cmd is None:
                return ucapi.StatusCodes.BAD_REQUEST
            code = HDMI_OUTPUT_CODES[cmd]
            return await self._cmd(self._conn.send(frame(0xA0, 0x45, code)))
        return ucapi.StatusCodes.NOT_IMPLEMENTED

    async def send_hdmi_output(self, cmd_id: str) -> ucapi.StatusCodes:
        """Send an HDMI output simple command."""
        code = HDMI_OUTPUT_CODES.get(cmd_id)
        if code is None:
            return ucapi.StatusCodes.NOT_IMPLEMENTED
        return await self._cmd(self._conn.send(frame(0xA0, 0x45, code)))

    async def send_simple_command(self, cmd_id: str) -> ucapi.StatusCodes:
        """Handle simple commands: tuner presets, HDMI output, audio settings, zone sync."""
        if cmd_id == "TUNER_PRESET_UP":
            return await self._cmd(self._conn.tuner_preset_up())
        if cmd_id == "TUNER_PRESET_DOWN":
            return await self._cmd(self._conn.tuner_preset_down())
        if cmd_id in HDMI_OUTPUT_CODES:
            return await self.send_hdmi_output(cmd_id)
        if cmd_id in WEB_SETTING_COMMANDS:
            feature, value = WEB_SETTING_COMMANDS[cmd_id]
            try:
                ok = await self._web_api.set_feature(feature, value)
                return ucapi.StatusCodes.OK if ok else ucapi.StatusCodes.BAD_REQUEST
            except Exception as ex:  # pylint: disable=broad-except
                _LOG.error("[%s] web setting %s failed: %s", self.id, cmd_id, ex)
                return ucapi.StatusCodes.SERVER_ERROR
        # Zone 2 sync commands
        if cmd_id == "ZONE2_LINK_VOLUME":
            await self.link_zone2_volume()
            return ucapi.StatusCodes.OK
        if cmd_id == "ZONE2_UNLINK_VOLUME":
            await self.unlink_zone2_volume()
            return ucapi.StatusCodes.OK
        if cmd_id == "ZONE2_FOLLOW_INPUT":
            await self.follow_zone2_input()
            return ucapi.StatusCodes.OK
        if cmd_id == "ZONE2_INDEPENDENT_INPUT":
            await self.independent_zone2_input()
            return ucapi.StatusCodes.OK
        return ucapi.StatusCodes.NOT_IMPLEMENTED

    # Zone 2 sync methods
    async def link_zone2_volume(self) -> bool:
        """Enable Zone 2 volume sync."""
        self._zone2_volume_linked = True
        main_vol = self._conn.zones[Zone.MAIN].volume
        if main_vol is not None:
            self._last_main_volume = main_vol
        _LOG.info("[%s] Zone 2 volume sync enabled", self.id)
        return True

    async def unlink_zone2_volume(self) -> bool:
        """Disable Zone 2 volume sync."""
        self._zone2_volume_linked = False
        _LOG.info("[%s] Zone 2 volume sync disabled", self.id)
        return True

    async def follow_zone2_input(self) -> bool:
        """Enable Zone 2 input follow."""
        self._zone2_input_follow = True
        _LOG.info("[%s] Zone 2 input follow enabled", self.id)
        return True

    async def independent_zone2_input(self) -> bool:
        """Disable Zone 2 input follow."""
        self._zone2_input_follow = False
        _LOG.info("[%s] Zone 2 input follow disabled", self.id)
        return True

    @property
    def zone2_volume_linked(self) -> bool:
        """Return Zone 2 volume sync state."""
        return self._zone2_volume_linked

    @property
    def zone2_input_follow(self) -> bool:
        """Return Zone 2 input follow state."""
        return self._zone2_input_follow

    async def _sync_zone2_volume(self, main_volume: int) -> None:
        """Sync Zone 2 volume to main zone if linked."""
        if not self._zone2_volume_linked or self._last_main_volume is None:
            self._last_main_volume = main_volume
            return

        delta = main_volume - self._last_main_volume
        current_z2 = self._conn.zones[Zone.ZONE2].volume

        if current_z2 is not None and delta != 0:
            new_z2 = max(0, min(100, current_z2 + delta))
            await self._set_volume(Zone.ZONE2, new_z2)
            _LOG.debug(
                "[%s] Zone 2 volume sync: %d → %d (Δ%d)",
                self.id,
                current_z2,
                new_z2,
                delta,
            )

        self._last_main_volume = main_volume

    async def _sync_zone2_input(self, input_code: int | None) -> None:
        """Sync Zone 2 input to main zone if following."""
        if not self._zone2_input_follow or input_code is None:
            return

        try:
            await self._set_input(Zone.ZONE2, input_code)
            _LOG.debug("[%s] Zone 2 input synced to 0x%02x", self.id, input_code)
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.debug("[%s] Zone 2 input sync failed: %s", self.id, ex)

    # media transport commands are not supported by this protocol
    async def next(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Not supported."""
        return ucapi.StatusCodes.NOT_IMPLEMENTED

    async def previous(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Not supported."""
        return ucapi.StatusCodes.NOT_IMPLEMENTED

    async def play_pause(self, zone: Zone = Zone.MAIN) -> ucapi.StatusCodes:
        """Not supported."""
        return ucapi.StatusCodes.NOT_IMPLEMENTED
