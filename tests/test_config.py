"""Tests for configuration loading."""

from __future__ import annotations

import pytest

from wu_mqtt_bridge.config import Settings


class TestSettings:
    """Test settings validation and defaults."""

    def test_valid_geocode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "48.86,2.35")
        s = Settings()
        assert s.wu_geocode == "48.86,2.35"

    def test_invalid_geocode_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "not-valid")
        with pytest.raises(Exception, match="latitude,longitude"):
            Settings()

    def test_invalid_geocode_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "999,999")
        with pytest.raises(Exception, match="Latitude must be"):
            Settings()

    def test_geocode_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear any existing env var
        monkeypatch.delenv("WU_GEOCODE", raising=False)
        with pytest.raises((ValueError, Exception)):
            Settings()

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "48.86,2.35")
        s = Settings()
        assert s.wu_language == "fr-FR"
        assert s.wu_units == "m"
        assert s.mqtt_host == "localhost"
        assert s.mqtt_port == 1883
        assert s.mqtt_retain is True
        assert s.mqtt_ha_discovery is True
        assert s.log_level == "INFO"
        assert s.dry_run is False

    def test_custom_mqtt_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "48.86,2.35")
        monkeypatch.setenv("MQTT_HOST", "broker.local")
        monkeypatch.setenv("MQTT_PORT", "8883")
        monkeypatch.setenv("MQTT_USERNAME", "user")
        monkeypatch.setenv("MQTT_PASSWORD", "pass")
        s = Settings()
        assert s.mqtt_host == "broker.local"
        assert s.mqtt_port == 8883
        assert s.mqtt_username == "user"
        assert s.mqtt_password == "pass"

    def test_invalid_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "48.86,2.35")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")
        with pytest.raises(Exception, match="log_level"):
            Settings()

    def test_negative_geocode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WU_GEOCODE", "-33.87,151.21")
        s = Settings()
        assert s.wu_geocode == "-33.87,151.21"
