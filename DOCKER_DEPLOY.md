# Docker Deployment Guide

Run the Sony AVR ZA integration in a Docker container for easy deployment to your Unfolded Circle Remote.

## Prerequisites

- Docker installed on your system
- Docker Compose (optional, for easier management)
- Sony AVR receiver on your network (<your receiver ip> or configured IP)

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# Build and start the integration
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the integration
docker-compose down
```

### Option 2: Using Make (Easiest)

```bash
# Build the image
make build

# Run the container
make run

# View logs
make logs

# Stop the container
make stop
```

### Option 3: Manual Docker Commands

```bash
# Build the image
docker build -t sony-avr-za-integration .

# Run the container
docker run -d \
  --name sony-avr-za-integration \
  --restart unless-stopped \
  -p 8080:8080 \
  -v ./config:/app/config \
  -e PYTHONUNBUFFERED=1 \
  sony-avr-za-integration

# View logs
docker logs -f sony-avr-za-integration

# Stop the container
docker stop sony-avr-za-integration
docker rm sony-avr-za-integration
```

---

## Configuration

### Environment Variables

Pass environment variables to customize behavior:

```bash
docker run -e LOG_LEVEL=DEBUG -e PORT=9000 ...
```

- `LOG_LEVEL` — Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `PORT` — Integration API port (default: 8080)
- `RECEIVER_IP` — Override receiver IP (default: xx.xx.xx.xx)
- `RECEIVER_PORT` — Command port (default: 33335)

### Persistent Configuration

Mount a config volume to persist settings across restarts:

```bash
-v ./config:/app/config
```

The integration will store zone sync preferences and other settings in this directory.

---

## Adding to Unfolded Circle Remote

Once the Docker container is running:

1. On your Unfolded Circle Remote 2/3:
   - Go to **Settings > Integrations**
   - Select **Add Integration**
   - Choose **Sony AVR ZA**
   - Enter your receiver IP: `<your receiver ip>` (or your actual IP)

2. The integration will discover:
   - Main zone media player
   - Zone 2 and Zone 3 media players
   - Input source selector
   - Sound mode selector
   - Audio settings controls

---

## Testing

### Test the Integration Locally

```bash
# Using Make
make dev-run

# Or manually
python3 src/driver.py
```

### Test Connection to Receiver

```bash
make dev-test  # Connects to receiver and dumps zone state

# Or manually
python3 src/test.py <your receiver ip>)
```

### Run Tests

```bash
make install  # Install test dependencies
make test     # Run pytest
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs sony-avr-za-integration

# Verify receiver is reachable
ping <your receiver ip>)

# Test web API
curl http://<your receiver ip>)/request.cgi
```

### Integration not appearing on remote

- Ensure container is running: `docker ps`
- Check firewall allows port 8080
- Verify remote can reach the machine running the container
- Restart integration: `make stop && make run`

### Zone 2 sync not working

- Ensure Zone 2 is powered on
- Check logs: `make logs | grep "Zone 2"`
- Verify commands are registered: Look for "ZONE2_LINK_VOLUME" in logs

### Connection timeouts

Check if receiver IP is correct:
```bash
make dev-test  # This will show connection attempts
```

---

## Network Configuration

### Docker on Same Machine as Remote

If running Docker on the same machine as Unfolded Circle:

```bash
docker run -p 8080:8080 ...
```

The remote will connect to `localhost:8080`

### Docker on Separate Machine

If running Docker on a different machine:

```bash
docker run -p 8080:8080 ...
```

Configure remote with the Docker host's IP address, not localhost.

### Docker with Host Network (Advanced)

For direct network access (Linux only):

```bash
docker run --network host ...
```

---

## Monitoring

### View Logs

```bash
# Tail logs
make logs

# With timestamps and colors
docker logs -f --timestamps sony-avr-za-integration

# Recent logs only (last 100 lines)
docker logs --tail 100 sony-avr-za-integration
```

### Check Health

```bash
# Container health status
docker ps

# Connection status
curl http://localhost:8080/health 2>/dev/null || echo "Service unavailable"
```

---

## Updating

### Rebuild After Code Changes

```bash
make clean    # Remove old container/image
make build    # Build new image
make run      # Start updated container
```

Or in one command:

```bash
docker-compose up -d --build
```

---

## Resource Usage

The integration is lightweight:

- **CPU:** Minimal (event-driven, not polling)
- **Memory:** ~50-100 MB base + overhead
- **Disk:** ~200 MB for image
- **Network:** Only sends commands when triggered + 20s status polling

---

## Production Deployment

### On a NAS or Server

Deploy to Synology, QNAP, or similar with Docker support:

```bash
# SCP the integration directory
scp -r integration-sonyavr-za user@nas:/docker/

# SSH into NAS and start
ssh user@nas
cd /docker/integration-sonyavr-za
docker-compose up -d
```

### With Reverse Proxy (Optional)

If you want the integration accessible from outside your network:

```yaml
# docker-compose.yml with nginx
version: '3.8'
services:
  sony-avr:
    build: .
    expose:
      - "8080"
    networks:
      - internal

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    networks:
      - internal

networks:
  internal:
```

---

## Support

For issues or questions:

1. Check logs: `make logs | grep -i error`
2. Test connection: `python3 discover_eq_features.py <your receiver ip>)`
3. Review INSTALL.md and README.md for additional context

