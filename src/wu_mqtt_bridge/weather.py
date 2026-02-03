"""Weather Underground API client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

WU_BASE_URL = "https://api.weather.com/v3/wx"
FORECAST_PATH = "/forecast/daily/5day"
HOURLY_PATH = "/forecast/hourly/2day"
CURRENT_PATH = "/observations/current"

# Timeout for API requests (seconds).
REQUEST_TIMEOUT = 30.0


@dataclass(frozen=True)
class CurrentConditions:
    """Current weather observation."""

    temperature: float | None
    feels_like: float | None
    humidity: int | None
    wind_speed: float | None
    wind_direction_cardinal: str | None
    uv_index: int | None
    condition: str | None
    icon_code: int | None
    pressure: float | None
    visibility: float | None


@dataclass(frozen=True)
class DayForecast:
    """Single day forecast."""

    day_of_week: str
    date: str  # ISO date from validTimeLocal
    temp_max: float | None
    temp_min: float | None
    narrative: str
    precip_chance_day: int | None
    precip_chance_night: int | None
    condition_day: str | None
    condition_night: str | None
    icon_code_day: int | None
    icon_code_night: int | None
    humidity_day: int | None
    humidity_night: int | None
    wind_speed_day: float | None
    wind_speed_night: float | None
    wind_direction_day: str | None
    wind_direction_night: str | None
    qpf: float | None  # quantitative precipitation forecast (mm)
    uv_index_day: int | None


@dataclass(frozen=True)
class HourForecast:
    """Single hour forecast."""

    time_local: str  # ISO datetime from validTimeLocal
    hour: int  # 0-23
    temperature: float | None
    condition: str | None
    icon_code: int | None
    qpf: float | None  # precipitation in mm


@dataclass(frozen=True)
class WeatherData:
    """Complete weather data bundle."""

    current: CurrentConditions | None
    forecast: list[DayForecast]
    hourly_today: list[HourForecast]
    raw_current: dict[str, Any] | None
    raw_forecast: dict[str, Any]


class WeatherClient:
    """Fetches weather data from the Weather Underground / weather.com API."""

    def __init__(
        self,
        geocode: str,
        api_key: str,
        language: str = "fr-FR",
        units: str = "m",
    ) -> None:
        self._geocode = geocode
        self._api_key = api_key
        self._language = language
        self._units = units
        self._http = httpx.Client(timeout=REQUEST_TIMEOUT)

    def close(self) -> None:
        self._http.close()

    def _params(self) -> dict[str, str]:
        return {
            "geocode": self._geocode,
            "format": "json",
            "units": self._units,
            "language": self._language,
            "apiKey": self._api_key,
        }

    def fetch_current(self) -> CurrentConditions | None:
        """Fetch current conditions. Returns None on failure."""
        url = f"{WU_BASE_URL}{CURRENT_PATH}"
        try:
            resp = self._http.get(url, params=self._params())
            resp.raise_for_status()
            data = resp.json()
            logger.debug("current_conditions_raw", data=json.dumps(data)[:500])
            return CurrentConditions(
                temperature=data.get("temperature"),
                feels_like=data.get("temperatureFeelsLike"),
                humidity=data.get("relativeHumidity"),
                wind_speed=data.get("windSpeed"),
                wind_direction_cardinal=data.get("windDirectionCardinal"),
                uv_index=data.get("uvIndex"),
                condition=data.get("wxPhraseLong"),
                icon_code=data.get("iconCode"),
                pressure=data.get("pressureAltimeter"),
                visibility=data.get("visibility"),
            )
        except httpx.HTTPStatusError as e:
            logger.warning("current_conditions_fetch_failed", status=e.response.status_code)
            return None
        except Exception as e:
            logger.warning("current_conditions_fetch_error", error=str(e))
            return None

    def fetch_forecast(self) -> tuple[list[DayForecast], dict[str, Any]]:
        """Fetch 5-day forecast. Raises on failure."""
        url = f"{WU_BASE_URL}{FORECAST_PATH}"
        resp = self._http.get(url, params=self._params())
        resp.raise_for_status()
        data = resp.json()
        logger.debug("forecast_raw", data=json.dumps(data)[:500])
        return _parse_forecast(data), data

    def fetch_hourly(self) -> list[HourForecast]:
        """Fetch hourly forecast and return today's hours."""
        url = f"{WU_BASE_URL}{HOURLY_PATH}"
        try:
            resp = self._http.get(url, params=self._params())
            resp.raise_for_status()
            data = resp.json()
            logger.debug("hourly_raw", data=json.dumps(data)[:500])
            return _parse_hourly(data)
        except httpx.HTTPStatusError as e:
            logger.warning("hourly_fetch_failed", status=e.response.status_code)
            return []
        except Exception as e:
            logger.warning("hourly_fetch_error", error=str(e))
            return []

    def fetch_all(self) -> WeatherData:
        """Fetch current conditions + forecast + hourly."""
        current = self.fetch_current()
        forecast, raw_forecast = self.fetch_forecast()
        hourly_today = self.fetch_hourly()

        raw_current: dict[str, Any] | None = None
        if current is not None:
            # Store raw current as dict for MQTT payload
            raw_current = {
                "temperature": current.temperature,
                "feels_like": current.feels_like,
                "humidity": current.humidity,
                "wind_speed": current.wind_speed,
                "wind_direction": current.wind_direction_cardinal,
                "uv_index": current.uv_index,
                "condition": current.condition,
                "icon_code": current.icon_code,
                "pressure": current.pressure,
                "visibility": current.visibility,
            }

        return WeatherData(
            current=current,
            forecast=forecast,
            hourly_today=hourly_today,
            raw_current=raw_current,
            raw_forecast=raw_forecast,
        )


def _parse_forecast(data: dict[str, Any]) -> list[DayForecast]:
    """Parse WU forecast response into structured data."""
    days_of_week = data.get("dayOfWeek", [])
    valid_times = data.get("validTimeLocal", [])
    temp_max = data.get("calendarDayTemperatureMax", [])
    temp_min = data.get("calendarDayTemperatureMin", [])
    narratives = data.get("narrative", [])
    qpf = data.get("qpf", [])

    daypart = data.get("daypart", [{}])[0] if data.get("daypart") else {}
    dp_precip = daypart.get("precipChance", [])
    dp_condition = daypart.get("wxPhraseLong", [])
    dp_icon = daypart.get("iconCode", [])
    dp_humidity = daypart.get("relativeHumidity", [])
    dp_wind_speed = daypart.get("windSpeed", [])
    dp_wind_dir = daypart.get("windDirectionCardinal", [])
    dp_uv = daypart.get("uvIndex", [])

    forecasts: list[DayForecast] = []
    for i in range(len(days_of_week)):
        day_idx = i * 2  # daypart index for day
        night_idx = i * 2 + 1  # daypart index for night

        date_str = valid_times[i][:10] if i < len(valid_times) else ""

        forecasts.append(
            DayForecast(
                day_of_week=days_of_week[i],
                date=date_str,
                temp_max=temp_max[i] if i < len(temp_max) else None,
                temp_min=temp_min[i] if i < len(temp_min) else None,
                narrative=narratives[i] if i < len(narratives) else "",
                precip_chance_day=_safe_idx(dp_precip, day_idx),
                precip_chance_night=_safe_idx(dp_precip, night_idx),
                condition_day=_safe_idx(dp_condition, day_idx),
                condition_night=_safe_idx(dp_condition, night_idx),
                icon_code_day=_safe_idx(dp_icon, day_idx),
                icon_code_night=_safe_idx(dp_icon, night_idx),
                humidity_day=_safe_idx(dp_humidity, day_idx),
                humidity_night=_safe_idx(dp_humidity, night_idx),
                wind_speed_day=_safe_idx(dp_wind_speed, day_idx),
                wind_speed_night=_safe_idx(dp_wind_speed, night_idx),
                wind_direction_day=_safe_idx(dp_wind_dir, day_idx),
                wind_direction_night=_safe_idx(dp_wind_dir, night_idx),
                qpf=qpf[i] if i < len(qpf) else None,
                uv_index_day=_safe_idx(dp_uv, day_idx),
            )
        )

    return forecasts


def _parse_hourly(data: dict[str, Any]) -> list[HourForecast]:
    """Parse WU hourly response, returning only today's hours."""
    valid_times = data.get("validTimeLocal", [])
    temperatures = data.get("temperature", [])
    conditions = data.get("wxPhraseLong", [])
    icon_codes = data.get("iconCode", [])
    qpf_values = data.get("qpf", [])

    if not valid_times:
        return []

    # Determine today's date from the first entry's local time
    today = valid_times[0][:10]

    hours: list[HourForecast] = []
    for i, time_str in enumerate(valid_times):
        if time_str[:10] != today:
            continue
        # Extract hour from ISO datetime e.g. "2026-02-03T22:00:00+0100"
        hour = int(time_str[11:13])
        hours.append(
            HourForecast(
                time_local=time_str,
                hour=hour,
                temperature=_safe_idx(temperatures, i),
                condition=_safe_idx(conditions, i),
                icon_code=_safe_idx(icon_codes, i),
                qpf=_safe_idx(qpf_values, i),
            )
        )

    return hours


def _safe_idx(lst: list[Any], idx: int) -> Any:
    """Safe list access, returns None if out of bounds."""
    return lst[idx] if idx < len(lst) else None
