import pytest

from app.core.config import get_settings
from app.services.device_service import connection_info


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("MEDIAMTX_RTSP_PUBLISH_URL", "rtsp://192.168.0.179:8554")
    monkeypatch.setenv("MINIO_EDGE_URL", "http://192.168.0.179:9000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_connection_info_has_the_push_and_upload_addresses(settings):
    info = connection_info("aibox")
    assert info.device_id == "aibox"
    assert info.rtsp_publish_url == "rtsp://192.168.0.179:8554"
    assert info.snapshot_upload_url == "http://192.168.0.179:9000"


def test_connection_info_lists_the_http_telemetry_endpoints(settings):
    endpoints = connection_info("aibox").http_endpoints
    assert endpoints["heartbeat"] == "/edge/heartbeat"
    assert endpoints["logs"] == "/edge/logs"
    assert endpoints["camera_status"] == "/edge/cameras/{camera_id}/status"
