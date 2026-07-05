# Build Without Docker/Podman Using GitHub Actions

Build the aarch64 binary in the cloud without installing anything on your Mac.

## Setup (One Time)

### 1. Create a GitHub Repository

If you don't have this code in a GitHub repo yet:

```bash
cd ~/Documents/UCR3\ Integrations/integration-sonyavr-za

git init
git add .
git commit -m "Initial Sony AVR ZA integration with Zone 2 sync"
git branch -M main
git remote add origin https://github.com/skyman64/integration-sonyavr-za.git
git push -u origin main
```

### 2. The Workflow File

The `.github/workflows/build-remote.yml` file is already created in your repo. It:
- Builds the binary on GitHub's Linux servers
- Packages it as a `.tar.gz`
- Makes it available for download

## Build the Binary

### Option A: Manual Trigger (Easiest)

1. Go to your GitHub repo
2. Click **Actions** tab
3. Click **Build for Remote 3** (left sidebar)
4. Click **Run workflow** (blue button)
5. Wait ~3 minutes for build to complete
6. Click the completed run
7. Under **Artifacts**, download `sony-avr-remote-binary`

### Option B: Automatic on Commit

Every time you `git push` to main, the binary rebuilds automatically.

```bash
# Make a code change
# Commit and push
git add src/avr.py
git commit -m "Update zone sync logic"
git push origin main

# Binary builds automatically
# Check Actions tab → Build for Remote 3 to monitor
```

### Option C: Tag-Based Release (Professional)

```bash
# Tag a release
git tag v1.0.0
git push origin v1.0.0

# Automatically creates a GitHub Release with the binary attached
```

---

## Download & Deploy

### From GitHub Actions

1. Go to **Actions** → **Build for Remote 3** → Latest run
2. Scroll to **Artifacts**
3. Click **sony-avr-remote-binary** to download
4. Unzip (if needed)
5. Upload `uc-intg-sonyavr-za-aarch64.tar.gz` to your Remote 3

### Direct Download Command

```bash
# Get the artifact URL from the Actions tab and download
curl -o uc-intg-sonyavr-za-aarch64.tar.gz https://github.com/skyman64/integration-sonyavr-za/releases/download/v1.0.0/uc-intg-sonyavr-za-aarch64.tar.gz
```

---

## Upload to Remote 3

Once you have the `.tar.gz` file:

1. Open remote's web UI: `http://<remote-ip>:8080`
2. Settings → Integrations → Install custom
3. Upload `uc-intg-sonyavr-za-aarch64.tar.gz`
4. Complete setup (enter receiver IP: `<your receiver ip>`)

Done!

---

## Benefits

✅ No Docker/Podman on your Mac  
✅ No local setup complexity  
✅ Always builds in consistent environment  
✅ Binary available for download anytime  
✅ Automatic builds on code changes  
✅ GitHub handles all the heavy lifting  

---

## Troubleshooting

### "Build failed" error

Check the workflow logs:
1. Go to **Actions** tab
2. Click failed run
3. Click **Build for Remote 3** job
4. Scroll down to see error details

### "No artifacts found"

The build might still be running. Refresh the page or wait a minute.

### Private Repository

If your repo is private, make sure your GitHub account can access it. The workflow runs under your account's permissions.

---

## Future Updates

Whenever you update the code:

```bash
cd ~/Documents/UCR3\ Integrations/integration-sonyavr-za

# Make your changes
# ... edit files ...

# Commit and push
git add .
git commit -m "Add feature X"
git push origin main

# Binary rebuilds automatically
# Download new version from Actions tab
```

That's it! No Docker, no local build tools needed.

