"""Constants file.

Sony ES (ZA platform / STR-AV7000ES) integration constants.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from enum import Enum

DEFAULT_PORT = 33335
DEFAULT_VOLUME_STEP = 2.0
DEFAULT_MAX_VOLUME = 100

# Simple commands exposed on the main-zone media player.
# HDMI output values (A0 45 <value>) are unverified; the rest are verified live.
SIMPLE_COMMANDS = [
    "ZONE_HDMI_OUTPUT_AB",
    "ZONE_HDMI_OUTPUT_A",
    "ZONE_HDMI_OUTPUT_B",
    "ZONE_HDMI_OUTPUT_OFF",
    "TUNER_PRESET_UP",
    "TUNER_PRESET_DOWN",
    "PURE_DIRECT_ON",
    "PURE_DIRECT_OFF",
    "SOUND_OPTIMIZER_OFF",
    "SOUND_OPTIMIZER_NORMAL",
    "SOUND_OPTIMIZER_LOW",
    "NEURAL_X_ON",
    "NEURAL_X_OFF",
    "ZONE2_LINK_VOLUME",
    "ZONE2_UNLINK_VOLUME",
    "ZONE2_FOLLOW_INPUT",
    "ZONE2_INDEPENDENT_INPUT",
]

# Simple commands implemented via the web endpoint (feature, value)
WEB_SETTING_COMMANDS = {
    "PURE_DIRECT_ON": ("audio.puredirect", "on"),
    "PURE_DIRECT_OFF": ("audio.puredirect", "off"),
    "SOUND_OPTIMIZER_OFF": ("audio.soundoptimizer", "off"),
    "SOUND_OPTIMIZER_NORMAL": ("audio.soundoptimizer", "normal"),
    "SOUND_OPTIMIZER_LOW": ("audio.soundoptimizer", "low"),
    "NEURAL_X_ON": ("audio.neuralx", "on"),
    "NEURAL_X_OFF": ("audio.neuralx", "off"),
}

HDMI_OUTPUT_CODES = {
    "ZONE_HDMI_OUTPUT_AB": 0x00,
    "ZONE_HDMI_OUTPUT_A": 0x01,
    "ZONE_HDMI_OUTPUT_B": 0x02,
    "ZONE_HDMI_OUTPUT_OFF": 0x03,
}

# Input source codes for the A0 42 command (zone byte selects the zone).
# Names follow the receiver's default web-UI input names.
# Verified by live enumeration on the device (fw 1.516): valid codes are
# 00 02 0a 0f 10 16 1a 1b 1c 2e 2f 3f
INPUT_CODES = {
    "BD/DVD": 0x1B,
    "SAT/CATV": 0x16,
    "GAME": 0x1C,
    "STB": 0x3F,
    "VIDEO": 0x10,
    "AUX": 0x0A,  # best guess between the two remaining valid codes (0x0A/0x00)
    "TV": 0x1A,
    "SA-CD/CD": 0x02,
    "FM TUNER": 0x2E,
    "AM TUNER": 0x2F,
    "SOURCE": 0x0F,  # zone follows main-zone input (zones 2/3 only)
}

INPUT_NAMES = {v: k for k, v in INPUT_CODES.items()}

# Sound field codes for the A3 42 command (main zone).
# Matches the receiver web UI sound field list (Z5 platform).
SOUND_FIELD_CODES = {
    "2ch Stereo": 0x00,
    "Direct": 0x02,
    "Auto Format Decoding": 0x21,
    "Dolby Surround": 0x23,
    "Neural:X": 0x25,
    "Multi Stereo": 0x27,
    "HD-D.C.S.": 0x33,
    "Concert Hall A": 0x1E,
    "Concert Hall B": 0x1F,
    "Concert Hall C": 0x38,
    "Jazz Club": 0x16,
    "Live Concert": 0x19,
}

SOUND_FIELD_NAMES = {v: k for k, v in SOUND_FIELD_CODES.items()}

ZONE_NAMES = {0: "Main", 1: "Zone 2", 2: "Zone 3"}


class SonySensors(str, Enum):
    """Sony sensor values."""

    SENSOR_VOLUME = "sensor_volume"
    SENSOR_MUTED = "sensor_muted"
    SENSOR_INPUT = "sensor_input"
    SENSOR_SOUND_MODE = "sensor_sound_mode"
    SENSOR_TUNER = "sensor_tuner"


class SonySelects(str, Enum):
    """Sony select values."""

    SELECT_INPUT_SOURCE = "select_input_source"
    SELECT_SOUND_MODE = "select_sound_mode"
