"""Tests for CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import respx
from click.testing import CliRunner

from wu_mqtt_bridge.__main__ import cli


class TestCLI:
    """Test CLI commands."""

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_run_missing_geocode(self) -> None:
        runner = CliRunner(env={"WU_GEOCODE": ""})
        result = runner.invoke(cli, ["run"])
        assert result.exit_code != 0

    @respx.mock
    def test_run_dry_run(self, forecast_response: dict, current_response: dict) -> None:
        respx.get("https://api.weather.com/v3/wx/observations/current").mock(
            return_value=httpx.Response(200, json=current_response)
        )
        respx.get("https://api.weather.com/v3/wx/forecast/daily/5day").mock(
            return_value=httpx.Response(200, json=forecast_response)
        )

        runner = CliRunner(env={"WU_GEOCODE": "48.86,2.35"})
        result = runner.invoke(cli, ["run", "--dry-run"])
        assert result.exit_code == 0
        assert "Forecast" in result.output or "forecast" in result.output.lower()

    @respx.mock
    def test_run_api_failure(self) -> None:
        respx.get("https://api.weather.com/v3/wx/observations/current").mock(
            return_value=httpx.Response(403)
        )
        respx.get("https://api.weather.com/v3/wx/forecast/daily/5day").mock(
            return_value=httpx.Response(500)
        )

        runner = CliRunner(env={"WU_GEOCODE": "48.86,2.35"})
        result = runner.invoke(cli, ["run", "--dry-run"])
        assert result.exit_code != 0

    @respx.mock
    @patch("wu_mqtt_bridge.__main__.MQTTPublisher")
    def test_run_publishes_to_mqtt(
        self,
        mock_publisher_cls: MagicMock,
        forecast_response: dict,
        current_response: dict,
    ) -> None:
        respx.get("https://api.weather.com/v3/wx/observations/current").mock(
            return_value=httpx.Response(200, json=current_response)
        )
        respx.get("https://api.weather.com/v3/wx/forecast/daily/5day").mock(
            return_value=httpx.Response(200, json=forecast_response)
        )

        mock_publisher = MagicMock()
        mock_publisher_cls.return_value = mock_publisher

        runner = CliRunner(env={"WU_GEOCODE": "48.86,2.35", "MQTT_HOST": "localhost"})
        result = runner.invoke(cli, ["run"])
        # Debug: print output if test fails
        if result.exit_code != 0:
            print(f"CLI output: {result.output}")
            if result.exception:
                import traceback

                traceback.print_exception(
                    type(result.exception),
                    result.exception,
                    result.exception.__traceback__,
                )
        assert result.exit_code == 0
        mock_publisher.connect.assert_called_once()
        mock_publisher.publish_weather.assert_called_once()
        mock_publisher.disconnect.assert_called_once()
