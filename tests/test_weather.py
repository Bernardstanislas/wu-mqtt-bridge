"""Tests for weather API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from wu_mqtt_bridge.weather import (
    WU_BASE_URL,
    CurrentConditions,
    DayForecast,
    WeatherClient,
    _parse_forecast,
)


class TestParseforecast:
    """Test forecast response parsing."""

    def test_parse_real_response(self, forecast_response: dict) -> None:
        result = _parse_forecast(forecast_response)
        assert len(result) > 0
        assert all(isinstance(d, DayForecast) for d in result)

    def test_forecast_fields(self, forecast_response: dict) -> None:
        result = _parse_forecast(forecast_response)
        day = result[0]
        assert day.day_of_week != ""
        assert day.date != ""
        assert day.narrative != ""
        assert day.temp_max is not None
        assert day.temp_min is not None

    def test_daypart_data(self, forecast_response: dict) -> None:
        result = _parse_forecast(forecast_response)
        day = result[0]
        # Day/night pairs should be present
        assert day.icon_code_day is not None or day.icon_code_night is not None

    def test_empty_response(self) -> None:
        result = _parse_forecast({"dayOfWeek": []})
        assert result == []

    def test_missing_daypart(self) -> None:
        data = {
            "dayOfWeek": ["Monday"],
            "validTimeLocal": ["2026-02-03T07:00:00+0100"],
            "calendarDayTemperatureMax": [12],
            "calendarDayTemperatureMin": [5],
            "narrative": ["Partly cloudy."],
            "qpf": [0.0],
        }
        result = _parse_forecast(data)
        assert len(result) == 1
        assert result[0].temp_max == 12
        assert result[0].precip_chance_day is None  # No daypart data


class TestWeatherClient:
    """Test WeatherClient with mocked HTTP."""

    @respx.mock
    def test_fetch_forecast(self, forecast_response: dict) -> None:
        respx.get(f"{WU_BASE_URL}/forecast/daily/5day").mock(
            return_value=httpx.Response(200, json=forecast_response)
        )
        client = WeatherClient(geocode="48.86,2.35", api_key="test")
        try:
            forecasts, raw = client.fetch_forecast()
            assert len(forecasts) > 0
            assert raw == forecast_response
        finally:
            client.close()

    @respx.mock
    def test_fetch_current(self, current_response: dict) -> None:
        respx.get(f"{WU_BASE_URL}/observations/current").mock(
            return_value=httpx.Response(200, json=current_response)
        )
        client = WeatherClient(geocode="48.86,2.35", api_key="test")
        try:
            result = client.fetch_current()
            assert isinstance(result, CurrentConditions)
            assert result.temperature is not None
        finally:
            client.close()

    @respx.mock
    def test_fetch_current_failure_returns_none(self) -> None:
        respx.get(f"{WU_BASE_URL}/observations/current").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        client = WeatherClient(geocode="48.86,2.35", api_key="test")
        try:
            result = client.fetch_current()
            assert result is None
        finally:
            client.close()

    @respx.mock
    def test_fetch_forecast_failure_raises(self) -> None:
        respx.get(f"{WU_BASE_URL}/forecast/daily/5day").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        client = WeatherClient(geocode="48.86,2.35", api_key="test")
        try:
            with pytest.raises(httpx.HTTPStatusError):
                client.fetch_forecast()
        finally:
            client.close()

    @respx.mock
    def test_fetch_all(self, forecast_response: dict, current_response: dict) -> None:
        respx.get(f"{WU_BASE_URL}/observations/current").mock(
            return_value=httpx.Response(200, json=current_response)
        )
        respx.get(f"{WU_BASE_URL}/forecast/daily/5day").mock(
            return_value=httpx.Response(200, json=forecast_response)
        )
        client = WeatherClient(geocode="48.86,2.35", api_key="test")
        try:
            data = client.fetch_all()
            assert data.current is not None
            assert len(data.forecast) > 0
            assert data.raw_current is not None
            assert data.raw_forecast == forecast_response
        finally:
            client.close()
