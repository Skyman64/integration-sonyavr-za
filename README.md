# Sony ES (ZA / STR-AV7000ES) integration for Unfolded Circle Remote Two/3

Fork of [albaintor/integration-sonyavr](https://github.com/albaintor/integration-sonyavr)
with the songpal backend replaced by the **native Sony ES IP control protocol
(TCP port 33335)** — the protocol actually spoken by ES custom-install
receivers (STR-ZA1000ES…ZA5000ES platform, incl. units reporting model type
"Z5" such as the STR-AV7000ES). These receivers do **not** expose Sony's
Audio Control (songpal) API, so the upstream integration cannot talk to them.

Built with [uc-integration-api](https://github.com/aitatoi/integration-python-library).

## What's different from upstream

- Native ES/ZA binary protocol client (`src/za_protocol.py`), no songpal
- **Zone 2 and Zone 3 media-player entities** with independent power,
  volume, mute, and input selection, plus optional Zone 2 volume/input sync
  to the main zone
- Push status updates: the receiver notifies volume/input/power/mute changes
  on the open control socket; a light 20 s poll backs this up
- Device identification and setup validation via the receiver's web endpoint
  (`POST /request.cgi`)
- No SSDP auto-discovery (the protocol doesn't support it) — enter the
  receiver's IP during setup and give it a DHCP reservation

## Protocol summary (verified live on fw 1.516)

```
Frame:      0x02 <len> <category> <command> [<zone>] [params…] <checksum>
Checksum:   two's complement of the sum of all bytes after 0x02
ACK/NAK:    0xFD / 0xFE
Zones:      0x00 main, 0x01 zone 2, 0x02 zone 3

Power       A0 60 <zone> <01|00>
Volume set  A0 52 <zone> 03 00 <vol 0..100>
Volume ±    A0 55 <zone> / A0 56 <zone>
Mute        A0 53 <zone> <01|00>
Input       A0 42 <zone> <input code>
Sound field A3 42 <code>
Queries     A0 82 <zone> (status), A0 92 <zone> 03 (volume), A3 82 00 (sound field)
Status rsp  A8 82 <zone> <input> <input> <bits> 07   (bit0 = power, bit1 = mute)
```

Note: commands to a powered-off zone are NAKed — power the zone on first.
See [PROTOCOL.md](PROTOCOL.md) for the full, empirically-mapped protocol
reference (every command/query byte-for-byte, verified live).

## Entities

- Media player: Main zone (power, volume, mute, input, sound field, HDMI out)
- Media player: Zone 2 (power, volume, mute, input)
- Media player: Zone 3 (power, volume, mute, input)
- Select: input source, sound mode (main zone)
- Sensors: volume, muted, input source, sound mode, tuner (band/freq/preset)

## Extra features

- **Custom input names**: names assigned in the receiver's web UI are read at
  connect time (`request.cgi`) and used as source labels on the remote.
- **Tuner**: preset up/down simple commands (`TUNER_PRESET_UP` /
  `TUNER_PRESET_DOWN`; the tuner must be the active input on some zone —
  direct preset selection is not supported by the firmware) and a live tuner
  sensor, e.g. "FM 88.50 MHz P1".
- **Sound settings** via web endpoint (verified live): simple commands
  `PURE_DIRECT_ON/OFF`, `SOUND_OPTIMIZER_OFF/NORMAL/LOW`, `NEURAL_X_ON/OFF`.
- **Zone 2 sync**: optional volume-follows-main and input-follows-main modes,
  toggled with the `ZONE2_LINK_VOLUME` / `ZONE2_UNLINK_VOLUME` and
  `ZONE2_FOLLOW_INPUT` / `ZONE2_INDEPENDENT_INPUT` simple commands.

Web endpoint protocol: `POST /request.cgi` with
`{"type":"http_get"|"http_set","packet":[{"id":1,"feature":"audio.puredirect","value":"on"}]}`
— no unlock required. Known feature groups: `audio.*`, `<INPUT>.inputname`,
`FM/AMpresetN.name`, `system.*`, `zone2/3.*`.

## Getting started

See [INSTALL.md](INSTALL.md) for the full setup guide (three ways to run
this: as an external Python process, in Docker, or as a self-contained
binary uploaded directly to the remote). Short version:

```bash
git clone https://github.com/Skyman64/integration-sonyavr-za.git
cd integration-sonyavr-za
pip3 install -r requirements.txt
python3 src/test.py <receiver-ip>   # smoke test: dumps zone state, then listens
python3 src/driver.py               # run the integration driver
```

Requires Python 3.11+. To upload this as a custom integration binary
directly to the remote, see [BUILDING.md](BUILDING.md).

## Architecture notes (src/)

| File | Role |
|---|---|
| `za_protocol.py` | Binary protocol client: frame builder/checksum, asyncio reader with reconnect+backoff, ACK(0xFD)/NAK(0xFE) handling, frame parsers (`A8 82` zone status, `A8 92` volume, `A9 82` tuner, `AB 82` sound field), per-zone `ZoneState`, `TunerState`, pyee events (`ZaEvents`). |
| `web_api.py` | `request.cgi` client: `get_features`/`set_feature`, input names, tuner preset names, audio settings. |
| `avr.py` | `SonyDevice` — glue between the protocol client(s) and ucapi. Zone-aware command methods, attribute assembly, event fan-out, 20 s status poll backing up push updates, custom input-name mapping, Zone 2 sync logic. |
| `media_player.py` | One `SonyMediaPlayer` class, instantiated 3× (MAIN/ZONE2/ZONE3). |
| `selector.py`, `sensor.py` | Main-zone selects (input/sound mode) and sensors (volume/muted/input/sound mode/tuner). |
| `driver.py` | ucapi integration driver entry point; registers media players, selects, and sensors. |
| `config.py` | Device config store; `extract_device_info()` identifies the receiver via `request.cgi`. No discovery is possible, so `handle_address_change()` is a no-op. |
| `setup_flow.py` | Setup flow; manual IP entry only, validated via `extract_device_info`. |
| `const.py` | Input codes, sound field codes, simple commands. |
| `discover.py` | Stub returning `[]` — the protocol has no SSDP/auto-discovery. |
| `test.py` | Live harness: `python3 src/test.py <ip>` connects, dumps zone state, then prints pushed updates. Useful for protocol reverse-engineering. |

## Behavioral notes learned from the device

- Commands to a **powered-off zone return NAK** — power the zone on first.
  This is receiver behavior, not a bug.
- Tuner preset up/down only ACK while a tuner input is active on some zone.
  Direct preset selection does not exist in this firmware.
- Query opcodes are ≥ `0x80` and read-only; set opcodes are `< 0x80`.
- Binary set-opcodes for audio settings (pure direct etc.) NAK; those
  settings are writable only via `request.cgi` (`audio.*` features).
- The receiver pushes state changes unsolicited on the open 33335 socket
  (same frame formats as query responses); the driver relies on this.
- FM frequency decode: 16-bit big-endian value / 100 = MHz (AM = raw kHz).

## Known limitations / possible next steps

- `AUX` input code is `0x0A` by default, chosen over `0x00` (both are valid
  codes; only one is actually AUX on a given unit) — verify on your own
  receiver with `src/test.py` and adjust `const.py` if needed.
- HDMI output codes (`A0 45 <00-03>`) are inherited from the Denon-series
  fork and have not been verified live on ES/ZA hardware.
- Audio format detection (`A4 82`) is not yet decoded — would enable a
  "now playing format" sensor.
- Device ID currently derives from the configured IP address rather than
  the receiver's MAC/serial (available via `A5 A1`); switching to a
  hardware-based ID would survive IP changes but is a breaking change for
  existing remote configs.
- Sleep timer and auto-standby state are read-only for now (set opcodes
  unknown).

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).

---

Documentation and repository cleanup performed with the assistance of
Claude Fable (Anthropic).
