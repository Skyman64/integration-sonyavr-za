#!/bin/bash
# Sony AVR ZA Integration Deployment Script
#
# Usage: ./deploy.sh [start|stop|restart|logs|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONTAINER_NAME="sony-avr-za-integration"
IMAGE_NAME="sony-avr-za-integration"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    log_info "Docker found: $(docker --version)"
}

check_receiver() {
    local receiver_ip="${1:-192.168.1.100}"
    log_info "Checking receiver at $receiver_ip..."

    if ping -c 1 "$receiver_ip" &> /dev/null; then
        log_info "✓ Receiver is reachable"
        return 0
    else
        log_warn "⚠ Receiver at $receiver_ip is not reachable"
        log_warn "  Make sure your receiver is powered on and has the correct IP"
        return 1
    fi
}

build_image() {
    log_info "Building Docker image..."
    docker build -t "$IMAGE_NAME" .
    log_info "✓ Image built successfully"
}

start_container() {
    log_info "Starting integration container..."

    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_warn "Container already exists, removing old one..."
        docker rm -f "$CONTAINER_NAME" > /dev/null 2>&1
    fi

    docker-compose up -d
    sleep 2

    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "✓ Container started successfully"
        show_status
    else
        log_error "Failed to start container"
        docker logs "$CONTAINER_NAME"
        exit 1
    fi
}

stop_container() {
    log_info "Stopping integration container..."
    docker-compose down
    log_info "✓ Container stopped"
}

restart_container() {
    log_info "Restarting integration container..."
    stop_container
    sleep 1
    start_container
}

show_logs() {
    log_info "Showing integration logs (press Ctrl+C to exit)..."
    docker-compose logs -f "$CONTAINER_NAME"
}

show_status() {
    log_info "Integration status:"
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "  Status: ${GREEN}RUNNING${NC}"
        log_info "  Container: $CONTAINER_NAME"
        local ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NAME")
        log_info "  IP: $ip (internal)"
        log_info "  Port: 8080"
    else
        log_error "  Status: NOT RUNNING"
    fi
    echo ""
    log_info "Next steps:"
    echo "  1. Add integration to your Unfolded Circle Remote"
    echo "  2. Configure receiver IP: 192.168.1.100"
    echo "  3. View logs: ./deploy.sh logs"
}

usage() {
    cat << EOF
Sony AVR ZA Integration - Deployment Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  start       Build and start the integration
  stop        Stop the running integration
  restart     Restart the integration
  logs        Show integration logs
  status      Show integration status
  clean       Remove container and image
  test        Test connection to receiver

Options:
  --receiver-ip IP    Receiver IP address (default: 192.168.1.100)
  --help              Show this help message

Examples:
  $0 start
  $0 start --receiver-ip 192.168.1.100
  $0 logs
  $0 restart
  $0 clean

EOF
}

main() {
    local command="${1:-start}"

    case "$command" in
        start)
            check_docker
            check_receiver
            build_image
            start_container
            ;;
        stop)
            stop_container
            ;;
        restart)
            check_docker
            restart_container
            ;;
        logs)
            check_docker
            show_logs
            ;;
        status)
            check_docker
            show_status
            ;;
        clean)
            log_info "Cleaning up..."
            docker-compose down
            docker rmi -f "$IMAGE_NAME" 2>/dev/null || true
            log_info "✓ Cleaned up"
            ;;
        test)
            local receiver_ip="${2:-192.168.1.100}"
            check_receiver "$receiver_ip"
            ;;
        --help|-h|help)
            usage
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
