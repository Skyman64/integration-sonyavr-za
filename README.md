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
  volume, mute, and input selection
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

Web endpoint protocol: `POST /request.cgi` with
`{"type":"http_get"|"http_set","packet":[{"id":1,"feature":"audio.puredirect","value":"on"}]}`
— no unlock required. Known feature groups: `audio.*`, `<INPUT>.inputname`,
`FM/AMpresetN.name`, `system.*`, `zone2/3.*`.

## Setup

- Requires Python 3.11+
- `pip3 install -r requirements.txt`
- Run: `python3 src/driver.py`
- Test harness: `python3 src/test.py <receiver-ip>` (connects, dumps zone
  state, then listens and prints pushed status changes)

For running as an external integration on the network, adjust `driver.json`
(`driver_id`, `name`, optional `port`) as described upstream.

## Build self-contained binary for the remote

Same as upstream: use the `unfoldedcircle/r2-pyinstaller` image on aarch64:

    docker run --rm --name builder \
        --user=$(id -u):$(id -g) \
        -v "$PWD":/workspace \
        docker.io/unfoldedcircle/r2-pyinstaller:3.11.6  \
        bash -c \
          "python -m pip install -r requirements.txt && \
          pyinstaller --clean --onefile --name src src/driver.py"

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).
