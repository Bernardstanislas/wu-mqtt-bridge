"""CLI entry point for wu-mqtt-bridge."""

from __future__ import annotations

import logging
import sys

import click
import structlog

from wu_mqtt_bridge.config import Settings
from wu_mqtt_bridge.mqtt import MQTTPublisher
from wu_mqtt_bridge.weather import WeatherClient, WeatherData

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _setup_logging(level: str) -> None:
    """Configure structlog."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            _LOG_LEVELS.get(level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


@click.group()
@click.version_option(package_name="wu-mqtt-bridge")
def cli() -> None:
    """Weather Underground → MQTT bridge for Home Assistant."""


@cli.command()
@click.option("--dry-run", is_flag=True, help="Fetch weather but don't publish to MQTT.")
def run(dry_run: bool) -> None:
    """Fetch weather data and publish to MQTT."""
    try:
        kwargs = {}
        if dry_run:
            kwargs["dry_run"] = True
        settings = Settings(**kwargs)  # type: ignore[arg-type]
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    _setup_logging(settings.log_level)
    log = structlog.get_logger()

    log.info(
        "starting",
        geocode=settings.wu_geocode,
        language=settings.wu_language,
        dry_run=settings.dry_run,
    )

    # Fetch weather data
    client = WeatherClient(
        geocode=settings.wu_geocode,
        api_key=settings.wu_api_key,
        language=settings.wu_language,
        units=settings.wu_units,
    )
    try:
        weather = client.fetch_all()
    except Exception as e:
        log.error("weather_fetch_failed", error=str(e))
        sys.exit(1)
    finally:
        client.close()

    log.info(
        "weather_fetched",
        has_current=weather.current is not None,
        forecast_days=len(weather.forecast),
    )

    if settings.dry_run:
        _print_summary(weather)
        log.info("dry_run_complete")
        return

    # Publish to MQTT
    publisher = MQTTPublisher(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        client_id=settings.mqtt_client_id,
        topic_prefix=settings.mqtt_topic_prefix,
        retain=settings.mqtt_retain,
        ha_discovery=settings.mqtt_ha_discovery,
        ha_discovery_prefix=settings.mqtt_ha_discovery_prefix,
    )
    try:
        publisher.connect()
        publisher.publish_weather(weather)
    except Exception as e:
        log.error("mqtt_publish_failed", error=str(e))
        sys.exit(1)
    finally:
        publisher.disconnect()

    log.info("done")


def _print_summary(weather: WeatherData) -> None:
    """Print a human-readable weather summary (for dry-run mode)."""
    if weather.current:
        c = weather.current
        click.echo(f"\n🌡️  Current: {c.temperature}°C (feels {c.feels_like}°C) — {c.condition}")
        click.echo(
            f"   💧 {c.humidity}% humidity | 💨 {c.wind_speed} km/h {c.wind_direction_cardinal}"
        )

    click.echo(f"\n📅 Forecast ({len(weather.forecast)} days):")
    for day in weather.forecast:
        click.echo(
            f"   {day.day_of_week} {day.date}: {day.temp_min}°/{day.temp_max}° — {day.narrative}"
        )


if __name__ == "__main__":
    cli()
