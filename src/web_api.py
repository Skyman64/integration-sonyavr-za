"""
Sony ES web configuration endpoint client (POST /request.cgi).

The receiver's built-in web server exposes every configuration feature as
JSON key/value pairs. Verified live: reads and writes work without the
web-UI unlock step.

  Read:  {"type":"http_get","packet":[{"id":1,"feature":"audio.puredirect"}]}
  Write: {"type":"http_set","packet":[{"id":1,"feature":"...","value":"..."}]}

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging

import aiohttp

_LOG = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=5)

# feature keys for user-assigned input names (blank value = default name)
INPUT_NAME_FEATURES = {
    "BD.inputname": "BD/DVD",
    "SAT.inputname": "SAT/CATV",
    "GAME.inputname": "GAME",
    "STB.inputname": "STB",
    "VIDEO.inputname": "VIDEO",
    "AUX.inputname": "AUX",
    "TV.inputname": "TV",
    "CD.inputname": "SA-CD/CD",
}

# audio settings features and their allowed values (from the web UI)
AUDIO_SETTINGS = {
    "audio.puredirect": ["on", "off"],
    "audio.soundoptimizer": ["off", "normal", "low"],
    "audio.neuralx": ["on", "off"],
    "audio.drangecomp": ["on", "auto", "off"],
    "audio.dualmono": ["main_sub", "main", "sub"],
}


class SonyWebApi:
    """Async client for the receiver's request.cgi endpoint."""

    def __init__(self, host: str):
        self._host = host

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        self._host = value

    async def get_features(self, features: list[str]) -> dict[str, str | None]:
        """Read a list of features; returns feature -> value."""
        payload = {
            "type": "http_get",
            "packet": [{"id": i + 1, "feature": f} for i, f in enumerate(features)],
        }
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(f"http://{self._host}/request.cgi", json=payload) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        result: dict[str, str | None] = {}
        for packet in data.get("packet", []):
            if packet and "feature" in packet:
                result[packet["feature"]] = packet.get("value")
        return result

    async def set_feature(self, feature: str, value: str) -> bool:
        """Write one feature; returns True on ACK."""
        payload = {
            "type": "http_set",
            "packet": [{"id": 1, "feature": feature, "value": value}],
        }
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(f"http://{self._host}/request.cgi", json=payload) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        packets = data.get("packet", [])
        ok = bool(packets) and packets[0].get("value") == "ACK"
        if not ok:
            _LOG.warning("[%s] set %s=%s failed: %s", self._host, feature, value, data)
        return ok

    async def get_input_names(self) -> dict[str, str]:
        """Return default-input-name -> display-name (custom if renamed)."""
        try:
            values = await self.get_features(list(INPUT_NAME_FEATURES.keys()))
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.warning("[%s] cannot read input names: %s", self._host, ex)
            return {}
        names: dict[str, str] = {}
        for feature, default_name in INPUT_NAME_FEATURES.items():
            value = values.get(feature)
            names[default_name] = value.strip() if value and value.strip() else default_name
        return names

    async def get_preset_names(self, band: str, count: int = 30) -> dict[int, str]:
        """Return preset number -> name for band 'FM' or 'AM'."""
        features = [f"{band}preset{i}.name" for i in range(1, count + 1)]
        try:
            values = await self.get_features(features)
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.warning("[%s] cannot read %s preset names: %s", self._host, band, ex)
            return {}
        names: dict[int, str] = {}
        for i in range(1, count + 1):
            value = values.get(f"{band}preset{i}.name")
            names[i] = value.strip() if value and value.strip() else f"{band} {i}"
        return names

    async def get_audio_settings(self) -> dict[str, str | None]:
        """Read all known audio settings."""
        try:
            return await self.get_features(list(AUDIO_SETTINGS.keys()))
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.warning("[%s] cannot read audio settings: %s", self._host, ex)
            return {}
