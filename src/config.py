"""
Configuration handling of the integration driver.

:copyright: (c) 2023 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import dataclasses
import json
import logging
import os
from asyncio import Lock
from dataclasses import dataclass, field, fields
from typing import Callable, Iterator
from urllib.parse import urlparse

import aiohttp
from ucapi import Entity, EntityTypes

from const import DEFAULT_VOLUME_STEP

MODEL_NAMES = {
    "Z0": "STR-ZA1000ES",
    "Z1": "STR-ZA2000ES",
    "Z3": "STR-ZA3000ES",
    "Z5": "STR-ZA5000ES",
}

_LOG = logging.getLogger(__name__)

_CFG_FILENAME = "config.json"


class SonyEntity(Entity):
    """Global Sony entity."""

    @property
    def deviceid(self) -> str:
        """Return the device identifier."""
        raise NotImplementedError()


def create_entity_id(avr_id: str, entity_type: EntityTypes) -> str:
    """Create a unique entity identifier for the given receiver and entity type."""
    return f"{entity_type.value}.{avr_id}"


def device_from_entity_id(entity_id: str) -> str | None:
    """
    Return the avr_id prefix of an entity_id.

    The prefix is the part before the first dot in the name and refers to the AVR device identifier.

    :param entity_id: the entity identifier
    :return: the device prefix, or None if entity_id doesn't contain a dot
    """
    return entity_id.split(".", 1)[1]


@dataclass
class DeviceInstance:
    """Sony device configuration."""

    # pylint: disable = W0622
    id: str
    name: str
    address: str
    always_on: bool = field(default=False)
    volume_step: float = field(default=DEFAULT_VOLUME_STEP)
    mac_address_wired: str | None = field(default=None)
    mac_address_wifi: str | None = field(default=None)
    sensor_include_device_name: bool = field(default=True)

    def __post_init__(self):
        """Apply default values on missing fields."""
        for attribute in fields(self):
            # If there is a default and the value of the field is none we can assign a value
            if (
                not isinstance(attribute.default, dataclasses.MISSING.__class__)
                and getattr(self, attribute.name) is None
            ):
                setattr(self, attribute.name, attribute.default)

    def get_device_part(self) -> str:
        """Return the device name part to build entity names."""
        if self.sensor_include_device_name:
            return self.name + " "
        return ""


class _EnhancedJSONEncoder(json.JSONEncoder):
    """Python dataclass json encoder."""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class Devices:
    """Integration driver configuration class. Manages all configured Sony devices."""

    def __init__(
        self,
        data_path: str,
        add_handler: Callable[[DeviceInstance], None],
        remove_handler: Callable[[DeviceInstance | None], None],
        update_handler: Callable[[DeviceInstance], None],
    ):
        """
        Create a configuration instance for the given configuration path.

        :param data_path: configuration path for the configuration file and client device certificates.
        """
        self._data_path: str = data_path
        self._cfg_file_path: str = os.path.join(data_path, _CFG_FILENAME)
        self._config: list[DeviceInstance] = []
        self._add_handler = add_handler
        self._remove_handler = remove_handler
        self._update_handler = update_handler
        self.load()
        self._config_lock = Lock()

    @property
    def data_path(self) -> str:
        """Return the configuration path."""
        return self._data_path

    def all(self) -> Iterator[DeviceInstance]:
        """Get an iterator for all devices configurations."""
        return iter(self._config)

    def empty(self) -> bool:
        """Return true if no devices configured."""
        return len(self._config) == 0

    def contains(self, avr_id: str) -> bool:
        """Check if there's a device with the given device identifier."""
        for item in self._config:
            if item.id == avr_id:
                return True
        return False

    def add_or_update(self, atv: DeviceInstance) -> None:
        """Add a new configured device."""
        if self.contains(atv.id):
            _LOG.debug("Existing config %s, updating it %s", atv.id, atv)
            self.update(atv)
            if self._update_handler is not None:
                self._update_handler(atv)
        else:
            _LOG.debug("Adding new config %s", atv)
            self._config.append(atv)
            self.store()
        if self._add_handler is not None:
            self._add_handler(atv)

    def get(self, avr_id: str) -> DeviceInstance | None:
        """Get device configuration for given identifier."""
        for item in self._config:
            if item.id == avr_id:
                # return a copy
                return dataclasses.replace(item)
        return None

    def update(self, device: DeviceInstance) -> bool:
        """Update a configured Sony device and persist configuration."""
        for item in self._config:
            if item.id == device.id:
                item.address = device.address
                item.name = device.name
                item.always_on = device.always_on
                item.volume_step = device.volume_step
                item.mac_address_wired = device.mac_address_wired
                item.mac_address_wired = device.mac_address_wired
                return self.store()
        return False

    def remove(self, avr_id: str) -> bool:
        """Remove the given device configuration."""
        device = self.get(avr_id)
        if device is None:
            return False
        try:
            self._config.remove(device)
            if self._remove_handler is not None:
                self._remove_handler(device)
            return True
        except ValueError:
            pass
        return False

    def clear(self) -> None:
        """Remove the configuration file."""
        self._config = []

        if os.path.exists(self._cfg_file_path):
            os.remove(self._cfg_file_path)

        if self._remove_handler is not None:
            self._remove_handler(None)

    def store(self) -> bool:
        """
        Store the configuration file.

        :return: True if the configuration could be saved.
        """
        try:
            with open(self._cfg_file_path, "w+", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, cls=_EnhancedJSONEncoder)
            return True
        except OSError:
            _LOG.error("Cannot write the config file")

        return False

    def export(self) -> str:
        """Export the configuration file to a string.

        :return: JSON formatted string of the current configuration
        """
        return json.dumps(self._config, ensure_ascii=False, cls=_EnhancedJSONEncoder)

    def import_config(self, updated_config: str) -> bool:
        """Import the updated configuration."""
        config_backup = self._config.copy()
        try:
            data = json.loads(updated_config)
            self._config.clear()
            for item in data:
                try:
                    self._config.append(DeviceInstance(**item))
                except TypeError as ex:
                    _LOG.warning("Invalid configuration entry will be ignored: %s", ex)

            _LOG.debug("Configuration to import : %s", self._config)

            # Now trigger events add/update/removal of devices based on old / updated list
            for device in self._config:
                found = False
                for old_device in config_backup:
                    if old_device.id == device.id:
                        if self._update_handler is not None:
                            self._update_handler(device)
                        found = True
                        break
                if not found and self._add_handler is not None:
                    self._add_handler(device)
            for old_device in config_backup:
                found = False
                for device in self._config:
                    if old_device.id == device.id:
                        found = True
                        break
                if not found and self._remove_handler is not None:
                    self._remove_handler(old_device)

            with open(self._cfg_file_path, "w+", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, cls=_EnhancedJSONEncoder)
            return True
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.error(
                "Cannot import the updated configuration %s, keeping existing configuration : %s", updated_config, ex
            )
            try:
                # Restore current configuration
                self._config = config_backup
                self.store()
            # pylint: disable = W0718
            except Exception:
                pass
        return False

    def load(self) -> bool:
        """Load the config into the config global variable.

        :return: True if the configuration could be loaded.
        """
        try:
            with open(self._cfg_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                # not using AtvDevice(**item) to be able to migrate old configuration files with missing attributes
                device_instance = DeviceInstance(
                    item.get("id"),
                    item.get("name"),
                    item.get("address"),
                    item.get("always_on", False),
                    item.get("volume_step", 2.0),
                    item.get("mac_address_wired", None),
                    item.get("mac_address_wifi", None),
                )
                self._config.append(device_instance)
            return True
        except OSError:
            _LOG.error("Cannot open the config file")
        except ValueError:
            _LOG.error("Empty or invalid config file")

        return False

    @staticmethod
    def extract_url(host: str) -> str:
        """Return the plain host/IP from user input."""
        if "://" in host:
            host = host.split("://", 1)[1]
        host = host.split("/", 1)[0]
        host = host.split(":", 1)[0]
        return host

    @staticmethod
    async def extract_device_info(host: str) -> DeviceInstance:
        """Extract device information from the receiver's web endpoint (request.cgi)."""
        host = Devices.extract_url(host)

        payload = {
            "type": "http_get",
            "packet": [
                {"id": 1, "feature": "system.modeltype"},
                {"id": 2, "feature": "system.version"},
            ],
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.post(f"http://{host}/request.cgi", json=payload) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)

        model_type = None
        version = None
        for packet in data.get("packet", []):
            if packet.get("feature") == "system.modeltype":
                model_type = packet.get("value")
            elif packet.get("feature") == "system.version":
                version = packet.get("value")

        model_name = MODEL_NAMES.get(model_type, f"Sony ES ({model_type})" if model_type else "Sony ES Receiver")
        unique_id = f"sonyza-{host.replace('.', '-')}"
        _LOG.info("Found %s (fw %s) at %s", model_name, version, host)

        return DeviceInstance(
            id=unique_id,
            name=model_name,
            address=host,
            always_on=False,
            volume_step=2,
            mac_address_wired=None,
            mac_address_wifi=None,
        )

    async def handle_address_change(self):
        """Address discovery is not supported by the ES/ZA control protocol.

        Configure the receiver with a static IP or DHCP reservation.
        """
        return


devices: Devices | None = None  # pylint: disable=C0103
