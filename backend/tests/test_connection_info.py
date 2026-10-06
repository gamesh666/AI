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
