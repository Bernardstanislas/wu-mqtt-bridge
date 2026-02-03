"""MQTT publisher with Home Assistant discovery support."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import paho.mqtt.client as mqtt_client
import structlog

from wu_mqtt_bridge.weather import WeatherData

logger = structlog.get_logger()

# HA icon mappings for WU icon codes
_WU_TO_HA_CONDITION: dict[int | None, str] = {
    0: "tornado",
    1: "hurricane",
    2: "hurricane",
    3: "lightning-rainy",
    4: "lightning-rainy",
    5: "rainy",  # rain/snow mix
    6: "rainy",
    7: "snowy",
    8: "snowy",
    9: "rainy",
    10: "rainy",  # freezing rain
    11: "rainy",
    12: "rainy",
    13: "snowy",
    14: "snowy",
    15: "snowy",
    16: "snowy",
    17: "hail",
    18: "snowy",
    19: "fog",
    20: "fog",
    21: "fog",
    22: "fog",
    23: "windy",
    24: "windy",
    25: "exceptional",  # cold
    26: "cloudy",
    27: "partlycloudy",
    28: "partlycloudy",
    29: "partlycloudy",
    30: "partlycloudy",
    31: "clear-night",
    32: "sunny",
    33: "clear-night",
    34: "sunny",
    35: "rainy",
    36: "exceptional",  # hot
    37: "lightning-rainy",
    38: "lightning-rainy",
    39: "rainy",
    40: "pouring",
    41: "snowy",
    42: "snowy",
    43: "snowy",
    44: "partlycloudy",
    45: "rainy",
    46: "snowy",
    47: "lightning-rainy",
}


class MQTTPublisher:
    """Publishes weather data to MQTT with optional HA discovery."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        client_id: str = "wu-mqtt-bridge",
        topic_prefix: str = "weather",
        retain: bool = True,
        ha_discovery: bool = True,
        ha_discovery_prefix: str = "homeassistant",
    ) -> None:
        self._host = host
        self._port = port
        self._topic_prefix = topic_prefix
        self._retain = retain
        self._ha_discovery = ha_discovery
        self._ha_discovery_prefix = ha_discovery_prefix

        self._client = mqtt_client.Client(
            client_id=client_id,
            callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,  # type: ignore[attr-defined]
        )
        if username:
            self._client.username_pw_set(username, password)

    def connect(self) -> None:
        """Connect to MQTT broker."""
        logger.info("mqtt_connecting", host=self._host, port=self._port)
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("mqtt_disconnected")

    def publish_weather(self, data: WeatherData) -> None:
        """Publish weather data to MQTT topics."""
        if self._ha_discovery:
            self._publish_ha_discovery()

        # Publish current conditions
        if data.raw_current is not None:
            self._publish(
                f"{self._topic_prefix}/current",
                data.raw_current,
            )
            logger.info(
                "published_current_conditions",
                temperature=data.raw_current.get("temperature"),
            )

        # Publish forecast as array
        forecast_payload = [asdict(day) for day in data.forecast]
        self._publish(f"{self._topic_prefix}/forecast", forecast_payload)
        logger.info("published_forecast", days=len(data.forecast))

        # Publish HA-compatible state for weather entity
        ha_state = self._build_ha_state(data)
        self._publish(f"{self._topic_prefix}/ha_state", ha_state)
        logger.info("published_ha_state")

    def _publish(self, topic: str, payload: Any) -> None:
        """Publish JSON payload to topic."""
        msg = json.dumps(payload, ensure_ascii=False)
        result = self._client.publish(topic, msg, retain=self._retain, qos=1)
        result.wait_for_publish(timeout=10)
        logger.debug("mqtt_published", topic=topic, size=len(msg))

    def _build_ha_state(self, data: WeatherData) -> dict[str, Any]:
        """Build Home Assistant weather entity state payload."""
        state: dict[str, Any] = {}

        if data.current is not None:
            state["temperature"] = data.current.temperature
            state["humidity"] = data.current.humidity
            state["wind_speed"] = data.current.wind_speed
            state["wind_bearing"] = data.current.wind_direction_cardinal
            state["pressure"] = data.current.pressure
            state["visibility"] = data.current.visibility
            state["condition"] = _wu_to_ha_condition(data.current.icon_code)

        state["forecast"] = [
            {
                "datetime": day.date,
                "temperature": day.temp_max,
                "templow": day.temp_min,
                "condition": _wu_to_ha_condition(day.icon_code_day),
                "precipitation_probability": day.precip_chance_day,
                "precipitation": day.qpf,
                "wind_speed": day.wind_speed_day,
                "wind_bearing": day.wind_direction_day,
                "humidity": day.humidity_day,
            }
            for day in data.forecast
        ]

        return state

    def _publish_ha_discovery(self) -> None:
        """Publish HA MQTT auto-discovery config for weather entity."""
        config = {
            "name": "Weather Underground",
            "unique_id": "wu_mqtt_bridge_weather",
            "object_id": "wu_mqtt_bridge",
            "state_topic": f"{self._topic_prefix}/ha_state",
            "temperature_unit": "°C",
            "wind_speed_unit": "km/h",
            "pressure_unit": "hPa",
            "visibility_unit": "km",
            "precipitation_unit": "mm",
            "temperature_template": "{{ value_json.temperature }}",
            "humidity_template": "{{ value_json.humidity }}",
            "wind_speed_template": "{{ value_json.wind_speed }}",
            "wind_bearing_template": "{{ value_json.wind_bearing }}",
            "pressure_template": "{{ value_json.pressure }}",
            "visibility_template": "{{ value_json.visibility }}",
            "condition_template": "{{ value_json.condition }}",
            "forecast_daily_topic": f"{self._topic_prefix}/ha_state",
            "forecast_daily_template": "{{ value_json.forecast | tojson }}",
            "device": {
                "identifiers": ["wu_mqtt_bridge"],
                "name": "WU MQTT Bridge",
                "model": "wu-mqtt-bridge",
                "manufacturer": "wu-mqtt-bridge",
            },
        }
        topic = f"{self._ha_discovery_prefix}/weather/wu_mqtt_bridge/config"
        msg = json.dumps(config, ensure_ascii=False)
        result = self._client.publish(topic, msg, retain=True, qos=1)
        result.wait_for_publish(timeout=10)
        logger.debug("ha_discovery_published", topic=topic)


def _wu_to_ha_condition(icon_code: int | None) -> str:
    """Map WU icon code to HA weather condition."""
    return _WU_TO_HA_CONDITION.get(icon_code, "exceptional")
