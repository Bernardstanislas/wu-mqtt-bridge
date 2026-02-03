# --- Build stage ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# --- Runtime stage ---
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/Bernardstanislas/wu-mqtt-bridge"
LABEL org.opencontainers.image.description="Weather Underground → MQTT bridge for Home Assistant"

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /app app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Healthcheck: verify the binary exists and responds
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD wu-mqtt-bridge --version || exit 1

USER app

ENTRYPOINT ["wu-mqtt-bridge"]
CMD ["run"]
