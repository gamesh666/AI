import pytest

from app.core.config import get_settings
from app.services.device_service import connection_info


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("MQTT_EDGE_USERNAME", "edge")
    monkeypatch.setenv("MQTT_EDGE_PASSWORD", "edge-secret")
    monkeypatch.setenv("MQTT_PUBLIC_HOST", "192.168.0.179")
    monkeypatch.setenv("MEDIAMTX_RTSP_PUBLISH_URL", "rtsp://192.168.0.179:8554")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_connection_info_for_admins_includes_the_mqtt_password(settings):
    info = connection_info("aibox", include_mqtt_password=True)
    assert info.device_id == "aibox"
    assert (info.mqtt_host, info.mqtt_username, info.mqtt_password) == ("192.168.0.179", "edge", "edge-secret")
    assert info.rtsp_publish_url == "rtsp://192.168.0.179:8554"
    assert info.topics["heartbeat"] == "edge/aibox/heartbeat"
    assert info.topics["camera_logs"] == "edge/aibox/cameras/{camera_id}/logs"


def test_connection_info_hides_the_mqtt_password_from_operators(settings):
    assert connection_info("aibox", include_mqtt_password=False).mqtt_password is None


def test_connection_info_lists_the_http_telemetry_endpoints(settings):
    info = connection_info("aibox", include_mqtt_password=True)
    assert info.mqtt_enabled is True
    assert info.http_endpoints["heartbeat"] == "/edge/heartbeat"
    assert info.http_endpoints["logs"] == "/edge/logs"


def test_switching_the_shared_mqtt_account_off_stops_handing_out_its_password(settings, monkeypatch):
    monkeypatch.setenv("MQTT_EDGE_ENABLED", "false")
    get_settings.cache_clear()
    info = connection_info("aibox", include_mqtt_password=True)
    assert info.mqtt_enabled is False
    assert info.mqtt_password is None
