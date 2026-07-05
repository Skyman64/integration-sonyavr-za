#!/bin/bash
# Build and package Sony AVR ZA integration for Unfolded Circle Remote 3
#
# Usage: ./build_remote.sh [clean]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup_old_builds() {
    log_info "Cleaning old builds..."
    rm -rf dist build *.spec artifacts uc-intg-sonyavr-za-aarch64.tar.gz
    log_info "✓ Cleaned"
}

check_requirements() {
    log_info "Checking requirements..."

    # Check for Docker or Podman
    if command -v docker &> /dev/null; then
        CONTAINER_CLI="docker"
        log_info "Using Docker: $(docker --version)"
    elif command -v podman &> /dev/null; then
        CONTAINER_CLI="podman"
        log_info "Using Podman: $(podman --version)"
    else
        log_error "Neither Docker nor Podman is installed"
        log_error "Install one of:"
        log_error "  - Docker: https://www.docker.com/products/docker-desktop"
        log_error "  - Podman: https://podman.io/docs/installation"
        exit 1
    fi

    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt not found"
        exit 1
    fi

    if [ ! -f "src/driver.py" ]; then
        log_error "src/driver.py not found"
        exit 1
    fi

    if [ ! -f "driver.json" ]; then
        log_error "driver.json not found"
        exit 1
    fi

    if [ ! -f "sony.png" ]; then
        log_error "sony.png not found"
        exit 1
    fi

    log_info "✓ All requirements met"
}

build_binary() {
    log_info "Building aarch64 binary with PyInstaller..."
    log_info "Using: $CONTAINER_CLI"
    log_info "This may take 2-3 minutes..."

    $CONTAINER_CLI run --rm --name builder \
        --user=$(id -u):$(id -g) \
        -v "$PWD":/workspace \
        docker.io/unfoldedcircle/r2-pyinstaller:3.11.6 \
        bash -c "python -m pip install -r requirements.txt && \
                 pyinstaller --clean --onefile --name driver src/driver.py"

    if [ -f "dist/driver" ]; then
        log_info "✓ Binary built successfully"
    else
        log_error "Binary not found at dist/driver"
        exit 1
    fi
}

package_archive() {
    log_info "Packaging archive..."

    mkdir -p artifacts/bin
    cp dist/driver artifacts/bin/driver
    cp driver.json artifacts/
    cp sony.png artifacts/

    cd artifacts
    tar czf ../uc-intg-sonyavr-za-aarch64.tar.gz *
    cd ..

    if [ -f "uc-intg-sonyavr-za-aarch64.tar.gz" ]; then
        local size=$(ls -lh uc-intg-sonyavr-za-aarch64.tar.gz | awk '{print $5}')
        log_info "✓ Archive created: uc-intg-sonyavr-za-aarch64.tar.gz ($size)"
    else
        log_error "Archive creation failed"
        exit 1
    fi
}

show_next_steps() {
    cat << EOF

${GREEN}✓ Build complete!${NC}

Archive ready: ${GREEN}uc-intg-sonyavr-za-aarch64.tar.gz${NC}

Next steps:

1. Open your remote's web configurator:
   http://<remote-ip>:8080

2. Navigate to: Settings → Integrations → Install custom

3. Upload the archive:
   ${GREEN}uc-intg-sonyavr-za-aarch64.tar.gz${NC}

4. Complete the setup flow (enter receiver IP: 192.168.1.100)

5. Done! Zone 2 sync commands available on remote

Need help? Read: BUILD_FOR_REMOTE.md

EOF
}

main() {
    log_info "Sony AVR ZA Integration - Remote Build"

    if [ "$1" = "clean" ]; then
        cleanup_old_builds
        return
    fi

    check_requirements
    cleanup_old_builds
    build_binary
    package_archive
    show_next_steps
}

main "$@"
