# Building the Remote 3 Binary

The Remote 3 runs aarch64 Linux and only accepts custom integrations as a
self-contained binary archive. Two ways to build it — pick whichever fits
your setup.

## Option 1: GitHub Actions (no local Docker/Podman needed)

The workflow at `.github/workflows/build.yml` already builds the binary on
every push to `main` and on version tags, using GitHub's Linux runners.

1. Fork or push this repo to your own GitHub account.
2. Go to **Actions → Build & Release → Run workflow** (or just push a
   commit — it builds automatically).
3. Wait a few minutes for the build to finish.
4. Open the completed run and download the artifact
   (`uc-intg-sonyavr-<version>-aarch64.tar.gz`) from the **Artifacts**
   section, or grab it from the pre-release/release the workflow creates.
5. Upload the `.tar.gz` to your remote (see [INSTALL.md](INSTALL.md#4-option-c--install-on-the-remote-3-itself)).

Tagging a commit `v1.2.3` and pushing the tag creates a proper GitHub
Release with the binary attached instead of a development pre-release.

## Option 2: Build locally with Docker or Podman

Uses the `unfoldedcircle/r2-pyinstaller` image to cross-build for aarch64
(no emulation needed if you're on Apple Silicon).

```bash
cd integration-sonyavr-za

docker run --rm --name builder \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 \
    bash -c "python -m pip install -r requirements.txt && \
             pyinstaller --clean --onefile --name driver src/driver.py"
```

(Substitute `podman` for `docker` if that's what you have installed —
same arguments work.)

This produces `dist/driver`. Package it:

```bash
mkdir -p artifacts/bin
cp dist/driver artifacts/bin/driver
cp driver.json artifacts/
cp sony.png artifacts/
cd artifacts && tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz * && cd ..
```

Or run the one-shot helper script that does all of the above:

```bash
chmod +x build_remote.sh
./build_remote.sh
```

Upload the resulting `uc-intg-sonyavr-za-aarch64.tar.gz` to the remote as
described in [INSTALL.md](INSTALL.md#4-option-c--install-on-the-remote-3-itself).

### Troubleshooting

- **Permission errors** — `chmod -R 755` the repo directory before
  mounting it into the container.
- **Binary is 50-100 MB** — normal; PyInstaller bundles the whole Python
  runtime.
- **Remote won't accept the upload** — check firmware version and enable
  "custom integrations" under developer options.
- **Zone 2 sync commands missing** — make sure you rebuilt after pulling
  the latest source; re-upload the archive.

## What gets uploaded

```
uc-intg-sonyavr-za-aarch64.tar.gz
├── bin/
│   └── driver          (compiled binary)
├── driver.json          (integration metadata)
└── sony.png             (icon)
```

The remote extracts this automatically and runs the `driver` binary.
Custom integrations and their config persist across reboots; re-upload the
archive to update.
