# Sony ES (ZA platform) IP Control Protocol Map

Empirically mapped against an STR-AV7000ES (model type "Z5", firmware 1.516)
at TCP port 33335. Full read-only query sweep: categories `A0`–`A7`,
opcodes `0x80`–`0xFF` (2,048 probes). Everything below is an actual response
from the device unless marked *hypothesis*.

## Frame format

```
0x02 <len> <category> <command> [params…] <checksum>
len      = bytes from category through params (checksum excluded)
checksum = two's complement of the sum of all bytes after 0x02
ACK 0xFD   NAK 0xFE  (NAK = unsupported opcode OR command rejected, e.g. zone off)
```

Categories: `A0` system/zones, `A1` tuner, `A3` audio, `A4` video/HDMI(?),
`A5` device identity. Responses/notifications use `category | 0x08`
(`A8`, `A9`, `AB`, `AC`, `AD`). State changes are pushed unsolicited on the
open socket in the same response formats.

## Verified control commands (all take effect, ACK 0xFD)

| Command | Frame (before checksum) | Notes |
|---|---|---|
| Power on/off | `A0 60 <zone> <01/00>` | zone 00 main, 01 z2, 02 z3 |
| Volume set | `A0 52 <zone> 03 00 <0..100>` | |
| Volume up/down | `A0 55 <zone>` / `A0 56 <zone>` | |
| Mute on/off | `A0 53 <zone> <01/00>` | |
| Input select | `A0 42 <zone> <code>` | see input codes below |
| Sound field | `A3 42 <code>` | main zone |
| Tuner preset up/down | `A1 0B` / `A1 0C` | tuner must be active input; direct preset select NAKs |
| HDMI output | `A0 45 <code>` | *hypothesis:* 00 A+B, 01 A, 02 B, 03 off (unverified) |

Commands to a powered-off zone return NAK.

## Input codes (enumerated live: complete set)

`00` unknown · `02` SA-CD/CD · `0A` AUX(*likely*) · `0F` SOURCE (zones) ·
`10` VIDEO · `16` SAT/CATV · `1A` TV · `1B` BD/DVD · `1C` GAME ·
`2E` FM · `2F` AM · `3F` STB

## Verified queries and response decodes

| Query | Response | Decode |
|---|---|---|
| `A0 82 <zone>` | `A8 82 <zone> <in> <in> <bits> 07` | bits: bit0 power, bit1 mute; main adds bit5 (undecoded) |
| `A0 92 <zone> 03` | `A8 92 <zone> 03 00 <vol>` | volume 0..100 |
| `A1 82 00` | `A9 82 <band> <preset> <mono> <fHi> <fLo>` | band 80 FM / 81 AM; preset FF none; FM freq = value/100 MHz, AM = raw kHz; mono bit7 |
| `A3 82` | `AB 82 <code> 00` | sound field code (see table below) |
| `A3 92` | `AB 92 00 <v>` | Sound Optimizer: 0 off, 1 normal, 2 low |
| `A3 97` | `AB 97 00 <v>` | Auto Phase Matching: 0 off, 2 auto |
| `A3 98` | `AB 98 <0/1>` | Pure Direct off/on |
| `A0 A0` | `A8 A0 "STR-Z5<spaces>"` | model string (ASCII, 14 chars) |
| `A5 A1` | `AD A1 <mac:6> <serial:12 ascii> <model:14 ascii> 00×6 "UC" …` | device identity block: MAC, serial, model, destination |
| `A5 81` | `AD 80 <mac:6>` | MAC address |

## Discovered, decode incomplete (answers but meaning unconfirmed)

| Query | Response payload seen | Best guess |
|---|---|---|
| `A0 80` | `01 1A` | system status summary (byte0 = power?) |
| `A0 90` | `00 00 13 00` | sleep/timer state (DN series uses A8 90 for timer) |
| `A0 A2` | `02 C0 00 00 C0 00 00` | firmware/hardware version block |
| `A0 A3` | `04` | unknown scalar |
| `A0 A4` | `40` | auto-standby state (DN: CC on / 4C off — differs here) |
| `A1 A0` | short frame `A9 0E` | tuner capability? |
| `A3 84` | `01` | unknown audio flag |
| `A3 90` | `00 02` | unknown audio setting (value 2) |
| `A3 91` | `00 00` | unknown audio setting |
| `A3 93` | `00 01` | unknown audio setting (value 1) |
| `A3 A0` | 6 × `00 00 7F FF 00 00` | per-channel level/EQ table (6 groups) |
| `A3 B0` | `10 01 01 01 01 01 01 01` | speaker configuration table |
| `A3 B1` | 24-byte blob incl. `FF 80 FF 80`, `0A 00` | speaker distance/crossover block |
| `A4 82` | `87 FF 00 00 00` | video/HDMI or input-stream status — candidate for audio-format detection; needs diffing while changing sources/formats |

To decode the incomplete entries: run `src/test.py`, change the suspected
setting on the receiver (front panel or web UI), and diff the pushed/queried
frames before and after.

## Sound field codes (set `A3 42 <code>`, observed + web UI list)

`00` 2ch Stereo · `02` Direct · `16` Jazz Club · `19` Live Concert ·
`1E`/`1F`/`38` Concert Hall A/B/C · `21` A.F.D. · `23` Dolby Surround ·
`25` Neural:X · `27` Multi Stereo · `33` HD-D.C.S.

## Web endpoint (port 80, `POST /request.cgi`)

JSON get/set of every configuration feature, no auth/unlock required:

```
{"type":"http_get","packet":[{"id":1,"feature":"audio.puredirect"}]}
{"type":"http_set","packet":[{"id":1,"feature":"audio.puredirect","value":"on"}]}
```

Known feature groups: `system.modeltype|version|destination`,
`<INPUT>.inputname` (BD/SAT/GAME/STB/VIDEO/AUX/TV/CD),
`FMpresetN.name` / `AMpresetN.name` (1–30),
`audio.puredirect|soundoptimizer|soundfield|neuralx|drangecomp|dualmono|dll|inceilingmode`,
`main|zone2|zone3.maxvol*|presetvol*|lineout`, plus the speaker/hdmi/network
settings pages. Writes return `{"value":"ACK"}` per packet.
