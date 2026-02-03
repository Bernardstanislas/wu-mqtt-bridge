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
            self._publish_ha_sensor_discovery(data)

        # Publish current conditions as individual sensor values
        if data.current is not None:
            sensors = {
                "temperature": data.current.temperature,
                "feels_like": data.current.feels_like,
                "humidity": data.current.humidity,
                "wind_speed": data.current.wind_speed,
                "wind_direction": data.current.wind_direction_cardinal,
                "pressure": data.current.pressure,
                "visibility": data.current.visibility,
                "uv_index": data.current.uv_index,
                "condition": _wu_to_ha_condition(data.current.icon_code),
            }
            for key, value in sensors.items():
                if value is not None:
                    self._publish(f"{self._topic_prefix}/{key}", value, raw=True)
            logger.info(
                "published_current_conditions",
                temperature=data.current.temperature,
            )

        # Publish raw current + forecast for advanced consumers
        if data.raw_current is not None:
            self._publish(f"{self._topic_prefix}/current", data.raw_current)

        forecast_payload = [asdict(day) for day in data.forecast]
        self._publish(f"{self._topic_prefix}/forecast", forecast_payload)
        logger.info("published_forecast", days=len(data.forecast))

        # Publish hourly forecast for today
        if data.hourly_today:
            for hour in data.hourly_today:
                h = f"{hour.hour:02d}"
                prefix = f"{self._topic_prefix}/hourly/{h}"
                self._publish(f"{prefix}/temperature", hour.temperature, raw=True)
                condition = _wu_to_ha_condition(hour.icon_code)
                self._publish(f"{prefix}/condition", condition, raw=True)
                precip = hour.qpf if hour.qpf is not None else 0.0
                self._publish(f"{prefix}/precipitation", precip, raw=True)
            logger.info("published_hourly", hours=len(data.hourly_today))

        # Publish HA-compatible state (kept for backward compat)
        ha_state = self._build_ha_state(data)
        self._publish(f"{self._topic_prefix}/ha_state", ha_state)
        logger.info("published_ha_state")

    def _publish(self, topic: str, payload: Any, *, raw: bool = False) -> None:
        """Publish payload to topic. If raw=True, publish as plain string."""
        msg = str(payload) if raw else json.dumps(payload, ensure_ascii=False)
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

    def _publish_ha_sensor_discovery(self, data: WeatherData) -> None:
        """Publish HA MQTT auto-discovery config as individual sensors."""
        device = {
            "identifiers": ["wu_mqtt_bridge"],
            "name": "Weather Underground",
            "model": "wu-mqtt-bridge",
            "manufacturer": "wu-mqtt-bridge",
        }

        sensors: list[dict[str, Any]] = [
            {
                "key": "temperature",
                "name": "Température",
                "device_class": "temperature",
                "unit": "°C",
                "icon": None,
            },
            {
                "key": "feels_like",
                "name": "Température ressentie",
                "device_class": "temperature",
                "unit": "°C",
                "icon": None,
            },
            {
                "key": "humidity",
                "name": "Humidité",
                "device_class": "humidity",
                "unit": "%",
                "icon": None,
            },
            {
                "key": "wind_speed",
                "name": "Vent",
                "device_class": "wind_speed",
                "unit": "km/h",
                "icon": None,
            },
            {
                "key": "wind_direction",
                "name": "Direction du vent",
                "device_class": None,
                "unit": None,
                "icon": "mdi:compass-outline",
            },
            {
                "key": "pressure",
                "name": "Pression",
                "device_class": "atmospheric_pressure",
                "unit": "hPa",
                "icon": None,
            },
            {
                "key": "visibility",
                "name": "Visibilité",
                "device_class": "distance",
                "unit": "km",
                "icon": None,
            },
            {
                "key": "uv_index",
                "name": "Indice UV",
                "device_class": None,
                "unit": None,
                "icon": "mdi:sun-wireless-outline",
            },
            {
                "key": "condition",
                "name": "Condition",
                "device_class": None,
                "unit": None,
                "icon": "mdi:weather-partly-cloudy",
            },
        ]

        for sensor in sensors:
            config: dict[str, Any] = {
                "name": sensor["name"],
                "unique_id": f"wu_mqtt_bridge_{sensor['key']}",
                "object_id": f"wu_{sensor['key']}",
                "state_topic": f"{self._topic_prefix}/{sensor['key']}",
                "device": device,
            }
            if sensor["device_class"]:
                config["device_class"] = sensor["device_class"]
            if sensor["unit"]:
                config["unit_of_measurement"] = sensor["unit"]
                config["state_class"] = "measurement"
            if sensor["icon"]:
                config["icon"] = sensor["icon"]

            topic = f"{self._ha_discovery_prefix}/sensor/wu_mqtt_bridge/{sensor['key']}/config"
            msg = json.dumps(config, ensure_ascii=False)
            result = self._client.publish(topic, msg, retain=True, qos=1)
            result.wait_for_publish(timeout=10)

        # Hourly sensors for today
        for hour in data.hourly_today:
            h = f"{hour.hour:02d}"
            hourly_sensors = [
                {
                    "key": f"hourly_{h}_temperature",
                    "name": f"Température {h}h",
                    "topic": f"{self._topic_prefix}/hourly/{h}/temperature",
                    "device_class": "temperature",
                    "unit": "°C",
                    "icon": None,
                },
                {
                    "key": f"hourly_{h}_condition",
                    "name": f"Condition {h}h",
                    "topic": f"{self._topic_prefix}/hourly/{h}/condition",
                    "device_class": None,
                    "unit": None,
                    "icon": "mdi:weather-partly-cloudy",
                },
                {
                    "key": f"hourly_{h}_precipitation",
                    "name": f"Précipitations {h}h",
                    "topic": f"{self._topic_prefix}/hourly/{h}/precipitation",
                    "device_class": "precipitation",
                    "unit": "mm",
                    "icon": None,
                },
            ]
            for s in hourly_sensors:
                hourly_cfg: dict[str, Any] = {
                    "name": s["name"],
                    "unique_id": f"wu_mqtt_bridge_{s['key']}",
                    "object_id": f"wu_{s['key']}",
                    "state_topic": s["topic"],
                    "device": device,
                }
                if s["device_class"]:
                    hourly_cfg["device_class"] = s["device_class"]
                if s["unit"]:
                    hourly_cfg["unit_of_measurement"] = s["unit"]
                    hourly_cfg["state_class"] = "measurement"
                if s["icon"]:
                    hourly_cfg["icon"] = s["icon"]

                topic = f"{self._ha_discovery_prefix}/sensor/wu_mqtt_bridge/{s['key']}/config"
                msg = json.dumps(hourly_cfg, ensure_ascii=False)
                result = self._client.publish(topic, msg, retain=True, qos=1)
                result.wait_for_publish(timeout=10)

        logger.debug("ha_hourly_discovery_published", hours=len(data.hourly_today))

        # Clean up old weather entity discovery
        old_topic = f"{self._ha_discovery_prefix}/weather/wu_mqtt_bridge/config"
        result = self._client.publish(old_topic, "", retain=True, qos=1)
        result.wait_for_publish(timeout=10)

        logger.debug("ha_sensor_discovery_published", count=len(sensors))


def _wu_to_ha_condition(icon_code: int | None) -> str:
    """Map WU icon code to HA weather condition."""
    return _WU_TO_HA_CONDITION.get(icon_code, "exceptional")
