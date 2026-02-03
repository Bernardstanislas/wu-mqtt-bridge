"""Tests for MQTT publisher."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from wu_mqtt_bridge.mqtt import MQTTPublisher, _wu_to_ha_condition
from wu_mqtt_bridge.weather import CurrentConditions, DayForecast, HourForecast, WeatherData


def _make_weather_data() -> WeatherData:
    """Create test weather data."""
    current = CurrentConditions(
        temperature=12.0,
        feels_like=10.0,
        humidity=75,
        wind_speed=15.0,
        wind_direction_cardinal="SSW",
        uv_index=2,
        condition="Partly Cloudy",
        icon_code=30,
        pressure=1013.0,
        visibility=10.0,
    )
    forecast = [
        DayForecast(
            day_of_week="Monday",
            date="2026-02-03",
            temp_max=14.0,
            temp_min=6.0,
            narrative="Partly cloudy with rain in the afternoon.",
            precip_chance_day=40,
            precip_chance_night=20,
            condition_day="Afternoon showers",
            condition_night="Mostly cloudy",
            icon_code_day=39,
            icon_code_night=27,
            humidity_day=70,
            humidity_night=85,
            wind_speed_day=20.0,
            wind_speed_night=10.0,
            wind_direction_day="SSW",
            wind_direction_night="S",
            qpf=1.5,
            uv_index_day=2,
        ),
    ]
    hourly = [
        HourForecast(
            time_local="2026-02-03T14:00:00+0100",
            hour=14,
            temperature=13.0,
            condition="Partly Cloudy",
            icon_code=30,
            qpf=0.0,
        ),
    ]
    return WeatherData(
        current=current,
        forecast=forecast,
        hourly_today=hourly,
        raw_current={
            "temperature": 12.0,
            "feels_like": 10.0,
            "humidity": 75,
            "wind_speed": 15.0,
            "wind_direction": "SSW",
            "uv_index": 2,
            "condition": "Partly Cloudy",
            "icon_code": 30,
            "pressure": 1013.0,
            "visibility": 10.0,
        },
        raw_forecast={},
    )


class TestMQTTPublisher:
    """Test MQTT publishing logic (broker mocked)."""

    @patch("wu_mqtt_bridge.mqtt.mqtt_client.Client")
    def test_publish_weather_topics(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_client.publish.return_value = mock_publish_result
        mock_client_cls.return_value = mock_client

        publisher = MQTTPublisher(host="localhost")
        publisher.connect()
        publisher.publish_weather(_make_weather_data())
        publisher.disconnect()

        topics_published = [call.args[0] for call in mock_client.publish.call_args_list]
        # Sensor discovery topics
        assert any("homeassistant/sensor/wu_mqtt_bridge/" in t for t in topics_published)
        # Data topics
        assert "weather/current" in topics_published
        assert "weather/forecast" in topics_published
        assert "weather/ha_state" in topics_published
        # Hourly topics
        assert "weather/hourly/14/temperature" in topics_published
        assert "weather/hourly/14/condition" in topics_published
        assert "weather/hourly/14/precipitation" in topics_published

    @patch("wu_mqtt_bridge.mqtt.mqtt_client.Client")
    def test_publish_without_current(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_client.publish.return_value = mock_publish_result
        mock_client_cls.return_value = mock_client

        data = WeatherData(
            current=None,
            forecast=[],
            hourly_today=[],
            raw_current=None,
            raw_forecast={},
        )

        publisher = MQTTPublisher(host="localhost")
        publisher.connect()
        publisher.publish_weather(data)
        publisher.disconnect()

        topics_published = [call.args[0] for call in mock_client.publish.call_args_list]
        assert "weather/current" not in topics_published
        assert "weather/forecast" in topics_published

    @patch("wu_mqtt_bridge.mqtt.mqtt_client.Client")
    def test_ha_discovery_disabled(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_client.publish.return_value = mock_publish_result
        mock_client_cls.return_value = mock_client

        publisher = MQTTPublisher(host="localhost", ha_discovery=False)
        publisher.connect()
        publisher.publish_weather(_make_weather_data())

        topics_published = [call.args[0] for call in mock_client.publish.call_args_list]
        assert not any("homeassistant/" in t for t in topics_published)

    @patch("wu_mqtt_bridge.mqtt.mqtt_client.Client")
    def test_ha_state_structure(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_publish_result = MagicMock()
        mock_client.publish.return_value = mock_publish_result
        mock_client_cls.return_value = mock_client

        publisher = MQTTPublisher(host="localhost")
        publisher.connect()
        publisher.publish_weather(_make_weather_data())

        # Find the ha_state publish call
        for call in mock_client.publish.call_args_list:
            if call.args[0] == "weather/ha_state":
                payload = json.loads(call.args[1])
                assert "temperature" in payload
                assert "forecast" in payload
                assert len(payload["forecast"]) == 1
                assert payload["forecast"][0]["temperature"] == 14.0
                assert payload["forecast"][0]["templow"] == 6.0
                break
        else:
            raise AssertionError("ha_state not published")


class TestConditionMapping:
    """Test WU icon code to HA condition mapping."""

    def test_sunny(self) -> None:
        assert _wu_to_ha_condition(32) == "sunny"

    def test_rainy(self) -> None:
        assert _wu_to_ha_condition(11) == "rainy"

    def test_unknown_returns_exceptional(self) -> None:
        assert _wu_to_ha_condition(999) == "exceptional"

    def test_none_returns_exceptional(self) -> None:
        assert _wu_to_ha_condition(None) == "exceptional"
