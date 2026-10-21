import uuid

from app.core.crypto import encrypt_secret
from app.core.enums import StreamType
from app.models.camera import Camera
from app.services.camera_service import build_authenticated_url, build_stream_path, split_credentials
from app.services.storage_service import build_snapshot_key, key_belongs_to_device
from app.services.stream_service import split_stream_path


def test_split_credentials_strips_userinfo():
    clean, user, pw = split_credentials("rtsp://admin:p%40ss@10.0.0.5:554/Streaming/101")
    assert clean == "rtsp://10.0.0.5:554/Streaming/101"
    assert (user, pw) == ("admin", "p@ss")
    assert split_credentials("rtsp://10.0.0.5/x") == ("rtsp://10.0.0.5/x", None, None)


def test_authenticated_url_is_rebuilt_for_edge_only():
    cam = Camera(
        rtsp_url="rtsp://10.0.0.5:554/s",
        rtsp_username="admin",
        rtsp_password_encrypted=encrypt_secret("p@ss:1"),
    )
    assert build_authenticated_url(cam) == "rtsp://admin:p%40ss%3A1@10.0.0.5:554/s"


def test_stream_path_uses_system_ids_not_camera_ip():
    assert build_stream_path("site01", "edge01", "cam01") == "ai/site01/edge01/cam01"
    assert build_stream_path(None, "edge01", "cam01") == "ai/unassigned/edge01/cam01"
    assert build_stream_path("site01", "edge01", "cam01", StreamType.ORIGINAL) == "original/site01/edge01/cam01"


def test_split_stream_path():
    assert split_stream_path("ai/site01/edge01/cam01") == (StreamType.AI, "ai/site01/edge01/cam01")
    assert split_stream_path("/original/site01/edge01/cam01") == (StreamType.ORIGINAL, "ai/site01/edge01/cam01")
    assert split_stream_path("cam01") is None
    assert split_stream_path("ai/site01/cam01") is None
    assert split_stream_path("hack/site01/edge01/cam01") is None
    assert split_stream_path("ai/a/b/c/d") is None


def test_snapshot_key_ownership():
    key = build_snapshot_key("edge-001", uuid.uuid4())
    assert key_belongs_to_device(key, "edge-001")
    assert not key_belongs_to_device(key, "edge-002")
    assert not key_belongs_to_device("2026/01/01/../edge-001/x.jpg", "edge-001")
    assert not key_belongs_to_device("2026/01/../edge-001/c/x.jpg", "edge-001")
