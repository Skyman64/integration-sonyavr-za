# Installation Guide — Sony ES (STR-AV7000ES / ZA) Integration for Unfolded Circle Remote 3

This guide covers everything from zero to controlling the receiver (all three
zones) from your Remote 3. There are two ways to run the integration:

- **Option A — External integration (recommended to start):** the driver runs
  on an always-on machine on your network (Mac, Linux box, NAS, Raspberry Pi,
  Docker host). Easiest to set up and debug.
- **Option B — On the remote itself:** build a self-contained aarch64 binary
  and upload it to the Remote 3 as a custom integration. No extra hardware,
  but requires a one-time Docker build.

---

## 1. Prepare the receiver (one time)

1. Give the receiver a **fixed IP address**. Easiest: a DHCP reservation on
   your router for the receiver's MAC. This integration has no auto-discovery,
   and the config stores the IP. (Current IP: `<your receiver ip>)`.)
2. Confirm **External Control is ON** (Network settings — already enabled on
   your unit).
3. Set **Network Standby ON** so the receiver accepts power-on commands while
   in standby. In the web UI (`http://<your receiver ip>)` → Network) or the front
   panel network settings. If network standby is off, the control port goes
   dark when the receiver is fully off and only IR can wake it.
4. Quick health check from any machine on the LAN:

       nc -z <your receiver ip>) 33335 && echo "control port open"

---

## 2. Option A — Run as an external integration

### 2.1 Install

Requires Python 3.11 or newer (`python3 --version`).

    cd "~/Documents/UCR3 Integrations/integration-sonyavr-za"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### 2.2 Smoke test the receiver connection

    python3 src/test.py <your receiver ip>)

You should see the three zones with power/volume/input and then live
notifications when you touch the volume knob or switch inputs. Ctrl-C to exit.

### 2.3 Run the driver

    UC_CONFIG_HOME=./config python3 src/driver.py

Notes:

- The driver listens on WebSocket port **9090** by default. Change it with the
  environment variable `UC_INTEGRATION_HTTP_PORT` or a `"port"` field in
  `driver.json` if 9090 is taken.
- `UC_CONFIG_HOME` is where the device configuration (`config.json`) is
  stored; create the directory first (`mkdir -p config`).
- Leave this running. For permanent use, wrap it in a service (see 2.5).

### 2.4 Add it on the Remote 3

1. On the remote or in the web configurator (`http://<remote-ip>`), go to
   **Settings → Integrations → + Add / Discover**.
2. The driver announces itself via mDNS; "Sony ES Receivers (ZA / AV7000ES)"
   should appear. If it doesn't, choose manual entry and point it at
   `ws://<driver-machine-ip>:9090`.
3. Run the setup flow: enter the receiver IP `<your receiver ip>)` when asked,
   pick the device, set volume step, finish.
4. Add the entities to your profile: you'll see **three media players**
   (Main, Zone 2, Zone 3) plus the sensors and input/sound-mode selects.
   Add whichever you want to activities/pages.

### 2.5 Keep it running (macOS launchd example)

Create `~/Library/LaunchAgents/com.kenn.sonyavr-za.plist`:

    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
      "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0"><dict>
      <key>Label</key><string>com.kenn.sonyavr-za</string>
      <key>ProgramArguments</key><array>
        <string>/Users/kwalker/Documents/UCR3 Integrations/integration-sonyavr-za/.venv/bin/python3</string>
        <string>/Users/kwalker/Documents/UCR3 Integrations/integration-sonyavr-za/src/driver.py</string>
      </array>
      <key>EnvironmentVariables</key><dict>
        <key>UC_CONFIG_HOME</key>
        <string>/Users/kwalker/Documents/UCR3 Integrations/integration-sonyavr-za/config</string>
      </dict>
      <key>RunAtLoad</key><true/>
      <key>KeepAlive</key><true/>
    </dict></plist>

Then: `launchctl load ~/Library/LaunchAgents/com.kenn.sonyavr-za.plist`

(On Linux use a systemd unit; on Docker, run the repo with
`python:3.11-slim`, `pip install -r requirements.txt`, expose 9090.)

---

## 3. Option B — Install on the Remote 3 itself

The remote runs aarch64 Linux; integrations must be uploaded as a
self-contained binary archive.

### 3.1 Build the binary (needs Docker)

On Apple Silicon (aarch64 — fast, no emulation):

    cd "~/Documents/UCR3 Integrations/integration-sonyavr-za"
    docker run --rm --name builder \
        --user=$(id -u):$(id -g) \
        -v "$PWD":/workspace \
        docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 \
        bash -c "python -m pip install -r requirements.txt && \
                 pyinstaller --clean --onefile --name driver src/driver.py"

The binary lands in `dist/driver`.

### 3.2 Package it

    mkdir -p artifacts/bin
    cp dist/driver artifacts/bin/driver
    cp driver.json sony.png artifacts/
    cd artifacts && tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz * && cd ..

(`driver.json` must be at the archive root; the binary in `bin/`.)

### 3.3 Upload to the remote

1. Web configurator → **Settings → Integrations → Install custom** (requires
   recent firmware; enable "custom integrations" in developer options if not
   visible).
2. Upload `uc-intg-sonyavr-za-aarch64.tar.gz`.
3. Run the setup flow (enter <your receiver ip>) and add the entities.

Note: custom integrations survive reboots but may need re-upload after some
firmware updates.

---

## 4. Verify end to end

1. Main zone: power toggle, volume up/down (watch the receiver display),
   mute, input select, sound field select.
2. Zone 2 / Zone 3: power on first, then volume/mute/input. Commands sent to
   a powered-off zone are rejected by the receiver by design (the entity will
   show the failure) — turn the zone on first.
3. Change volume with the physical knob: the remote's entity should update
   within a second (push notifications).

## 5. Troubleshooting

- **Setup fails at IP entry** — check `http://<your receiver ip>)` loads in a
  browser and `nc -z <your receiver ip>) 33335` succeeds from the driver machine.
- **Everything unavailable after receiver power cycle** — the driver
  auto-reconnects with backoff (2 s → 30 s); wait ~30 s or restart the driver.
- **AUX selects the wrong input** — run `python3 src/test.py`, select AUX on
  the front panel, note the `input=0x??` code pushed, and fix the `AUX` entry
  in `src/const.py` (`0x0A` vs `0x00`).
- **Verbose logs** — `UC_LOG_LEVEL=DEBUG` (or edit logging setup in
  `driver.py`); protocol frames are logged at DEBUG in `za_protocol.py`.
