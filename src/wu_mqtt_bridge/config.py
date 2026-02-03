"""Configuration via environment variables."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# Public API key embedded in WU frontend JS — not a secret.
_DEFAULT_WU_API_KEY = "e1f10a1e78da46f5b10a1e78da96f525"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are prefixed with their section for clarity:
      - WU_* for Weather Underground API
      - MQTT_* for MQTT broker
      - LOG_LEVEL for logging
    """

    model_config = {"env_prefix": "", "case_sensitive": False}

    # --- Weather Underground ---
    wu_geocode: str = Field(
        description="Latitude,longitude (e.g. '48.86,2.35' for Paris)",
    )
    wu_api_key: str = Field(default=_DEFAULT_WU_API_KEY, description="WU/TWC API key")
    wu_language: str = Field(default="fr-FR", description="Response language")
    wu_units: str = Field(
        default="m", description="Unit system: 'm' (metric), 'e' (imperial), 'h' (hybrid)"
    )

    # --- MQTT ---
    mqtt_host: str = Field(default="localhost", description="MQTT broker hostname")
    mqtt_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_username: str | None = Field(default=None, description="MQTT username")
    mqtt_password: str | None = Field(default=None, description="MQTT password")
    mqtt_topic_prefix: str = Field(default="weather", description="MQTT topic prefix")
    mqtt_client_id: str = Field(default="wu-mqtt-bridge", description="MQTT client ID")
    mqtt_retain: bool = Field(default=True, description="Retain MQTT messages")
    mqtt_ha_discovery: bool = Field(
        default=True, description="Publish Home Assistant MQTT discovery config"
    )
    mqtt_ha_discovery_prefix: str = Field(
        default="homeassistant", description="HA MQTT discovery prefix"
    )

    # --- General ---
    log_level: str = Field(default="INFO", description="Log level")
    dry_run: bool = Field(default=False, description="Fetch weather but don't publish to MQTT")

    @field_validator("wu_geocode")
    @classmethod
    def validate_geocode(cls, v: str) -> str:
        parts = v.split(",")
        if len(parts) != 2:
            raise ValueError("wu_geocode must be 'latitude,longitude' (e.g. '48.86,2.35')")
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError as err:
            raise ValueError("wu_geocode must contain valid numbers") from err
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Latitude must be -90..90 and longitude -180..180")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v.upper()
