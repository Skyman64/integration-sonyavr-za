# CLAUDE.md — AI Assistant Handoff Notes

Context document for AI models (Claude or otherwise) working on this codebase
in future sessions. Read this before making changes. Human owner: skyman64.

## What this project is

An Unfolded Circle Remote Two/3 integration driver for the **Sony
STR-AV7000ES** AV receiver (and the whole Sony ES "ZA" platform:
STR-ZA1000ES…ZA5000ES). It is a fork of
[albaintor/integration-sonyavr](https://github.com/albaintor/integration-sonyavr)
with the entire songpal backend replaced.

**Critical background:** the upstream integration uses `python-songpal`
(Sony Audio Control API, ports 10000/54480). This receiver family does NOT
implement that API at all — those ports are closed. Do not reintroduce
songpal. The receiver speaks two things:

1. **Binary control protocol on TCP 33335** (33336 is also open, unused by
   us) — the same command set as the RS-232C custom-install protocol.
   Implemented in `src/za_protocol.py`.
2. **JSON web configuration endpoint** `POST http://<ip>/request.cgi` —
   the receiver's built-in settings web UI uses it; no auth/unlock needed.
   Implemented in `src/web_api.py`.

**`PROTOCOL.md` is the authoritative protocol reference** — every frame in
it was verified live against the actual receiver (fw 1.516, model type
"Z5"). Keep it updated when you decode anything new. Entries marked
*hypothesis* are educated guesses; do not present them as verified.

## Environment facts

- Receiver IP: **XX.XX.XX.XX** (web UI on port 80; needs a DHCP
  reservation — the driver has no discovery).
- The receiver answers on 33335 even in standby (network standby on).
- Requires **Python 3.11+** (uses `enum.StrEnum`). ucapi ~= 0.6.0.
- Repo lives at `~/Documents/UCR3 Integrations/integration-sonyavr-za`,
  git history on top of the upstream repo's history.
- A test venv may exist at `/tmp/zaenv` (aiohttp, pyee, ucapi installed);
  recreate with `python3 -m venv /tmp/zaenv && /tmp/zaenv/bin/pip install
  aiohttp pyee "ucapi~=0.6.0"`.


## File map (src/)

| File | Role |
|---|---|
| `za_protocol.py` | Binary protocol client. Frame builder/checksum, asyncio reader with reconnect+backoff, ACK(0xFD)/NAK(0xFE) handling, frame parsers (`A8 82` zone status, `A8 92` volume, `A9 82` tuner, `AB 82` sound field), per-zone `ZoneState`, `TunerState`, pyee events (`ZaEvents`). |
| `web_api.py` | `request.cgi` client: `get_features`/`set_feature`, input names, tuner preset names, audio settings. Known feature lists at top of file. |
| `avr.py` | `SonyDevice` — glue between protocol client(s) and ucapi. Zone-aware command methods (all take `zone: Zone = Zone.MAIN`), attribute assembly, event fan-out (`Events.UPDATE` with flat main-zone attrs + `"zone2"`/`"zone3"` sub-dicts), 20 s status poll backing up push updates, custom input-name mapping (display↔default), `send_simple_command()` dispatcher. |
| `media_player.py` | One `SonyMediaPlayer` class, instantiated 3× (MAIN/ZONE2/ZONE3). Zone entities pull their sub-dict in `filter_changed_attributes`. Entity ids: `media_player.<devid>`, `media_player.<devid>.zone2`, `.zone3`. |
| `selector.py`, `sensor.py` | Main-zone selects (input/sound mode) and sensors (volume/muted/input/sound mode/**tuner**). Mostly upstream code; `SonySensorTuner` added. |
| `driver.py` | ucapi integration driver (upstream structure). Registers 3 media players + selects + sensors in `_register_available_entities`. Entity→device mapping is via the `deviceid` property, not id parsing. |
| `config.py` | Device config store. `extract_device_info()` identifies via `request.cgi` (`system.modeltype`/`version`). Device id is currently `sonyza-<ip-with-dashes>` — see "worthwhile next steps". `handle_address_change()` is a no-op (no discovery). |
| `setup_flow.py` | Upstream setup flow; manual IP entry only, validated via `extract_device_info`. |
| `const.py` | Input codes, sound field codes, simple commands, `WEB_SETTING_COMMANDS` (web-backed simple commands). |
| `discover.py` | Stub returning `[]` (protocol has no SSDP). Kept because file deletion may be blocked in sandbox; safe to delete for real. |
| `test.py` | Live harness: `python3 src/test.py <ip>` connects, dumps zone state, then prints pushed updates. Use it for protocol reverse-engineering diffs. |

## Behavioral rules learned from the device

- Commands to a **powered-off zone return NAK** — power the zone on first.
  This is receiver behavior, not a bug.
- Tuner preset up/down only ACK while a tuner input is active on some zone.
  Direct preset selection does not exist in this firmware (all candidate
  opcodes NAK).
- Query opcodes are ≥ 0x80 and read-only; set opcodes are < 0x80. A full
  read-only sweep of `A0–A7 × 80–FF` was already done (results in
  PROTOCOL.md) — no need to repeat it.
- Binary set-opcodes for audio settings (pure direct etc.) NAK; those
  settings are writable only via `request.cgi` (`audio.*` features).
- The receiver pushes state changes unsolicited on the open 33335 socket
  (same frame formats as query responses). The driver relies on this.
- FM frequency decode: 16-bit big-endian value / 100 = MHz (NOT the
  /99.5 approximation found in the peteS-UK/sonyavr HA code). AM = raw kHz.

## Testing etiquette (receiver is live in Kenn's home)

- Prefer read-only queries. For write tests use **Zone 2** (line-out, off
  in normal use) and **always restore state**: it should end
  `power=off, input=0x02 (CD)`. If you touch the tuner, restore band AM
  (last known: AM 530 kHz, no preset).
- Main zone is in daily use (input STB = code 0x3F). Don't switch main
  input or toggle main power without asking Kenn.
- Reversible main-zone tests (volume ±1 step, pure direct on→off) are fine.

## Known-unverified items (flagged in code comments too)

- `AUX` input code: `0x0A` chosen over `0x00` (both valid, one is AUX).
  Verify: run test.py, have user select AUX on the front panel, read the
  pushed status frame, fix `const.py` if needed.
- HDMI output codes (`A0 45 <00-03>`): inherited from DN series, never
  tested (could switch main HDMI out — ask first).
- Main-zone status byte bit5 (main shows `0x21` where zones show `0x01`):
  meaning unknown.

## Worthwhile next steps (agreed, not yet done)

1. **Audio format detection**: decode `A4 82` (response `AC 82 87 FF 00 00
   00`). Requires diffing while user plays different formats
   (Atmos vs PCM vs DTS). Would feed a "now playing format" sensor.
2. **Device id from hardware**: `A5 A1` query returns MAC + 12-char ASCII
   serial + model + destination. Switch `config.extract_device_info` to use
   the serial (via a short 33335 connection) instead of IP-based id.
   Migration concern: existing remote configs reference the old id.
3. Sleep timer (`A0 90` query works; set opcode unknown) and auto-standby
   (`A0 A4`).
4. Decode `A3 A0/B0/B1` (channel levels / speaker config / distances).
5. Wake-on-LAN fallback using the MAC from `A5 81`.
6. Possibly publish upstream (PR to albaintor or standalone repo) — code is
   MPL-2.0; keep upstream attribution.

## How to verify changes end-to-end

```bash
cd "~/Documents/UCR3 Integrations/integration-sonyavr-za"
# syntax/import check (needs py3.11+; sandbox python may be 3.10 — use Mac)
/tmp/zaenv/bin/python -c "import asyncio; asyncio.new_event_loop(); \
  import sys; sys.path.insert(0,'src'); \
  import za_protocol, web_api, const, config, avr, media_player, selector, sensor, setup_flow, driver; \
  print('OK')"
# live smoke test
/tmp/zaenv/bin/python src/test.py 10.64.67.230
# run the driver (remote connects via ws://<mac-ip>:9090)
UC_CONFIG_HOME=./config /tmp/zaenv/bin/python src/driver.py
```

See INSTALL.md for deployment (external driver vs on-remote binary via
`unfoldedcircle/r2-pyinstaller` docker image).
