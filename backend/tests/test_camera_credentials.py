import uuid

from app.core.crypto import encrypt_secret
from app.models.camera import Camera
from app.services.camera_service import build_authenticated_url, split_credentials
from app.services.mappers import mask_rtsp_url
from app.services.storage_service import build_snapshot_key, key_belongs_to_device


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


def test_mask_never_leaks_credentials():
    assert mask_rtsp_url("rtsp://u:p@host:554/a") == "rtsp://host:554/a"


def test_snapshot_key_ownership():
    key = build_snapshot_key("edge-001", uuid.uuid4())
    assert key_belongs_to_device(key, "edge-001")
    assert not key_belongs_to_device(key, "edge-002")
    assert not key_belongs_to_device("2026/01/01/../edge-001/x.jpg", "edge-001")
    assert not key_belongs_to_device("2026/01/../edge-001/c/x.jpg", "edge-001")
