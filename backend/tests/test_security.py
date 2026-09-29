import uuid

import pytest

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_STREAM,
    TokenError,
    create_access_token,
    create_stream_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.stream import MediaMTXAuthRequest
from app.services.stream_service import StreamService


def test_password_hashing():
    h = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)


def test_access_token_type_is_enforced():
    token, _ = create_access_token(uuid.uuid4(), "admin")
    assert decode_token(token, TOKEN_TYPE_ACCESS)["role"] == "admin"
    with pytest.raises(TokenError):
        decode_token(token, TOKEN_TYPE_STREAM)


def test_credential_encryption_roundtrip():
    enc = encrypt_secret("camera-pass")
    assert "camera-pass" not in enc
    assert decrypt_secret(enc) == "camera-pass"


def test_mediamtx_read_auth_is_bound_to_path():
    token, _ = create_stream_token(uuid.uuid4(), "cam-abc")
    ok = MediaMTXAuthRequest(action="read", path="cam-abc", token=token, protocol="webrtc")
    other = MediaMTXAuthRequest(action="read", path="cam-other", token=token, protocol="webrtc")
    via_query = MediaMTXAuthRequest(action="read", path="cam-abc", query=f"token={token}", protocol="hls")
    assert StreamService._authorize_read(ok, "cam-abc")
    assert not StreamService._authorize_read(other, "cam-other")
    assert StreamService._authorize_read(via_query, "cam-abc")
    assert not StreamService._authorize_read(MediaMTXAuthRequest(action="read", path="cam-abc"), "cam-abc")
