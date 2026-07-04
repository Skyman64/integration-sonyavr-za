"""
Sony ES (ZA-series platform) IP control protocol client.

Implements the binary control protocol spoken on TCP port 33335 by
Sony ES custom-install receivers (STR-ZA1000ES..ZA5000ES platform,
including units reporting model type "Z5" such as the STR-AV7000ES
web UI variant).

Frame format:  0x02 <len> <category> <command> [<zone>] [params...] <checksum>
  - len       = number of bytes following (category..params), excluding checksum
  - checksum  = two's complement of the sum of all bytes after the 0x02 STX
  - ACK = 0xFD, NAK = 0xFE
  - category 0xA0 = system/audio, 0xA3 = sound field
  - responses/notifications use category | 0x08 (0xA8, 0xAB)
  - zone byte: 0x00 = main, 0x01 = zone 2, 0x02 = zone 3

Verified live against receiver firmware 1.516 (model type Z5).

:license: Mozilla Public License Version 2.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum

from pyee.asyncio import AsyncIOEventEmitter

_LOG = logging.getLogger(__name__)

ACK = 0xFD
NAK = 0xFE
STX = 0x02

DEFAULT_PORT = 33335
RECONNECT_DELAY_MIN = 2.0
RECONNECT_DELAY_MAX = 30.0
COMMAND_TIMEOUT = 5.0


class Zone(IntEnum):
    """Receiver zones."""

    MAIN = 0x00
    ZONE2 = 0x01
    ZONE3 = 0x02


class ZaEvents:
    """Event names emitted by SonyZaConnection."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ZONE_UPDATE = "zone_update"  # args: Zone, ZoneState
    SOUND_FIELD = "sound_field"  # args: int
    TUNER_UPDATE = "tuner_update"  # args: TunerState


def checksum(data: bytes | bytearray) -> int:
    """Two's complement of the sum of all bytes after STX."""
    return (0x100 - (sum(data[1:]) & 0xFF)) & 0xFF


def frame(*payload: int) -> bytes:
    """Build a complete frame: STX, len, payload..., checksum."""
    body = bytearray([STX, len(payload)]) + bytearray(payload)
    body.append(checksum(body))
    return bytes(body)


@dataclass
class TunerState:
    """Runtime state of the tuner.

    Frame (verified live): A9 82 <band> <preset> <mono> <freq_hi> <freq_lo>
      band:   0x80 = FM, 0x81 = AM
      preset: 1..30, 0xFF = none
      freq:   FM = 16-bit value / 100 MHz; AM = raw kHz
    """

    band: str | None = None  # "FM" / "AM"
    preset: int | None = None  # None if no preset selected
    stereo: bool | None = None
    frequency: float | None = None  # MHz for FM, kHz for AM

    def __str__(self) -> str:
        if self.band is None:
            return ""
        freq = f"{self.frequency:.2f} MHz" if self.band == "FM" else f"{int(self.frequency)} kHz"
        preset = f" P{self.preset}" if self.preset else ""
        return f"{self.band} {freq}{preset}"


@dataclass
class ZoneState:
    """Runtime state of one zone."""

    power: bool | None = None
    volume: int | None = None  # raw device steps
    muted: bool | None = None
    input_code: int | None = None
    extra: dict = field(default_factory=dict)


class SonyZaConnection:
    """Asyncio TCP client for the Sony ES IP control protocol."""

    def __init__(self, host: str, port: int = DEFAULT_PORT, loop: asyncio.AbstractEventLoop | None = None):
        self._host = host
        self._port = port
        self._loop = loop or asyncio.get_event_loop()
        self.events = AsyncIOEventEmitter(self._loop)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._connected: bool = False
        self._closing: bool = False
        self._send_lock = asyncio.Lock()
        self._ack_waiter: asyncio.Future | None = None
        self.zones: dict[Zone, ZoneState] = {z: ZoneState() for z in Zone}
        self.sound_field_code: int | None = None
        self.tuner = TunerState()

    @property
    def connected(self) -> bool:
        """Return connection state."""
        return self._connected

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        self._host = value

    async def connect(self) -> None:
        """Open the control connection and start the listener."""
        if self._connected:
            return
        self._closing = False
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), timeout=COMMAND_TIMEOUT
        )
        self._connected = True
        self._reader_task = self._loop.create_task(self._read_loop())
        _LOG.debug("[%s] connected on port %d", self._host, self._port)
        self.events.emit(ZaEvents.CONNECTED)
        await self.query_all()

    async def disconnect(self) -> None:
        """Close the connection."""
        self._closing = True
        await self._teardown()

    async def _teardown(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # pylint: disable=broad-except
                pass
            self._writer = None
        self._reader = None

    async def _reconnect_loop(self) -> None:
        delay = RECONNECT_DELAY_MIN
        while not self._closing and not self._connected:
            try:
                await self.connect()
                return
            except Exception as ex:  # pylint: disable=broad-except
                _LOG.debug("[%s] reconnect failed: %s", self._host, ex)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_DELAY_MAX)

    def _schedule_reconnect(self) -> None:
        if self._closing:
            return
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self._loop.create_task(self._reconnect_loop())

    # ------------------------------------------------------------------ I/O

    async def _read_loop(self) -> None:
        buf = bytearray()
        try:
            while True:
                data = await self._reader.read(256)
                if not data:
                    raise ConnectionResetError("connection closed by receiver")
                buf += data
                buf = self._parse_buffer(buf)
        except asyncio.CancelledError:
            return
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.warning("[%s] connection lost: %s", self._host, ex)
            self._connected = False
            self.events.emit(ZaEvents.DISCONNECTED)
            self._schedule_reconnect()

    def _parse_buffer(self, buf: bytearray) -> bytearray:
        while buf:
            b0 = buf[0]
            if b0 in (ACK, NAK):
                if self._ack_waiter and not self._ack_waiter.done():
                    self._ack_waiter.set_result(b0 == ACK)
                del buf[0]
                continue
            if b0 != STX:
                _LOG.debug("[%s] discarding unexpected byte 0x%02x", self._host, b0)
                del buf[0]
                continue
            if len(buf) < 2:
                break
            flen = buf[1]
            total = 2 + flen + 1  # STX + len + payload + checksum
            if len(buf) < total:
                break
            pkt = bytes(buf[:total])
            del buf[:total]
            if checksum(pkt[:-1]) != pkt[-1]:
                _LOG.debug("[%s] bad checksum in frame %s", self._host, pkt.hex(" "))
                continue
            self._handle_frame(pkt)
        return buf

    def _handle_frame(self, pkt: bytes) -> None:
        _LOG.debug("[%s] recv %s", self._host, pkt.hex(" "))
        cat, cmd = pkt[2], pkt[3]
        payload = pkt[4:-1]
        if cat == 0xA8 and cmd == 0x82 and len(payload) >= 5:
            # status frame: zone, input, input, state-bits, 0x07
            # state bits (verified live): bit0 = power, bit1 = mute
            zone = self._zone(payload[0])
            if zone is None:
                return
            state = self.zones[zone]
            state.input_code = payload[1]
            state.power = bool(payload[3] & 0x01)
            state.muted = bool(payload[3] & 0x02)
            state.extra["status_raw"] = payload.hex(" ")
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, state)
        elif cat == 0xA8 and cmd == 0x92 and len(payload) >= 4:
            # volume frame: zone, 0x03, 0x00, volume
            zone = self._zone(payload[0])
            if zone is None:
                return
            self.zones[zone].volume = payload[3]
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        elif cat == 0xA8 and cmd == 0x93 and len(payload) >= 2:
            # mute notification (empirical): zone, muted
            zone = self._zone(payload[0])
            if zone is None:
                return
            self.zones[zone].muted = bool(payload[1])
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        elif cat == 0xA8 and cmd == 0x60 and len(payload) >= 2:
            # power notification (empirical): zone, power
            zone = self._zone(payload[0])
            if zone is None:
                return
            self.zones[zone].power = bool(payload[1])
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        elif cat == 0xA9 and cmd == 0x82 and len(payload) >= 5:
            # tuner status: band, preset, mono, freq_hi, freq_lo
            self.tuner.band = "AM" if payload[0] & 0x01 else "FM"
            self.tuner.preset = None if payload[1] == 0xFF else payload[1]
            self.tuner.stereo = not bool(payload[2] & 0x80)
            raw = (payload[3] << 8) | payload[4]
            self.tuner.frequency = raw / 100 if self.tuner.band == "FM" else float(raw)
            self.events.emit(ZaEvents.TUNER_UPDATE, self.tuner)
        elif cat == 0xAB and cmd == 0x82 and len(payload) >= 1:
            self.sound_field_code = payload[0]
            self.events.emit(ZaEvents.SOUND_FIELD, self.sound_field_code)
        else:
            _LOG.debug("[%s] unhandled frame %s", self._host, pkt.hex(" "))

    @staticmethod
    def _zone(value: int) -> Zone | None:
        try:
            return Zone(value)
        except ValueError:
            return None

    async def send(self, data: bytes, expect_ack: bool = True) -> bool:
        """Send a frame; return True if ACKed (or if no ack expected)."""
        if not self._connected or self._writer is None:
            raise ConnectionError("not connected")
        async with self._send_lock:
            waiter: asyncio.Future | None = None
            if expect_ack:
                waiter = self._loop.create_future()
                self._ack_waiter = waiter
            _LOG.debug("[%s] send %s", self._host, data.hex(" "))
            self._writer.write(data)
            await self._writer.drain()
            if waiter is None:
                return True
            try:
                return await asyncio.wait_for(waiter, timeout=COMMAND_TIMEOUT)
            except asyncio.TimeoutError:
                # Queries are answered with a data frame instead of ACK
                return True
            finally:
                self._ack_waiter = None

    # ------------------------------------------------------------- commands

    async def power(self, zone: Zone, on: bool) -> bool:
        """Set power for a zone."""
        ok = await self.send(frame(0xA0, 0x60, zone, 0x01 if on else 0x00))
        if ok:
            self.zones[zone].power = on
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        return ok

    async def set_volume(self, zone: Zone, volume: int) -> bool:
        """Set absolute volume (raw device steps)."""
        volume = max(0, min(volume, 100))
        ok = await self.send(frame(0xA0, 0x52, zone, 0x03, 0x00, volume))
        if ok:
            self.zones[zone].volume = volume
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        return ok

    async def volume_up(self, zone: Zone) -> bool:
        """Volume up one step."""
        return await self.send(frame(0xA0, 0x55, zone))

    async def volume_down(self, zone: Zone) -> bool:
        """Volume down one step."""
        return await self.send(frame(0xA0, 0x56, zone))

    async def mute(self, zone: Zone, muted: bool) -> bool:
        """Set mute state for a zone."""
        ok = await self.send(frame(0xA0, 0x53, zone, 0x01 if muted else 0x00))
        if ok:
            self.zones[zone].muted = muted
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        return ok

    async def select_input(self, zone: Zone, input_code: int) -> bool:
        """Select input source by device code."""
        ok = await self.send(frame(0xA0, 0x42, zone, input_code))
        if ok:
            self.zones[zone].input_code = input_code
            self.events.emit(ZaEvents.ZONE_UPDATE, zone, self.zones[zone])
        return ok

    async def select_sound_field(self, code: int) -> bool:
        """Select sound field (main zone only)."""
        ok = await self.send(frame(0xA3, 0x42, code))
        if ok:
            self.sound_field_code = code
            self.events.emit(ZaEvents.SOUND_FIELD, code)
        return ok

    async def tuner_preset_up(self) -> bool:
        """Next tuner preset (tuner must be the active input on a zone)."""
        return await self.send(frame(0xA1, 0x0B))

    async def tuner_preset_down(self) -> bool:
        """Previous tuner preset (tuner must be the active input on a zone)."""
        return await self.send(frame(0xA1, 0x0C))

    # -------------------------------------------------------------- queries

    async def query_status(self, zone: Zone) -> None:
        """Request input/status frame for a zone."""
        await self.send(frame(0xA0, 0x82, zone), expect_ack=False)

    async def query_volume(self, zone: Zone) -> None:
        """Request volume for a zone."""
        await self.send(frame(0xA0, 0x92, zone, 0x03), expect_ack=False)

    async def query_sound_field(self) -> None:
        """Request current sound field."""
        await self.send(frame(0xA3, 0x82, 0x00), expect_ack=False)

    async def query_tuner(self) -> None:
        """Request tuner status."""
        await self.send(frame(0xA1, 0x82, 0x00), expect_ack=False)

    async def query_all(self) -> None:
        """Query status and volume of all zones plus sound field."""
        for zone in Zone:
            await self.query_status(zone)
            await self.query_volume(zone)
        await self.query_sound_field()
        await self.query_tuner()
