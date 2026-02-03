# wu-mqtt-bridge 🌤️→📡

Weather Underground → MQTT bridge for Home Assistant.

Fetches weather data from the Weather Underground / weather.com API and publishes it to an MQTT broker with Home Assistant auto-discovery support.

## Features

- **Current conditions** + **5-day forecast**
- **MQTT auto-discovery** — shows up as a weather entity in HA automatically
- **Configurable via env vars** — 12-factor friendly
- **Dry-run mode** — test without a broker
- **Docker-ready** — multi-arch image (amd64/arm64)
- **Structured logging** — JSON-friendly with structlog

## Quick Start

### Docker Compose (recommended)

```bash
# Set your location
export WU_GEOCODE="48.86,2.35"  # Paris

# Start Mosquitto + bridge
docker compose up --build
```

### Standalone

```bash
pip install .

# Required
export WU_GEOCODE="48.86,2.35"
export MQTT_HOST="your-broker"

# Run
wu-mqtt-bridge run

# Or dry-run (no MQTT needed)
wu-mqtt-bridge run --dry-run
```

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `WU_GEOCODE` | *required* | Latitude,longitude (e.g. `48.86,2.35`) |
| `WU_API_KEY` | *(public key)* | Weather.com API key |
| `WU_LANGUAGE` | `fr-FR` | Response language |
| `WU_UNITS` | `m` | Units: `m` (metric), `e` (imperial), `h` (hybrid) |
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USERNAME` | — | MQTT auth username |
| `MQTT_PASSWORD` | — | MQTT auth password |
| `MQTT_TOPIC_PREFIX` | `weather` | Topic prefix |
| `MQTT_RETAIN` | `true` | Retain messages |
| `MQTT_HA_DISCOVERY` | `true` | Publish HA discovery config |
| `LOG_LEVEL` | `INFO` | Log level |
| `DRY_RUN` | `false` | Fetch without publishing |

## MQTT Topics

| Topic | Content |
|---|---|
| `weather/current` | Current conditions JSON |
| `weather/forecast` | 5-day forecast array |
| `weather/ha_state` | HA-compatible weather entity state |
| `homeassistant/weather/wu_mqtt_bridge/config` | HA auto-discovery config |

## Home Assistant

With MQTT auto-discovery enabled (default), a weather entity `weather.wu_mqtt_bridge` appears automatically in HA. Use it in Lovelace with the built-in weather forecast card.

## Development

```bash
# Install dev dependencies
make dev

# Run linter
make lint

# Run tests
make test

# Type check
make typecheck

# Auto-format
make format
```

## Deployment

Run as a cron job or scheduled container — typically once per morning:

```bash
# crontab example
0 7 * * * docker compose -f /path/to/docker-compose.yml run --rm wu-mqtt-bridge
```

Tag a release to build and push the Docker image to GHCR:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## License

MIT
