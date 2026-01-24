FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for armv7 (needed to compile httptools, uvloop)
# These are removed after pip install to keep the image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (paths relative to repo root)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build dependencies to reduce image size
RUN apt-get purge -y --auto-remove gcc libc-dev

# Copy application code
COPY sipring/ sipring/
COPY pyproject.toml .

# Create data directory
RUN mkdir -p /data

# Environment variables
ENV SIPRING_DATA_DIR=/data
ENV SIPRING_LOG_LEVEL=INFO

# Expose ports
# 8080: HTTP API
# 5062: SIP UDP (needs host networking or proper port mapping)
EXPOSE 8080
EXPOSE 5062/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Run the application
CMD ["uvicorn", "sipring.main:app", "--host", "0.0.0.0", "--port", "8080"]
