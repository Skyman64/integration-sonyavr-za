# Installation Guide — Sony ES (STR-AV7000ES / ZA) Integration for Unfolded Circle Remote 3

This covers everything from zero to controlling the receiver (all three
zones) from your Remote 3. There are three ways to run the integration:

- **Option A — External Python process (recommended to start):** the driver
  runs on an always-on machine on your network (Mac, Linux box, NAS,
  Raspberry Pi). Easiest to set up and debug.
- **Option B — Docker container:** same as Option A, but packaged as a
  container for easier deployment/updates on a NAS or server.
- **Option C — On the remote itself:** build a self-contained aarch64 binary
  and upload it to the Remote 3 as a custom integration. No extra hardware
  needed to run it, but building the binary requires Docker/Podman or
  GitHub Actions — see [BUILDING.md](BUILDING.md).

---

## 1. Prepare the receiver (one time)

1. Give the receiver a **fixed IP address** — a DHCP reservation on your
   router is easiest. This integration has no auto-discovery and the
   config stores the IP.
2. Confirm **External Control** is ON (receiver's network settings).
3. Set **Network Standby ON** so the receiver accepts power-on commands
   while in standby (web UI → Network, or the front-panel network
   settings). If network standby is off, the control port goes dark when
   the receiver is fully off and only IR can wake it.
4. Quick health check from any machine on the LAN (replace with your
   receiver's actual IP throughout this guide):

       nc -z 192.168.1.100 33335 && echo "control port open"

---

## 2. Option A — Run as an external Python process

Requires Python 3.11 or newer (`python3 --version`).

```bash
git clone https://github.com/Skyman64/integration-sonyavr-za.git
cd integration-sonyavr-za
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Smoke test the receiver connection:

```bash
python3 src/test.py 192.168.1.100
```

You should see the three zones with power/volume/input, then live
notifications when you touch the volume knob or switch inputs. Ctrl-C to
exit.

Run the driver:

```bash
mkdir -p config
UC_CONFIG_HOME=./config python3 src/driver.py
```

Notes:

- The driver listens on WebSocket port **9090** by default. Change it with
  the `UC_INTEGRATION_HTTP_PORT` environment variable or a `"port"` field
  in `driver.json` if 9090 is taken.
- `UC_CONFIG_HOME` is where `config.json` (device configuration) is stored.
- Leave this running for permanent use — wrap it in a launchd/systemd
  service, or use Option B (Docker) instead.

### Keep it running

**macOS (launchd):** create `~/Library/LaunchAgents/com.example.sonyavr-za.plist`
(swap in your own reverse-DNS identifier and paths):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.example.sonyavr-za</string>
  <key>ProgramArguments</key><array>
    <string>/path/to/integration-sonyavr-za/.venv/bin/python3</string>
    <string>/path/to/integration-sonyavr-za/src/driver.py</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>UC_CONFIG_HOME</key>
    <string>/path/to/integration-sonyavr-za/config</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.example.sonyavr-za.plist`

**Linux:** use a systemd unit that runs the same command with `WorkingDirectory`
and `Environment=UC_CONFIG_HOME=...` set.

---

## 3. Option B — Docker container

### Quick start

```bash
# Using Docker Compose (recommended)
docker-compose up -d
docker-compose logs -f

# Or using Make
make build
make run
make logs

# Or manually
docker build -t sony-avr-za-integration .
docker run -d \
  --name sony-avr-za-integration \
  --restart unless-stopped \
  -p 8080:8080 \
  -v ./config:/app/config \
  -e PYTHONUNBUFFERED=1 \
  sony-avr-za-integration
```

### Configuration

Environment variables (pass with `-e` or in `docker-compose.yml`):

- `LOG_LEVEL` — Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `PORT` — Integration API port (default: 8080)

Mount `-v ./config:/app/config` to persist device configuration across
container restarts.

### Networking

- **Docker on the same machine as the remote's driver-discovery network:**
  expose `-p 8080:8080`; the remote connects to the host's IP on port 8080.
- **Docker on a separate machine:** point the remote at that machine's IP.
- **`--network host` (Linux only):** simplest if you don't need port
  remapping.

### Troubleshooting

```bash
docker logs sony-avr-za-integration      # check container logs
ping 192.168.1.100                       # verify receiver is reachable
curl http://192.168.1.100/request.cgi    # verify the web endpoint responds
```

If the integration doesn't appear on the remote: confirm the container is
running (`docker ps`), that your firewall allows port 8080, and that the
remote can reach the host machine.

---

## 4. Option C — Install on the Remote 3 itself

The remote runs aarch64 Linux; integrations must be uploaded as a
self-contained binary archive. See [BUILDING.md](BUILDING.md) to build
`uc-intg-sonyavr-za-aarch64.tar.gz`, then:

1. Open the remote's web configurator → **Settings → Integrations →
   Install custom** (enable "custom integrations" in developer options if
   you don't see this).
2. Upload the `.tar.gz` archive.
3. Run the setup flow: enter the receiver's IP, pick the device, set the
   volume step, finish.

Custom integrations survive reboots but may need re-upload after some
firmware updates.

---

## 5. Add entities on the Remote 3 (all options)

1. **Settings → Integrations → + Add / Discover.** The driver announces
   itself via mDNS as "Sony ES Receivers (ZA / AV7000ES)"; if it doesn't
   appear, use manual entry and point it at `ws://<driver-machine-ip>:9090`
   (Option A/B) or select it directly (Option C).
2. Run the setup flow: enter the receiver's IP, pick the device, set the
   volume step, finish.
3. Add the entities to your profile: **three media players** (Main, Zone 2,
   Zone 3) plus the sensors and input/sound-mode selects.

## 6. Verify end to end

1. Main zone: power toggle, volume up/down (watch the receiver display),
   mute, input select, sound field select.
2. Zone 2 / Zone 3: power on first, then volume/mute/input. Commands sent
   to a powered-off zone are rejected by the receiver by design — the
   entity will show the failure until you turn the zone on.
3. Change volume with the physical remote or front-panel knob: the entity
   should update within a second (push notifications).

## 7. Troubleshooting

- **Setup fails at IP entry** — check `http://<receiver-ip>` loads in a
  browser and `nc -z <receiver-ip> 33335` succeeds from the driver machine.
- **Everything unavailable after a receiver power cycle** — the driver
  auto-reconnects with backoff (2 s → 30 s); wait ~30 s or restart the
  driver.
- **AUX selects the wrong input** — run `python3 src/test.py <receiver-ip>`,
  select AUX on the front panel, note the `input=0x??` code pushed, and fix
  the `AUX` entry in `src/const.py` (`0x0A` vs `0x00`).
- **Verbose logs** — set `UC_LOG_LEVEL=DEBUG`; protocol frames are logged
  at DEBUG in `za_protocol.py`.
