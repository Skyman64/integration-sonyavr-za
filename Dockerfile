FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the integration source
COPY src/ ./src/
COPY driver.json .
COPY *.py ./

# Create config directory
RUN mkdir -p /app/config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import asyncio; from src.za_protocol import SonyZaConnection; print('OK')" || exit 1

# Set environment
ENV PYTHONUNBUFFERED=1
ENV UCR_DRIVER_PATH=/app

# Run the integration
CMD ["python3", "src/driver.py"]
