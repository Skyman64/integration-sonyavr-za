# Build & Deploy Integration to Unfolded Circle Remote 3

Build a self-contained binary and upload directly to your Remote 3.

## Prerequisites

- **Docker** or **Podman** installed on your Mac
  - Docker: https://www.docker.com/products/docker-desktop
  - Podman: https://podman.io/docs/installation (recommended if you prefer open-source)
- Unfolded Circle Remote 3 on your network
- Recent firmware with "custom integrations" enabled (Settings > Developer Options)

## Step 1: Build the Binary

### Using Docker (or substitute `podman` if you prefer)

```bash
cd ~/Documents/UCR3\ Integrations/integration-sonyavr-za

docker run --rm --name builder \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 \
    bash -c "python -m pip install -r requirements.txt && \
             pyinstaller --clean --onefile --name driver src/driver.py"
```

Or with **Podman** (if that's what you have installed):

```bash
podman run --rm --name builder \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 \
    bash -c "python -m pip install -r requirements.txt && \
             pyinstaller --clean --onefile --name driver src/driver.py"
```

This builds an aarch64 binary at `dist/driver` (no emulation needed on Apple Silicon).

Expected output:
```
...
Building EXE from EXE-00.toc completed successfully.
```

## Step 2: Package for Remote

```bash
# Create artifact structure
mkdir -p artifacts/bin

# Copy files
cp dist/driver artifacts/bin/driver
cp driver.json artifacts/
cp sony.png artifacts/

# Create archive
cd artifacts && tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz * && cd ..

# Verify
ls -lh uc-intg-sonyavr-za-aarch64.tar.gz
```

You should have: `uc-intg-sonyavr-za-aarch64.tar.gz` (~50-100 MB)

## Step 3: Upload to Remote

### Via Web UI (Easiest)

1. Open remote's web configurator:
   - Find your remote's IP on your network
   - Go to `http://<remote-ip>:8080`

2. Navigate:
   - Settings → Integrations → Install custom

3. Upload:
   - Select `uc-intg-sonyavr-za-aarch64.tar.gz`
   - Wait for extraction (may take 1-2 minutes)

4. Setup:
   - Integration setup flow appears
   - Enter receiver IP: `10.64.67.230`
   - Complete setup

5. Done:
   - Entities appear on remote
   - Zone 2 sync commands available on Zone 2 media player

### Via SSH (Alternative)

If you prefer direct upload:

```bash
# Find remote IP
remote_ip="192.168.x.x"  # Replace with your remote IP

# Upload archive
scp uc-intg-sonyavr-za-aarch64.tar.gz uc-integrations@$remote_ip:/home/uc-integrations/

# SSH into remote (if needed for troubleshooting)
ssh uc-integrations@$remote_ip
```

---

## One-Line Build & Package Script

### Using build_remote.sh (Easiest - Auto-detects Docker/Podman)

```bash
cd ~/Documents/UCR3\ Integrations/integration-sonyavr-za
chmod +x build_remote.sh
./build_remote.sh
```

### Manual One-Liner (Docker)

```bash
cd ~/Documents/UCR3\ Integrations/integration-sonyavr-za && \
docker run --rm --name builder --user=$(id -u):$(id -g) -v "$PWD":/workspace docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 bash -c "python -m pip install -r requirements.txt && pyinstaller --clean --onefile --name driver src/driver.py" && \
mkdir -p artifacts/bin && \
cp dist/driver artifacts/bin/driver && \
cp driver.json artifacts/ && \
cp sony.png artifacts/ && \
cd artifacts && tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz * && cd .. && \
echo "✓ Archive ready: $(ls -lh uc-intg-sonyavr-za-aarch64.tar.gz | awk '{print $9, $5}')"
```

### Manual One-Liner (Podman)

```bash
cd ~/Documents/UCR3\ Integrations/integration-sonyavr-za && \
podman run --rm --name builder --user=$(id -u):$(id -g) -v "$PWD":/workspace docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 bash -c "python -m pip install -r requirements.txt && pyinstaller --clean --onefile --name driver src/driver.py" && \
mkdir -p artifacts/bin && \
cp dist/driver artifacts/bin/driver && \
cp driver.json artifacts/ && \
cp sony.png artifacts/ && \
cd artifacts && tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz * && cd .. && \
echo "✓ Archive ready: $(ls -lh uc-intg-sonyavr-za-aarch64.tar.gz | awk '{print $9, $5}')"
```

## Troubleshooting

### Build fails with permission errors

Make sure Docker has permission to your workspace:

```bash
chmod -R 755 ~/Documents/UCR3\ Integrations/integration-sonyavr-za
```

### Binary is too large

PyInstaller bundles the entire Python runtime. Expected size: 50-100 MB. This is normal.

### Remote won't upload archive

1. Check firmware version (Settings → About)
2. Enable developer options (Settings → Developer Options)
3. Enable "custom integrations"
4. Try uploading again

### Integration doesn't appear after upload

1. Check remote logs:
   ```bash
   remote_ip="192.168.x.x"
   ssh uc-integrations@$remote_ip
   tail -f /home/uc-integrations/.config/unfolded-circle/driver.log
   ```

2. Restart integration:
   - Remote: Settings → Integrations → Sony AVR ZA → Options → Restart

3. If still broken, re-upload archive

### Zone 2 sync commands not showing

1. Make sure you're on the **Zone 2** media player (not main zone)
2. Rebuild with latest code: `pyinstaller --clean ...`
3. Re-upload archive

---

## What Gets Uploaded

```
uc-intg-sonyavr-za-aarch64.tar.gz
├── bin/
│   └── driver          (compiled binary, ~60 MB)
├── driver.json         (integration metadata)
└── sony.png            (icon)
```

The remote automatically extracts this and runs the `driver` binary.

---

## Persistence

- Custom integrations survive reboot ✓
- Zone sync settings persist ✓ (stored in remote's config)
- Updates via web UI ✓ (just upload newer .tar.gz)

---

## Updates

To rebuild and deploy an update:

```bash
# 1. Make code changes in src/
# 2. Rebuild binary
docker run --rm --name builder --user=$(id -u):$(id -g) -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 \
    bash -c "python -m pip install -r requirements.txt && \
             pyinstaller --clean --onefile --name driver src/driver.py"

# 3. Repackage
mkdir -p artifacts/bin && cp dist/driver artifacts/bin/ && \
cp driver.json sony.png artifacts/ && \
cd artifacts && tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz * && cd ..

# 4. Upload new .tar.gz to remote
```

Or use the one-line script above.

---

## Uninstall

On the remote:
- Settings → Integrations → Sony AVR ZA → Options → Uninstall
- Files are removed from the remote

---

## Next Steps

1. Run the build script above
2. Open `http://<remote-ip>:8080` in browser
3. Upload `uc-intg-sonyavr-za-aarch64.tar.gz`
4. Complete setup flow (enter receiver IP)
5. Test Zone 2 sync commands on remote

You're done! The integration now runs directly on your Remote 3.

